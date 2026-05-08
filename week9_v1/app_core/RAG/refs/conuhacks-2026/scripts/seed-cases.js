/**
 * Seed Database with Test Cases
 * Run with: npm run seed:cases
 * 
 * This script populates the database with various test cases
 * to test triage functionality with different symptoms and severity levels
 */

const mongoose = require('mongoose');
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');

// Read .env.local file
function getEnvVar(key) {
  // Try process.env first (if running in Next.js environment)
  if (process.env[key]) {
    return process.env[key];
  }
  
  // Try reading .env.local file
  const envPath = path.join(__dirname, '..', '.env.local');
  if (fs.existsSync(envPath)) {
    try {
      const content = fs.readFileSync(envPath, 'utf8');
      const lines = content.split('\n');
      
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('#') || !trimmed) continue;
        
        const match = trimmed.match(/^([^=]+)=(.*)$/);
        if (match && match[1].trim() === key) {
          return match[2].trim().replace(/^["']|["']$/g, '');
        }
      }
    } catch (e) {
      // File read failed, continue
    }
  }
  
  return null;
}

const MONGODB_URI = getEnvVar('MONGODB_URI');

if (!MONGODB_URI) {
  console.error('❌ MONGODB_URI not found in .env.local');
  process.exit(1);
}

// Define Case Schema (simplified for seeding)
const CaseSchema = new mongoose.Schema({
  status: {
    type: String,
    enum: ['in_progress', 'completed', 'escalated'],
    default: 'completed',
  },
  user: {
    anonymousId: String,
    ageRange: String,
    pregnant: mongoose.Schema.Types.Mixed,
  },
  intake: {
    chiefComplaint: String,
    symptoms: [String],
    severity: mongoose.Schema.Types.Mixed,
    onset: String,
    pattern: String,
    redFlags: {
      any: mongoose.Schema.Types.Mixed,
      details: [String],
    },
    history: {
      conditions: [String],
      meds: [String],
      allergies: [String],
    },
    vitals: {
      tempC: mongoose.Schema.Types.Mixed,
      hr: mongoose.Schema.Types.Mixed,
      spo2: mongoose.Schema.Types.Mixed,
    },
  },
  assistant: {
    triageLevel: String,
    confidence: Number,
    reasons: [String],
    nextSteps: [String],
    monitoringPlan: [String],
    escalationTriggers: [String],
    questionsAsked: [{
      id: String,
      question: String,
      answer: mongoose.Schema.Types.Mixed,
      timestamp: Date,
    }],
    intakeSummary: String,
    disclaimerShown: Boolean,
  },
  adminReview: {
    reviewed: Boolean,
    reviewedAt: Date,
    reviewedBy: String,
    adminTriageLevel: String,
    adminNotes: String,
    onWatchList: Boolean,
    watchListReason: String,
  },
}, {
  timestamps: true,
});

const Case = mongoose.models.Case || mongoose.model('Case', CaseSchema);

