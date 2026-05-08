import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Patient from '@/models/Patient';
import Case from '@/models/Case';

/**
 * POST /api/patients/update-phone
 * Update patient phone number by health card, patient ID, or case ID
 * This is a convenience endpoint for quick phone updates during intake
 */
export async function POST(request: NextRequest) {
  try {
    await connectDB();

    const body = await request.json();
    const { phone, healthCardNumber, patientId, caseId } = body;

    if (!phone) {
      return NextResponse.json({ 
        error: 'phone is required' 
      }, { status: 400 });
    }

    if (!healthCardNumber && !patientId && !caseId) {
      return NextResponse.json({ 
        error: 'One of healthCardNumber, patientId, or caseId is required' 
      }, { status: 400 });
    }

    let patient = null;

    // Find patient by health card number
    if (healthCardNumber) {
      patient = await Patient.findOne({ 
        healthCardNumber: healthCardNumber.toUpperCase().trim() 
      });
    }
    // Find patient by patient ID
    else if (patientId) {
      patient = await Patient.findById(patientId);
    }
    // Find patient by case ID
    else if (caseId) {
      const caseDoc = await Case.findById(caseId);
      if (!caseDoc) {
        return NextResponse.json({ 
          error: 'Case not found' 
        }, { status: 404 });
      }

      // Update phone in case as well
      caseDoc.user.phone = phone;
      await caseDoc.save();

      // Find linked patient
      if (caseDoc.user.patientId) {
        patient = await Patient.findById(caseDoc.user.patientId);
      } else {
        // No linked patient yet
        return NextResponse.json({ 
          success: true,
          message: 'Phone number saved to case (no patient linked yet)',
          caseUpdated: true,
          patientUpdated: false
        });
      }
    }

    if (!patient) {
      return NextResponse.json({ 
        error: 'Patient not found' 
      }, { status: 404 });
    }

    // Update patient phone
    if (!patient.contactInfo) {
      patient.contactInfo = { phone };
    } else {
      patient.contactInfo.phone = phone;
    }

    await patient.save();

    console.log(`Phone number updated for patient ${patient._id}: ${phone}`);

    // Also update phone in any linked cases if we updated via patientId or healthCardNumber
    if (!caseId) {
      await Case.updateMany(
        { 'user.patientId': patient._id.toString() },
        { $set: { 'user.phone': phone } }
      );
      console.log(`Updated phone in all cases for patient ${patient._id}`);
    }

    return NextResponse.json({ 
      success: true,
      message: 'Phone number updated successfully',
      patientId: patient._id,
      phone: patient.contactInfo.phone,
      caseUpdated: !!caseId,
      patientUpdated: true
    });
  } catch (error: any) {
    console.error('Error updating phone number:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to update phone number' 
    }, { status: 500 });
  }
}

