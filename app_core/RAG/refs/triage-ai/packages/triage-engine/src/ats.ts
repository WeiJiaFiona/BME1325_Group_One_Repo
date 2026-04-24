/**
 * Australian Triage Scale (ATS) Implementation
 *
 * The ATS is the official triage scale used in Australian emergency departments.
 * It classifies patients into 5 categories based on clinical urgency.
 *
 * Reference: Australasian College for Emergency Medicine (ACEM)
 * https://acem.org.au/Content-Sources/Advancing-Emergency-Medicine/Better-Outcomes-for-Patients/Triage
 */

import { z } from 'zod';

/**
 * ATS Category Definitions
 * Each category has a maximum waiting time before clinical treatment should begin
 */
export const ATSCategory = z.enum(['ATS1', 'ATS2', 'ATS3', 'ATS4', 'ATS5']);
export type ATSCategory = z.infer<typeof ATSCategory>;

export interface ATSCategoryInfo {
  category: ATSCategory;
  name: string;
  description: string;
  maxWaitTime: string;
  maxWaitMinutes: number;
  color: string; // For UI visualization
  examples: string[];
}

export const ATS_CATEGORIES: Record<ATSCategory, ATSCategoryInfo> = {
  ATS1: {
    category: 'ATS1',
    name: 'Resuscitation',
    description: 'Immediately life-threatening. Conditions that are threats to life or imminent risk of deterioration.',
    maxWaitTime: 'Immediate',
    maxWaitMinutes: 0,
    color: '#DC2626', // Red
    examples: [
      'Cardiac arrest',
      'Respiratory arrest',
      'Immediate risk to airway',
      'Severe respiratory distress',
      'Systolic BP < 80 (adults)',
      'Unresponsive or responds to pain only (GCS ≤ 9)',
      'Ongoing seizure',
      'Major multi-trauma',
    ],
  },
  ATS2: {
    category: 'ATS2',
    name: 'Emergency',
    description: 'Imminently life-threatening. Conditions that are a potential threat to life, organ, or limb.',
    maxWaitTime: '10 minutes',
    maxWaitMinutes: 10,
    color: '#EA580C', // Orange
    examples: [
      'Chest pain likely cardiac',
      'Severe respiratory distress',
      'Stridor',
      'Severe asthma',
      'Acute stroke',
      'Fever with signs of lethargy or petechial rash',
      'Severe pain',
      'Active major haemorrhage',
      'Major fractures',
      'Altered conscious state',
      'Severe dehydration',
      'High-risk overdose',
      'Severe agitation or aggression',
    ],
  },
  ATS3: {
    category: 'ATS3',
    name: 'Urgent',
    description: 'Potentially life-threatening. Conditions that could progress to life or limb threatening, or may result in significant morbidity.',
    maxWaitTime: '30 minutes',
    maxWaitMinutes: 30,
    color: '#EAB308', // Yellow
    examples: [
      'Moderate respiratory distress',
      'Persistent vomiting',
      'Moderate pain',
      'Fever in immunocompromised patients',
      'Significant abdominal pain',
      'Head injury with brief loss of consciousness',
      'Moderate blood loss',
      'Limb injury with neurovascular compromise',
      'Acute psychosis or severe anxiety',
      'Possible ectopic pregnancy',
    ],
  },
  ATS4: {
    category: 'ATS4',
    name: 'Semi-urgent',
    description: 'Potentially serious. Conditions that may deteriorate or would benefit from early intervention.',
    maxWaitTime: '60 minutes',
    maxWaitMinutes: 60,
    color: '#22C55E', // Green
    examples: [
      'Mild respiratory distress',
      'Foreign body in eye, ear, or nose',
      'Mild to moderate pain',
      'Urinary symptoms',
      'Mild head injury (no LOC)',
      'Minor lacerations',
      'Swollen joint',
      'Mild allergic reaction',
      'Vomiting without dehydration',
      'Eye inflammation or infection',
    ],
  },
  ATS5: {
    category: 'ATS5',
    name: 'Non-urgent',
    description: 'Less urgent. Conditions that are minor or part of a chronic condition.',
    maxWaitTime: '120 minutes',
    maxWaitMinutes: 120,
    color: '#3B82F6', // Blue
    examples: [
      'Minor wounds (not requiring sutures)',
      'Minor rash',
      'Minor symptoms of chronic stable illness',
      'Medication refill',
      'Minor follow-up',
      'Result review',
      'Certificate request',
      'Old injury (>72hrs) no disability',
    ],
  },
};

/**
 * Red Flag Clinical Indicators
 * These MUST trigger immediate escalation regardless of other factors
 */
