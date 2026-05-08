import { z } from 'zod';

// Urgency levels matching clinical standards
export const UrgencyLevel = z.enum([
  'EMERGENCY',    // Immediate attention (chest pain, stroke, severe allergic reaction)
  'URGENT',       // < 1 hour (high fever, severe pain, worsening symptoms)
  'SEMI_URGENT',  // < 4 hours (moderate symptoms, concerning but stable)
  'STANDARD',     // Same day (routine concerns)
  'NON_URGENT',   // Scheduled (follow-ups, minor issues)
]);

export type UrgencyLevel = z.infer<typeof UrgencyLevel>;

// Symptom extracted from patient input
export const SymptomSchema = z.object({
  description: z.string(),
  location: z.string().optional(),
  duration: z.string().optional(),
  severity: z.number().min(1).max(10).optional(),
  onset: z.enum(['sudden', 'gradual']).optional(),
  associated: z.array(z.string()).optional(),
});

export type Symptom = z.infer<typeof SymptomSchema>;

// Patient intake data
export const PatientIntakeSchema = z.object({
  patientId: z.string().optional(),
  rawInput: z.string(),
  symptoms: z.array(SymptomSchema),
  demographics: z.object({
    age: z.number().optional(),
    sex: z.enum(['male', 'female', 'other']).optional(),
  }).optional(),
  medicalHistory: z.array(z.string()).optional(),
  currentMedications: z.array(z.string()).optional(),
  allergies: z.array(z.string()).optional(),
});

export type PatientIntake = z.infer<typeof PatientIntakeSchema>;

// Red flag conditions that require immediate escalation
export const RedFlagSchema = z.object({
  detected: z.boolean(),
  flags: z.array(z.object({
    condition: z.string(),
    evidence: z.string(),
    action: z.string(),
  })),
});

export type RedFlag = z.infer<typeof RedFlagSchema>;

// Triage result
export const TriageResultSchema = z.object({
  severity: z.number().min(1).max(5),
  urgency: UrgencyLevel,
  confidence: z.number().min(0).max(1),
  redFlags: RedFlagSchema,
  specialtyMatch: z.array(z.string()),
  reasoning: z.string(),
  recommendations: z.array(z.string()),
  estimatedWaitTime: z.string().optional(),
});

export type TriageResult = z.infer<typeof TriageResultSchema>;

// Doctor summary for pre-consultation
export const DoctorSummarySchema = z.object({
  headline: z.string(),
  keySymptoms: z.array(z.string()),
  severity: z.number().min(1).max(5),
  urgency: UrgencyLevel,
  redFlags: z.array(z.string()),
  relevantHistory: z.array(z.string()),
  suggestedQuestions: z.array(z.string()),
  differentialDiagnosis: z.array(z.string()),
  triageReasoning: z.string(),
});

export type DoctorSummary = z.infer<typeof DoctorSummarySchema>;

// Full triage session
export const TriageSessionSchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  intake: PatientIntakeSchema,
  result: TriageResultSchema,
  doctorSummary: DoctorSummarySchema,
  auditLog: z.array(z.object({
    timestamp: z.string(),
    action: z.string(),
    details: z.record(z.unknown()),
  })),
});

export type TriageSession = z.infer<typeof TriageSessionSchema>;