const testCases = [
  // EMERGENCY CASES
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '40-64',
    },
    intake: {
      chiefComplaint: 'Severe chest pain with shortness of breath',
      symptoms: ['Chest pain', 'Shortness of breath', 'Sweating', 'Nausea'],
      severity: 9,
      onset: '30 minutes ago',
      pattern: 'Sudden onset, getting worse',
      redFlags: {
        any: true,
        details: ['Severe chest pain', 'Difficulty breathing', 'Radiating pain to left arm'],
      },
      history: {
        conditions: ['Hypertension', 'High cholesterol'],
        meds: ['Lisinopril', 'Aspirin'],
        allergies: [],
      },
      vitals: {
        hr: 110,
        spo2: 92,
      },
    },
    assistant: {
      triageLevel: 'EMERGENCY',
      confidence: 0.95,
      reasons: [
        'Severe chest pain with cardiac risk factors',
        'Low oxygen saturation (92%)',
        'Multiple emergency red flags present',
        'Symptoms consistent with possible cardiac event',
      ],
      nextSteps: [
        'Call 911 immediately',
        'Do not drive yourself',
        'Chew aspirin if available and not allergic',
        'Stay calm and wait for emergency services',
      ],
      monitoringPlan: [],
      escalationTriggers: [],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '40-64', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Severe chest pain', timestamp: new Date() },
        { id: 'severity', question: 'Severity?', answer: '9', timestamp: new Date() },
        { id: 'redFlags', question: 'Emergency symptoms?', answer: 'Yes', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with severe chest pain (9/10), sudden onset 30 minutes ago, associated with shortness of breath, sweating, and nausea. Oxygen saturation 92%. History of hypertension and high cholesterol. Multiple emergency red flags present. EMERGENCY - immediate medical attention required.',
      disclaimerShown: true,
    },
    status: 'escalated',
  },
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '18-39',
    },
    intake: {
      chiefComplaint: 'Severe allergic reaction with difficulty breathing',
      symptoms: ['Hives', 'Swelling of face and throat', 'Difficulty breathing', 'Dizziness'],
      severity: 10,
      onset: '15 minutes ago',
      pattern: 'Rapid progression',
      redFlags: {
        any: true,
        details: ['Severe breathing difficulty', 'Facial swelling', 'Possible anaphylaxis'],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: ['Peanuts', 'Shellfish'],
      },
      vitals: {
        hr: 130,
        spo2: 88,
      },
    },
    assistant: {
      triageLevel: 'EMERGENCY',
      confidence: 0.98,
      reasons: [
        'Severe allergic reaction with airway involvement',
        'Very low oxygen saturation (88%)',
        'Rapid progression of symptoms',
        'Life-threatening anaphylaxis suspected',
      ],
      nextSteps: [
        'Call 911 immediately',
        'Use epinephrine auto-injector if available',
        'Do not delay seeking emergency care',
        'Monitor breathing closely',
      ],
      monitoringPlan: [],
      escalationTriggers: [],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '18-39', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Allergic reaction', timestamp: new Date() },
        { id: 'severity', question: 'Severity?', answer: '10', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with severe allergic reaction, rapid onset 15 minutes ago. Symptoms include hives, facial/throat swelling, difficulty breathing, and dizziness. Oxygen saturation 88%. Known allergies to peanuts and shellfish. EMERGENCY - anaphylaxis suspected, immediate medical attention required.',
      disclaimerShown: true,
    },
    status: 'escalated',
  },
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '65+',
    },
    intake: {
      chiefComplaint: 'Sudden weakness on one side of body',
      symptoms: ['Facial drooping', 'Arm weakness', 'Speech difficulty', 'Confusion'],
      severity: 9,
      onset: '1 hour ago',
      pattern: 'Sudden onset',
      redFlags: {
        any: true,
        details: ['Stroke symptoms', 'Sudden neurological changes', 'Facial asymmetry'],
      },
      history: {
        conditions: ['Atrial fibrillation', 'Hypertension'],
        meds: ['Warfarin', 'Metoprolol'],
        allergies: [],
      },
      vitals: {},
    },
    assistant: {
      triageLevel: 'EMERGENCY',
      confidence: 0.97,
      reasons: [
        'Classic stroke symptoms (FAST)',
        'Sudden onset neurological changes',
        'High-risk patient with AFib history',
        'Time-sensitive condition requiring immediate care',
      ],
      nextSteps: [
        'Call 911 immediately',
        'Note time of symptom onset',
        'Do not give food or drink',
        'Transport to stroke center if possible',
      ],
      monitoringPlan: [],
      escalationTriggers: [],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '65+', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Weakness on one side', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with sudden onset weakness on one side of body, facial drooping, arm weakness, and speech difficulty. Onset 1 hour ago. History of atrial fibrillation and hypertension. EMERGENCY - stroke suspected, immediate medical attention required.',
      disclaimerShown: true,
    },
    status: 'escalated',
  },

  // URGENT CASES
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '18-39',
    },
    intake: {
      chiefComplaint: 'High fever with severe headache',
      symptoms: ['Fever 39.5°C', 'Severe headache', 'Neck stiffness', 'Light sensitivity'],
      severity: 8,
      onset: '12 hours ago',
      pattern: 'Worsening',
      redFlags: {
        any: true,
        details: ['High fever', 'Neck stiffness', 'Severe headache'],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: [],
      },
      vitals: {
        tempC: 39.5,
        hr: 95,
      },
    },
    assistant: {
      triageLevel: 'URGENT',
      confidence: 0.85,
      reasons: [
        'High fever with neurological symptoms',
        'Neck stiffness and photophobia present',
        'Possible meningitis - requires urgent evaluation',
        'Symptoms worsening over 12 hours',
      ],
      nextSteps: [
        'Seek urgent medical care today',
        'Go to urgent care or emergency department',
        'Monitor symptoms closely',
        'Do not delay if symptoms worsen',
      ],
      monitoringPlan: [
        'Monitor temperature every 2 hours',
        'Watch for worsening headache or neck stiffness',
        'Note any changes in mental status',
      ],
      escalationTriggers: [
        'Worsening headache',
        'Increased neck stiffness',
        'Confusion or altered mental status',
        'Rash develops',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '18-39', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'High fever', timestamp: new Date() },
        { id: 'severity', question: 'Severity?', answer: '8', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with high fever (39.5°C), severe headache, neck stiffness, and light sensitivity. Onset 12 hours ago, worsening. URGENT - possible meningitis, requires same-day medical evaluation.',
      disclaimerShown: true,
    },
    status: 'completed',
  },
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '40-64',
    },
    intake: {
      chiefComplaint: 'Severe abdominal pain',
      symptoms: ['Severe right lower quadrant pain', 'Nausea', 'Fever', 'Loss of appetite'],
      severity: 8,
      onset: '6 hours ago',
      pattern: 'Steady, severe pain',
      redFlags: {
        any: true,
        details: ['Severe abdominal pain', 'Fever with pain'],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: [],
      },
      vitals: {
        tempC: 38.2,
        hr: 100,
      },
    },
    assistant: {
      triageLevel: 'URGENT',
      confidence: 0.80,
      reasons: [
        'Severe abdominal pain with fever',
        'Possible appendicitis or other surgical emergency',
        'Symptoms require urgent evaluation',
        'Cannot rule out serious condition',
      ],
      nextSteps: [
        'Seek urgent medical care today',
        'Go to urgent care or emergency department',
        'Do not eat or drink until evaluated',
        'Avoid pain medications that mask symptoms',
      ],
      monitoringPlan: [
        'Monitor pain level',
        'Watch for fever changes',
        'Note any vomiting or other symptoms',
      ],
      escalationTriggers: [
        'Pain becomes unbearable',
        'Fever increases',
        'Vomiting develops',
        'Pain spreads to entire abdomen',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '40-64', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Abdominal pain', timestamp: new Date() },
        { id: 'severity', question: 'Severity?', answer: '8', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with severe right lower quadrant abdominal pain (8/10), onset 6 hours ago. Associated with nausea, fever (38.2°C), and loss of appetite. URGENT - possible appendicitis or surgical emergency, requires same-day evaluation.',
      disclaimerShown: true,
    },
    status: 'completed',
  },
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '3-12',
    },
    intake: {
      chiefComplaint: 'Child with high fever and difficulty breathing',
      symptoms: ['Fever 40°C', 'Rapid breathing', 'Cough', 'Wheezing'],
      severity: 7,
      onset: '8 hours ago',
      pattern: 'Worsening',
      redFlags: {
        any: true,
        details: ['High fever in child', 'Breathing difficulty'],
      },
      history: {
        conditions: ['Asthma'],
        meds: ['Albuterol inhaler'],
        allergies: [],
      },
      vitals: {
        tempC: 40,
        hr: 120,
        spo2: 94,
      },
    },
    assistant: {
      triageLevel: 'URGENT',
      confidence: 0.88,
      reasons: [
        'High fever in pediatric patient',
        'Respiratory distress with low oxygen',
        'Asthma history increases risk',
        'Requires urgent pediatric evaluation',
      ],
      nextSteps: [
        'Seek urgent pediatric care today',
        'Use rescue inhaler if available',
        'Monitor breathing closely',
        'Consider emergency department if breathing worsens',
      ],
      monitoringPlan: [
        'Monitor temperature every 2 hours',
        'Watch breathing rate and effort',
        'Check oxygen if available',
        'Monitor for dehydration',
      ],
      escalationTriggers: [
        'Breathing becomes more difficult',
        'Oxygen drops below 92%',
        'Child becomes lethargic',
        'Unable to speak in sentences',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '3-12', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Fever and breathing', timestamp: new Date() },
      ],
      intakeSummary: 'Pediatric patient (3-12 years) presents with high fever (40°C), rapid breathing, cough, and wheezing. Onset 8 hours ago, worsening. History of asthma. Oxygen saturation 94%. URGENT - requires same-day pediatric evaluation.',
      disclaimerShown: true,
    },
    status: 'completed',
  },

  // NON-URGENT CASES
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '18-39',
    },
    intake: {
      chiefComplaint: 'Persistent headache for 3 days',
      symptoms: ['Headache', 'Mild nausea', 'Sensitivity to light'],
      severity: 5,
      onset: '3 days ago',
      pattern: 'Constant, moderate',
      redFlags: {
        any: false,
        details: [],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: [],
      },
      vitals: {},
    },
    assistant: {
      triageLevel: 'NON_URGENT',
      confidence: 0.75,
      reasons: [
        'Moderate headache without emergency red flags',
        'Symptoms present for 3 days',
        'No severe neurological symptoms',
        'Can be evaluated in 1-3 days',
      ],
      nextSteps: [
        'See healthcare provider in 1-3 days',
        'Try over-the-counter pain relief if appropriate',
        'Rest and stay hydrated',
        'Monitor for any new or worsening symptoms',
      ],
      monitoringPlan: [
        'Track headache severity daily',
        'Note any new symptoms',
        'Monitor for changes in pattern',
      ],
      escalationTriggers: [
        'Headache becomes severe (8+/10)',
        'New neurological symptoms develop',
        'Fever develops',
        'Symptoms persist beyond 1 week',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '18-39', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Headache', timestamp: new Date() },
        { id: 'severity', question: 'Severity?', answer: '5', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with persistent headache for 3 days, moderate severity (5/10). Associated with mild nausea and light sensitivity. No emergency red flags. NON_URGENT - can be evaluated in 1-3 days.',
      disclaimerShown: true,
    },
    status: 'completed',
  },
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '40-64',
    },
    intake: {
      chiefComplaint: 'Persistent cough with mild fever',
      symptoms: ['Cough', 'Mild fever 37.8°C', 'Fatigue', 'Sore throat'],
      severity: 4,
      onset: '5 days ago',
      pattern: 'Gradual improvement',
      redFlags: {
        any: false,
        details: [],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: [],
      },
      vitals: {
        tempC: 37.8,
      },
    },
    assistant: {
      triageLevel: 'NON_URGENT',
      confidence: 0.70,
      reasons: [
        'Mild symptoms without emergency red flags',
        'Symptoms improving gradually',
        'Low-grade fever only',
        'Can be managed with follow-up care',
      ],
      nextSteps: [
        'See healthcare provider in 1-3 days if symptoms persist',
        'Rest and stay hydrated',
        'Monitor temperature',
        'Consider over-the-counter symptom relief',
      ],
      monitoringPlan: [
        'Monitor temperature daily',
        'Track cough frequency',
        'Watch for worsening symptoms',
      ],
      escalationTriggers: [
        'Fever increases above 38.5°C',
        'Difficulty breathing develops',
        'Symptoms worsen significantly',
        'Symptoms persist beyond 10 days',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '40-64', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Cough', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with persistent cough for 5 days, mild fever (37.8°C), fatigue, and sore throat. Symptoms gradually improving. No emergency red flags. NON_URGENT - can be evaluated in 1-3 days if symptoms persist.',
      disclaimerShown: true,
    },
    status: 'completed',
  },

  // SELF-CARE CASES
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '18-39',
    },
    intake: {
      chiefComplaint: 'Mild sore throat',
      symptoms: ['Sore throat', 'Mild discomfort'],
      severity: 2,
      onset: '2 days ago',
      pattern: 'Mild, stable',
      redFlags: {
        any: false,
        details: [],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: [],
      },
      vitals: {},
    },
    assistant: {
      triageLevel: 'SELF_CARE',
      confidence: 0.85,
      reasons: [
        'Mild symptoms only',
        'No fever or emergency red flags',
        'Symptoms manageable at home',
        'Typical viral illness pattern',
      ],
      nextSteps: [
        'Rest and stay hydrated',
        'Gargle with warm salt water',
        'Use throat lozenges if needed',
        'Monitor for worsening symptoms',
      ],
      monitoringPlan: [
        'Monitor for fever development',
        'Watch for worsening pain',
        'Note if symptoms persist beyond 7 days',
      ],
      escalationTriggers: [
        'Fever develops',
        'Severe difficulty swallowing',
        'Symptoms worsen significantly',
        'Symptoms persist beyond 1 week',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '18-39', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Sore throat', timestamp: new Date() },
        { id: 'severity', question: 'Severity?', answer: '2', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with mild sore throat (2/10), onset 2 days ago. No fever or emergency red flags. SELF_CARE - can be managed at home with rest and hydration.',
      disclaimerShown: true,
    },
    status: 'completed',
  },
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '18-39',
    },
    intake: {
      chiefComplaint: 'Minor cut on finger',
      symptoms: ['Small cut', 'Mild bleeding', 'Minimal pain'],
      severity: 2,
      onset: '1 hour ago',
      pattern: 'Stable',
      redFlags: {
        any: false,
        details: [],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: [],
      },
      vitals: {},
    },
    assistant: {
      triageLevel: 'SELF_CARE',
      confidence: 0.90,
      reasons: [
        'Minor injury',
        'Bleeding controlled',
        'No signs of infection',
        'Can be managed with first aid',
      ],
      nextSteps: [
        'Clean the wound with soap and water',
        'Apply pressure to stop bleeding',
        'Cover with clean bandage',
        'Monitor for signs of infection',
      ],
      monitoringPlan: [
        'Watch for signs of infection (redness, swelling, pus)',
        'Keep wound clean and dry',
        'Change bandage daily',
      ],
      escalationTriggers: [
        'Signs of infection develop',
        'Bleeding does not stop',
        'Wound is deep or gaping',
        'Foreign object in wound',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '18-39', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Cut on finger', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with minor cut on finger, minimal bleeding, mild pain (2/10). Onset 1 hour ago. SELF_CARE - can be managed with basic first aid at home.',
      disclaimerShown: true,
    },
    status: 'completed',
  },

  // UNCERTAIN CASES
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '18-39',
    },
    intake: {
      chiefComplaint: 'Vague symptoms',
      symptoms: ['Fatigue', 'General malaise'],
      severity: 3,
      onset: '1 week ago',
      pattern: 'Intermittent',
      redFlags: {
        any: 'unknown',
        details: [],
      },
      history: {
        conditions: [],
        meds: [],
        allergies: [],
      },
      vitals: {},
    },
    assistant: {
      triageLevel: 'UNCERTAIN',
      confidence: 0.50,
      reasons: [
        'Vague symptoms without clear pattern',
        'Insufficient information for safe triage',
        'Symptoms could indicate various conditions',
        'Requires professional evaluation',
      ],
      nextSteps: [
        'Consult with healthcare provider',
        'Consider calling 811 (health information line)',
        'Monitor symptoms and document changes',
        'Seek care if symptoms worsen or new symptoms develop',
      ],
      monitoringPlan: [
        'Document all symptoms daily',
        'Note any pattern or triggers',
        'Monitor for new symptoms',
      ],
      escalationTriggers: [
        'New concerning symptoms develop',
        'Symptoms worsen significantly',
        'Fever or other red flags appear',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '18-39', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Fatigue', timestamp: new Date() },
      ],
      intakeSummary: 'Patient presents with vague symptoms of fatigue and general malaise for 1 week. Insufficient information for safe triage. UNCERTAIN - recommend consultation with healthcare provider.',
      disclaimerShown: true,
    },
    status: 'completed',
  },
  {
    user: {
      anonymousId: uuidv4(),
      ageRange: '65+',
    },
    intake: {
      chiefComplaint: 'Multiple chronic symptoms',
      symptoms: ['Joint pain', 'Fatigue', 'Dizziness'],
      severity: 4,
      onset: 'Several weeks',
      pattern: 'Chronic, variable',
      redFlags: {
        any: 'unknown',
        details: [],
      },
      history: {
        conditions: ['Diabetes', 'Hypertension', 'Arthritis'],
        meds: ['Metformin', 'Lisinopril', 'Ibuprofen'],
        allergies: [],
      },
      vitals: {},
    },
    assistant: {
      triageLevel: 'UNCERTAIN',
      confidence: 0.55,
      reasons: [
        'Multiple chronic conditions complicate assessment',
        'Symptoms could be related to existing conditions or new issue',
        'Requires clinical evaluation to determine cause',
        'Complex medical history needs professional review',
      ],
      nextSteps: [
        'Consult with primary care provider',
        'Review medications with healthcare provider',
        'Monitor symptoms and document changes',
        'Consider medication review',
      ],
      monitoringPlan: [
        'Track all symptoms daily',
        'Monitor blood pressure and blood sugar if applicable',
        'Note medication timing and symptoms',
      ],
      escalationTriggers: [
        'Severe dizziness or falls',
        'Chest pain or difficulty breathing',
        'Significant worsening of any symptom',
        'New concerning symptoms',
      ],
      questionsAsked: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes', timestamp: new Date() },
        { id: 'ageRange', question: 'Age range?', answer: '65+', timestamp: new Date() },
        { id: 'chiefComplaint', question: 'Main concern?', answer: 'Multiple symptoms', timestamp: new Date() },
      ],
      intakeSummary: 'Elderly patient with multiple chronic symptoms (joint pain, fatigue, dizziness) over several weeks. Complex medical history with diabetes, hypertension, and arthritis. Multiple medications. UNCERTAIN - requires professional evaluation to determine if symptoms are related to existing conditions or new issue.',
      disclaimerShown: true,
    },
    status: 'completed',
  },
];

