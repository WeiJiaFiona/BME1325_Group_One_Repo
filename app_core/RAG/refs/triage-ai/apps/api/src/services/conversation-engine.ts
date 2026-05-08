import { conversationStore } from '../store/conversation-store.js';
import { ConversationResponse, Conversation, CollectedData } from '../types.js';
import { llmClient } from './llm-client.js';
import {
  buildClinicalContext,
  retrieveRelevantConditions,
  getMinimumATSFromSymptoms,
  ATS_GUIDELINES,
  ClinicalCondition
} from './medical-knowledge.js';

// Triage result types
interface TriageSession {
  id: string;
  timestamp: string;
  result: {
    severity: number;
    urgency: 'EMERGENCY' | 'URGENT' | 'SEMI_URGENT' | 'STANDARD' | 'NON_URGENT';
    atsCategory: number;
    maxWaitTime: string;
    confidence: number;
    redFlags: {
      detected: boolean;
      flags: Array<{ condition: string; evidence: string; action: string }>;
    };
    specialtyMatch: string[];
    reasoning: string;
    recommendations: string[];
  };
  doctorSummary: {
    headline: string;
    keySymptoms: string[];
    severity: number;
    urgency: string;
    atsCategory: number;
    maxWaitTime: string;
    redFlags: string[];
    relevantHistory: string[];
    suggestedQuestions: string[];
    differentialDiagnosis: string[];
    triageReasoning: string;
  };
}

const CONVERSATION_SYSTEM_PROMPT = `You are TriageAI, a warm and professional medical triage assistant using the Australian Triage Scale (ATS).

YOUR ROLE:
1. Gather clinical information through empathetic conversation
2. Identify red flags requiring immediate escalation
3. Determine ATS category (1-5) and provide clear next steps

AUSTRALIAN TRIAGE SCALE (ATS):
- ATS 1: Immediate - Life threatening
- ATS 2: 10 minutes - Imminent threat to life
- ATS 3: 30 minutes - Potentially life threatening
- ATS 4: 60 minutes - Potentially serious
- ATS 5: 120 minutes - Less urgent

CRITICAL RED FLAGS (ATS 1-2):
- Chest pain (crushing, radiating, sweating)
- Severe breathing difficulty
- Stroke symptoms (face droop, arm weakness, slurred speech)
- Sudden severe headache ("worst ever")
- Throat swelling with allergy
- Suicidal thoughts with plan
- Heavy bleeding
- Confusion or altered consciousness

CONVERSATION STYLE:
- Be warm, empathetic, and reassuring
- ALWAYS acknowledge what the patient said before asking follow-up
- Never repeat questions about information already given
- Use natural language - avoid sounding like a robot
- Keep responses concise but caring

CRITICAL INTERFACE CONSTRAINT:
- You are in a TEXT-ONLY chat interface
- NEVER ask users to nod, shake head, blink, wave, or make any physical gesture
- NEVER assume camera, video, or voice input is available
- If a user says they cannot type, DO NOT ask follow-up questions - escalate immediately
- Always phrase questions so they can be answered with typed text

EXAMPLE GOOD RESPONSES:
- "I'm sorry you're dealing with a headache. How long has it been bothering you?"
- "A 3 out of 10 pain - that's helpful to know. Have you tried anything for relief yet?"
- "Sounds like stress and poor sleep could be the culprit. Let me check a few more things..."

WHAT TO GATHER (OPQRST for pain):
- Onset: When did it start?
- Provocation: What makes it better/worse?
- Quality: What does it feel like?
- Radiation: Does it spread anywhere?
- Severity: 1-10 scale
- Time: How long, getting better/worse?

RESPONSE FORMAT (valid JSON):
{
  "message": "Your warm, helpful response to the patient",
  "clinicalAssessment": {
    "symptoms": ["symptom1", "symptom2"],
    "duration": "if known",
    "severity": 1-10,
    "redFlagsIdentified": [],
    "dataGathered": ["onset", "severity", "etc"]
  },
  "readyToTriage": true/false,
  "suggestedATS": 1-5 or null,
  "reasoning": "brief clinical reasoning"
}

Set readyToTriage=true when:
- Any red flags present (triage immediately)
- OR you have: main symptoms + duration + severity + context (usually 2-3 exchanges)`;

const GREETING_MESSAGE = "Hi, I'm TriageAI, your virtual health assistant. I'm here to help understand your symptoms and guide you to the right care. What's bringing you in today?";

export class ConversationEngine {
  constructor() {
    console.log(`[ConversationEngine] Using LLM provider: ${llmClient.getProvider()}`);
  }

  async startConversation(patientId?: string): Promise<ConversationResponse> {
    const conversation = await conversationStore.create(patientId);

    // Add greeting message
    await conversationStore.addMessage(conversation.id, 'assistant', GREETING_MESSAGE);
    await conversationStore.updateStage(conversation.id, 'collecting');

    return {
      conversationId: conversation.id,
      message: GREETING_MESSAGE,
      stage: 'collecting',
      isComplete: false,
    };
  }

