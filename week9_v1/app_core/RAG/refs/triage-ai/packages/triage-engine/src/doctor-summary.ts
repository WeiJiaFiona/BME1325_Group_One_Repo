import { z } from 'zod';
import { PatientIntake, TriageResult, DoctorSummary, DoctorSummarySchema } from './types.js';

// LLM client interface - supports multiple backends
interface LLMClient {
  messages: {
    create: (params: any) => Promise<any>;
  };
}

const DOCTOR_SUMMARY_PROMPT = `You are a medical AI assistant preparing pre-consultation briefings for doctors.

Your role is to summarize patient triage data into a concise, actionable briefing that helps the doctor:
1. Quickly understand the patient's presentation
2. Know what red flags to watch for
3. Have context-appropriate questions ready
4. Consider relevant differential diagnoses

The doctor will use this summary to:
- Prepare for a rapid virtual consultation
- Make informed decisions about digital prescriptions
- Identify cases that need in-person follow-up

Format your response as structured JSON that can be displayed in a doctor dashboard.

Be concise but thorough. Doctors are busy - every word must add value.`;

export class DoctorSummaryGenerator {
  private client: LLMClient;
  private model: string;
  private apiKey: string;

  constructor(apiKey?: string) {
    this.apiKey = apiKey || process.env.GROQ_API_KEY || '';
    this.model = 'llama-3.3-70b-versatile';
    this.client = this.createGroqClient();
  }

  private createGroqClient(): LLMClient {
    const apiKey = this.apiKey;
    const model = this.model;

    return {
      messages: {
        create: async (params: any) => {
          const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${apiKey}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              model: model,
              messages: [
                { role: 'system', content: params.system },
                ...params.messages,
              ],
              max_tokens: params.max_tokens || 2048,
              temperature: 0.7,
            }),
          });

          if (!response.ok) {
            throw new Error(`Groq API error: ${response.status}`);
          }

          const data = await response.json();
          return {
            content: [{ type: 'text', text: data.choices[0].message.content }],
          };
        },
      },
    };
  }

  async generate(intake: PatientIntake, triageResult: TriageResult): Promise<DoctorSummary> {
    const briefingRequest = this.formatBriefingRequest(intake, triageResult);

    const response = await this.client.messages.create({
      system: DOCTOR_SUMMARY_PROMPT,
      max_tokens: 2048,
      messages: [
        {
          role: 'user',
          content: briefingRequest,
        },
      ],
    });

    const content = response.content[0];
    if (content.type !== 'text') {
      throw new Error('Unexpected response type');
    }

    // Extract JSON from response
    let jsonStr = content.text;
    const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1];
    }

    const parsed = JSON.parse(jsonStr);
    return DoctorSummarySchema.parse(parsed);
  }

  private formatBriefingRequest(intake: PatientIntake, result: TriageResult): string {
    return `Generate a doctor pre-consultation briefing for the following case:

PATIENT STATEMENT:
"${intake.rawInput}"

TRIAGE ASSESSMENT:
- Severity: ${result.severity}/5
- Urgency: ${result.urgency}
- Red Flags: ${result.redFlags.detected ? result.redFlags.flags.map(f => f.condition).join(', ') : 'None detected'}
- Specialty Match: ${result.specialtyMatch.join(', ')}
- Triage Reasoning: ${result.reasoning}

SYMPTOMS IDENTIFIED:
${intake.symptoms.map((s, i) => `${i + 1}. ${s.description}${s.duration ? ` (${s.duration})` : ''}${s.severity ? ` - Severity ${s.severity}/10` : ''}`).join('\n')}

${intake.medicalHistory?.length ? `MEDICAL HISTORY:\n${intake.medicalHistory.join(', ')}` : ''}

${intake.currentMedications?.length ? `CURRENT MEDICATIONS:\n${intake.currentMedications.join(', ')}` : ''}

${intake.allergies?.length ? `ALLERGIES:\n${intake.allergies.join(', ')}` : ''}

Generate a structured briefing the doctor can review in under 30 seconds before the virtual consultation.
Include suggested questions specific to this presentation.
Include 2-4 differential diagnoses to consider.`;
  }
}
