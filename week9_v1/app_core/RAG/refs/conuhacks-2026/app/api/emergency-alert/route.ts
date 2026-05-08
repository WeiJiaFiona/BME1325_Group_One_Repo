import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';

export async function POST(request: NextRequest) {
  try {
    await connectDB();

    const body = await request.json();
    const { caseId, timestamp } = body;

    if (!caseId) {
      return NextResponse.json({ error: 'caseId is required' }, { status: 400 });
    }

    // Update case to mark as emergency alert sent
    const caseDoc = await Case.findById(caseId);
    if (caseDoc) {
      caseDoc.status = 'escalated';
      caseDoc.assistant.triageLevel = 'EMERGENCY';
      if (!caseDoc.assistant.reasons) {
        caseDoc.assistant.reasons = [];
      }
      caseDoc.assistant.reasons.push('Patient identified as emergency on initial screening');
      await caseDoc.save();
    }

    // In a real implementation, this would:
    // 1. Send notification to nurse station dashboard (WebSocket/SSE)
    // 2. Send SMS/email alerts to on-duty nurses
    // 3. Log to emergency monitoring system
    // 4. Trigger audio/visual alerts in nurse station
    
    console.log('🚨 EMERGENCY ALERT:', {
      caseId,
      timestamp,
      message: 'Patient marked emergency on initial screening - requires immediate attention'
    });

    // Simulate notification system
    // In production, you would integrate with:
    // - Hospital notification system
    // - Paging system
    // - Real-time dashboard updates
    
    return NextResponse.json({ 
      success: true,
      message: 'Emergency alert sent to nurse station',
      caseId,
      timestamp
    });
  } catch (error: any) {
    console.error('Error sending emergency alert:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to send emergency alert' 
    }, { status: 500 });
  }
}

