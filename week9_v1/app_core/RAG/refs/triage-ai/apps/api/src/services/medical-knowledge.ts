/**
 * Medical Knowledge Base for TriageAI
 * Based on Australian Triage Scale (ATS) and ACEM Guidelines
 *
 * This module provides:
 * - Clinical condition definitions with ATS categories
 * - Symptom-to-condition mapping
 * - RAG-style retrieval for clinical context
 *
 * Full knowledge base contains 100+ conditions.
 * Contact pranjal@dataxlr8.ai for commercial license.
 */

export interface ClinicalCondition {
  id: string;
  name: string;
  category: string;
  atsCategory: 1 | 2 | 3 | 4 | 5;
  maxWaitTime: string;
  keywords: string[];
  symptoms: string[];
  redFlags: string[];
  differentials: string[];
  questions: string[];
  criteria: string;
  action: string;
}

export interface TriageGuideline {
  atsCategory: 1 | 2 | 3 | 4 | 5;
  name: string;
  maxWaitTime: string;
  color: string;
  description: string;
  clinicalDescriptors: string[];
  examples: string[];
}

// Australian Triage Scale Categories (public information)
export const ATS_GUIDELINES: TriageGuideline[] = [
  {
    atsCategory: 1,
    name: 'Resuscitation',
    maxWaitTime: 'Immediate',
    color: '#DC2626',
    description: 'Conditions that are threats to life or imminent risk of deterioration',
    clinicalDescriptors: ['Cardiac arrest', 'Respiratory arrest', 'Immediate risk to airway'],
    examples: ['Cardiac arrest', 'Respiratory arrest', 'Severe shock']
  },
  {
    atsCategory: 2,
    name: 'Emergency',
    maxWaitTime: '10 minutes',
    color: '#EA580C',
    description: 'Conditions that are imminently life-threatening',
    clinicalDescriptors: ['Risk of airway compromise', 'Severe respiratory distress', 'Chest pain likely cardiac'],
    examples: ['Chest pain - likely cardiac', 'Stroke symptoms', 'Severe asthma']
  },
  {
    atsCategory: 3,
    name: 'Urgent',
    maxWaitTime: '30 minutes',
    color: '#CA8A04',
    description: 'Conditions that could potentially be life-threatening',
    clinicalDescriptors: ['Moderate shortness of breath', 'Severe pain', 'High fever'],
    examples: ['Moderate asthma', 'Severe pain', 'High fever with systemic symptoms']
  },
  {
    atsCategory: 4,
    name: 'Semi-urgent',
    maxWaitTime: '60 minutes',
    color: '#16A34A',
    description: 'Conditions that are potentially serious',
    clinicalDescriptors: ['Mild shortness of breath', 'Moderate pain', 'Vomiting/diarrhoea'],
    examples: ['Mild asthma', 'Moderate pain', 'Minor head injury']
  },
  {
    atsCategory: 5,
    name: 'Non-urgent',
    maxWaitTime: '120 minutes',
    color: '#2563EB',
    description: 'Conditions that are less urgent',
    clinicalDescriptors: ['Minor symptoms', 'Low acuity', 'Chronic problems'],
    examples: ['Minor wounds', 'Prescription requests', 'Minor pain']
  }
];

/**
 * Clinical conditions database
 * Full database contains detailed symptom patterns and clinical rules
 */
const CLINICAL_CONDITIONS: ClinicalCondition[] = [
  // Sample entry - full database proprietary
  {
    id: 'chest-pain-cardiac',
    name: 'Chest Pain - Cardiac',
    category: 'cardiovascular',
    atsCategory: 2,
    maxWaitTime: '10 minutes',
    keywords: ['chest pain', 'crushing', 'radiating'],
    symptoms: ['Chest pain', 'Shortness of breath', 'Sweating'],
    redFlags: ['Radiating to arm/jaw', 'Associated with sweating', 'Crushing quality'],
    differentials: ['ACS', 'Unstable Angina', 'STEMI', 'NSTEMI'],
    questions: ['Character of pain?', 'Radiation?', 'Associated symptoms?'],
    criteria: 'Chest pain with cardiac features',
    action: 'Immediate ECG, cardiac workup'
  }
  // ... 100+ additional conditions in full version
];

/**
 * Build clinical context for RAG retrieval
 * Matches patient symptoms to relevant conditions
 */
export function buildClinicalContext(patientDescription: string): string {
  // Simplified - full implementation uses semantic matching
  const conditions = retrieveRelevantConditions(patientDescription);
  if (conditions.length === 0) return 'No specific conditions matched';

  return conditions.map(c =>
    `Consider ${c.name} (ATS ${c.atsCategory}): ${c.criteria}`
  ).join('\n');
}

/**
 * Retrieve relevant conditions based on symptoms
 * Full implementation uses vector similarity and keyword matching
 */
export function retrieveRelevantConditions(text: string): ClinicalCondition[] {
  const lowerText = text.toLowerCase();
  return CLINICAL_CONDITIONS.filter(condition =>
    condition.keywords.some(kw => lowerText.includes(kw))
  );
}

/**
 * Get minimum ATS category from symptom keywords
 * Safety floor - LLM cannot triage below this level
 */
export function getMinimumATSFromSymptoms(text: string): number {
  const conditions = retrieveRelevantConditions(text);
  if (conditions.length === 0) return 5;
  return Math.min(...conditions.map(c => c.atsCategory));
}
