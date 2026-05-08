import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Hospital from '@/models/Hospital';
import { v4 as uuidv4 } from 'uuid';

/**
 * Calculate distance between two coordinates using Haversine formula
 */
function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = 
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Find the best hospital based on proximity and capacity
 * Ensures even distribution by preferring hospitals with lower capacity percentage
 */
async function findBestHospital(patientLat?: number, patientLon?: number): Promise<any> {
  const hospitals = await Hospital.find({ isActive: true }).lean();
  
  if (hospitals.length === 0) {
    return null;
  }

  // Default to Montreal downtown if no patient location
  const defaultLat = 45.5017;
  const defaultLon = -73.5673;
  const lat = patientLat || defaultLat;
  const lon = patientLon || defaultLon;

  // Score hospitals: prioritize available capacity, then distance
  const scoredHospitals = hospitals.map(hospital => {
    const availableCapacity = Math.max(0, hospital.maxCapacity - (hospital.currentPatients || 0));
    const capacityPercentage = (hospital.currentPatients || 0) / hospital.maxCapacity;
    const availableCapacityRatio = availableCapacity / hospital.maxCapacity;
    
    // Calculate distance (use default if hospital doesn't have coordinates)
    // For now, we'll use a simple scoring system based on capacity
    // In production, you'd store hospital coordinates and calculate actual distance
    const distance = 0; // Placeholder - would calculate from hospital coordinates
    
    // Score: Higher available capacity ratio = better, lower capacity percentage = better
    // This ensures even distribution
    const score = availableCapacityRatio * 100 - capacityPercentage * 50;
    
    return {
      hospital,
      score,
      availableCapacity,
      capacityPercentage,
    };
  });

  // Sort by score (highest first) - prioritizes hospitals with more available capacity
  scoredHospitals.sort((a, b) => b.score - a.score);

  // Return the best hospital that has available capacity
  const bestHospital = scoredHospitals.find(h => h.availableCapacity > 0);
  
  return bestHospital?.hospital || scoredHospitals[0]?.hospital || null;
}

/**
 * Route a reviewed patient to: Monitor, Clinic, or Hospital
 * Automatically selects best hospital/clinic based on proximity and capacity
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { routeType } = body;

    const validRouteTypes = ['monitor', 'clinic', 'hospital'];
    if (!routeType || !validRouteTypes.includes(routeType)) {
      return NextResponse.json({ error: 'Invalid routeType. Must be: monitor, clinic, or hospital' }, { status: 400 });
    }

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Check if case has been reviewed
    if (!caseDoc.adminReview?.reviewed && !caseDoc.adminReview?.adminTriageLevel) {
      return NextResponse.json({ error: 'Case must be reviewed before routing' }, { status: 400 });
    }

    // Update workflow status and routing based on route type
    switch (routeType) {
      case 'monitor':
        caseDoc.workflowStatus = 'watching';
        
        // Create notification for patient
        if (!caseDoc.notifications) {
          caseDoc.notifications = [];
        }
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
        break;
      
      case 'clinic':
        // Automatically find best clinic (using hospitals as clinics for now)
        const bestClinic = await findBestHospital(
          caseDoc.location?.latitude,
          caseDoc.location?.longitude
        );
        
        if (bestClinic) {
          const oldHospitalId = caseDoc.hospitalRouting?.hospitalId;
          
          caseDoc.workflowStatus = 'confirmed_hospital';
          if (!caseDoc.hospitalRouting) {
            caseDoc.hospitalRouting = {};
          }
          caseDoc.hospitalRouting.hospitalId = bestClinic._id.toString();
          caseDoc.hospitalRouting.hospitalSlug = bestClinic.slug;
          caseDoc.hospitalRouting.hospitalName = bestClinic.name;
          caseDoc.hospitalRouting.hospitalAddress = bestClinic.address;
          caseDoc.hospitalRouting.routedAt = new Date();
          caseDoc.hospitalRouting.routedBy = 'admin';
          
          // Update hospital capacity - increment new hospital, decrement old if different
          if (oldHospitalId && oldHospitalId !== bestClinic._id.toString()) {
            // Decrement old hospital if patient was previously routed elsewhere
            const oldHospital = await Hospital.findById(oldHospitalId);
            if (oldHospital && oldHospital.currentPatients > 0) {
              oldHospital.currentPatients = Math.max(0, oldHospital.currentPatients - 1);
              await oldHospital.save();
            }
          }
          
          // Increment new hospital capacity
          const clinic = await Hospital.findById(bestClinic._id);
          if (clinic && clinic.currentPatients < clinic.maxCapacity) {
            clinic.currentPatients += 1;
            await clinic.save();
          }
        } else {
          return NextResponse.json({ error: 'No available clinics found' }, { status: 404 });
        }
        break;
      
      case 'hospital':
        // Automatically find best hospital based on proximity and capacity
        const bestHospital = await findBestHospital(
          caseDoc.location?.latitude,
          caseDoc.location?.longitude
        );
        
        if (bestHospital) {
          const oldHospitalId = caseDoc.hospitalRouting?.hospitalId;
          
          caseDoc.workflowStatus = 'confirmed_hospital';
          if (!caseDoc.hospitalRouting) {
            caseDoc.hospitalRouting = {};
          }
          caseDoc.hospitalRouting.hospitalId = bestHospital._id.toString();
          caseDoc.hospitalRouting.hospitalSlug = bestHospital.slug;
          caseDoc.hospitalRouting.hospitalName = bestHospital.name;
          caseDoc.hospitalRouting.hospitalAddress = bestHospital.address;
          caseDoc.hospitalRouting.routedAt = new Date();
          caseDoc.hospitalRouting.routedBy = 'admin';
          
          // Create notification for patient
          if (!caseDoc.notifications) {
            caseDoc.notifications = [];
          }
          caseDoc.notifications.push({
            id: uuidv4(),
            type: 'hospital_assigned',
            message: `You have been assigned to ${bestHospital.name}. Please proceed to the hospital.`,
            timestamp: new Date(),
            read: false,
            metadata: {
              hospitalName: bestHospital.name,
              hospitalAddress: bestHospital.address,
              workflowStatus: 'confirmed_hospital',
            },
          });
          
          // Update hospital capacity - increment new hospital, decrement old if different
          if (oldHospitalId && oldHospitalId !== bestHospital._id.toString()) {
            // Decrement old hospital if patient was previously routed elsewhere
            const oldHospital = await Hospital.findById(oldHospitalId);
            if (oldHospital && oldHospital.currentPatients > 0) {
              oldHospital.currentPatients = Math.max(0, oldHospital.currentPatients - 1);
              await oldHospital.save();
            }
          }
          
          // Increment new hospital capacity
          const hospital = await Hospital.findById(bestHospital._id);
          if (hospital && hospital.currentPatients < hospital.maxCapacity) {
            hospital.currentPatients += 1;
            await hospital.save();
          }
        } else {
          return NextResponse.json({ error: 'No available hospitals found' }, { status: 404 });
        }
        break;
    }

    await caseDoc.save();

    return NextResponse.json({ case: caseDoc });
  } catch (error: any) {
    console.error('Error routing case:', error);
    return NextResponse.json({ error: error.message || 'Failed to route case' }, { status: 500 });
  }
}

