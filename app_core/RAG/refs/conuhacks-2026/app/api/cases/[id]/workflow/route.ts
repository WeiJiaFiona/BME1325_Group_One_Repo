import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Hospital from '@/models/Hospital';
import { v4 as uuidv4 } from 'uuid';

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    let { workflowStatus, hospitalId, hospitalName, hospitalAddress, routedBy, checkedInBy } = body;

    const validStatuses = ['pending_review', 'confirmed_hospital', 'watching', 'on_route', 'checked_in', 'discharged'];
    if (workflowStatus && !validStatuses.includes(workflowStatus)) {
      return NextResponse.json({ error: 'Invalid workflowStatus' }, { status: 400 });
    }

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Store old values BEFORE updating (critical for capacity tracking)
    const oldWorkflowStatus = caseDoc.workflowStatus;
    const oldHospitalId = caseDoc.hospitalRouting?.hospitalId;

    // Update workflow status
    if (workflowStatus) {
      caseDoc.workflowStatus = workflowStatus;
    }

    // Update hospital routing
    if (!caseDoc.hospitalRouting) {
      caseDoc.hospitalRouting = {};
    }

    // Auto-suggest hospital if status is confirmed_hospital and no hospital is selected
    if (workflowStatus === 'confirmed_hospital' && !hospitalId) {
      // Find the hospital with the most available capacity
      const availableHospitals = await Hospital.find({ isActive: true })
        .sort({ currentPatients: 1 }) // Sort by least patients (most available)
        .limit(1);
      
      if (availableHospitals.length > 0) {
        const suggestedHospital = availableHospitals[0];
        hospitalId = suggestedHospital._id.toString();
        caseDoc.hospitalRouting.hospitalId = hospitalId;
        caseDoc.hospitalRouting.hospitalSlug = suggestedHospital.slug;
        caseDoc.hospitalRouting.hospitalName = suggestedHospital.name;
        caseDoc.hospitalRouting.hospitalAddress = suggestedHospital.address;
      }
    }

    // If hospitalId is provided, fetch from database
    if (hospitalId) {
      const hospital = await Hospital.findById(hospitalId);
      if (hospital) {
        caseDoc.hospitalRouting.hospitalId = hospital._id.toString();
        caseDoc.hospitalRouting.hospitalSlug = hospital.slug;
        caseDoc.hospitalRouting.hospitalName = hospital.name;
        caseDoc.hospitalRouting.hospitalAddress = hospital.address;
      }
    } else {
      // Fallback to manual entry
      if (hospitalName !== undefined) {
        caseDoc.hospitalRouting.hospitalName = hospitalName;
      }
      if (hospitalAddress !== undefined) {
        caseDoc.hospitalRouting.hospitalAddress = hospitalAddress;
      }
    }

    // Update hospital capacity when status changes
    
    // Handle hospital capacity updates
    if (hospitalId && oldHospitalId !== hospitalId) {
      // Patient is being routed to a different hospital
      // Decrement old hospital if it exists and was in a capacity-consuming status
      if (oldHospitalId && (oldWorkflowStatus === 'confirmed_hospital' || oldWorkflowStatus === 'on_route' || oldWorkflowStatus === 'checked_in')) {
        const oldHospital = await Hospital.findById(oldHospitalId);
        if (oldHospital && oldHospital.currentPatients > 0) {
          oldHospital.currentPatients = Math.max(0, oldHospital.currentPatients - 1);
          await oldHospital.save();
        }
      }
      
      // Increment new hospital if status is confirmed_hospital or later
      if (workflowStatus === 'confirmed_hospital' || workflowStatus === 'on_route' || workflowStatus === 'checked_in') {
        const newHospital = await Hospital.findById(hospitalId);
        if (newHospital && newHospital.currentPatients < newHospital.maxCapacity) {
          newHospital.currentPatients += 1;
          await newHospital.save();
        }
      }
    } else if (hospitalId && workflowStatus === 'confirmed_hospital' && oldWorkflowStatus !== 'confirmed_hospital' && !oldHospitalId) {
      // Patient is being routed to a hospital for the first time (not from route endpoint)
      // This handles manual routing through workflow endpoint
      const hospital = await Hospital.findById(hospitalId);
      if (hospital && hospital.currentPatients < hospital.maxCapacity) {
        hospital.currentPatients += 1;
        await hospital.save();
      }
    }
    
    // Handle status changes that affect capacity
    // If moving from confirmed_hospital/on_route to checked_in, no change (already counted)
    // If moving from checked_in to discharged, decrement
    if (oldWorkflowStatus === 'checked_in' && workflowStatus === 'discharged' && oldHospitalId) {
      const hospital = await Hospital.findById(oldHospitalId);
      if (hospital && hospital.currentPatients > 0) {
        hospital.currentPatients = Math.max(0, hospital.currentPatients - 1);
        await hospital.save();
      }
    }


    // Create notifications when status changes
    if (workflowStatus && workflowStatus !== oldWorkflowStatus) {
      if (!caseDoc.notifications) {
        caseDoc.notifications = [];
      }

      if (workflowStatus === 'confirmed_hospital' && caseDoc.hospitalRouting?.hospitalName) {
        // Notify patient they've been assigned to a hospital
        caseDoc.notifications.push({
          id: uuidv4(),
          type: 'hospital_assigned',
          message: `You have been assigned to ${caseDoc.hospitalRouting.hospitalName}. Please proceed to the hospital.`,
          timestamp: new Date(),
          read: false,
          metadata: {
            hospitalName: caseDoc.hospitalRouting.hospitalName,
            hospitalAddress: caseDoc.hospitalRouting.hospitalAddress,
            workflowStatus: 'confirmed_hospital',
          },
        });
      } else if (workflowStatus === 'watching') {
        // Notify patient they're being monitored
        caseDoc.notifications.push({
          id: uuidv4(),
          type: 'status_update',
          message: 'Your case is being monitored. A healthcare professional will review your assessment.',
          timestamp: new Date(),
          read: false,
          metadata: {
            workflowStatus: 'watching',
          },
        });
      } else if (workflowStatus === 'discharged') {
        // Notify patient they've been discharged
        caseDoc.notifications.push({
          id: uuidv4(),
          type: 'status_update',
          message: 'You have been discharged. Take care!',
          timestamp: new Date(),
          read: false,
          metadata: {
            workflowStatus: 'discharged',
          },
        });
      }
    }

    // Set routed timestamp when status changes to on_route
    if (workflowStatus === 'on_route' && !caseDoc.hospitalRouting.routedAt) {
      caseDoc.hospitalRouting.routedAt = new Date();
      if (routedBy) {
        caseDoc.hospitalRouting.routedBy = routedBy;
      }
    }

    // Set checked in timestamp when status changes to checked_in
    if (workflowStatus === 'checked_in' && !caseDoc.hospitalRouting.checkedInAt) {
      caseDoc.hospitalRouting.checkedInAt = new Date();
      if (checkedInBy) {
        caseDoc.hospitalRouting.checkedInBy = checkedInBy;
      }
    }

    await caseDoc.save();

    return NextResponse.json({ case: caseDoc });
  } catch (error: any) {
    console.error('Error updating workflow status:', error);
    return NextResponse.json({ error: error.message || 'Failed to update workflow status' }, { status: 500 });
  }
}

