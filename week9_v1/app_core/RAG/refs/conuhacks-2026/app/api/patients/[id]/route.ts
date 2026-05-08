import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Patient from '@/models/Patient';

/**
 * GET /api/patients/[id]
 * Fetch patient details and medical history
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const patientId = params.id;

    const patient = await Patient.findById(patientId);
    if (!patient) {
      return NextResponse.json({ 
        error: 'Patient not found' 
      }, { status: 404 });
    }

    return NextResponse.json({ patient });
  } catch (error: any) {
    console.error('Error fetching patient:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to fetch patient' 
    }, { status: 500 });
  }
}

