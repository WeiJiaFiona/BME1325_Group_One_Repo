const API_BASE = import.meta.env.VITE_API_URL || '/api';

export interface Message {
  role: 'assistant' | 'user';
  content: string;
  timestamp: string;
}

export interface ConversationResponse {
  conversationId: string;
  message: string;
  stage: 'greeting' | 'collecting' | 'clarifying' | 'triaging' | 'complete';
  isComplete: boolean;
  triageResult?: TriageSession;
}

export interface TriageSession {
  id: string;
  timestamp: string;
  result: TriageResult;
  doctorSummary: DoctorSummary;
}

export interface TriageResult {
  severity: number;
  urgency: 'EMERGENCY' | 'URGENT' | 'SEMI_URGENT' | 'STANDARD' | 'NON_URGENT';
  confidence: number;
  redFlags: {
    detected: boolean;
    flags: Array<{
      condition: string;
      evidence: string;
      action: string;
    }>;
  };
  specialtyMatch: string[];
  reasoning: string;
  recommendations: string[];
}

export interface DoctorSummary {
  headline: string;
  keySymptoms: string[];
  severity: number;
  urgency: string;
  redFlags: string[];
  relevantHistory: string[];
  suggestedQuestions: string[];
  differentialDiagnosis: string[];
  triageReasoning: string;
}

export async function startConversation(): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE}/conversation/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error('Failed to start conversation');
  }

  return response.json();
}

export async function sendMessage(
  conversationId: string,
  message: string
): Promise<ConversationResponse> {
  const response = await fetch(`${API_BASE}/conversation/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversationId, message }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || 'Failed to send message');
  }

  return response.json();
}
