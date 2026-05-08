import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';

/**
 * Patient confirms they are on route to hospital
 * This updates the workflow status and calculates ETA
 */
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { estimatedArrivalMinutes } = body; // Estimated minutes until arrival

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    if (caseDoc.workflowStatus !== 'confirmed_hospital') {
      return NextResponse.json({ error: 'Case must be confirmed for hospital first' }, { status: 400 });
    }

    // Update workflow status to on_route
    caseDoc.workflowStatus = 'on_route';

    // Update hospital routing
    if (!caseDoc.hospitalRouting) {
      caseDoc.hospitalRouting = {};
    }

    caseDoc.hospitalRouting.patientConfirmedRoute = true;
    caseDoc.hospitalRouting.patientConfirmedAt = new Date();

    // Calculate estimated arrival time
    if (estimatedArrivalMinutes) {
      const estimatedArrival = new Date();
      estimatedArrival.setMinutes(estimatedArrival.getMinutes() + parseInt(estimatedArrivalMinutes));
      caseDoc.hospitalRouting.estimatedArrival = estimatedArrival;
    }

    // Set routed timestamp if not already set
    if (!caseDoc.hospitalRouting.routedAt) {
      caseDoc.hospitalRouting.routedAt = new Date();
    }

    await caseDoc.save();

    return NextResponse.json({ 
      case: caseDoc,
      message: 'Patient confirmed on route. Admin has been notified.',
    });
  } catch (error: any) {
    console.error('Error confirming patient route:', error);
    return NextResponse.json({ error: error.message || 'Failed to confirm route' }, { status: 500 });
  }
}