  async processMessage(conversationId: string, userMessage: string): Promise<ConversationResponse> {
    const conversation = await conversationStore.get(conversationId);
    if (!conversation) {
      throw new Error('Conversation not found');
    }

    if (conversation.stage === 'complete') {
      return {
        conversationId,
        message: "This assessment has already been completed. Please start a new conversation for a new assessment.",
        stage: 'complete',
        isComplete: true,
        triageResult: conversation.triageResult,
      };
    }

    // Add user message
    await conversationStore.addMessage(conversationId, 'user', userMessage);

    // LAYER 1: Deterministic red flag keyword detection (<1ms)
    const redFlags = this.checkRedFlagKeywords(userMessage);
    if (redFlags.length > 0) {
      return this.handleEmergencyTriage(conversationId, userMessage, redFlags);
    }

    // LAYER 2: Retrieve relevant clinical context (RAG)
    const allUserMessages = conversation.messages
      .filter(m => m.role === 'user')
      .map(m => m.content)
      .join(' ') + ' ' + userMessage;

    const clinicalContext = buildClinicalContext(allUserMessages);
    const relevantConditions = retrieveRelevantConditions(allUserMessages);
    const minATS = getMinimumATSFromSymptoms(allUserMessages);

    // Check message count for forced progression
    const userMessageCount = conversation.messages.filter(m => m.role === 'user').length + 1;
    const forceTriageAfter = 4;

    // Build conversation history with clinical context
    const messages = this.buildMessageHistory(conversation, userMessage, clinicalContext);

    // LAYER 3: LLM reasoning with clinical context
    const responseText = await llmClient.chat([
      { role: 'system', content: CONVERSATION_SYSTEM_PROMPT },
      ...messages,
    ]);

    // Parse AI response
    let parsed = this.parseResponse(responseText);

    // Update collected data
    if (parsed.clinicalAssessment) {
      const currentData = conversation.collectedData;
      await conversationStore.updateCollectedData(conversationId, {
        symptoms: [...new Set([...currentData.symptoms, ...(parsed.clinicalAssessment.symptoms || [])])],
        duration: parsed.clinicalAssessment.duration || currentData.duration,
        severity: parsed.clinicalAssessment.severity || currentData.severity,
        additionalContext: currentData.additionalContext,
      });
    }

    // Add assistant message
    await conversationStore.addMessage(conversationId, 'assistant', parsed.message);

    // LAYER 4: Safety envelope - Force triage after sufficient exchanges
    const shouldTriage = parsed.readyToTriage ||
      userMessageCount >= forceTriageAfter ||
      ((parsed.clinicalAssessment?.redFlagsIdentified?.length ?? 0) > 0);

    if (shouldTriage) {
      await conversationStore.updateStage(conversationId, 'triaging');

      // Perform triage with clinical context
      const triageResult = await this.performTriage(conversationId, relevantConditions, minATS);

      return {
        conversationId,
        message: parsed.message,
        stage: 'complete',
        isComplete: true,
        triageResult,
      };
    }

    // Continue conversation
    await conversationStore.updateStage(conversationId, userMessageCount >= 2 ? 'clarifying' : 'collecting');

    return {
      conversationId,
      message: parsed.message,
      stage: conversation.stage,
      isComplete: false,
    };
  }

