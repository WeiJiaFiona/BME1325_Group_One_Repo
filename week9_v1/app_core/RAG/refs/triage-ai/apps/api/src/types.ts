import { z } from 'zod';

// Conversation stages
export type ConversationStage =
  | 'greeting'
  | 'collecting'
  | 'clarifying'
  | 'triaging'
  | 'complete';

// Message in conversation
export interface Message {
  role: 'assistant' | 'user';
  content: string;
  timestamp: string;
}

// Collected patient data during conversation
export interface CollectedData {
  symptoms: string[];
  duration?: string;
  severity?: number;
  location?: string;
  age?: number;
  sex?: 'male' | 'female' | 'other';
  medicalHistory?: string[];
  medications?: string[];
  allergies?: string[];
  additionalContext?: string;
}

// Full conversation state
export interface Conversation {
  id: string;
  stage: ConversationStage;
  messages: Message[];
  collectedData: CollectedData;
  triageResult?: unknown; // TriageSession from engine
  createdAt: string;
  updatedAt: string;
}

// API Request schemas
export const StartConversationRequestSchema = z.object({
  patientId: z.string().optional(),
});

export const SendMessageRequestSchema = z.object({
  conversationId: z.string().uuid(),
  message: z.string().min(1).max(5000),
});

// API Response types
export interface ConversationResponse {
  conversationId: string;
  message: string;
  stage: ConversationStage;
  isComplete: boolean;
  triageResult?: unknown;
}
