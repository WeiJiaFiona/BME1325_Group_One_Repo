import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';

/**
 * POST /api/cases/[id]/health-check
 * Record a health status check-in while patient is waiting
 */
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const caseId = params.id;
    const body = await request.json();
    const { 
      symptomsWorsened, 
      newSymptoms, 
      painLevel, 
      notes,
      timestamp 
    } = body;

    const caseDoc = await Case.findById(caseId);
    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Initialize healthChecks array if it doesn't exist
    if (!caseDoc.healthChecks) {
      caseDoc.healthChecks = [];
    }

    // Add new health check
    const healthCheck = {
      timestamp: timestamp || new Date(),
      symptomsWorsened: symptomsWorsened || false,
      newSymptoms: newSymptoms || [],
      painLevel: painLevel || null,
      notes: notes || '',
    };

    caseDoc.healthChecks.push(healthCheck);

    // If symptoms worsened or high pain, flag for urgent review
    if (symptomsWorsened || painLevel >= 8) {
      if (!caseDoc.adminReview) {
        caseDoc.adminReview = {
          reviewed: false,
          onWatchList: false,
        };
      }
      caseDoc.adminReview.onWatchList = true;
      caseDoc.adminReview.watchListReason = symptomsWorsened 
        ? 'Patient reported worsening symptoms while waiting'
        : 'Patient reported high pain level while waiting';
      
      // Update triage if it was previously lower
      if (caseDoc.assistant.triageLevel === 'NON_URGENT' || caseDoc.assistant.triageLevel === 'SELF_CARE') {
        caseDoc.assistant.triageLevel = 'URGENT';
        caseDoc.assistant.escalationTriggers.push('Escalated due to worsening condition while waiting');
      }
    }

    await caseDoc.save();

    console.log(`Health check recorded for case ${caseId}:`, healthCheck);

    return NextResponse.json({
      success: true,
      message: 'Health check recorded',
      healthCheck,
      escalated: symptomsWorsened || painLevel >= 8,
      currentTriageLevel: caseDoc.assistant.triageLevel
    });
  } catch (error: any) {
    console.error('Error recording health check:', error);
    return NextResponse.json({
      error: error.message || 'Failed to record health check'
    }, { status: 500 });
  }
}

/**
 * GET /api/cases/[id]/health-check
 * Get all health checks for a case
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const caseId = params.id;

    const caseDoc = await Case.findById(caseId).select('healthChecks assistant.triageLevel workflowStatus');
    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    return NextResponse.json({
      success: true,
      healthChecks: caseDoc.healthChecks || [],
      currentTriageLevel: caseDoc.assistant?.triageLevel,
      workflowStatus: caseDoc.workflowStatus
    });
  } catch (error: any) {
    console.error('Error fetching health checks:', error);
    return NextResponse.json({
      error: error.message || 'Failed to fetch health checks'
    }, { status: 500 });
  }
}

