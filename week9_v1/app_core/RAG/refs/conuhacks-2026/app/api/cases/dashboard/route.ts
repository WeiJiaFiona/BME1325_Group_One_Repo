import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';

// Mark route as dynamic since it uses request.url
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    await connectDB();

    const { searchParams } = new URL(request.url);
    const filter = searchParams.get('filter'); // 'emergency' | 'urgent' | 'non_urgent' | 'self_care' | 'uncertain' | 'watchlist' | 'all'
    const page = parseInt(searchParams.get('page') || '1');
    const limit = parseInt(searchParams.get('limit') || '20');
    const skip = (page - 1) * limit;

    // Build query
    const query: any = {};

    // Filter by case status - only show completed cases
    query.status = 'completed';

    // Workflow status filters
    const workflowFilters = ['pending_review', 'confirmed_hospital', 'watching', 'on_route', 'checked_in', 'discharged'];
    if (filter && workflowFilters.includes(filter)) {
      if (filter === 'pending_review') {
        // Include cases that haven't been reviewed yet (no adminReview.reviewed or no adminReview.adminTriageLevel)
        query.$or = [
          { 'adminReview.reviewed': { $ne: true } },
          { 'adminReview': { $exists: false } },
          { 'adminReview.adminTriageLevel': { $exists: false } },
          { 'adminReview.reviewed': false },
          { workflowStatus: 'pending_review' },
          { workflowStatus: { $exists: false } },
          { workflowStatus: null }
        ];
      } else {
        query.workflowStatus = filter;
      }
    } else if (filter === 'watchlist') {
      query['adminReview.onWatchList'] = true;
    } else if (filter && filter !== 'all') {
      // Filter by triage level (use admin review if available, otherwise AI assessment)
      const triageLevel = filter.toUpperCase();
      query.$or = [
        { 'adminReview.adminTriageLevel': triageLevel },
        { 'assistant.triageLevel': triageLevel, $or: [
          { 'adminReview.reviewed': { $ne: true } },
          { 'adminReview': { $exists: false } }
        ]}
      ];
    }

    // Get cases
    const cases = await Case.find(query)
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(limit)
      .lean();

    // Get counts by severity (only for completed cases)
    const total = await Case.countDocuments({ status: 'completed' });
    const emergencyCount = await Case.countDocuments({
      status: 'completed',
      $or: [
        { 'adminReview.adminTriageLevel': 'EMERGENCY' },
        { 'assistant.triageLevel': 'EMERGENCY', 'adminReview.reviewed': { $ne: true } }
      ]
    });
    const urgentCount = await Case.countDocuments({
      status: 'completed',
      $or: [
        { 'adminReview.adminTriageLevel': 'URGENT' },
        { 'assistant.triageLevel': 'URGENT', 'adminReview.reviewed': { $ne: true } }
      ]
    });
    const nonUrgentCount = await Case.countDocuments({
      status: 'completed',
      $or: [
        { 'adminReview.adminTriageLevel': 'NON_URGENT' },
        { 'assistant.triageLevel': 'NON_URGENT', 'adminReview.reviewed': { $ne: true } }
      ]
    });
    const selfCareCount = await Case.countDocuments({
      status: 'completed',
      $or: [
        { 'adminReview.adminTriageLevel': 'SELF_CARE' },
        { 'assistant.triageLevel': 'SELF_CARE', 'adminReview.reviewed': { $ne: true } }
      ]
    });
    const uncertainCount = await Case.countDocuments({
      status: 'completed',
      $or: [
        { 'adminReview.adminTriageLevel': 'UNCERTAIN' },
        { 'assistant.triageLevel': 'UNCERTAIN', 'adminReview.reviewed': { $ne: true } }
      ]
    });
    const watchListCount = await Case.countDocuments({ status: 'completed', 'adminReview.onWatchList': true });
    
    // Workflow status counts (only for completed cases)
    // Pending review includes cases that haven't been reviewed yet
    const pendingReviewCount = await Case.countDocuments({
      status: 'completed',
      $or: [
        { 'adminReview.reviewed': { $ne: true } },
        { 'adminReview': { $exists: false } },
        { 'adminReview.adminTriageLevel': { $exists: false } },
        { 'adminReview.reviewed': false },
        { workflowStatus: 'pending_review' },
        { workflowStatus: { $exists: false } },
        { workflowStatus: null }
      ]
    });
    const confirmedHospitalCount = await Case.countDocuments({ status: 'completed', workflowStatus: 'confirmed_hospital' });
    const watchingCount = await Case.countDocuments({ status: 'completed', workflowStatus: 'watching' });
    const onRouteCount = await Case.countDocuments({ status: 'completed', workflowStatus: 'on_route' });
    const checkedInCount = await Case.countDocuments({ status: 'completed', workflowStatus: 'checked_in' });
    const dischargedCount = await Case.countDocuments({ status: 'completed', workflowStatus: 'discharged' });

    return NextResponse.json({
      cases,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
      counts: {
        emergency: emergencyCount,
        urgent: urgentCount,
        nonUrgent: nonUrgentCount,
        selfCare: selfCareCount,
        uncertain: uncertainCount,
        watchList: watchListCount,
        pendingReview: pendingReviewCount,
        confirmedHospital: confirmedHospitalCount,
        watching: watchingCount,
        onRoute: onRouteCount,
        checkedIn: checkedInCount,
        discharged: dischargedCount,
        total,
      },
    });
  } catch (error: any) {
    console.error('Error fetching dashboard cases:', error);
    return NextResponse.json({ error: error.message || 'Failed to fetch cases' }, { status: 500 });
  }
}

