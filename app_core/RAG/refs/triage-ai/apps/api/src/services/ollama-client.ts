/**
 * Ollama API Client for local LLM inference
 * Uses the Ollama REST API for chat completions
 */

const OLLAMA_BASE_URL = process.env.OLLAMA_URL || 'http://127.0.0.1:11434';

interface OllamaMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

interface OllamaResponse {
  model: string;
  created_at: string;
  message: {
    role: 'assistant';
    content: string;
  };
  done: boolean;
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  eval_count?: number;
}

export interface ChatOptions {
  model?: string;
  temperature?: number;
  maxTokens?: number;
}

const DEFAULT_MODEL = process.env.OLLAMA_MODEL || 'llama3.1';

export class OllamaClient {
  private baseUrl: string;
  private defaultModel: string;

  constructor(baseUrl?: string, model?: string) {
    this.baseUrl = baseUrl || OLLAMA_BASE_URL;
    this.defaultModel = model || DEFAULT_MODEL;
  }

  async chat(
    messages: OllamaMessage[],
    options: ChatOptions = {}
  ): Promise<string> {
    const model = options.model || this.defaultModel;

    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        messages,
        stream: false,
        options: {
          temperature: options.temperature ?? 0.7,
          num_predict: options.maxTokens ?? 2048,
        },
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Ollama API error: ${response.status} - ${error}`);
    }

    const data: OllamaResponse = await response.json();
    return data.message.content;
  }

  async isAvailable(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tags`, {
        method: 'GET',
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  async listModels(): Promise<string[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tags`);
      const data = await response.json();
      return data.models?.map((m: { name: string }) => m.name) || [];
    } catch {
      return [];
    }
  }
}

export const ollamaClient = new OllamaClient();