  private async handleEmergencyTriage(
    conversationId: string,
    userMessage: string,
    redFlags: string[]
  ): Promise<ConversationResponse> {
    await conversationStore.updateStage(conversationId, 'triaging');

    // Map red flags to ATS categories and actions
    const flagActions: Record<string, { ats: number; action: string }> = {
      // ATS 1 - Resuscitation
      'Cardiac arrest': { ats: 1, action: 'Begin CPR, call 000, defibrillation if available' },
      'Respiratory arrest': { ats: 1, action: 'Secure airway, ventilation, call 000' },
      'Possible anaphylaxis': { ats: 1, action: 'Immediate adrenaline, airway management' },
      'Airway obstruction': { ats: 1, action: 'Immediate airway clearance, back blows/chest thrusts' },

      // ATS 2 - Emergency
      'Chest pain': { ats: 2, action: 'Immediate ECG and cardiac workup' },
      'Difficulty breathing': { ats: 2, action: 'Immediate respiratory assessment, oxygen' },
      'Sudden severe headache': { ats: 2, action: 'Urgent CT scan to rule out SAH' },
      'Loss of consciousness': { ats: 2, action: 'Neurological assessment, monitor airway' },
      'Possible stroke symptoms': { ats: 2, action: 'Immediate stroke protocol (CT, thrombolysis assessment)' },
      'Seizure': { ats: 2, action: 'Protect airway, recovery position, time seizure' },
      'Suicidal ideation': { ats: 2, action: 'Immediate mental health assessment, ensure safety' },
      'Severe bleeding': { ats: 2, action: 'Immediate haemostasis and volume resuscitation' },
      'Altered mental status': { ats: 2, action: 'Immediate assessment for reversible causes' },
      'Major trauma': { ats: 2, action: 'Trauma team activation, ABCDE assessment' },
      'Severe burns': { ats: 2, action: 'Cool burns, assess airway for inhalation injury' },
      'Electrocution': { ats: 2, action: 'Cardiac monitoring, assess for arrhythmias' },
      'Near-drowning': { ats: 2, action: 'Protect airway, assess for aspiration' },
      'Drug overdose': { ats: 2, action: 'Assess airway, naloxone if opioid suspected' },
      'Poisoning': { ats: 2, action: 'Contact Poisons Information Centre 13 11 26' },
      'Collapse': { ats: 2, action: 'Full assessment, ECG, bloods' },

      // Communication impairment - if patient can't type, don't ask more questions
      'Communication impairment': { ats: 2, action: 'Patient unable to communicate - call 000 immediately, do not ask follow-up questions' },
      'Paediatric emergency': { ats: 1, action: 'Immediate paediatric resuscitation - call 000, begin CPR if not breathing' },
      'Violence/Safety concern': { ats: 2, action: 'Contact police (000) and ensure safety first, then address medical concerns' },

      // Additional ATS 2 conditions
      'GI bleeding': { ats: 2, action: 'IV access, type and cross, urgent gastro consult' },
      'Possible meningitis': { ats: 2, action: 'Immediate antibiotics, LP consideration' },
      'Obstetric emergency': { ats: 2, action: 'Urgent obstetric review, IV access, USS' },
      'Testicular emergency': { ats: 2, action: 'Urgent urology review, Doppler USS' },
      'Allergic reaction': { ats: 2, action: 'Antihistamines, steroids, observe for progression' },
      'Febrile infant': { ats: 2, action: 'Septic workup, IV antibiotics' },
      'Acute vision loss': { ats: 2, action: 'Urgent ophthalmology review' },
      'Acute abdomen': { ats: 2, action: 'Surgical review, CT abdomen, NBM' },
      'Post-partum haemorrhage': { ats: 2, action: 'Urgent obstetric review, IV fluids, uterotonics' },
      'Compartment syndrome': { ats: 2, action: 'Urgent orthopaedic review, compartment pressures' },
      'Severe dehydration': { ats: 2, action: 'IV fluids, electrolyte check, assess cause' },
      'Immunocompromised fever': { ats: 2, action: 'Immediate broad-spectrum antibiotics, neutropenic protocol' },

      // ATS 3 - Urgent conditions (30 minute wait)
      'Asthma exacerbation': { ats: 3, action: 'Nebulised salbutamol, assess severity, oxygen if SpO2 <94%' },
      'High fever': { ats: 3, action: 'Assess source of infection, paracetamol, bloods if indicated' },
      'Kidney stone': { ats: 3, action: 'Analgesia, antiemetic, CT KUB if first presentation' },
      'Possible appendicitis': { ats: 3, action: 'Surgical review, CT abdomen, NBM' },
      'Head injury with vomiting': { ats: 3, action: 'CT head, neuro obs, assess for skull fracture' },
      'Fracture or dislocation': { ats: 3, action: 'X-ray, analgesia, splint, orthopaedic review' },
      'Panic attack': { ats: 3, action: 'Calm environment, reassurance, exclude cardiac cause' },
      'Severe migraine': { ats: 3, action: 'Analgesia, antiemetic, dark quiet room, exclude SAH' },
      'Diabetic foot infection': { ats: 3, action: 'Wound assessment, bloods, IV antibiotics, vascular review' },
      'Dehydration': { ats: 3, action: 'Oral/IV fluids, assess electrolytes, identify cause' },
      'Foreign body eye': { ats: 3, action: 'Slit lamp examination, topical anaesthetic, removal' },
      'Abscess': { ats: 3, action: 'Incision and drainage, antibiotics if cellulitis' },
      'Paediatric respiratory': { ats: 3, action: 'Oxygen assessment, nebulised salbutamol, parent present' },
      'DVT symptoms': { ats: 3, action: 'D-dimer, Doppler USS, anticoagulation if confirmed' },
      'Severe back pain': { ats: 3, action: 'Exclude cauda equina (bladder, saddle anaesthesia), analgesia' },
      'Cellulitis': { ats: 3, action: 'Mark margins, IV antibiotics, elevate limb' },
      'Epistaxis': { ats: 3, action: 'Anterior nasal packing, silver nitrate if visible vessel' },
      'Haemoptysis': { ats: 3, action: 'CXR, assess volume, bronchoscopy if significant' },
      'Urinary retention': { ats: 3, action: 'Catheterisation, assess for cause' },
      'Post-operative complication': { ats: 3, action: 'Contact surgical team, assess wound' },
      'Possible ectopic': { ats: 3, action: 'Urgent USS, beta-hCG, gynae review' },
      'Animal bite': { ats: 3, action: 'Wound assessment, tetanus, consider rabies prophylaxis' },
      'Foreign body ingestion': { ats: 3, action: 'X-ray, assess for battery/magnet, paediatric review' },
    };

    const worstATS = Math.min(...redFlags.map(f => flagActions[f]?.ats || 2));
    const atsGuideline = ATS_GUIDELINES.find(g => g.atsCategory === worstATS)!;

    // Map ATS to urgency
    const atsToUrgency: Record<number, 'EMERGENCY' | 'URGENT' | 'SEMI_URGENT' | 'STANDARD' | 'NON_URGENT'> = {
      1: 'EMERGENCY',
      2: 'EMERGENCY',
      3: 'URGENT',
      4: 'SEMI_URGENT',
      5: 'NON_URGENT',
    };
    const urgency = atsToUrgency[worstATS] || 'URGENT';

    // Build appropriate message based on ATS category
    let actionText: string;
    let recommendations: string[];

    if (worstATS === 1) {
      actionText = 'Call 000 immediately - this is life-threatening';
      recommendations = [
        'Call emergency services (000) immediately',
        'Do not drive yourself to the hospital',
        'Stay calm and remain still',
      ];
    } else if (worstATS === 2) {
      actionText = 'Call 000 or go to your nearest Emergency Department immediately';
      recommendations = [
        'Go to Emergency Department immediately',
        'Call 000 if symptoms worsen',
        'Have someone drive you - do not drive yourself',
      ];
    } else {
      actionText = `Go to your nearest Emergency Department within ${atsGuideline.maxWaitTime}`;
      recommendations = [
        `Seek medical attention within ${atsGuideline.maxWaitTime}`,
        'Go to Emergency Department or urgent care',
        'If symptoms worsen, call 000',
      ];
    }

    const urgentMessage = `⚠️ **${atsGuideline.name.toUpperCase()} - ${atsGuideline.maxWaitTime}**

I've identified symptoms that require medical attention:
${redFlags.map(f => `• ${f}`).join('\n')}

**What you need to do:**
1. ${actionText}
2. ${worstATS <= 2 ? 'Do not drive yourself' : 'Have someone drive you if possible'}
3. Stay calm and monitor your symptoms
${redFlags.includes('Chest pain') ? '4. If you have aspirin and are not allergic, take 300mg' : ''}

This assessment has been logged for the healthcare team.`;

    await conversationStore.addMessage(conversationId, 'assistant', urgentMessage);

    // Build triage result
    const emergencyResult: TriageSession = {
      id: conversationId,
      timestamp: new Date().toISOString(),
      result: {
        severity: 6 - worstATS, // Convert ATS to severity (ATS 1 = severity 5, ATS 5 = severity 1)
        urgency,
        atsCategory: worstATS,
        maxWaitTime: atsGuideline.maxWaitTime,
        confidence: 0.95,
        redFlags: {
          detected: true,
          flags: redFlags.map(flag => ({
            condition: flag,
            evidence: userMessage,
            action: flagActions[flag]?.action || 'URGENT ASSESSMENT REQUIRED',
          })),
        },
        specialtyMatch: ['Emergency Medicine'],
        reasoning: `Conditions detected via deterministic keyword matching: ${redFlags.join(', ')}. ${atsGuideline.name} categorization per ATS guidelines.`,
        recommendations,
      },
      doctorSummary: {
        headline: `${worstATS <= 2 ? '🚨' : '⚠️'} ATS ${worstATS}: ${redFlags[0]} - ${atsGuideline.maxWaitTime}`,
        keySymptoms: redFlags,
        severity: 6 - worstATS,
        urgency,
        atsCategory: worstATS,
        maxWaitTime: atsGuideline.maxWaitTime,
        redFlags: redFlags,
        relevantHistory: [],
        suggestedQuestions: [
          'What is the patient\'s medical history?',
          'Any current medications or allergies?',
          'Time of symptom onset?'
        ],
        differentialDiagnosis: this.getDifferentialsForRedFlags(redFlags),
        triageReasoning: `Deterministic red flag detection triggered immediate ${atsGuideline.name} categorization. ${redFlags.join(', ')} identified in patient presentation.`,
      },
    };

    await conversationStore.setTriageResult(conversationId, emergencyResult);

    return {
      conversationId,
      message: urgentMessage,
      stage: 'complete',
      isComplete: true,
      triageResult: emergencyResult,
    };
  }

