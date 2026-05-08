/**
 * Unified LLM Client
 * Automatically switches between Ollama (local) and Gemini (cloud) based on environment
 *
 * For local development: uses Ollama (free, runs on your machine)
 * For production: uses Gemini (covered by Google Cloud credits)
 */

import { OllamaClient } from './ollama-client.js';
import { GeminiClient } from './gemini-client.js';

export interface LLMMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface LLMOptions {
  temperature?: number;
  maxTokens?: number;
}

type LLMProvider = 'ollama' | 'gemini' | 'groq';

class UnifiedLLMClient {
  private provider: LLMProvider;
  private ollamaClient: OllamaClient;
  private geminiClient: GeminiClient;

  constructor() {
    // Determine provider based on environment
    if (process.env.GEMINI_API_KEY) {
      this.provider = 'gemini';
      console.log('[LLM] Using Gemini (Google Cloud)');
    } else if (process.env.GROQ_API_KEY) {
      this.provider = 'groq';
      console.log('[LLM] Using Groq');
    } else {
      this.provider = 'ollama';
      console.log('[LLM] Using Ollama (local)');
    }

    this.ollamaClient = new OllamaClient();
    this.geminiClient = new GeminiClient();
  }

  async chat(messages: LLMMessage[], options: LLMOptions = {}): Promise<string> {
    switch (this.provider) {
      case 'gemini':
        return this.geminiClient.chat(messages, options);

      case 'groq':
        return this.chatWithGroq(messages, options);

      case 'ollama':
      default:
        return this.ollamaClient.chat(messages, options);
    }
  }

  private async chatWithGroq(messages: LLMMessage[], options: LLMOptions): Promise<string> {
    const apiKey = process.env.GROQ_API_KEY;
    const model = process.env.GROQ_MODEL || 'llama-3.1-70b-versatile';

    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? 2048,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Groq API error: ${response.status} - ${error}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  }

  async isAvailable(): Promise<boolean> {
    switch (this.provider) {
      case 'gemini':
        return this.geminiClient.isAvailable();
      case 'groq':
        return !!process.env.GROQ_API_KEY;
      case 'ollama':
      default:
        return this.ollamaClient.isAvailable();
    }
  }

  getProvider(): string {
    return this.provider;
  }
}

export const llmClient = new UnifiedLLMClient();
