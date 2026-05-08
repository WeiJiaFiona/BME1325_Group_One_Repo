import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Hospital from '@/models/Hospital';

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
 * Estimate travel time in minutes based on distance (km)
 * Assumes average city driving speed of 40 km/h
 */
function estimateTravelTime(distanceKm: number): number {
  const averageSpeedKmh = 40; // Average city driving speed
  return Math.ceil((distanceKm / averageSpeedKmh) * 60); // Convert to minutes
}

/**
 * Get all patients at a specific hospital with full details
 * Returns patients with workflowStatus: confirmed_hospital, on_route, or checked_in
 * Includes calculated ETAs based on patient location
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> | { slug: string } }
) {
  try {
    await connectDB();

    // Handle both Next.js 14 (Promise) and Next.js 13 (direct) params
    const resolvedParams = params instanceof Promise ? await params : params;
    const { slug } = resolvedParams;

    // Get hospital details including location
    const hospital = await Hospital.findOne({ slug }).lean() as any;
    if (!hospital) {
      return NextResponse.json({ error: 'Hospital not found' }, { status: 404 });
    }

    const hospitalId = hospital._id.toString();
    const hospitalObjectId = hospital._id;

    // Find all cases that are routed to this hospital
    // Include all statuses that indicate a patient is at or coming to the hospital
    const query = {
      $and: [
        {
          $or: [
            { 'hospitalRouting.hospitalId': hospitalObjectId },
            { 'hospitalRouting.hospitalId': hospitalId },
            { 'hospitalRouting.hospitalId': hospitalObjectId.toString() }
          ]
        },
        {
          $or: [
            { workflowStatus: { $in: ['confirmed_hospital', 'on_route', 'checked_in', 'watching', 'pending_review'] } },
            { workflowStatus: { $exists: false } },
            { workflowStatus: null }
          ]
        },
        { status: { $ne: 'completed' } }
      ]
    };

    const cases = await Case.find(query)
      .sort({ createdAt: -1 })
      .lean();

    console.log(`[Hospital Patients API] Found ${cases.length} patients for hospital ${slug} (ID: ${hospitalId})`);

    // Calculate ETAs for each patient
    const patientsWithETA = cases.map((patient: any) => {
      let estimatedArrival: Date | null = null;
      let estimatedMinutes: number | null = null;
      let distanceKm: number | null = null;

      // If patient has an explicit ETA from patient confirmation, use that
      if (patient.hospitalRouting?.estimatedArrival) {
        estimatedArrival = new Date(patient.hospitalRouting.estimatedArrival);
        const now = new Date();
        estimatedMinutes = Math.ceil((estimatedArrival.getTime() - now.getTime()) / (1000 * 60));
      } 
      // Otherwise, calculate ETA based on patient location and hospital location
      else if (patient.location?.latitude && patient.location?.longitude && hospital.latitude && hospital.longitude) {
        distanceKm = calculateDistance(
          patient.location.latitude,
          patient.location.longitude,
          hospital.latitude,
          hospital.longitude
        );
        estimatedMinutes = estimateTravelTime(distanceKm);
        estimatedArrival = new Date();
        estimatedArrival.setMinutes(estimatedArrival.getMinutes() + estimatedMinutes);
      }
      // If no location data, use a default estimate (30 minutes)
      else if (patient.workflowStatus === 'on_route' || patient.workflowStatus === 'confirmed_hospital') {
        estimatedMinutes = 30; // Default estimate
        estimatedArrival = new Date();
        estimatedArrival.setMinutes(estimatedArrival.getMinutes() + estimatedMinutes);
      }

      return {
        ...patient,
        estimatedArrival,
        estimatedMinutes,
        distanceKm,
      };
    });

    return NextResponse.json({ 
      hospital: {
        _id: hospital._id,
        name: hospital.name,
        address: hospital.address,
        phone: hospital.phone,
        maxCapacity: hospital.maxCapacity,
        currentPatients: hospital.currentPatients,
        availableCapacity: Math.max(0, hospital.maxCapacity - (hospital.currentPatients || 0)),
      },
      patients: patientsWithETA,
      count: patientsWithETA.length 
    });
  } catch (error: any) {
    console.error('Error fetching hospital patients:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch patients' }, { status: 500 });
  }
}