  private getDifferentialsForRedFlags(redFlags: string[]): string[] {
    const differentials: string[] = [];

    if (redFlags.includes('Chest pain')) {
      differentials.push('Acute Coronary Syndrome', 'Unstable Angina', 'Aortic Dissection', 'Pulmonary Embolism');
    }
    if (redFlags.includes('Difficulty breathing')) {
      differentials.push('Acute Asthma', 'Pulmonary Embolism', 'Pneumothorax', 'Heart Failure');
    }
    if (redFlags.includes('Sudden severe headache')) {
      differentials.push('Subarachnoid Haemorrhage', 'Intracerebral Haemorrhage', 'Meningitis');
    }
    if (redFlags.includes('Possible stroke symptoms')) {
      differentials.push('Ischaemic Stroke', 'Haemorrhagic Stroke', 'TIA');
    }
    if (redFlags.includes('Possible anaphylaxis')) {
      differentials.push('Anaphylaxis', 'Severe Allergic Reaction', 'Angioedema');
    }

    return differentials.length > 0 ? differentials : ['Requires clinical evaluation'];
  }

  private buildMessageHistory(
    conversation: Conversation,
    latestMessage: string,
    clinicalContext: string
  ): Array<{ role: 'user' | 'assistant'; content: string }> {
    const messages: Array<{ role: 'user' | 'assistant'; content: string }> = [];

    // Add previous messages
    for (const msg of conversation.messages) {
      if (msg.role === 'assistant' && messages.length === 0) continue; // Skip greeting
      messages.push({
        role: msg.role,
        content: msg.content,
      });
    }

    // Build context note
    const contextNote = this.buildContextNote(conversation);

    // Add clinical context from RAG retrieval
    const augmentedMessage = `Patient says: "${latestMessage}"

${clinicalContext}

[Assessment context: ${contextNote}]

Based on the clinical conditions above, ask the most relevant follow-up question OR if you have sufficient information, set readyToTriage=true.`;

    // Add the latest user message with clinical context
    messages.push({
      role: 'user',
      content: augmentedMessage,
    });

    return messages;
  }

