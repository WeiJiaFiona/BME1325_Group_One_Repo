export * from './types.js';
export { SymptomParser } from './symptom-parser.js';
export { TriageEngine } from './triage-engine.js';
export { DoctorSummaryGenerator } from './doctor-summary.js';

// Australian Triage Scale (ATS) exports
export * from './ats.js';
export { GuardrailsEngine, guardrailsEngine } from './guardrails.js';
export { ATSTriageEngine, ATSDoctorSummaryGenerator, atsTriageEngine, atsDoctorSummaryGenerator } from './ats-engine.js';

import { v4 as uuidv4 } from 'uuid';
import { SymptomParser } from './symptom-parser.js';
import { TriageEngine } from './triage-engine.js';
import { DoctorSummaryGenerator } from './doctor-summary.js';
import { PatientIntake, TriageSession } from './types.js';

/**
 * TriageService - Unified interface for the complete triage workflow
 *
 * This service orchestrates:
 * 1. Symptom parsing (natural language → structured data)
 * 2. Triage assessment (severity, urgency, red flags)
 * 3. Doctor summary generation (pre-consultation briefing)
 */
export class TriageService {
  private symptomParser: SymptomParser;
  private triageEngine: TriageEngine;
  private summaryGenerator: DoctorSummaryGenerator;

  constructor(apiKey?: string) {
    this.symptomParser = new SymptomParser(apiKey);
    this.triageEngine = new TriageEngine(apiKey);
    this.summaryGenerator = new DoctorSummaryGenerator(apiKey);
  }

  /**
   * Process a patient's symptom description through the full triage pipeline
   *
   * @param rawInput - Patient's natural language symptom description
   * @param options - Additional patient context (demographics, history, etc.)
   * @returns Complete triage session with assessment and doctor summary
   */
  async process(
    rawInput: string,
    options?: {
      patientId?: string;
      demographics?: { age?: number; sex?: 'male' | 'female' | 'other' };
      medicalHistory?: string[];
      currentMedications?: string[];
      allergies?: string[];
    }
  ): Promise<TriageSession> {
    const sessionId = uuidv4();
    const timestamp = new Date().toISOString();
    const auditLog: TriageSession['auditLog'] = [];

    // Step 1: Parse symptoms
    auditLog.push({
      timestamp: new Date().toISOString(),
      action: 'SYMPTOM_PARSE_START',
      details: { rawInput },
    });

    const parsed = await this.symptomParser.parse(rawInput);

    auditLog.push({
      timestamp: new Date().toISOString(),
      action: 'SYMPTOM_PARSE_COMPLETE',
      details: { symptomCount: parsed.symptoms.length },
    });

    // Build intake record
    const intake: PatientIntake = {
      patientId: options?.patientId,
      rawInput,
      symptoms: parsed.symptoms,
      demographics: options?.demographics,
      medicalHistory: options?.medicalHistory,
      currentMedications: options?.currentMedications,
      allergies: options?.allergies,
    };

    // Step 2: Triage assessment
    auditLog.push({
      timestamp: new Date().toISOString(),
      action: 'TRIAGE_ASSESSMENT_START',
      details: {},
    });

    const result = await this.triageEngine.assess(intake);

    auditLog.push({
      timestamp: new Date().toISOString(),
      action: 'TRIAGE_ASSESSMENT_COMPLETE',
      details: {
        severity: result.severity,
        urgency: result.urgency,
        redFlagsDetected: result.redFlags.detected,
      },
    });

    // Step 3: Generate doctor summary
    auditLog.push({
      timestamp: new Date().toISOString(),
      action: 'DOCTOR_SUMMARY_START',
      details: {},
    });

    const doctorSummary = await this.summaryGenerator.generate(intake, result);

    auditLog.push({
      timestamp: new Date().toISOString(),
      action: 'DOCTOR_SUMMARY_COMPLETE',
      details: {},
    });

    return {
      id: sessionId,
      timestamp,
      intake,
      result,
      doctorSummary,
      auditLog,
    };
  }
}
