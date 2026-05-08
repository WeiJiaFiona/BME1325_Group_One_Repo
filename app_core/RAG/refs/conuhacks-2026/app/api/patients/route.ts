import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Patient from '@/models/Patient';
import Case from '@/models/Case';

/**
 * GET /api/patients?healthCardNumber=xxx
 * Fetch a patient by health card number
 */
export async function GET(request: NextRequest) {
  try {
    await connectDB();

    const searchParams = request.nextUrl.searchParams;
    const healthCardNumber = searchParams.get('healthCardNumber');
    const anonymousId = searchParams.get('anonymousId');

    if (!healthCardNumber && !anonymousId) {
      return NextResponse.json({ 
        error: 'healthCardNumber or anonymousId is required' 
      }, { status: 400 });
    }

    let patient;
    
    if (healthCardNumber) {
      patient = await Patient.findOne({ 
        healthCardNumber: healthCardNumber.toUpperCase() 
      });
    } else if (anonymousId) {
      patient = await Patient.findOne({
        anonymousIds: anonymousId
      });
    }

    if (!patient) {
      return NextResponse.json({ 
        error: 'Patient not found',
        exists: false 
      }, { status: 404 });
    }

    return NextResponse.json({ 
      patient,
      exists: true 
    });
  } catch (error: any) {
    console.error('Error fetching patient:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to fetch patient' 
    }, { status: 500 });
  }
}

/**
 * POST /api/patients
 * Create or update a patient record from health card data
 */
export async function POST(request: NextRequest) {
  try {
    await connectDB();

    const body = await request.json();
    const { 
      healthCardNumber, 
      demographics, 
      anonymousId,
      caseId,
      contactInfo,
      consentGiven 
    } = body;

    if (!healthCardNumber) {
      return NextResponse.json({ 
        error: 'healthCardNumber is required' 
      }, { status: 400 });
    }

    const normalizedHealthCardNumber = healthCardNumber.toUpperCase().trim();

    // Check if patient already exists
    let patient = await Patient.findOne({ 
      healthCardNumber: normalizedHealthCardNumber 
    });

    if (patient) {
      // Update existing patient
      console.log('Updating existing patient:', patient._id);
      
      // Update demographics if provided
      if (demographics) {
        patient.demographics = {
          ...patient.demographics,
          ...demographics,
          healthCardNumber: normalizedHealthCardNumber,
        };
      }

      // Add anonymous ID if not already tracked
      if (anonymousId && !patient.anonymousIds.includes(anonymousId)) {
        patient.anonymousIds.push(anonymousId);
      }

      // Update contact info if provided
      if (contactInfo) {
        patient.contactInfo = {
          ...patient.contactInfo,
          ...contactInfo,
        };
      }

      // Update consent if provided
      if (consentGiven !== undefined) {
        patient.consentGiven = consentGiven;
        if (consentGiven && !patient.consentDate) {
          patient.consentDate = new Date();
        }
      }

      // Update last visit
      patient.lastVisit = new Date();

    } else {
      // Create new patient
      console.log('Creating new patient with health card:', normalizedHealthCardNumber);
      
      patient = new Patient({
        healthCardNumber: normalizedHealthCardNumber,
        demographics: {
          ...demographics,
          healthCardNumber: normalizedHealthCardNumber,
        },
        anonymousIds: anonymousId ? [anonymousId] : [],
        contactInfo: contactInfo || undefined,
        consentGiven: consentGiven || false,
        consentDate: consentGiven ? new Date() : undefined,
        firstVisit: new Date(),
        lastVisit: new Date(),
        totalVisits: 0,
        medicalHistory: {
          conditions: [],
          medications: [],
          allergies: [],
          lastUpdated: new Date(),
        },
        visits: [],
      });
    }

    // If a case ID is provided, link it to this patient and add to visit history
    if (caseId) {
      const caseDoc = await Case.findById(caseId);
      if (caseDoc) {
        // Link case to patient
        caseDoc.user.patientId = patient._id.toString();
        await caseDoc.save();

        // Add to visit history if not already added
        const visitExists = patient.visits.some(
          (visit: any) => visit.caseId.toString() === caseId
        );

        if (!visitExists) {
          patient.visits.push({
            caseId: caseDoc._id,
            visitDate: caseDoc.createdAt,
            chiefComplaint: caseDoc.intake.chiefComplaint,
            triageLevel: caseDoc.assistant.triageLevel,
            hospitalId: caseDoc.hospitalRouting?.hospitalId,
            hospitalName: caseDoc.hospitalRouting?.hospitalName,
          });
          patient.totalVisits = patient.visits.length;
        }

        // Update medical history from case intake
        if (caseDoc.intake.history) {
          // Merge conditions
          const newConditions = caseDoc.intake.history.conditions || [];
          patient.medicalHistory.conditions = [
            ...new Set([...patient.medicalHistory.conditions, ...newConditions])
          ];

          // Merge medications
          const newMeds = caseDoc.intake.history.meds || [];
          patient.medicalHistory.medications = [
            ...new Set([...patient.medicalHistory.medications, ...newMeds])
          ];

          // Merge allergies
          const newAllergies = caseDoc.intake.history.allergies || [];
          patient.medicalHistory.allergies = [
            ...new Set([...patient.medicalHistory.allergies, ...newAllergies])
          ];

          patient.medicalHistory.lastUpdated = new Date();
        }
      }
    }

    await patient.save();

    console.log('Patient saved successfully:', patient._id);

    return NextResponse.json({ 
      success: true,
      patient,
      isNew: !patient.visits || patient.visits.length === 0
    }, { status: patient.visits && patient.visits.length > 0 ? 200 : 201 });
  } catch (error: any) {
    console.error('Error creating/updating patient:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to create/update patient' 
    }, { status: 500 });
  }
}

/**
 * PATCH /api/patients/:id
 * Update specific patient fields
 */
export async function PATCH(request: NextRequest) {
  try {
    await connectDB();

    const body = await request.json();
    const { patientId, updates } = body;

    if (!patientId) {
      return NextResponse.json({ 
        error: 'patientId is required' 
      }, { status: 400 });
    }

    const patient = await Patient.findById(patientId);
    if (!patient) {
      return NextResponse.json({ 
        error: 'Patient not found' 
      }, { status: 404 });
    }

    // Apply updates
    if (updates.demographics) {
      patient.demographics = { ...patient.demographics, ...updates.demographics };
    }
    if (updates.contactInfo) {
      patient.contactInfo = { ...patient.contactInfo, ...updates.contactInfo };
    }
    if (updates.medicalHistory) {
      patient.medicalHistory = { ...patient.medicalHistory, ...updates.medicalHistory };
      patient.medicalHistory.lastUpdated = new Date();
    }
    if (updates.notes !== undefined) {
      patient.notes = updates.notes;
    }

    await patient.save();

    return NextResponse.json({ 
      success: true,
      patient 
    });
  } catch (error: any) {
    console.error('Error updating patient:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to update patient' 
    }, { status: 500 });
  }
}

