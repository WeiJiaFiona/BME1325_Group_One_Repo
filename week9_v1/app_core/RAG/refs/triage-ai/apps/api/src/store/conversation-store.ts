import { Conversation, CollectedData, Message, ConversationStage } from '../types.js';
import { supabase, isSupabaseConfigured } from '../lib/supabase.js';
import { v4 as uuidv4 } from 'uuid';

/**
 * Hybrid conversation store
 * Uses Supabase when configured, falls back to in-memory
 */
class ConversationStore {
  private conversations: Map<string, Conversation> = new Map();

  async create(patientId?: string): Promise<Conversation> {
    const id = uuidv4();
    const now = new Date().toISOString();

    const conversation: Conversation = {
      id,
      stage: 'greeting',
      messages: [],
      collectedData: {
        symptoms: [],
      },
      createdAt: now,
      updatedAt: now,
    };

    // Persist to Supabase if configured
    if (isSupabaseConfigured && supabase) {
      try {
        await supabase.from('conversations').insert({
          id,
          stage: 'greeting',
          collected_data: { symptoms: [] },
          created_at: now,
          updated_at: now,
        });
        console.log(`[Supabase] Created conversation ${id}`);
      } catch (error) {
        console.error('[Supabase] Failed to create conversation:', error);
      }
    }

    this.conversations.set(id, conversation);
    return conversation;
  }

  async get(id: string): Promise<Conversation | undefined> {
    // Try in-memory first
    let conversation = this.conversations.get(id);

    // If not in memory but Supabase configured, try to fetch
    if (!conversation && isSupabaseConfigured && supabase) {
      try {
        const { data: convData } = await supabase
          .from('conversations')
          .select('*')
          .eq('id', id)
          .single();

        if (convData) {
          const { data: messagesData } = await supabase
            .from('messages')
            .select('*')
            .eq('conversation_id', id)
            .order('created_at', { ascending: true });

          conversation = {
            id: convData.id,
            stage: convData.stage,
            messages: (messagesData || []).map((m: { role: string; content: string; created_at: string }) => ({
              role: m.role as 'assistant' | 'user',
              content: m.content,
              timestamp: m.created_at,
            })),
            collectedData: convData.collected_data || { symptoms: [] },
            triageResult: convData.triage_result,
            createdAt: convData.created_at,
            updatedAt: convData.updated_at,
          };

          // Cache in memory
          this.conversations.set(id, conversation);
        }
      } catch (error) {
        console.error('[Supabase] Failed to get conversation:', error);
      }
    }

    return conversation;
  }

  async addMessage(id: string, role: 'assistant' | 'user', content: string): Promise<void> {
    const conversation = this.conversations.get(id);
    if (!conversation) throw new Error(`Conversation ${id} not found`);

    const timestamp = new Date().toISOString();

    conversation.messages.push({
      role,
      content,
      timestamp,
    });
    conversation.updatedAt = timestamp;

    // Persist to Supabase
    if (isSupabaseConfigured && supabase) {
      try {
        await supabase.from('messages').insert({
          conversation_id: id,
          role,
          content,
          created_at: timestamp,
        });

        await supabase
          .from('conversations')
          .update({ updated_at: timestamp })
          .eq('id', id);
      } catch (error) {
        console.error('[Supabase] Failed to add message:', error);
      }
    }
  }

  async updateStage(id: string, stage: ConversationStage): Promise<void> {
    const conversation = this.conversations.get(id);
    if (!conversation) throw new Error(`Conversation ${id} not found`);

    conversation.stage = stage;
    conversation.updatedAt = new Date().toISOString();

    // Persist to Supabase
    if (isSupabaseConfigured && supabase) {
      try {
        await supabase
          .from('conversations')
          .update({ stage, updated_at: conversation.updatedAt })
          .eq('id', id);
      } catch (error) {
        console.error('[Supabase] Failed to update stage:', error);
      }
    }
  }

  async updateCollectedData(id: string, data: Partial<CollectedData>): Promise<void> {
    const conversation = this.conversations.get(id);
    if (!conversation) throw new Error(`Conversation ${id} not found`);

    conversation.collectedData = {
      ...conversation.collectedData,
      ...data,
    };
    conversation.updatedAt = new Date().toISOString();

    // Persist to Supabase
    if (isSupabaseConfigured && supabase) {
      try {
        await supabase
          .from('conversations')
          .update({
            collected_data: conversation.collectedData,
            updated_at: conversation.updatedAt
          })
          .eq('id', id);
      } catch (error) {
        console.error('[Supabase] Failed to update collected data:', error);
      }
    }
  }

  async setTriageResult(id: string, result: unknown): Promise<void> {
    const conversation = this.conversations.get(id);
    if (!conversation) throw new Error(`Conversation ${id} not found`);

    conversation.triageResult = result;
    conversation.stage = 'complete';
    conversation.updatedAt = new Date().toISOString();

    // Persist to Supabase
    if (isSupabaseConfigured && supabase) {
      try {
        await supabase
          .from('conversations')
          .update({
            triage_result: result,
            stage: 'complete',
            updated_at: conversation.updatedAt
          })
          .eq('id', id);
        console.log(`[Supabase] Saved triage result for ${id}`);
      } catch (error) {
        console.error('[Supabase] Failed to set triage result:', error);
      }
    }
  }

  // Cleanup old conversations (call periodically)
  cleanup(maxAgeMs: number = 3600000): void {
    const now = Date.now();
    for (const [id, conv] of this.conversations) {
      if (now - new Date(conv.updatedAt).getTime() > maxAgeMs) {
        this.conversations.delete(id);
      }
    }
  }
}

export const conversationStore = new ConversationStore();
