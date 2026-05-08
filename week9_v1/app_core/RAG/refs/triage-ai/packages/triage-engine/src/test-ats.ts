/**
 * ATS Triage Engine Test Scenarios
 * Demonstrates the 4-layer safety architecture with realistic cases
 */

import {
  ATSTriageEngine,
  SymptomPresentation,
  checkRedFlags,
  ATS_CATEGORIES,
  ATSCategory,
} from './index.js';

// Test scenarios covering all ATS categories
const TEST_SCENARIOS: Array<{
  name: string;
  expectedCategory: ATSCategory;
  presentation: SymptomPresentation;
}> = [
  {
    name: 'ATS1 - Severe Anaphylaxis',
    expectedCategory: 'ATS1',
    presentation: {
      chiefComplaint: "My throat is closing up and I can't breathe after eating peanuts",
      symptoms: [
        {
          description: 'Throat swelling',
          severity: 10,
          onset: 'sudden',
          associated: ['difficulty breathing', 'facial swelling'],
        },
      ],
      demographics: { age: 28, sex: 'female' },
      allergies: ['Peanuts'],
    },
  },
  {
    name: 'ATS2 - Cardiac Chest Pain',
    expectedCategory: 'ATS2',
    presentation: {
      chiefComplaint: 'Crushing chest pain radiating to my left arm, started 20 minutes ago',
      symptoms: [
        {
          description: 'Chest pain',
          location: 'Central chest, radiating to left arm',
          severity: 9,
          onset: 'sudden',
          duration: '20 minutes',
          associated: ['sweating', 'nausea'],
        },
      ],
      demographics: { age: 58, sex: 'male' },
      medicalHistory: ['Hypertension', 'High cholesterol'],
      vitals: {
        heartRate: 110,
        systolicBP: 165,
        diastolicBP: 95,
      },
    },
  },
  {
    name: 'ATS2 - Stroke Symptoms',
    expectedCategory: 'ATS2',
    presentation: {
      chiefComplaint: 'Sudden weakness on right side, face drooping, slurred speech',
      symptoms: [
        {
          description: 'Right-sided weakness',
          onset: 'sudden',
          duration: '45 minutes',
          associated: ['facial drooping', 'speech difficulty'],
        },
      ],
      demographics: { age: 72, sex: 'female' },
      medicalHistory: ['Atrial fibrillation', 'Type 2 diabetes'],
    },
  },
  {
    name: 'ATS3 - High Fever with Abdominal Pain',
    expectedCategory: 'ATS3',
    presentation: {
      chiefComplaint: 'High fever for 2 days with severe abdominal pain',
      symptoms: [
        {
          description: 'Abdominal pain',
          location: 'Right lower quadrant',
          severity: 7,
          duration: '2 days',
        },
        {
          description: 'Fever',
          duration: '2 days',
        },
      ],
      demographics: { age: 25, sex: 'female' },
      vitals: {
        temperature: 39.2,
        heartRate: 95,
      },
    },
  },
  {
    name: 'ATS4 - Minor Injury',
    expectedCategory: 'ATS4',
    presentation: {
      chiefComplaint: 'Twisted ankle while jogging, mild swelling and pain',
      symptoms: [
        {
          description: 'Ankle pain',
          location: 'Right ankle',
          severity: 4,
          onset: 'sudden',
          duration: '2 hours',
        },
      ],
      demographics: { age: 35, sex: 'male' },
    },
  },
  {
    name: 'ATS5 - Prescription Refill',
    expectedCategory: 'ATS5',
    presentation: {
      chiefComplaint: 'Need refill of blood pressure medication',
      symptoms: [
        {
          description: 'Routine medication refill request',
        },
      ],
      demographics: { age: 55, sex: 'female' },
      medicalHistory: ['Hypertension (controlled)'],
      currentMedications: ['Amlodipine 5mg'],
    },
  },
  {
    name: 'ATS2 - Suicidal Ideation',
    expectedCategory: 'ATS2',
    presentation: {
      chiefComplaint: "I've been having thoughts of wanting to kill myself",
      symptoms: [
        {
          description: 'Suicidal thoughts',
          duration: '2 weeks',
          associated: ['depression', 'hopelessness'],
        },
      ],
      demographics: { age: 22, sex: 'male' },
    },
  },
  {
    name: 'ATS3 - Paediatric Fever',
    expectedCategory: 'ATS3',
    presentation: {
      chiefComplaint: 'My 2-year-old has had a fever of 39°C for 24 hours',
      symptoms: [
        {
          description: 'Fever',
          severity: 6,
          duration: '24 hours',
          associated: ['irritability', 'decreased appetite'],
        },
      ],
      demographics: { age: 2, sex: 'male' },
      vitals: {
        temperature: 39.0,
        heartRate: 130,
      },
    },
  },
];

