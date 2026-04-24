import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Patient from '@/models/Patient';
import Case from '@/models/Case';

/**
 * PATCH /api/patients/[id]/contact
 * Update patient contact information (phone, email, emergency contact)
 */
export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const patientId = params.id;
    const body = await request.json();
    const { phone, email, emergencyContact } = body;

    const patient = await Patient.findById(patientId);
    if (!patient) {
      return NextResponse.json({ 
        error: 'Patient not found' 
      }, { status: 404 });
    }

    // Initialize contactInfo if it doesn't exist
    if (!patient.contactInfo) {
      patient.contactInfo = {};
    }

    // Update fields if provided
    if (phone !== undefined) {
      patient.contactInfo.phone = phone;
      console.log(`Updated phone for patient ${patientId}: ${phone}`);
    }

    if (email !== undefined) {
      patient.contactInfo.email = email;
      console.log(`Updated email for patient ${patientId}: ${email}`);
    }

    if (emergencyContact !== undefined) {
      patient.contactInfo.emergencyContact = emergencyContact;
      console.log(`Updated emergency contact for patient ${patientId}`);
    }

    await patient.save();

    return NextResponse.json({ 
      success: true,
      message: 'Contact information updated',
      contactInfo: patient.contactInfo
    });
  } catch (error: any) {
    console.error('Error updating contact information:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to update contact information' 
    }, { status: 500 });
  }
}

/**
 * GET /api/patients/[id]/contact
 * Get patient contact information
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const patientId = params.id;

    const patient = await Patient.findById(patientId).select('contactInfo demographics.name');
    if (!patient) {
      return NextResponse.json({ 
        error: 'Patient not found' 
      }, { status: 404 });
    }

    return NextResponse.json({ 
      success: true,
      patientId: patient._id,
      patientName: patient.demographics?.name,
      contactInfo: patient.contactInfo || {
        phone: null,
        email: null,
        emergencyContact: null
      }
    });
  } catch (error: any) {
    console.error('Error fetching contact information:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to fetch contact information' 
    }, { status: 500 });
  }
}

