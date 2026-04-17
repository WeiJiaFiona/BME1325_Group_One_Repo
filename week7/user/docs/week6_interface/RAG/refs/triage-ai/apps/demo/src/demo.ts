/**
 * TriageAI Demo - Showcasing AI-Powered Patient Triage
 *
 * This demo shows the complete workflow:
 * 1. Patient describes symptoms in natural language
 * 2. AI parses and structures the symptoms
 * 3. Triage engine assesses severity and urgency
 * 4. Doctor receives a pre-consultation summary
 *
 * Built for virtual consultation + digital prescription workflows.
 */

import { TriageService } from '../../../packages/triage-engine/src/index.js';
import chalk from 'chalk';
import ora from 'ora';

const DEMO_CASES = [
  {
    name: 'Routine Care',
    input: "I've had a mild headache for the past two days. It's not too bad, maybe a 3 out of 10. Paracetamol helps a bit. No fever or anything else.",
    demographics: { age: 32, sex: 'female' as const },
  },
  {
    name: 'Urgent - High Fever',
    input: "My 4 year old son has had a fever of 39.5°C for the past 6 hours. He's not eating and seems very tired. He also has a runny nose.",
    demographics: { age: 4, sex: 'male' as const },
    medicalHistory: ['Asthma'],
  },
  {
    name: 'Red Flag - Chest Pain',
    input: "I'm having chest pain that started about 30 minutes ago. It's tight and squeezing, and I feel it going down my left arm. I'm sweating too. I'm 58 and I have high blood pressure.",
    demographics: { age: 58, sex: 'male' as const },
    medicalHistory: ['Hypertension', 'High cholesterol'],
    currentMedications: ['Amlodipine 5mg', 'Atorvastatin 20mg'],
  },
];

async function runDemo() {
  console.log(chalk.bold.cyan('\n╔════════════════════════════════════════════════════════════╗'));
  console.log(chalk.bold.cyan('║           TriageAI - AI-Powered Patient Triage              ║'));
  console.log(chalk.bold.cyan('║     Virtual Consultation • Digital Prescription Ready       ║'));
  console.log(chalk.bold.cyan('╚════════════════════════════════════════════════════════════╝\n'));

  const service = new TriageService();

  for (const testCase of DEMO_CASES) {
    console.log(chalk.bold.yellow(`\n━━━ Case: ${testCase.name} ━━━\n`));

    console.log(chalk.dim('Patient Input:'));
    console.log(chalk.white(`"${testCase.input}"\n`));

    if (testCase.demographics) {
      console.log(chalk.dim(`Demographics: ${testCase.demographics.age}yo ${testCase.demographics.sex}`));
    }
    if (testCase.medicalHistory?.length) {
      console.log(chalk.dim(`History: ${testCase.medicalHistory.join(', ')}`));
    }
    if (testCase.currentMedications?.length) {
      console.log(chalk.dim(`Medications: ${testCase.currentMedications.join(', ')}`));
    }

    const spinner = ora('Processing triage...').start();

    try {
      const session = await service.process(testCase.input, {
        demographics: testCase.demographics,
        medicalHistory: testCase.medicalHistory,
        currentMedications: testCase.currentMedications,
      });

      spinner.succeed('Triage complete');

      // Display triage result
      console.log(chalk.bold.green('\n📋 Triage Assessment:'));
      const severityColor = session.result.severity >= 4 ? chalk.red : session.result.severity >= 3 ? chalk.yellow : chalk.green;
      console.log(`   Severity: ${severityColor(`${session.result.severity}/5`)}`);
      console.log(`   Urgency: ${getUrgencyColor(session.result.urgency)(session.result.urgency)}`);
      console.log(`   Confidence: ${(session.result.confidence * 100).toFixed(0)}%`);

      if (session.result.redFlags.detected) {
        console.log(chalk.red.bold('\n   ⚠️  RED FLAGS DETECTED:'));
        session.result.redFlags.flags.forEach(flag => {
          console.log(chalk.red(`      • ${flag.condition}: ${flag.action}`));
        });
      }

      console.log(chalk.dim(`\n   Reasoning: ${session.result.reasoning.substring(0, 200)}...`));

      if (session.result.recommendations.length > 0) {
        console.log(chalk.cyan('\n   Recommendations:'));
        session.result.recommendations.forEach(rec => {
          console.log(chalk.cyan(`      • ${rec}`));
        });
      }

      // Display doctor summary
      console.log(chalk.bold.blue('\n👨‍⚕️ Doctor Pre-Consultation Summary:'));
      console.log(chalk.bold(`   ${session.doctorSummary.headline}`));
      console.log(chalk.dim(`\n   Key Symptoms:`));
      session.doctorSummary.keySymptoms.forEach(s => console.log(chalk.dim(`      • ${s}`)));

      if (session.doctorSummary.suggestedQuestions.length > 0) {
        console.log(chalk.dim(`\n   Suggested Questions:`));
        session.doctorSummary.suggestedQuestions.slice(0, 3).forEach(q => console.log(chalk.dim(`      • ${q}`)));
      }

      if (session.doctorSummary.differentialDiagnosis.length > 0) {
        console.log(chalk.dim(`\n   Differential Diagnosis:`));
        session.doctorSummary.differentialDiagnosis.slice(0, 3).forEach(d => console.log(chalk.dim(`      • ${d}`)));
      }

      console.log(chalk.dim(`\n   Session ID: ${session.id}`));
      console.log(chalk.dim(`   Audit events logged: ${session.auditLog.length}`));

    } catch (error) {
      spinner.fail('Triage failed');
      console.error(chalk.red(error instanceof Error ? error.message : 'Unknown error'));
    }

    console.log(chalk.dim('\n' + '─'.repeat(60)));
  }

  console.log(chalk.bold.cyan('\n✅ Demo complete - Ready for virtual consultations\n'));
}

function getUrgencyColor(urgency: string) {
  switch (urgency) {
    case 'EMERGENCY': return chalk.red.bold;
    case 'URGENT': return chalk.red;
    case 'SEMI_URGENT': return chalk.yellow;
    case 'STANDARD': return chalk.green;
    case 'NON_URGENT': return chalk.dim;
    default: return chalk.white;
  }
}

runDemo().catch(console.error);