  private buildContextNote(conversation: Conversation): string {
    const data = conversation.collectedData;
    const parts: string[] = [];

    if (data.symptoms.length > 0) {
      parts.push(`Symptoms: ${data.symptoms.join(', ')}`);
    }
    if (data.duration) {
      parts.push(`Duration: ${data.duration}`);
    }
    if (data.severity) {
      parts.push(`Severity: ${data.severity}/10`);
    }

    const messageCount = conversation.messages.filter(m => m.role === 'user').length;
    parts.push(`Exchange #${messageCount + 1}`);

    return parts.join(' | ') || 'Initial assessment';
  }

  private parseResponse(responseText: string): {
    message: string;
    clinicalAssessment?: {
      symptoms: string[];
      duration?: string;
      severity?: number;
      redFlagsIdentified?: string[];
      dataGathered?: string[];
    };
    readyToTriage: boolean;
    suggestedATS?: number;
    reasoning?: string;
  } {
    try {
      let jsonStr = responseText;

      // Handle markdown code blocks
      const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
      if (jsonMatch) {
        jsonStr = jsonMatch[1];
      }

      // Extract JSON object
      const objectMatch = jsonStr.match(/\{[\s\S]*\}/);
      if (objectMatch) {
        jsonStr = objectMatch[0];
      }

      const parsed = JSON.parse(jsonStr);

      if (!parsed.message || typeof parsed.message !== 'string') {
        throw new Error('Invalid message');
      }

      return {
        message: parsed.message,
        clinicalAssessment: parsed.clinicalAssessment,
        readyToTriage: parsed.readyToTriage || false,
        suggestedATS: parsed.suggestedATS,
        reasoning: parsed.reasoning,
      };
    } catch {
      // Fallback extraction
      const messageMatch = responseText.match(/"message"\s*:\s*"([^"]+)"/);
      let cleanMessage = messageMatch ? messageMatch[1] : responseText;

      cleanMessage = cleanMessage
        .replace(/\{[\s\S]*\}/g, '')
        .replace(/```[\s\S]*?```/g, '')
        .trim();

      if (!cleanMessage) {
        cleanMessage = "Can you tell me more about your symptoms? How long have you had them and how severe are they on a scale of 1-10?";
      }

      return {
        message: cleanMessage,
        readyToTriage: false,
      };
    }
  }

  private async performTriage(
    conversationId: string,
    relevantConditions: ClinicalCondition[],
    minATSFromKeywords: number
  ): Promise<TriageSession> {
    const conversation = (await conversationStore.get(conversationId))!;
    const data = conversation.collectedData;

    // Gather all patient input
    const userMessages = conversation.messages
      .filter(m => m.role === 'user')
      .map(m => m.content)
      .join(' ');

    // Build context for triage
    const clinicalContext = relevantConditions.length > 0
      ? relevantConditions.map(c =>
        `${c.name} (ATS ${c.atsCategory}): ${c.criteria}`
      ).join('\n')
      : 'No specific conditions matched';

    const triagePrompt = `You are a medical triage AI using the Australian Triage Scale. Analyze and categorize this patient.

PATIENT PRESENTATION:
${userMessages}

COLLECTED DATA:
- Symptoms: ${data.symptoms.join(', ') || 'Not specified'}
- Duration: ${data.duration || 'Not specified'}
- Severity: ${data.severity ? `${data.severity}/10` : 'Not specified'}

RELEVANT CLINICAL CONDITIONS (from knowledge base):
${clinicalContext}

MINIMUM ATS FROM KEYWORDS: ${minATSFromKeywords}

ATS CATEGORIES:
1 - Resuscitation (Immediate): Life-threatening
2 - Emergency (10 min): Imminent threat to life
3 - Urgent (30 min): Potentially life-threatening
4 - Semi-urgent (60 min): Potentially serious
5 - Non-urgent (120 min): Less urgent

IMPORTANT: Your ATS category MUST be <= ${minATSFromKeywords} (cannot be less urgent than keyword detection suggests).

Respond with ONLY this JSON:
{
  "atsCategory": <1-5>,
  "urgency": "<EMERGENCY|URGENT|SEMI_URGENT|STANDARD|NON_URGENT>",
  "confidence": <0.6-0.95>,
  "primaryCondition": "<most likely condition>",
  "differentials": ["<diff1>", "<diff2>"],
  "reasoning": "<2-3 sentence clinical reasoning>",
  "recommendations": ["<action1>", "<action2>", "<action3>"],
  "questionsForDoctor": ["<question1>", "<question2>"]
}`;

    const responseText = await llmClient.chat([
      { role: 'user', content: triagePrompt }
    ], { temperature: 0.2 });

    // Parse response
    let triageData;
    try {
      let jsonStr = responseText;
      const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
      if (jsonMatch) jsonStr = jsonMatch[1];
      const objectMatch = jsonStr.match(/\{[\s\S]*\}/);
      if (objectMatch) jsonStr = objectMatch[0];
      triageData = JSON.parse(jsonStr);
    } catch {
      // Fallback with safe defaults
      triageData = {
        atsCategory: Math.min(4, minATSFromKeywords),
        urgency: 'STANDARD',
        confidence: 0.6,
        primaryCondition: 'Requires clinical evaluation',
        differentials: ['Further assessment needed'],
        reasoning: 'Unable to determine specific condition. Clinical evaluation recommended.',
        recommendations: ['See your GP within 24 hours', 'Return if symptoms worsen'],
        questionsForDoctor: ['Detailed symptom history needed']
      };
    }

    // SAFETY ENVELOPE: Enforce minimum ATS from keyword detection
    const finalATS = Math.min(triageData.atsCategory || 4, minATSFromKeywords);
    const atsGuideline = ATS_GUIDELINES.find(g => g.atsCategory === finalATS)!;

    // Map ATS to urgency
    const atsToUrgency: Record<number, 'EMERGENCY' | 'URGENT' | 'SEMI_URGENT' | 'STANDARD' | 'NON_URGENT'> = {
      1: 'EMERGENCY',
      2: 'EMERGENCY',
      3: 'URGENT',
      4: 'SEMI_URGENT',
      5: 'NON_URGENT'
    };

    const session: TriageSession = {
      id: conversationId,
      timestamp: new Date().toISOString(),
      result: {
        severity: 6 - finalATS, // Convert ATS to severity (ATS 1 = severity 5)
        urgency: atsToUrgency[finalATS],
        atsCategory: finalATS,
        maxWaitTime: atsGuideline.maxWaitTime,
        confidence: triageData.confidence || 0.7,
        redFlags: {
          detected: finalATS <= 2,
          flags: finalATS <= 2 ? [{
            condition: triageData.primaryCondition || 'Urgent condition',
            evidence: userMessages.slice(0, 100),
            action: triageData.recommendations?.[0] || 'Urgent assessment required'
          }] : []
        },
        specialtyMatch: this.mapConditionToSpecialty(triageData.primaryCondition),
        reasoning: triageData.reasoning || '',
        recommendations: triageData.recommendations || ['Consult your healthcare provider'],
      },
      doctorSummary: {
        headline: `ATS ${finalATS} (${atsGuideline.name}): ${triageData.primaryCondition || 'Assessment complete'}`,
        keySymptoms: data.symptoms.length > 0 ? data.symptoms : ['As per patient description'],
        severity: 6 - finalATS,
        urgency: atsToUrgency[finalATS],
        atsCategory: finalATS,
        maxWaitTime: atsGuideline.maxWaitTime,
        redFlags: finalATS <= 2 ? [triageData.primaryCondition] : [],
        relevantHistory: [],
        suggestedQuestions: triageData.questionsForDoctor || [],
        differentialDiagnosis: triageData.differentials || [],
        triageReasoning: `${triageData.reasoning} ATS ${finalATS} assigned based on clinical presentation and ${relevantConditions.length > 0 ? 'knowledge base match' : 'general assessment'}.`,
      }
    };

    await conversationStore.setTriageResult(conversationId, session);
    return session;
  }

  private mapConditionToSpecialty(condition: string): string[] {
    const conditionLower = (condition || '').toLowerCase();

    if (conditionLower.includes('chest') || conditionLower.includes('cardiac') || conditionLower.includes('heart')) {
      return ['Cardiology', 'Emergency Medicine'];
    }
    if (conditionLower.includes('stroke') || conditionLower.includes('neuro') || conditionLower.includes('headache')) {
      return ['Neurology', 'Emergency Medicine'];
    }
    if (conditionLower.includes('breathing') || conditionLower.includes('respiratory') || conditionLower.includes('asthma')) {
      return ['Respiratory Medicine', 'Emergency Medicine'];
    }
    if (conditionLower.includes('mental') || conditionLower.includes('suicid') || conditionLower.includes('anxiety')) {
      return ['Psychiatry', 'Emergency Medicine'];
    }
    if (conditionLower.includes('abdominal') || conditionLower.includes('stomach') || conditionLower.includes('bowel')) {
      return ['Gastroenterology', 'General Surgery'];
    }

    return ['General Practice'];
  }

  private checkRedFlagKeywords(text: string): string[] {
    const lowerText = text.toLowerCase();
    const flags: string[] = [];

    const keywordPatterns = [
      // Cardiovascular
      { pattern: /chest pain|chest tightness|chest pressure|crushing.*chest|radiating.*arm|pressure.*chest/, flag: 'Chest pain' },
      { pattern: /no pulse|has no pulse|not beating|heart stopped/, flag: 'Cardiac arrest' },

      // Respiratory
      { pattern: /can't breathe|cannot breathe|hard to breathe|shortness of breath|gasping|difficulty breathing|struggling to breathe/, flag: 'Difficulty breathing' },
      { pattern: /not breathing|stopped breathing|barely breathing|lips.*blue|turning blue|cyanosis/, flag: 'Respiratory arrest' },
      { pattern: /choking|airway.*blocked|throat.*closed/, flag: 'Airway obstruction' },

      // Neurological
      { pattern: /worst headache|thunderclap headache|sudden severe headache|never had headache this bad/, flag: 'Sudden severe headache' },
      { pattern: /passed out|fainted|lost consciousness|blacked out|unresponsive|not responding|not moving/, flag: 'Loss of consciousness' },
      { pattern: /face droop|face.*droop|arm weak|arm.*weak|slurred speech|can't speak|one side.*weak|stroke/, flag: 'Possible stroke symptoms' },
      { pattern: /seizure|convulsing|fitting|having a fit/, flag: 'Seizure' },

      // Anaphylaxis
      { pattern: /can't swallow|throat closing|swelling.*throat|throat.*swelling|allergic.*breathing|throat is closing/, flag: 'Possible anaphylaxis' },

      // Mental Health
      { pattern: /want to die|kill myself|suicide|self.?harm|ending my life|end my life|better off dead|hanging|hanged/, flag: 'Suicidal ideation' },

      // Trauma & Bleeding
      { pattern: /heavy bleeding|won't stop bleeding|blood everywhere|soaked.*blood|massive blood/, flag: 'Severe bleeding' },
      { pattern: /car accident|car crash|major accident|serious accident|hit by|run over/, flag: 'Major trauma' },
      { pattern: /burn.*all over|severe burn|large.*burn|house fire|on fire|explosion/, flag: 'Severe burns' },
      { pattern: /electrocuted|electric shock|power lines|high voltage/, flag: 'Electrocution' },
      { pattern: /drowning|pulled from.*water|swallowed water.*passed out|found in pool/, flag: 'Near-drowning' },

      // Toxicology
      { pattern: /overdose|took too many|pills.*unconscious|needles.*passed out|drug.*unresponsive/, flag: 'Drug overdose' },
      { pattern: /poison|poisoning|swallowed.*chemical|drank.*bleach/, flag: 'Poisoning' },

      // General
      { pattern: /confused|don't know where|altered mental|acting strange|not making sense/, flag: 'Altered mental status' },
      { pattern: /collapsed|found on floor|found unconscious/, flag: 'Collapse' },

      // Additional Emergency Conditions (ATS 2)
      { pattern: /vomiting.*blood|vomited blood|haematemesis|black.*tarry.*stool|melena/, flag: 'GI bleeding' },
      { pattern: /stiff neck.*fever|fever.*stiff neck|rash.*doesn't fade|petechial/, flag: 'Possible meningitis' },
      { pattern: /pregnant.*severe.*pain|pregnant.*bleeding|ectopic|one.?sided.*pain.*pregnant/, flag: 'Obstetric emergency' },
      { pattern: /testicle.*pain|testicular.*pain|scrotum.*severe|sudden.*testicle/, flag: 'Testicular emergency' },
      { pattern: /hives.*spreading|face.*swelling|lips.*swelling|angioed/, flag: 'Allergic reaction' },
      { pattern: /baby.*fever|infant.*fever|newborn.*fever|6.*week.*fever/, flag: 'Febrile infant' },
      { pattern: /sudden.*can.?t see|suddenly.*blind|vision.*loss|curtain.*over.*eye|curtain.*came down|lost.*vision|cannot see|can.?t see.*eye/, flag: 'Acute vision loss' },
      { pattern: /belly.*hard.*board|abdomen.*rigid|peritonitis/, flag: 'Acute abdomen' },
      { pattern: /just gave birth.*bleeding|post.?partum.*bleed|soaking.*pad/, flag: 'Post-partum haemorrhage' },
      { pattern: /haven't.*urinated.*\d+.*hour|can't.*urinate|urinary.*retention/, flag: 'Urinary retention' },
      { pattern: /can.?t move.*toes|leg.*tight.*pain|compartment|limb.*swelling.*injury|leg.*severe.*pain.*toes/, flag: 'Compartment syndrome' },
      { pattern: /surgery.*last week.*pain|post.?op.*pain|recent surgery/, flag: 'Post-operative complication' },
      { pattern: /severe.*dehydration|extremely dehydrated|not urinating|haven.?t urinated|havent urinated|dark urine.*not eating|sunken.*eyes|can.?t keep.*down.*lips/, flag: 'Severe dehydration' },

      // ATS 3 - Urgent (30 minutes) - Potentially life-threatening
      { pattern: /asthma.*attack|asthma.*worse|wheezing|using.*inhaler|nebulizer|puffer/, flag: 'Asthma exacerbation' },
      { pattern: /high fever|fever.*39|fever.*40|temperature.*39|temperature.*40|burning up/, flag: 'High fever' },
      { pattern: /kidney stone|severe.*flank.*pain|excruciating.*back.*radiating|renal colic|colicky.*pain.*side.*groin|side.*radiating.*groin/, flag: 'Kidney stone' },
      { pattern: /lower right.*pain|pain.*lower right|belly.*button.*lower right|appendicitis|appendix/, flag: 'Possible appendicitis' },
      { pattern: /hit.*head.*vomit|head.*vomit|concussion.*vomit|fell.*head.*threw up|head.*threw up/, flag: 'Head injury with vomiting' },
      { pattern: /broken.*bone|fracture|bone.*sticking out|deformed.*limb|snapped|dislocated|bent.*wrong way|arm.*bent/, flag: 'Fracture or dislocation' },
      { pattern: /panic attack|heart racing.*dying|heart racing.*scared|can.?t calm down.*anxiety|hyperventilating|overwhelming fear|can.?t catch.*breath.*racing/, flag: 'Panic attack' },
      { pattern: /severe migraine|migraine.*vomiting|worst migraine|blinding headache/, flag: 'Severe migraine' },
      { pattern: /diabetic.*foot.*infection|diabetic.*wound|foot ulcer.*diabetic|infected.*foot.*diabetes/, flag: 'Diabetic foot infection' },
      { pattern: /vomiting.*diarrhea|diarrhea.*vomiting|vomiting.*days|diarrhea.*days|dizzy.*stand.*dry|can.?t keep.*down/, flag: 'Dehydration' },
      { pattern: /something.*in.*eye|foreign body.*eye|metal.*eye|dust.*eye.*painful|can.?t see.*eye/, flag: 'Foreign body eye' },
      { pattern: /abscess|boil.*painful|swelling.*pus|infected.*lump|cyst.*infected|lump.*red.*hot|painful.*lump.*fever/, flag: 'Abscess' },
      { pattern: /child.*asthma|child.*wheezing|kid.*breathing|toddler.*breathing/, flag: 'Paediatric respiratory' },
      { pattern: /leg.*swollen.*painful|calf.*swollen|calf.*painful|calf.*red.*painful|dvt|deep vein|blood clot.*leg|long.*flight.*swollen/, flag: 'DVT symptoms' },
      { pattern: /back pain.*can.?t walk|severe back pain|can.?t move.*back|acute back pain/, flag: 'Severe back pain' },
      { pattern: /cellulitis|redness.*spreading|infection.*spreading|red.*hot.*swollen|red.*getting bigger|spreading up/, flag: 'Cellulitis' },
      { pattern: /nose.*won.?t stop.*bleeding|nosebleed.*\d+.*minutes|nose.*bleeding.*long time/, flag: 'Epistaxis' },
      { pattern: /coughing.*blood|blood.*sputum|haemoptysis|coughed up blood/, flag: 'Haemoptysis' },
      { pattern: /haven.?t.*pee|can.?t.*pee|haven.?t.*urinate|can.?t.*urinate|belly.*swollen.*painful.*pee/, flag: 'Urinary retention' },

      // Additional edge cases
      { pattern: /chemotherapy.*fever|chemo.*temperature|immunocompromised.*fever|immune.*suppressed.*fever|cancer.*fever|transplant.*fever/, flag: 'Immunocompromised fever' },
      { pattern: /might be pregnant.*cramp|pregnant.*cramp|could be pregnant.*pain|possible pregnancy.*bleeding/, flag: 'Possible ectopic' },
      { pattern: /dog.*bit|bitten.*dog|bitten.*cat|animal.*bite|stray.*bit|rabies/, flag: 'Animal bite' },
      { pattern: /swallowed.*coin|swallowed.*battery|child.*swallowed|toddler.*swallowed|swallowed.*object|swallowed.*magnet/, flag: 'Foreign body ingestion' },

      // Communication impairment with emergency - immediate escalation
      { pattern: /can.?t type|cannot type|unable to type|hard to type|difficult to type|can.?t communicate|cannot communicate/, flag: 'Communication impairment' },
      { pattern: /can.?t speak|cannot speak|lost.*voice|mute|speech.*impaired/, flag: 'Communication impairment' },
      { pattern: /deaf|blind|can.?t see|cannot see|can.?t hear|cannot hear/, flag: 'Communication impairment' },
      { pattern: /don.?t speak english|no english|need.*translator|need.*interpreter|language barrier/, flag: 'Communication impairment' },

      // Paediatric emergencies - immediate escalation
      { pattern: /baby.*not breathing|infant.*blue|newborn.*limp|child.*unconscious|toddler.*choking/, flag: 'Paediatric emergency' },
      { pattern: /baby.*choking|infant.*choking|child.*not breathing|kid.*not breathing/, flag: 'Paediatric emergency' },

      // Violence/Safety - immediate escalation
      { pattern: /being attacked|someone.*hurting|domestic violence|being abused|assault.*happening/, flag: 'Violence/Safety concern' },
      { pattern: /attacker|intruder|break.*in|someone.*in.*house|stalker/, flag: 'Violence/Safety concern' },
    ];

    for (const { pattern, flag } of keywordPatterns) {
      if (pattern.test(lowerText)) {
        flags.push(flag);
      }
    }

    return flags;
  }

  async getConversation(conversationId: string): Promise<Conversation | undefined> {
    return conversationStore.get(conversationId);
  }
}

export const conversationEngine = new ConversationEngine();
