import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import { getHospitalById } from '@/lib/hospitals';

/**
 * Send notification to patient when confirmed to go to hospital
 * In a real system, this would send SMS/email/push notification
 * For now, we'll just mark that notification was sent
 */
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

    if (caseDoc.workflowStatus !== 'confirmed_hospital') {
      return NextResponse.json({ error: 'Case must be confirmed for hospital first' }, { status: 400 });
    }

    const hospital = caseDoc.hospitalRouting?.hospitalId 
      ? getHospitalById(caseDoc.hospitalRouting.hospitalId)
      : null;

    // In a real system, you would send actual notification here
    // For now, we'll return the notification details
    const notification = {
      caseId: caseDoc._id,
      message: `You have been confirmed to go to ${caseDoc.hospitalRouting?.hospitalName || 'the hospital'}. Please confirm when you are on route.`,
      hospital: hospital ? {
        name: hospital.name,
        address: hospital.address,
        phone: hospital.phone,
      } : caseDoc.hospitalRouting ? {
        name: caseDoc.hospitalRouting.hospitalName,
        address: caseDoc.hospitalRouting.hospitalAddress,
      } : null,
      confirmationLink: `/patient/${caseDoc._id}/confirm-route`,
    };

    return NextResponse.json({ 
      notification,
      message: 'Notification sent to patient',
    });
  } catch (error: any) {
    console.error('Error sending notification:', error);
    return NextResponse.json({ error: error.message || 'Failed to send notification' }, { status: 500 });
  }
}

