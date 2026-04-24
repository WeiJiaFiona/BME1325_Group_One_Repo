import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Hospital from '@/models/Hospital';

/**
 * Get recent emergency alerts for a specific hospital
 * Returns cases that have been escalated to EMERGENCY status within the last hour
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
    const { searchParams } = new URL(request.url);
    const sinceMinutes = parseInt(searchParams.get('since') || '60'); // Default: last 60 minutes

    // Find hospital by slug
    const hospital = await Hospital.findOne({ slug }).lean() as any;
    if (!hospital) {
      return NextResponse.json({ error: 'Hospital not found' }, { status: 404 });
    }

    const hospitalId = hospital._id.toString();

    // Calculate the time threshold
    const sinceTime = new Date();
    sinceTime.setMinutes(sinceTime.getMinutes() - sinceMinutes);

    // Find cases that:
    // 1. Are routed to this hospital
    // 2. Have status 'escalated' OR triageLevel 'EMERGENCY'
    // 3. Were updated within the time window
    const emergencyCases = await Case.find({
      $and: [
        {
          $or: [
            { 'hospitalRouting.hospitalId': hospital._id },
            { 'hospitalRouting.hospitalId': hospitalId }
          ]
        },
        {
          $or: [
            { status: 'escalated' },
            { 'assistant.triageLevel': 'EMERGENCY' },
            { 'adminReview.adminTriageLevel': 'EMERGENCY' }
          ]
        },
        { updatedAt: { $gte: sinceTime } }
      ]
    })
      .sort({ updatedAt: -1 })
      .limit(50)
      .lean();

    // Format the response
    const alerts = emergencyCases.map((caseDoc: any) => ({
      caseId: caseDoc._id.toString(),
      patientName: caseDoc.user?.healthCardScan?.name || 'Unknown',
      chiefComplaint: caseDoc.intake?.chiefComplaint || 'No chief complaint',
      triageLevel: caseDoc.adminReview?.adminTriageLevel || caseDoc.assistant?.triageLevel || 'EMERGENCY',
      escalatedAt: caseDoc.updatedAt,
      workflowStatus: caseDoc.workflowStatus,
      symptoms: caseDoc.intake?.symptoms || [],
      severity: caseDoc.intake?.severity || 'Unknown',
      redFlags: caseDoc.intake?.redFlags?.details || [],
    }));

    return NextResponse.json({ 
      alerts,
      count: alerts.length,
      hospital: {
        _id: hospital._id,
        name: hospital.name,
      }
    });
  } catch (error: any) {
    console.error('Error fetching emergency alerts:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch emergency alerts' }, { status: 500 });
  }
}

