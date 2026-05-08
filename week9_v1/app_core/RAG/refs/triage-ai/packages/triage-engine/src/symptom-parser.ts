import { z } from 'zod';
import { Symptom, SymptomSchema } from './types.js';

// LLM client interface - supports multiple backends
interface LLMClient {
  messages: {
    create: (params: any) => Promise<any>;
  };
}

const ParsedSymptomsSchema = z.object({
  symptoms: z.array(SymptomSchema),
  additionalContext: z.string().optional(),
});

const SYMPTOM_PARSER_PROMPT = `You are a medical symptom parser. Extract structured symptoms from patient descriptions.

For each symptom, extract:
- description: The main symptom in medical terminology
- location: Body part/area affected (if mentioned)
- duration: How long they've had it (if mentioned)
- severity: 1-10 scale based on their description (if determinable)
- onset: "sudden" or "gradual" (if mentioned)
- associated: Related symptoms mentioned together

Be precise and clinical. Do not add symptoms not mentioned.
Do not diagnose - only parse what the patient says.

Respond with JSON only.`;

export class SymptomParser {
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
              max_tokens: params.max_tokens || 1024,
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

  async parse(rawInput: string): Promise<{ symptoms: Symptom[]; additionalContext?: string }> {
    const response = await this.client.messages.create({
      system: SYMPTOM_PARSER_PROMPT,
      max_tokens: 1024,
      messages: [
        {
          role: 'user',
          content: `Parse the following patient input into structured symptoms:\n\n"${rawInput}"`,
        },
      ],
    });

    const content = response.content[0];
    if (content.type !== 'text') {
      throw new Error('Unexpected response type');
    }

    // Extract JSON from response (handle markdown code blocks)
    let jsonStr = content.text;
    const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      jsonStr = jsonMatch[1];
    }

    const parsed = JSON.parse(jsonStr);
    return ParsedSymptomsSchema.parse(parsed);
  }
}
