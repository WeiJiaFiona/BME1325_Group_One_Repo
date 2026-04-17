import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    caseDoc.status = 'completed';
    await caseDoc.save();

    return NextResponse.json({ case: caseDoc });
  } catch (error: any) {
    console.error('Error completing case:', error);
    return NextResponse.json({ error: error.message || 'Failed to complete case' }, { status: 500 });
  }
}