export const RED_FLAG_INDICATORS = [
  // Cardiac
  {
    id: 'cardiac_chest_pain',
    name: 'Cardiac-type chest pain',
    description: 'Chest pain with radiation, diaphoresis, or cardiac history',
    keywords: ['chest pain', 'chest tightness', 'chest pressure', 'crushing', 'radiating to arm', 'radiating to jaw'],
    minCategory: 'ATS2' as ATSCategory,
    action: 'Immediate ECG and cardiac workup',
  },
  // Respiratory
  {
    id: 'severe_dyspnea',
    name: 'Severe respiratory distress',
    description: 'Unable to speak in sentences, using accessory muscles',
    keywords: ["can't breathe", 'hard to breathe', 'gasping', 'choking', 'suffocating'],
    minCategory: 'ATS1' as ATSCategory,
    action: 'Immediate airway assessment',
  },
  // Neurological
  {
    id: 'stroke_symptoms',
    name: 'Possible stroke (FAST)',
    description: 'Face drooping, Arm weakness, Speech difficulty, Time to call emergency',
    keywords: ['face drooping', 'arm weakness', 'slurred speech', "can't speak", 'one side', 'sudden weakness', 'sudden numbness'],
    minCategory: 'ATS2' as ATSCategory,
    action: 'Stroke protocol - CT within 25 minutes',
  },
  {
    id: 'thunderclap_headache',
    name: 'Thunderclap headache',
    description: 'Sudden severe headache reaching maximum intensity within seconds',
    keywords: ['worst headache', 'thunderclap', 'sudden severe headache'],
    minCategory: 'ATS2' as ATSCategory,
    action: 'Rule out subarachnoid haemorrhage',
  },
  {
    id: 'altered_consciousness',
    name: 'Altered consciousness',
    description: 'Confusion, disorientation, or decreased GCS',
    keywords: ['confused', 'disoriented', "don't know where", 'altered mental', 'not making sense'],
    minCategory: 'ATS2' as ATSCategory,
    action: 'Neurological assessment and workup',
  },
  {
    id: 'loss_of_consciousness',
    name: 'Loss of consciousness',
    description: 'Syncope or unwitnessed collapse',
    keywords: ['passed out', 'fainted', 'blacked out', 'lost consciousness', 'collapsed'],
    minCategory: 'ATS2' as ATSCategory,
    action: 'Cardiac and neurological workup',
  },
  // Anaphylaxis
  {
    id: 'anaphylaxis',
    name: 'Possible anaphylaxis',
    description: 'Allergic reaction with airway or circulatory compromise',
    keywords: ["can't swallow", 'throat closing', 'throat swelling', 'tongue swelling', 'severe allergic'],
    minCategory: 'ATS1' as ATSCategory,
    action: 'Adrenaline and resuscitation standby',
  },
  // Haemorrhage
  {
    id: 'severe_bleeding',
    name: 'Severe bleeding',
    description: 'Uncontrolled haemorrhage',
    keywords: ['heavy bleeding', "won't stop bleeding", 'blood everywhere', 'bleeding out'],
    minCategory: 'ATS2' as ATSCategory,
    action: 'Haemorrhage control and fluid resuscitation',
  },
  // Mental Health
  {
    id: 'suicidal_ideation',
    name: 'Suicidal ideation or self-harm',
    description: 'Active suicidal thoughts or recent self-harm',
    keywords: ['want to die', 'kill myself', 'suicide', 'self harm', 'end my life'],
    minCategory: 'ATS2' as ATSCategory,
    action: 'Mental health crisis intervention, ensure safety',
  },
  // Paediatric
  {
    id: 'paediatric_fever',
    name: 'Paediatric fever with red flags',
    description: 'Fever in child with lethargy, rash, or signs of meningism',
    keywords: ['fever', 'high temperature'],
    ageCondition: (age?: number) => age !== undefined && age < 3,
    minCategory: 'ATS3' as ATSCategory,
    action: 'Paediatric assessment, consider sepsis workup',
  },
];

/**
 * Clinical discriminators for ATS categorisation
 * Based on ACEM guidelines
 */
export const CLINICAL_DISCRIMINATORS = {
  // Vital signs thresholds
  vitals: {
    criticalHypotension: { systolic: 80 }, // ATS1-2
    moderateHypotension: { systolic: 90 }, // ATS2-3
    criticalTachycardia: { hr: 150 }, // ATS2
    criticalBradycardia: { hr: 40 }, // ATS2
    criticalHypoxia: { spo2: 90 }, // ATS2
    moderateHypoxia: { spo2: 94 }, // ATS3
    highFever: { temp: 39.0 }, // °C, affects category based on context
    criticalFever: { temp: 40.0 }, // ATS2-3 depending on age
  },

  // Pain severity thresholds
  pain: {
    severe: { min: 8, max: 10 }, // ATS2-3
    moderate: { min: 5, max: 7 }, // ATS3-4
    mild: { min: 1, max: 4 }, // ATS4-5
  },

  // Time since onset
  onset: {
    hyperacute: { maxHours: 1 }, // Higher acuity
    acute: { maxHours: 24 }, // Standard
    subacute: { maxHours: 72 }, // May be lower acuity
    chronic: { minDays: 3 }, // Often lower acuity
  },
};

