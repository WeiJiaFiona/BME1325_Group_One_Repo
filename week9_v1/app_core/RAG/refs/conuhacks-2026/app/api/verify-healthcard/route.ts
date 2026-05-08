import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import Patient from '@/models/Patient';

export async function POST(request: NextRequest) {
  try {
    await connectDB();

    const body = await request.json();
    const { caseId, verifiedData, phone } = body;

    if (!caseId || !verifiedData) {
      return NextResponse.json({ error: 'caseId and verifiedData are required' }, { status: 400 });
    }

    const caseDoc = await Case.findById(caseId);
    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Calculate actual age from verified date of birth if available
    let ageWasSet = false;
    if (verifiedData.dateOfBirth) {
      try {
        const dob = new Date(verifiedData.dateOfBirth);
        const today = new Date();
        let age = today.getFullYear() - dob.getFullYear();
        const monthDiff = today.getMonth() - dob.getMonth();
        
        // Adjust age if birthday hasn't occurred yet this year
        if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
          age--;
        }
        
        caseDoc.user.age = age;
        ageWasSet = true;
      } catch (err) {
        console.error('Error calculating age from verified DOB:', err);
      }
    }

    // Update health card scan information with verified data
    if (!caseDoc.user.healthCardScan) {
      caseDoc.user.healthCardScan = {
        scanned: true,
        ageSet: false,
      };
    }

    caseDoc.user.healthCardScan = {
      scanned: true,
      ageSet: ageWasSet,
      dateOfBirth: verifiedData.dateOfBirth || undefined,
      name: verifiedData.name || undefined,
      sex: verifiedData.sex || undefined,
      healthCardNumber: verifiedData.healthCardNumber || undefined,
      versionCode: verifiedData.versionCode || undefined,
      expiryDate: verifiedData.expiryDate || undefined,
      confidence: caseDoc.user.healthCardScan?.confidence || 'medium',
      scannedAt: caseDoc.user.healthCardScan?.scannedAt || new Date(),
      fieldsExtracted: {
        name: !!verifiedData.name,
        dateOfBirth: !!verifiedData.dateOfBirth,
        sex: !!verifiedData.sex,
        expiryDate: !!verifiedData.expiryDate,
        healthCardNumber: !!verifiedData.healthCardNumber,
        versionCode: !!verifiedData.versionCode,
      },
    };

    // Save phone number if provided
    if (phone) {
      caseDoc.user.phone = phone;
    }

    await caseDoc.save();

    console.log('Health card data verified and saved for case:', caseId);

    // Create or update patient record if health card number is available
    let patient = null;
    let patientId = null;
    let isNewPatient = false;

    if (verifiedData.healthCardNumber) {
      try {
        const normalizedHealthCardNumber = verifiedData.healthCardNumber.toUpperCase().trim();
        
        // Check if patient already exists
        patient = await Patient.findOne({ 
          healthCardNumber: normalizedHealthCardNumber 
        });

        if (patient) {
          console.log('Found existing patient:', patient._id);
          
          // Update patient demographics
          patient.demographics = {
            ...patient.demographics,
            name: verifiedData.name || patient.demographics.name,
            dateOfBirth: verifiedData.dateOfBirth || patient.demographics.dateOfBirth,
            sex: verifiedData.sex || patient.demographics.sex,
            healthCardNumber: normalizedHealthCardNumber,
            versionCode: verifiedData.versionCode || patient.demographics.versionCode,
            expiryDate: verifiedData.expiryDate || patient.demographics.expiryDate,
          };

          // Update contact info if phone is provided
          if (phone) {
            if (!patient.contactInfo) {
              patient.contactInfo = { phone };
            } else {
              patient.contactInfo.phone = phone;
            }
          }

          // Add anonymous ID if not already tracked
          if (!patient.anonymousIds.includes(caseDoc.user.anonymousId)) {
            patient.anonymousIds.push(caseDoc.user.anonymousId);
          }

          // Update last visit
          patient.lastVisit = new Date();

        } else {
          console.log('Creating new patient with health card:', normalizedHealthCardNumber);
          isNewPatient = true;
          
          // Create new patient
          patient = new Patient({
            healthCardNumber: normalizedHealthCardNumber,
            demographics: {
              name: verifiedData.name,
              dateOfBirth: verifiedData.dateOfBirth,
              sex: verifiedData.sex,
              healthCardNumber: normalizedHealthCardNumber,
              versionCode: verifiedData.versionCode,
              expiryDate: verifiedData.expiryDate,
            },
            contactInfo: phone ? { phone } : undefined,
            anonymousIds: [caseDoc.user.anonymousId],
            consentGiven: false, // Will be set when consent is given
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

        // Add this case to visit history if not already added
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

        // Update medical history from case intake if available
        if (caseDoc.intake.history) {
          const newConditions = caseDoc.intake.history.conditions || [];
          patient.medicalHistory.conditions = [
            ...new Set([...patient.medicalHistory.conditions, ...newConditions])
          ];

          const newMeds = caseDoc.intake.history.meds || [];
          patient.medicalHistory.medications = [
            ...new Set([...patient.medicalHistory.medications, ...newMeds])
          ];

          const newAllergies = caseDoc.intake.history.allergies || [];
          patient.medicalHistory.allergies = [
            ...new Set([...patient.medicalHistory.allergies, ...newAllergies])
          ];

          patient.medicalHistory.lastUpdated = new Date();
        }

        await patient.save();
        patientId = patient._id.toString();

        // Link case to patient
        caseDoc.user.patientId = patientId;
        await caseDoc.save();

        console.log('Patient record created/updated and linked to case:', patientId);

      } catch (patientError: any) {
        console.error('Error creating/updating patient record:', patientError);
        // Don't fail the entire request if patient creation fails
        // The health card data is still saved to the case
      }
    }

    return NextResponse.json({ 
      success: true,
      message: 'Health card data verified and saved',
      ageSet: ageWasSet,
      patientLinked: !!patientId,
      patientId,
      isNewPatient,
      hasExistingHistory: patient && patient.visits.length > 1
    });
  } catch (error: any) {
    console.error('Error saving verified health card data:', error);
    return NextResponse.json({ 
      error: error.message || 'Failed to save verified data' 
    }, { status: 500 });
  }
}

