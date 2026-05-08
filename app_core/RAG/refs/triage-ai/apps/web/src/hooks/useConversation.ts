import { useState, useCallback } from 'react';
import {
  startConversation,
  sendMessage,
  ConversationResponse,
  TriageSession,
  Message,
} from '../lib/api';

interface ConversationState {
  conversationId: string | null;
  messages: Message[];
  stage: ConversationResponse['stage'];
  isLoading: boolean;
  isTyping: boolean;
  error: string | null;
  triageResult: TriageSession | null;
  isComplete: boolean;
}

export function useConversation() {
  const [state, setState] = useState<ConversationState>({
    conversationId: null,
    messages: [],
    stage: 'greeting',
    isLoading: false,
    isTyping: false,
    error: null,
    triageResult: null,
    isComplete: false,
  });

  const start = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await startConversation();

      setState(prev => ({
        ...prev,
        conversationId: response.conversationId,
        messages: [
          {
            role: 'assistant',
            content: response.message,
            timestamp: new Date().toISOString(),
          },
        ],
        stage: response.stage,
        isLoading: false,
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to start conversation',
      }));
    }
  }, []);

  const send = useCallback(async (message: string) => {
    if (!state.conversationId || !message.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: message.trim(),
      timestamp: new Date().toISOString(),
    };

    // Add user message immediately
    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isTyping: true,
      error: null,
    }));

    try {
      const response = await sendMessage(state.conversationId, message.trim());

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
      };

      setState(prev => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
        stage: response.stage,
        isTyping: false,
        isComplete: response.isComplete,
        triageResult: response.triageResult || null,
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        isTyping: false,
        error: error instanceof Error ? error.message : 'Failed to send message',
      }));
    }
  }, [state.conversationId]);

  const reset = useCallback(() => {
    setState({
      conversationId: null,
      messages: [],
      stage: 'greeting',
      isLoading: false,
      isTyping: false,
      error: null,
      triageResult: null,
      isComplete: false,
    });
  }, []);

  return {
    ...state,
    start,
    send,
    reset,
  };
}
