import Patient, { PatientDocument } from '@/models/Patient';
import Case, { CaseDocument } from '@/models/Case';
import connectDB from './mongodb';

/**
 * Find a patient by health card number
 */
export async function findPatientByHealthCard(healthCardNumber: string): Promise<PatientDocument | null> {
  await connectDB();
  return Patient.findOne({ 
    healthCardNumber: healthCardNumber.toUpperCase().trim() 
  });
}

/**
 * Find a patient by anonymous ID
 */
export async function findPatientByAnonymousId(anonymousId: string): Promise<PatientDocument | null> {
  await connectDB();
  return Patient.findOne({
    anonymousIds: anonymousId
  });
}

/**
 * Find or create a patient from health card data
 */
export async function findOrCreatePatient(data: {
  healthCardNumber: string;
  name?: string;
  dateOfBirth?: string;
  sex?: string;
  versionCode?: string;
  expiryDate?: string;
  anonymousId?: string;
}): Promise<{ patient: PatientDocument; isNew: boolean }> {
  await connectDB();

  const normalizedHealthCardNumber = data.healthCardNumber.toUpperCase().trim();
  
  let patient = await Patient.findOne({ 
    healthCardNumber: normalizedHealthCardNumber 
  });

  if (patient) {
    // Update existing patient
    patient.demographics = {
      ...patient.demographics,
      name: data.name || patient.demographics.name,
      dateOfBirth: data.dateOfBirth || patient.demographics.dateOfBirth,
      sex: data.sex || patient.demographics.sex,
      healthCardNumber: normalizedHealthCardNumber,
      versionCode: data.versionCode || patient.demographics.versionCode,
      expiryDate: data.expiryDate || patient.demographics.expiryDate,
    };

    if (data.anonymousId && !patient.anonymousIds.includes(data.anonymousId)) {
      patient.anonymousIds.push(data.anonymousId);
    }

    patient.lastVisit = new Date();
    await patient.save();

    return { patient, isNew: false };
  } else {
    // Create new patient
    patient = new Patient({
      healthCardNumber: normalizedHealthCardNumber,
      demographics: {
        name: data.name,
        dateOfBirth: data.dateOfBirth,
        sex: data.sex,
        healthCardNumber: normalizedHealthCardNumber,
        versionCode: data.versionCode,
        expiryDate: data.expiryDate,
      },
      anonymousIds: data.anonymousId ? [data.anonymousId] : [],
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

    await patient.save();
    return { patient, isNew: true };
  }
}

/**
 * Link a case to a patient
 */
export async function linkCaseToPatient(
  caseId: string, 
  patientId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    await connectDB();

    const caseDoc = await Case.findById(caseId);
    if (!caseDoc) {
      return { success: false, error: 'Case not found' };
    }

    const patient = await Patient.findById(patientId);
    if (!patient) {
      return { success: false, error: 'Patient not found' };
    }

    // Link case to patient
    caseDoc.user.patientId = patientId;
    await caseDoc.save();

    // Add to patient's visit history if not already added
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

      // Update medical history
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
    }

    return { success: true };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}

/**
 * Get patient medical history with all cases
 */
export async function getPatientMedicalHistory(patientId: string) {
  await connectDB();

  const patient = await Patient.findById(patientId);
  if (!patient) {
    throw new Error('Patient not found');
  }

  // Fetch all cases linked to this patient
  const cases = await Case.find({ 
    'user.patientId': patientId 
  }).sort({ createdAt: -1 });

  return {
    patient: {
      id: patient._id,
      name: patient.demographics.name,
      dateOfBirth: patient.demographics.dateOfBirth,
      age: patient.demographics.age,
      sex: patient.demographics.sex,
      healthCardNumber: patient.demographics.healthCardNumber,
    },
    medicalHistory: patient.medicalHistory,
    visits: patient.visits,
    cases: cases.map(caseDoc => ({
      id: caseDoc._id,
      createdAt: caseDoc.createdAt,
      chiefComplaint: caseDoc.intake.chiefComplaint,
      symptoms: caseDoc.intake.symptoms,
      triageLevel: caseDoc.assistant.triageLevel,
      hospital: caseDoc.hospitalRouting?.hospitalName,
      status: caseDoc.status,
    })),
    statistics: {
      totalVisits: patient.totalVisits,
      firstVisit: patient.firstVisit,
      lastVisit: patient.lastVisit,
    },
  };
}

/**
 * Update patient medical history
 */
export async function updatePatientMedicalHistory(
  patientId: string,
  history: {
    conditions?: string[];
    medications?: string[];
    allergies?: string[];
  }
): Promise<PatientDocument> {
  await connectDB();

  const patient = await Patient.findById(patientId);
  if (!patient) {
    throw new Error('Patient not found');
  }

  if (history.conditions) {
    patient.medicalHistory.conditions = [
      ...new Set([...patient.medicalHistory.conditions, ...history.conditions])
    ];
  }

  if (history.medications) {
    patient.medicalHistory.medications = [
      ...new Set([...patient.medicalHistory.medications, ...history.medications])
    ];
  }

  if (history.allergies) {
    patient.medicalHistory.allergies = [
      ...new Set([...patient.medicalHistory.allergies, ...history.allergies])
    ];
  }

  patient.medicalHistory.lastUpdated = new Date();
  await patient.save();

  return patient;
}

/**
 * Search patients by name
 */
export async function searchPatientsByName(name: string, limit: number = 10): Promise<PatientDocument[]> {
  await connectDB();

  return Patient.find({
    'demographics.name': { $regex: name, $options: 'i' }
  })
  .sort({ lastVisit: -1 })
  .limit(limit);
}

/**
 * Get patients with recent visits
 */
export async function getRecentPatients(limit: number = 20): Promise<PatientDocument[]> {
  await connectDB();

  return Patient.find({ isActive: true })
    .sort({ lastVisit: -1 })
    .limit(limit);
}