async function seedDatabase() {
  try {
    console.log('🔌 Connecting to MongoDB...');
    await mongoose.connect(MONGODB_URI);
    console.log('✅ Connected to MongoDB\n');

    // Clear existing cases (optional - comment out if you want to keep existing data)
    const existingCount = await Case.countDocuments();
    if (existingCount > 0) {
      console.log(`⚠️  Found ${existingCount} existing cases.`);
      console.log('   (Not deleting - adding new test cases)\n');
    }

    console.log(`📝 Seeding ${testCases.length} test cases...\n`);

    // Insert test cases
    const insertedCases = await Case.insertMany(testCases);

    console.log('✅ Successfully seeded database!\n');
    console.log('📊 Summary:');
    
    const byTriage = insertedCases.reduce((acc, c) => {
      const level = c.assistant.triageLevel || 'UNKNOWN';
      acc[level] = (acc[level] || 0) + 1;
      return acc;
    }, {});

    Object.entries(byTriage).forEach(([level, count]) => {
      console.log(`   ${level}: ${count} case(s)`);
    });

    console.log(`\n   Total: ${insertedCases.length} cases`);
    console.log('\n🎉 Database seeding complete!');
    console.log('   You can now test the dashboard at http://localhost:3000/dashboard\n');

    process.exit(0);
  } catch (error) {
    console.error('❌ Error seeding database:', error);
    process.exit(1);
  }
}

seedDatabase();

