import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import { v4 as uuidv4 } from 'uuid';

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { triageLevel, notes, reviewedBy, onWatchList, watchListReason } = body;

    if (!triageLevel) {
      return NextResponse.json({ error: 'triageLevel is required' }, { status: 400 });
    }

    const validTriageLevels = ['EMERGENCY', 'URGENT', 'NON_URGENT', 'SELF_CARE', 'UNCERTAIN'];
    if (!validTriageLevels.includes(triageLevel)) {
      return NextResponse.json({ error: 'Invalid triageLevel' }, { status: 400 });
    }

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Update admin review
    const wasReviewed = caseDoc.adminReview?.reviewed || false;
    caseDoc.adminReview = {
      reviewed: true,
      reviewedAt: new Date(),
      reviewedBy: reviewedBy || 'admin',
      adminTriageLevel: triageLevel,
      adminNotes: notes || '',
      onWatchList: onWatchList || false,
      watchListReason: watchListReason || '',
    };

    // Create notification if this is the first review
    if (!wasReviewed) {
      if (!caseDoc.notifications) {
        caseDoc.notifications = [];
      }
      caseDoc.notifications.push({
        id: uuidv4(),
        type: 'review_complete',
        message: 'A healthcare professional has reviewed your assessment. You will be notified of next steps.',
        timestamp: new Date(),
        read: false,
        metadata: {
          triageLevel,
          reviewedBy: reviewedBy || 'admin',
        },
      });
    }

    await caseDoc.save();

    return NextResponse.json({ case: caseDoc });
  } catch (error: any) {
    console.error('Error reviewing case:', error);
    return NextResponse.json({ error: error.message || 'Failed to review case' }, { status: 500 });
  }
}

