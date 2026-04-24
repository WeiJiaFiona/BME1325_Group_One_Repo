import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Hospital from '@/models/Hospital';
import Case from '@/models/Case';
import mongoose from 'mongoose';

/**
 * GET /api/hospitals/[slug]/wait-estimate?triageLevel=URGENT
 * Calculate estimated wait time based on queue position and severity
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> | { slug: string } }
) {
  console.log('=== WAIT ESTIMATE ROUTE HIT ===');
  console.log('URL:', request.url);
  
  try {
    await connectDB();

    // Handle both Next.js 14 (Promise) and Next.js 13 (direct) params
    const resolvedParams = params instanceof Promise ? await params : params;
    const slug = resolvedParams.slug;
    const { searchParams } = new URL(request.url);
    const triageLevel = searchParams.get('triageLevel') || 'NON_URGENT';

    console.log('Params resolved:', { slug, triageLevel });

    // Find hospital by slug first
    let hospital = await Hospital.findOne({ slug });
    
    // If not found by slug, check if the slug parameter is actually an ObjectId
    // MongoDB ObjectIds are 24 hex characters
    if (!hospital && /^[0-9a-fA-F]{24}$/.test(slug)) {
      console.log('Slug looks like ObjectId, trying to find by _id:', slug);
      try {
        hospital = await Hospital.findById(new mongoose.Types.ObjectId(slug));
        if (hospital) {
          console.log('Found hospital by ObjectId:', { id: hospital._id.toString(), name: hospital.name, slug: hospital.slug });
        }
      } catch (idError) {
        console.error('Error converting to ObjectId:', idError);
      }
    }
    
    if (!hospital) {
      console.error('Hospital not found with slug/ID:', slug);
      const allHospitals = await Hospital.find({}).select('_id name slug').lean();
      return NextResponse.json({ 
        error: 'Hospital not found',
        searchedSlug: slug,
        availableHospitals: allHospitals.map((h: any) => ({ id: String(h._id), name: h.name, slug: h.slug }))
      }, { status: 404 });
    }

    console.log('Found hospital:', { id: hospital._id.toString(), name: hospital.name, slug: hospital.slug });

    // Average treatment times by severity (in minutes)
    const treatmentTimes: { [key: string]: number } = {
      'EMERGENCY': 60,      // 1 hour
      'URGENT': 45,         // 45 minutes
      'NON_URGENT': 30,     // 30 minutes  
      'SELF_CARE': 20,      // 20 minutes
      'UNCERTAIN': 35,      // 35 minutes
    };

    // Priority weights (higher = seen first)
    const priorityWeights: { [key: string]: number } = {
      'EMERGENCY': 5,
      'URGENT': 4,
      'NON_URGENT': 3,
      'SELF_CARE': 2,
      'UNCERTAIN': 2,
    };

    // Get all checked-in patients waiting (not discharged)
    const hospitalIdStr = hospital._id.toString();
    const waitingCases = await Case.find({
      $and: [
        {
          $or: [
            { 'hospitalRouting.hospitalId': hospital._id },
            { 'hospitalRouting.hospitalId': hospitalIdStr }
          ]
        },
        {
          $or: [
            { workflowStatus: { $in: ['checked_in', 'confirmed_hospital', 'watching', 'pending_review'] } },
            { workflowStatus: { $exists: false } },
            { workflowStatus: null }
          ]
        },
        { status: { $ne: 'completed' } }
      ]
    }).lean();
    
    console.log(`Found ${waitingCases.length} waiting cases for hospital ${slug} (ID: ${hospitalIdStr})`);

    // Count patients by severity
    const counts: { [key: string]: number } = {
      'EMERGENCY': 0,
      'URGENT': 0,
      'NON_URGENT': 0,
      'SELF_CARE': 0,
      'UNCERTAIN': 0,
    };

    waitingCases.forEach(c => {
      const level = c.adminReview?.adminTriageLevel || c.assistant?.triageLevel || 'UNCERTAIN';
      if (counts[level] !== undefined) {
        counts[level]++;
      }
    });

    // Calculate estimated wait time based on queue position
    const userPriority = priorityWeights[triageLevel] || 2;
    let estimatedWait = 0;

    // Patients with higher priority will be seen first
    for (const [level, count] of Object.entries(counts)) {
      const levelPriority = priorityWeights[level] || 2;
      
      if (levelPriority > userPriority) {
        // All higher priority patients go first
        estimatedWait += count * treatmentTimes[level];
      } else if (levelPriority === userPriority) {
        // Same priority - add half the queue (average position)
        estimatedWait += (count / 2) * treatmentTimes[level];
      }
      // Lower priority patients don't affect wait time
    }

    // Add base wait time from hospital's current wait
    const baseWait = hospital.currentWait || 45;
    estimatedWait = Math.max(estimatedWait, baseWait * 0.5);

    // Factor in capacity utilization
    const utilizationRate = hospital.currentPatients / hospital.maxCapacity;
    if (utilizationRate > 0.8) {
      estimatedWait *= 1.3; // 30% longer wait when very busy
    } else if (utilizationRate > 0.6) {
      estimatedWait *= 1.15; // 15% longer wait when busy
    }

    // If no patients ahead, use base wait time
    if (estimatedWait === 0) {
      estimatedWait = baseWait;
    }
    
    // Round to nearest 5 minutes
    estimatedWait = Math.round(estimatedWait / 5) * 5;
    estimatedWait = Math.max(5, estimatedWait); // Minimum 5 minutes

    // Calculate queue position (patients ahead with higher or equal priority)
    let queuePosition = 0;
    for (const [level, count] of Object.entries(counts)) {
      const levelPriority = priorityWeights[level] || 2;
      if (levelPriority >= userPriority) {
        queuePosition += count;
      }
    }
    
    console.log('Wait estimate calculation:', {
      slug,
      hospitalId: hospital._id.toString(),
      triageLevel,
      waitingCasesCount: waitingCases.length,
      counts,
      queuePosition,
      estimatedWait,
      baseWait,
      utilizationRate
    });

    // Calculate total patients in queue
    const totalPatientsInQueue = Object.values(counts).reduce((sum, count) => sum + count, 0);
    
    // Calculate average treatment time for user's priority level
    const userTreatmentTime = treatmentTimes[triageLevel] || 30;
    
    // Calculate estimated time per patient ahead (weighted average)
    let totalTreatmentTimeAhead = 0;
    let totalPatientsAhead = 0;
    for (const [level, count] of Object.entries(counts)) {
      const levelPriority = priorityWeights[level] || 2;
      if (levelPriority >= userPriority) {
        totalTreatmentTimeAhead += count * treatmentTimes[level];
        totalPatientsAhead += count;
      }
    }
    const avgTimePerPatient = totalPatientsAhead > 0 
      ? Math.round(totalTreatmentTimeAhead / totalPatientsAhead)
      : userTreatmentTime;

    return NextResponse.json({
      success: true,
      estimate: {
        hospitalId: hospital._id,
        hospitalName: hospital.name,
        triageLevel,
        estimatedWaitMinutes: Math.max(5, estimatedWait), // Minimum 5 minutes
        estimatedWaitRange: {
          min: Math.max(5, Math.floor(estimatedWait * 0.7)),
          max: Math.ceil(estimatedWait * 1.3)
        },
        queuePosition,
        totalPatientsInQueue,
        patientsAhead: {
          emergency: counts.EMERGENCY,
          urgent: counts.URGENT,
          nonUrgent: counts.NON_URGENT,
          selfCare: counts.SELF_CARE,
          uncertain: counts.UNCERTAIN,
        },
        hospitalUtilization: utilizationRate,
        hospitalCapacity: {
          current: hospital.currentPatients,
          max: hospital.maxCapacity,
          available: Math.max(0, hospital.maxCapacity - hospital.currentPatients),
          utilizationPercent: (utilizationRate * 100).toFixed(1)
        },
        treatmentTimes: {
          userLevel: userTreatmentTime,
          averagePerPatient: avgTimePerPatient,
          emergency: treatmentTimes.EMERGENCY,
          urgent: treatmentTimes.URGENT,
          nonUrgent: treatmentTimes.NON_URGENT,
        },
        message: estimatedWait < 30
          ? 'Short wait expected - you should be seen relatively soon'
          : estimatedWait < 60
          ? 'Moderate wait expected - please remain patient'
          : 'Longer wait expected - we appreciate your patience'
      }
    });
  } catch (error: any) {
    console.error('Error calculating wait estimate:', error);
    return NextResponse.json({
      error: error.message || 'Failed to calculate wait estimate'
    }, { status: 500 });
  }
}