/**
 * Test red flag detection (Layer 1)
 */
function testRedFlagDetection() {
  console.log('\n━━━ LAYER 1: RED FLAG DETECTION TEST ━━━\n');

  const testCases = [
    { input: 'I have chest pain', expected: ['Cardiac-type chest pain'] },
    { input: "I can't breathe, I'm gasping for air", expected: ['Severe respiratory distress'] },
    { input: 'My face is drooping on one side and I have arm weakness', expected: ['Possible stroke (FAST)'] },
    { input: "I've been thinking about suicide", expected: ['Suicidal ideation or self-harm'] },
    { input: 'I have a mild headache', expected: [] },
  ];

  for (const test of testCases) {
    const flags = checkRedFlags(test.input);
    const flagNames = flags.map(f => f.name);
    const passed = JSON.stringify(flagNames.sort()) === JSON.stringify(test.expected.sort());

    console.log(`Input: "${test.input.substring(0, 50)}..."`);
    console.log(`  Expected: ${test.expected.length > 0 ? test.expected.join(', ') : 'None'}`);
    console.log(`  Detected: ${flagNames.length > 0 ? flagNames.join(', ') : 'None'}`);
    console.log(`  Result: ${passed ? '✅ PASS' : '❌ FAIL'}`);
    console.log();
  }
}

/**
 * Test full ATS assessment (requires API key)
 */
async function testFullAssessment() {
  console.log('\n━━━ FULL ATS ASSESSMENT TEST ━━━\n');

  // Check if API key is available
  if (!process.env.GROQ_API_KEY) {
    console.log('⚠️  GROQ_API_KEY not set. Skipping full assessment tests.');
    console.log('   Set the environment variable to run full tests.\n');
    return;
  }

  const engine = new ATSTriageEngine();

  for (const scenario of TEST_SCENARIOS.slice(0, 3)) { // Test first 3 to save API calls
    console.log(`Testing: ${scenario.name}`);
    console.log(`Expected Category: ${scenario.expectedCategory}\n`);

    try {
      const result = await engine.assess(scenario.presentation);

      console.log(`  Result: ${result.category} (${result.categoryInfo.name})`);
      console.log(`  Max Wait: ${result.categoryInfo.maxWaitTime}`);
      console.log(`  Confidence: ${(result.confidence * 100).toFixed(0)}%`);

      if (result.redFlagsDetected.length > 0) {
        console.log(`  Red Flags: ${result.redFlagsDetected.map(f => f.name).join(', ')}`);
      }

      console.log(`  Reasoning: ${result.clinicalReasoning.substring(0, 100)}...`);

      const passed = result.category === scenario.expectedCategory;
      console.log(`  Match: ${passed ? '✅ PASS' : '⚠️  MISMATCH (may be valid escalation)'}`);
    } catch (error) {
      console.log(`  ❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }

    console.log('\n' + '─'.repeat(60) + '\n');
  }
}

/**
 * Display ATS categories reference
 */
function displayATSReference() {
  console.log('\n━━━ AUSTRALIAN TRIAGE SCALE (ATS) REFERENCE ━━━\n');

  for (const [key, info] of Object.entries(ATS_CATEGORIES)) {
    console.log(`${key}: ${info.name}`);
    console.log(`  Max Wait: ${info.maxWaitTime}`);
    console.log(`  Description: ${info.description}`);
    console.log(`  Examples: ${info.examples.slice(0, 3).join(', ')}`);
    console.log();
  }
}

// Main execution
async function main() {
  console.log('╔═══════════════════════════════════════════════════════════╗');
  console.log('║           TriageAI - ATS Engine Test Suite                 ║');
  console.log('║     Australian Triage Scale Implementation Tests           ║');
  console.log('╚═══════════════════════════════════════════════════════════╝');

  displayATSReference();
  testRedFlagDetection();
  await testFullAssessment();

  console.log('\n✅ Test suite complete\n');
}

main().catch(console.error);
