import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { onWatchList, watchListReason } = body;

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Initialize adminReview if it doesn't exist
    if (!caseDoc.adminReview) {
      caseDoc.adminReview = {
        reviewed: false,
        onWatchList: false,
      };
    }

    // Update watch list status
    caseDoc.adminReview.onWatchList = onWatchList || false;
    caseDoc.adminReview.watchListReason = watchListReason || '';

    await caseDoc.save();

    return NextResponse.json({ case: caseDoc });
  } catch (error: any) {
    console.error('Error updating watch list:', error);
    return NextResponse.json({ error: error.message || 'Failed to update watch list' }, { status: 500 });
  }
}