/**
 * ATS Assessment Result
 */
export const ATSAssessmentSchema = z.object({
  category: ATSCategory,
  categoryInfo: z.object({
    name: z.string(),
    description: z.string(),
    maxWaitTime: z.string(),
    color: z.string(),
  }),
  confidence: z.number().min(0).max(1),
  redFlagsDetected: z.array(z.object({
    id: z.string(),
    name: z.string(),
    evidence: z.string(),
    action: z.string(),
  })),
  clinicalReasoning: z.string(),
  discriminatorsUsed: z.array(z.string()),
  recommendations: z.array(z.string()),
  escalationNotes: z.string().optional(),
  auditTrail: z.array(z.object({
    step: z.string(),
    result: z.string(),
    timestamp: z.string(),
  })),
});

export type ATSAssessment = z.infer<typeof ATSAssessmentSchema>;

/**
 * Symptom presentation for triage
 */
export const SymptomPresentationSchema = z.object({
  chiefComplaint: z.string(),
  symptoms: z.array(z.object({
    description: z.string(),
    location: z.string().optional(),
    duration: z.string().optional(),
    severity: z.number().min(1).max(10).optional(),
    onset: z.enum(['sudden', 'gradual']).optional(),
    associated: z.array(z.string()).optional(),
  })),
  demographics: z.object({
    age: z.number().optional(),
    sex: z.enum(['male', 'female', 'other']).optional(),
  }).optional(),
  vitals: z.object({
    heartRate: z.number().optional(),
    systolicBP: z.number().optional(),
    diastolicBP: z.number().optional(),
    temperature: z.number().optional(),
    respiratoryRate: z.number().optional(),
    spo2: z.number().optional(),
  }).optional(),
  medicalHistory: z.array(z.string()).optional(),
  currentMedications: z.array(z.string()).optional(),
  allergies: z.array(z.string()).optional(),
});

export type SymptomPresentation = z.infer<typeof SymptomPresentationSchema>;

/**
 * Check for red flags in text input
 * This is the DETERMINISTIC safety layer - runs BEFORE LLM
 */
export function checkRedFlags(
  text: string,
  age?: number
): Array<{ id: string; name: string; evidence: string; action: string; minCategory: ATSCategory }> {
  const lowerText = text.toLowerCase();
  const detectedFlags: Array<{ id: string; name: string; evidence: string; action: string; minCategory: ATSCategory }> = [];

  for (const flag of RED_FLAG_INDICATORS) {
    // Check age condition if applicable
    if (flag.ageCondition && !flag.ageCondition(age)) {
      continue;
    }

    // Check keywords
    for (const keyword of flag.keywords) {
      if (lowerText.includes(keyword.toLowerCase())) {
        detectedFlags.push({
          id: flag.id,
          name: flag.name,
          evidence: keyword,
          action: flag.action,
          minCategory: flag.minCategory,
        });
        break; // Only add each flag once
      }
    }
  }

  return detectedFlags;
}

/**
 * Get the minimum (most urgent) ATS category from detected red flags
 */
export function getMinimumCategoryFromFlags(
  flags: Array<{ minCategory: ATSCategory }>
): ATSCategory | null {
  if (flags.length === 0) return null;

  const categoryOrder: ATSCategory[] = ['ATS1', 'ATS2', 'ATS3', 'ATS4', 'ATS5'];
  let minIndex = categoryOrder.length;

  for (const flag of flags) {
    const index = categoryOrder.indexOf(flag.minCategory);
    if (index < minIndex) {
      minIndex = index;
    }
  }

  return categoryOrder[minIndex];
}

/**
 * Validate that LLM response doesn't under-triage
 * This is a safety guardrail that prevents the LLM from being too optimistic
 */
export function enforceMinimumCategory(
  llmCategory: ATSCategory,
  redFlagCategory: ATSCategory | null
): ATSCategory {
  if (!redFlagCategory) return llmCategory;

  const categoryOrder: ATSCategory[] = ['ATS1', 'ATS2', 'ATS3', 'ATS4', 'ATS5'];
  const llmIndex = categoryOrder.indexOf(llmCategory);
  const redFlagIndex = categoryOrder.indexOf(redFlagCategory);

  // Return the more urgent (lower index) category
  return llmIndex <= redFlagIndex ? llmCategory : redFlagCategory;
}
