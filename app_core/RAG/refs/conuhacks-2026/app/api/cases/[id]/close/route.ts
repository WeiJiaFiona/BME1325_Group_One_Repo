import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Hospital from '@/models/Hospital';
import { v4 as uuidv4 } from 'uuid';

/**
 * Close a case - only allowed by the hospital that the case is assigned to
 * This endpoint verifies hospital ownership and updates:
 * - Case status to 'completed'
 * - Workflow status to 'discharged'
 * - Hospital capacity (decrements currentPatients)
 * - Creates a notification for the patient
 */
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { hospitalSlug, hospitalId, closedBy } = body;

    // Find the case
    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Verify the case is already completed
    if (caseDoc.status === 'completed') {
      return NextResponse.json({ error: 'Case is already closed' }, { status: 400 });
    }

    // Verify hospital ownership
    let hospital: any = null;
    if (hospitalSlug) {
      hospital = await Hospital.findOne({ slug: hospitalSlug });
    } else if (hospitalId) {
      hospital = await Hospital.findById(hospitalId);
    }

    if (!hospital) {
      return NextResponse.json({ error: 'Hospital not found' }, { status: 404 });
    }

    const hospitalIdStr = hospital._id.toString();
    const hospitalObjectId = hospital._id;
    const caseHospitalId = caseDoc.hospitalRouting?.hospitalId;

    // Verify the case belongs to this hospital
    // Check both string and ObjectId formats
    if (!caseHospitalId || 
        (caseHospitalId !== hospitalIdStr && 
         caseHospitalId !== hospitalObjectId.toString() &&
         caseHospitalId !== hospitalObjectId)) {
      return NextResponse.json(
        { error: 'This case does not belong to the specified hospital' },
        { status: 403 }
      );
    }

    // Store old workflow status for capacity tracking
    const oldWorkflowStatus = caseDoc.workflowStatus;

    // Update case status
    caseDoc.status = 'completed';
    caseDoc.workflowStatus = 'discharged';

    // Update hospital capacity if patient was in a capacity-consuming status
    if (oldWorkflowStatus === 'checked_in' || oldWorkflowStatus === 'on_route' || oldWorkflowStatus === 'confirmed_hospital') {
      if (hospital.currentPatients > 0) {
        hospital.currentPatients = Math.max(0, hospital.currentPatients - 1);
        await hospital.save();
      }
    }

    // Create notification for patient
    if (!caseDoc.notifications) {
      caseDoc.notifications = [];
    }
    caseDoc.notifications.push({
      id: uuidv4(),
      type: 'status_update',
      message: `Your case has been closed at ${hospital.name}. Thank you for using our services.`,
      timestamp: new Date(),
      read: false,
      metadata: {
        workflowStatus: 'discharged',
        hospitalName: hospital.name,
      },
    });

    await caseDoc.save();

    return NextResponse.json({
      case: caseDoc,
      message: 'Case closed successfully',
    });
  } catch (error: any) {
    console.error('Error closing case:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to close case' },
      { status: 500 }
    );
  }
}

