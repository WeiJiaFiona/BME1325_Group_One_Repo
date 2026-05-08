/**
 * Google Gemini API Client for cloud LLM inference
 * Uses Vertex AI / Gemini API - covered by Google Cloud credits
 */

const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-1.5-flash';

interface GeminiMessage {
  role: 'user' | 'model';
  parts: { text: string }[];
}

interface ChatOptions {
  model?: string;
  temperature?: number;
  maxTokens?: number;
}

export class GeminiClient {
  private apiKey: string;
  private model: string;

  constructor(apiKey?: string, model?: string) {
    this.apiKey = apiKey || GEMINI_API_KEY;
    this.model = model || GEMINI_MODEL;
  }

  async chat(
    messages: { role: 'system' | 'user' | 'assistant'; content: string }[],
    options: ChatOptions = {}
  ): Promise<string> {
    const model = options.model || this.model;

    // Convert messages to Gemini format
    // Gemini doesn't have system role, so we prepend it to first user message
    let systemPrompt = '';
    const geminiMessages: GeminiMessage[] = [];

    for (const msg of messages) {
      if (msg.role === 'system') {
        systemPrompt = msg.content + '\n\n';
      } else {
        const role = msg.role === 'assistant' ? 'model' : 'user';
        const content = msg.role === 'user' && systemPrompt
          ? systemPrompt + msg.content
          : msg.content;

        if (msg.role === 'user') {
          systemPrompt = ''; // Clear after using
        }

        geminiMessages.push({
          role,
          parts: [{ text: content }]
        });
      }
    }

    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${this.apiKey}`;

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: geminiMessages,
        generationConfig: {
          temperature: options.temperature ?? 0.7,
          maxOutputTokens: options.maxTokens ?? 2048,
        },
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Gemini API error: ${response.status} - ${error}`);
    }

    const data = await response.json();

    if (!data.candidates?.[0]?.content?.parts?.[0]?.text) {
      throw new Error('No response from Gemini');
    }

    return data.candidates[0].content.parts[0].text;
  }

  async isAvailable(): Promise<boolean> {
    if (!this.apiKey) return false;

    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${this.apiKey}`;
      const response = await fetch(url);
      return response.ok;
    } catch {
      return false;
    }
  }
}

export const geminiClient = new GeminiClient();
