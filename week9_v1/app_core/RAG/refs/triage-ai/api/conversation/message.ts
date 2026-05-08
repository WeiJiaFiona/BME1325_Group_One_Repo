import type { VercelRequest, VercelResponse } from '@vercel/node';
import { checkRateLimit } from '../lib/rate-limiter';

// Shared conversation store (will reset between cold starts)
const conversations = new Map<string, any>();

const SYSTEM_PROMPT = `You are TriageAI, a warm and professional medical triage assistant using the Australian Triage Scale (ATS).

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

EXAMPLE GOOD RESPONSES:
- "I'm sorry you're dealing with a headache. How long has it been bothering you?"
- "A 3 out of 10 pain - that's helpful to know. Have you tried anything for relief yet?"
- "Sounds like stress and poor sleep could be the culprit. Let me check a few more things..."

RESPONSE FORMAT (valid JSON):
{
  "message": "Your warm, helpful response to the patient",
  "readyToTriage": false,
  "triageResult": null
}

Set readyToTriage=true after 2-3 exchanges or when you have enough info:
{
  "readyToTriage": true,
  "triageResult": {
    "category": "ATS1-5",
    "categoryName": "RESUSCITATION/EMERGENCY/URGENT/SEMI-URGENT/NON-URGENT",
    "maxWaitTime": "Immediate/10 min/30 min/60 min/120 min",
    "severity": 1-5,
    "urgency": "EMERGENCY/URGENT/SEMI_URGENT/STANDARD/NON_URGENT",
    "confidence": 0.6-0.95,
    "reasoning": "clinical reasoning",
    "recommendations": ["recommendation1"],
    "doctorSummary": {
      "headline": "one line for doctor",
      "keySymptoms": ["symptom1"],
      "differentialDiagnosis": ["diagnosis1"]
    }
  }
}`;

