import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Hospital from '@/models/Hospital';
import Case from '@/models/Case';

export async function GET(
  request: NextRequest,
  { params }: { params: { slug: string } }
) {
  try {
    await connectDB();

    const { slug } = params;
    const { searchParams } = new URL(request.url);
    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '20');
    const skip = (page - 1) * limit;

    // Find the hospital by slug
    const hospital = await Hospital.findOne({ slug }).lean() as any;

    if (!hospital) {
      return NextResponse.json({ error: 'Hospital not found' }, { status: 404 });
    }

    // Find all cases routed to this hospital
    const hospitalId = hospital._id.toString();
    const query = {
      $or: [
        { 'hospitalRouting.hospitalId': hospital._id },
        { 'hospitalRouting.hospitalId': hospitalId }
      ]
    };

    const cases = await Case.find(query)
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(limit)
      .lean();

    const total = await Case.countDocuments(query);

    // Get counts by severity for this hospital
    const emergencyCount = await Case.countDocuments({
      ...query,
      $or: [
        { 'adminReview.adminTriageLevel': 'EMERGENCY' },
        { 'assistant.triageLevel': 'EMERGENCY', 'adminReview.reviewed': { $ne: true } }
      ]
    });

    const urgentCount = await Case.countDocuments({
      ...query,
      $or: [
        { 'adminReview.adminTriageLevel': 'URGENT' },
        { 'assistant.triageLevel': 'URGENT', 'adminReview.reviewed': { $ne: true } }
      ]
    });

    const nonUrgentCount = await Case.countDocuments({
      ...query,
      $or: [
        { 'adminReview.adminTriageLevel': 'NON_URGENT' },
        { 'assistant.triageLevel': 'NON_URGENT', 'adminReview.reviewed': { $ne: true } }
      ]
    });

    const selfCareCount = await Case.countDocuments({
      ...query,
      $or: [
        { 'adminReview.adminTriageLevel': 'SELF_CARE' },
        { 'assistant.triageLevel': 'SELF_CARE', 'adminReview.reviewed': { $ne: true } }
      ]
    });

    const uncertainCount = await Case.countDocuments({
      ...query,
      $or: [
        { 'adminReview.adminTriageLevel': 'UNCERTAIN' },
        { 'assistant.triageLevel': 'UNCERTAIN', 'adminReview.reviewed': { $ne: true } }
      ]
    });

    // Workflow status counts
    const pendingReviewCount = await Case.countDocuments({
      ...query,
      $or: [
        { workflowStatus: 'pending_review' },
        { workflowStatus: { $exists: false } },
        { workflowStatus: null }
      ]
    });

    const confirmedHospitalCount = await Case.countDocuments({ ...query, workflowStatus: 'confirmed_hospital' });
    const watchingCount = await Case.countDocuments({ ...query, workflowStatus: 'watching' });
    const onRouteCount = await Case.countDocuments({ ...query, workflowStatus: 'on_route' });
    const checkedInCount = await Case.countDocuments({ ...query, workflowStatus: 'checked_in' });
    const dischargedCount = await Case.countDocuments({ ...query, workflowStatus: 'discharged' });

    return NextResponse.json({
      hospital: {
        ...hospital,
        availableCapacity: Math.max(0, hospital.maxCapacity - (hospital.currentPatients || 0)),
        capacityPercentage: ((hospital.currentPatients || 0) / hospital.maxCapacity) * 100,
      },
      cases,
      pagination: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
      counts: {
        total,
        emergency: emergencyCount,
        urgent: urgentCount,
        nonUrgent: nonUrgentCount,
        selfCare: selfCareCount,
        uncertain: uncertainCount,
        pendingReview: pendingReviewCount,
        confirmedHospital: confirmedHospitalCount,
        watching: watchingCount,
        onRoute: onRouteCount,
        checkedIn: checkedInCount,
        discharged: dischargedCount,
      },
    });
  } catch (error: any) {
    console.error('Error fetching hospital cases:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch hospital cases' }, { status: 500 });
  }
}