// Red flag keyword detection (<1ms deterministic safety)
function checkRedFlags(text: string): Array<{ condition: string; evidence: string; action: string; ats: number }> {
  const lowerText = text.toLowerCase();
  const flags: Array<{ condition: string; evidence: string; action: string; ats: number }> = [];

  const patterns = [
    // ATS 1 - Resuscitation
    { pattern: /no pulse|has no pulse|not beating|heart stopped/, condition: 'Cardiac arrest', action: 'Begin CPR, call 000', ats: 1 },
    { pattern: /not breathing|stopped breathing|barely breathing|lips.*blue|cyanosis/, condition: 'Respiratory arrest', action: 'Secure airway, call 000', ats: 1 },
    { pattern: /can.?t swallow|throat closing|throat.*swelling|anaphylax/, condition: 'Possible anaphylaxis', action: 'Adrenaline, airway management', ats: 1 },
    { pattern: /choking|airway.*blocked/, condition: 'Airway obstruction', action: 'Immediate airway clearance', ats: 1 },

    // ATS 2 - Emergency
    { pattern: /chest pain|chest tightness|chest pressure|crushing.*chest|radiating.*arm|heart attack|having.*heart attack|think.*heart attack|mi\b|myocardial/, condition: 'Chest pain', action: 'Immediate ECG and cardiac workup', ats: 2 },
    { pattern: /can.?t breathe|cannot breathe|hard to breathe|shortness of breath|gasping|difficulty breathing/, condition: 'Difficulty breathing', action: 'Respiratory assessment, oxygen', ats: 2 },
    { pattern: /worst headache|thunderclap headache|sudden severe headache|never had headache this bad/, condition: 'Sudden severe headache', action: 'Urgent CT to rule out SAH', ats: 2 },
    { pattern: /passed out|fainted|lost consciousness|unresponsive|not responding/, condition: 'Loss of consciousness', action: 'Neurological assessment', ats: 2 },
    { pattern: /face droop|arm weak|slurred speech|one side.*weak|stroke/, condition: 'Possible stroke', action: 'Immediate stroke protocol', ats: 2 },
    { pattern: /seizure|convulsing|fitting/, condition: 'Seizure', action: 'Protect airway, time seizure', ats: 2 },
    { pattern: /want to die|kill myself|suicide|self.?harm|ending my life|hanging/, condition: 'Suicidal ideation', action: 'Immediate mental health assessment', ats: 2 },
    { pattern: /heavy bleeding|won.?t stop bleeding|blood everywhere|soaked.*blood/, condition: 'Severe bleeding', action: 'Haemostasis and volume resuscitation', ats: 2 },
    { pattern: /confused|don.?t know where|altered mental|acting strange/, condition: 'Altered mental status', action: 'Assess for reversible causes', ats: 2 },
    { pattern: /car accident|car crash|major accident|hit by|run over/, condition: 'Major trauma', action: 'Trauma team activation', ats: 2 },
    { pattern: /burn.*all over|severe burn|large.*burn|house fire/, condition: 'Severe burns', action: 'Cool burns, assess airway', ats: 2 },
    { pattern: /overdose|took too many|pills.*unconscious/, condition: 'Drug overdose', action: 'Assess airway, naloxone if opioid', ats: 2 },
    { pattern: /vomiting.*blood|vomited blood|black.*tarry.*stool/, condition: 'GI bleeding', action: 'IV access, urgent gastro consult', ats: 2 },
    { pattern: /stiff neck.*fever|fever.*stiff neck|rash.*doesn.?t fade/, condition: 'Possible meningitis', action: 'Immediate antibiotics', ats: 2 },
    { pattern: /testicle.*pain|testicular.*pain|scrotum.*severe/, condition: 'Testicular emergency', action: 'Urgent urology review', ats: 2 },
    { pattern: /baby.*fever|infant.*fever|newborn.*fever/, condition: 'Febrile infant', action: 'Septic workup, IV antibiotics', ats: 2 },
    { pattern: /chemotherapy.*fever|chemo.*temperature|immunocompromised.*fever/, condition: 'Immunocompromised fever', action: 'Immediate broad-spectrum antibiotics', ats: 2 },
    { pattern: /can.?t type|cannot type|unable to type|hard to type|can.?t communicate|cannot communicate/, condition: 'Communication impairment', action: 'Patient unable to communicate - call 000 immediately', ats: 2 },
    { pattern: /baby.*not breathing|infant.*blue|newborn.*limp|child.*unconscious|toddler.*choking|baby.*choking|infant.*choking/, condition: 'Paediatric emergency', action: 'Immediate paediatric resuscitation - call 000', ats: 1 },
    { pattern: /being attacked|someone.*hurting|domestic violence|being abused|assault.*happening/, condition: 'Violence/Safety concern', action: 'Contact police (000) and ensure safety first', ats: 2 },

    // ATS 3 - Urgent
    { pattern: /asthma.*attack|asthma.*worse|wheezing|using.*inhaler/, condition: 'Asthma exacerbation', action: 'Nebulised salbutamol, assess severity', ats: 3 },
    { pattern: /high fever|fever.*39|fever.*40|temperature.*39|temperature.*40/, condition: 'High fever', action: 'Assess source of infection', ats: 3 },
    { pattern: /kidney stone|severe.*flank.*pain|colicky.*pain.*groin/, condition: 'Kidney stone', action: 'Analgesia, CT KUB', ats: 3 },
    { pattern: /lower right.*pain|pain.*lower right|appendicitis/, condition: 'Possible appendicitis', action: 'Surgical review, CT abdomen', ats: 3 },
    { pattern: /hit.*head.*vomit|head.*vomit|concussion.*vomit/, condition: 'Head injury with vomiting', action: 'CT head, neuro obs', ats: 3 },
    { pattern: /broken.*bone|fracture|bone.*sticking out|bent.*wrong way/, condition: 'Fracture', action: 'X-ray, analgesia, splint', ats: 3 },
    { pattern: /panic attack|heart racing.*dying|hyperventilating/, condition: 'Panic attack', action: 'Calm environment, exclude cardiac', ats: 3 },
    { pattern: /calf.*swollen|calf.*painful|dvt|deep vein|blood clot.*leg/, condition: 'DVT symptoms', action: 'D-dimer, Doppler USS', ats: 3 },
    { pattern: /cellulitis|redness.*spreading|red.*getting bigger/, condition: 'Cellulitis', action: 'IV antibiotics, mark margins', ats: 3 },
    { pattern: /dog.*bit|bitten.*dog|animal.*bite/, condition: 'Animal bite', action: 'Wound assessment, tetanus, rabies', ats: 3 },
    { pattern: /swallowed.*coin|swallowed.*battery|child.*swallowed/, condition: 'Foreign body ingestion', action: 'X-ray, paediatric review', ats: 3 },
  ];

  for (const { pattern, condition, action, ats } of patterns) {
    if (pattern.test(lowerText)) {
      const match = lowerText.match(pattern);
      flags.push({
        condition,
        evidence: match ? match[0] : 'keyword detected',
        action,
        ats,
      });
    }
  }

  return flags;
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  // Enable CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Rate limit: 30 messages per minute per IP
  const allowed = await checkRateLimit(req, res, 'message');
  if (!allowed) return;

  const { conversationId, message } = req.body;

  if (!conversationId || !message) {
    return res.status(400).json({ error: 'conversationId and message required' });
  }

  // Check for red flags first (deterministic, <1ms)
  const redFlags = checkRedFlags(message);
  const hasRedFlags = redFlags.length > 0;

  try {
    // Build conversation context
    const conversation = conversations.get(conversationId) || {
      messages: [],
      collectedData: { symptoms: [] },
    };

    // Add user message to history
    conversation.messages.push({ role: 'user', content: message });

    // Build messages for Groq API
    const groqMessages = [
      { role: 'system', content: SYSTEM_PROMPT },
      ...conversation.messages.map((m: any) => ({
        role: m.role,
        content: m.role === 'user' && hasRedFlags && m.content === message
          ? `${m.content}\n\n[SYSTEM: RED FLAGS DETECTED - ${redFlags.map(f => f.condition).join(', ')}. Provide immediate ATS1/ATS2 triage.]`
          : m.content,
      })),
    ];

    // Call Groq API (free, fast Llama)
    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.GROQ_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'llama-3.3-70b-versatile',
        messages: groqMessages,
        max_tokens: 1024,
        temperature: 0.7,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Groq API error: ${error}`);
    }

    const data = await response.json();
    const responseText = data.choices[0]?.message?.content || '';

    // Parse JSON response
    let parsed;
    try {
      const jsonMatch = responseText.match(/\{[\s\S]*\}/);
      parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : { message: responseText, readyToTriage: false };
    } catch {
      parsed = { message: responseText.replace(/```json|```/g, '').trim(), readyToTriage: false };
    }

    // Determine worst ATS from detected flags
    const worstATS = hasRedFlags ? Math.min(...redFlags.map(f => f.ats)) : 5;
    const atsConfig: Record<number, { name: string; wait: string; urgency: string }> = {
      1: { name: 'RESUSCITATION', wait: 'Immediate', urgency: 'EMERGENCY' },
      2: { name: 'EMERGENCY', wait: '10 minutes', urgency: 'EMERGENCY' },
      3: { name: 'URGENT', wait: '30 minutes', urgency: 'URGENT' },
      4: { name: 'SEMI-URGENT', wait: '60 minutes', urgency: 'SEMI_URGENT' },
      5: { name: 'NON-URGENT', wait: '120 minutes', urgency: 'NON_URGENT' },
    };

    // Force triage if red flags detected (whether or not LLM decided to triage)
    if (hasRedFlags) {
      const config = atsConfig[worstATS];
      // Override or create triage result with deterministic red-flag-based severity
      const redFlagTriage = {
        category: `ATS${worstATS}`,
        categoryName: config.name,
        maxWaitTime: config.wait,
        severity: 6 - worstATS, // ATS 2 -> severity 4 (Severe)
        urgency: config.urgency,
        atsCategory: worstATS,
        confidence: 0.95,
        redFlags: { detected: true, flags: redFlags.map(f => ({ condition: f.condition, evidence: f.evidence, action: f.action })) },
        reasoning: `${config.name} - ${redFlags.map(f => f.condition).join(', ')} detected. ${worstATS <= 2 ? 'Call 000 or go to Emergency immediately.' : 'Seek medical attention within ' + config.wait + '.'}`,
        recommendations: redFlags.map(f => f.action),
        doctorSummary: parsed.triageResult?.doctorSummary || {
          headline: `ATS ${worstATS} (${config.name}): ${redFlags[0].condition}`,
          keySymptoms: redFlags.map(f => f.condition),
          differentialDiagnosis: redFlags.map(f => f.condition),
        },
      };
      // Merge LLM's doctorSummary details if available, but ensure red flags always included
      if (parsed.triageResult?.doctorSummary) {
        const flagConditions = redFlags.map(f => f.condition);
        const llmSymptoms = parsed.triageResult.doctorSummary.keySymptoms || [];
        const llmDiagnosis = parsed.triageResult.doctorSummary.differentialDiagnosis || [];
        redFlagTriage.doctorSummary = {
          ...parsed.triageResult.doctorSummary,
          keySymptoms: Array.from(new Set(flagConditions.concat(llmSymptoms))),
          differentialDiagnosis: Array.from(new Set(flagConditions.concat(llmDiagnosis))),
        };
      }
      parsed.readyToTriage = true;
      parsed.triageResult = redFlagTriage;
    }

    // Normalize LLM triage result (when LLM decides readyToTriage without red flags)
    if (parsed.readyToTriage && parsed.triageResult && !hasRedFlags) {
      // Extract ATS category from various possible LLM response formats
      let atsFromLLM = parsed.triageResult.atsCategory;
      if (!atsFromLLM && parsed.triageResult.category) {
        // Parse from "ATS4" or "ATS 4" format
        const match = String(parsed.triageResult.category).match(/ATS\s*(\d)/i);
        atsFromLLM = match ? parseInt(match[1]) : null;
      }
      if (!atsFromLLM && parsed.triageResult.severity) {
        // Convert severity (1-5) to ATS (5-1)
        atsFromLLM = 6 - parsed.triageResult.severity;
      }
      // Map urgency to ATS as fallback
      if (!atsFromLLM && parsed.triageResult.urgency) {
        const urgencyToATS: Record<string, number> = {
          'EMERGENCY': 2, 'URGENT': 3, 'SEMI_URGENT': 4, 'SEMI-URGENT': 4, 'STANDARD': 4, 'NON_URGENT': 5, 'NON-URGENT': 5
        };
        atsFromLLM = urgencyToATS[parsed.triageResult.urgency] || 4;
      }
      // Default to ATS 4 (semi-urgent) if nothing found
      const finalATS = atsFromLLM || 4;
      const config = atsConfig[finalATS];

      // Ensure all required fields are set - ALWAYS calculate severity from ATS for consistency
      parsed.triageResult.atsCategory = finalATS;
      parsed.triageResult.maxWaitTime = parsed.triageResult.maxWaitTime || config.wait;
      parsed.triageResult.urgency = parsed.triageResult.urgency || config.urgency;
      parsed.triageResult.severity = 6 - finalATS; // Always override LLM's severity with ATS-based calculation
      parsed.triageResult.confidence = parsed.triageResult.confidence || 0.7;
      parsed.triageResult.redFlags = parsed.triageResult.redFlags || { detected: false, flags: [] };
      parsed.triageResult.recommendations = parsed.triageResult.recommendations || ['Consult your healthcare provider'];
    }

    // Store conversation
    conversation.messages.push({ role: 'assistant', content: parsed.message });
    conversations.set(conversationId, conversation);

    return res.json({
      conversationId,
      message: parsed.message,
      stage: parsed.readyToTriage ? 'complete' : 'collecting',
      isComplete: parsed.readyToTriage,
      triageResult: parsed.triageResult ? {
        id: conversationId,
        timestamp: new Date().toISOString(),
        result: {
          severity: parsed.triageResult.severity,
          urgency: parsed.triageResult.urgency,
          atsCategory: parsed.triageResult.atsCategory,
          maxWaitTime: parsed.triageResult.maxWaitTime,
          confidence: parsed.triageResult.confidence,
          redFlags: parsed.triageResult.redFlags,
          specialtyMatch: ['Emergency Medicine'],
          reasoning: parsed.triageResult.reasoning,
          recommendations: parsed.triageResult.recommendations,
        },
        doctorSummary: {
          ...parsed.triageResult.doctorSummary,
          severity: parsed.triageResult.severity,
          urgency: parsed.triageResult.urgency,
          atsCategory: parsed.triageResult.atsCategory,
          maxWaitTime: parsed.triageResult.maxWaitTime,
          redFlags: parsed.triageResult.redFlags?.flags?.map((f: any) => f.condition) || [],
          relevantHistory: [],
          suggestedQuestions: ['What is the patient\'s medical history?'],
          triageReasoning: parsed.triageResult.reasoning,
        },
      } : undefined,
    });
  } catch (error: any) {
    console.error('API Error:', error);
    return res.status(500).json({
      error: 'Failed to process message',
      details: error.message,
    });
  }
}
