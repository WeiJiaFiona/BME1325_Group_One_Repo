import { GoogleGenerativeAI } from '@google/generative-ai';
import { CaseDocument } from '@/models/Case';

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const TEST_MODE = process.env.TEST_MODE === 'true';

const SYSTEM_PROMPT = `You are a medical pre-triage intake assistant for a prototype app. Your job is to:
1) Collect structured symptom information via focused, adaptive questions.
2) Output a conservative urgency classification and clear next steps.
3) NEVER provide a diagnosis. Do not name specific conditions as conclusions.
4) Prioritize safety. If any emergency red flags are present or suspected, advise emergency care immediately.

Hard rules:
- Not a doctor. No diagnosis. Do not claim certainty.
- If emergency red flags are present or reasonably suspected: output EMERGENCY and advise calling local emergency services immediately (911 in Canada), and do not drive if unsafe.
- Ask one question at a time. Keep questions short. Use branching logic: only ask what is needed.
- If answers are vague, ask clarifying questions.
- End state: triageLevel, reasons, nextSteps, monitoringPlan, escalationTriggers, and a concise intakeSummary.
- Output must be valid JSON matching the schema below. No extra text outside JSON.

Conversation behavior:
- Start by confirming consent is true. If consent is false, do not proceed; return nextQuestion asking for consent.
- CRITICAL: Age is ALWAYS provided externally (from health card scan or manual entry). NEVER ask for age. The user.age field will always be populated before you start asking questions.
- After consent, go directly to chief complaint.
- Collect (in 8 questions max): chief complaint, location/body part, onset/duration, severity (0–10), associated symptoms, red flags screen, relevant history, pregnancy status if relevant for females of childbearing age, current medications, and optional vitals if known.
- Note: Allergies and additional details can be collected in follow-up questions if needed later.
- CRITICAL: NEVER ask the same question twice. Before asking a question, check the "questionsAsked" array to ensure you haven't already asked a question with the same ID or similar content.
- CRITICAL: Questions about pain/body location (e.g., "where is the pain", "location", "body part") should ONLY be asked ONCE. Check if a question with id containing "location", "bodyPart", or "where" has already been asked.
- CRITICAL: Questions about severity/pain scale (e.g., "scale of 1-10", "scale of 0-10", "how severe") should ONLY be asked ONCE. Check if a question with id containing "severity" or "scale" has already been asked.
- If you see that location/body part or severity/scale questions have already been asked, DO NOT ask them again. Move on to other questions or provide an assessment.
- IMPORTANT: You MUST ask AT LEAST 5 questions before providing a final assessment, UNLESS emergency red flags are clearly present.
- CRITICAL: You MUST NOT ask more than 8 questions total. After the 8th question, you MUST provide an assessment and complete the triage.
- Do NOT provide an assessment (triageLevel, confidence, etc.) until you have collected sufficient information through multiple questions OR reached the 8 question limit.
- Only include the "assessment" field in your response when you have enough information to safely triage, when emergency red flags are identified, OR when you've reached 8 questions.
- If you don't have enough information yet AND haven't reached 8 questions, return ONLY "nextQuestion" without the "assessment" field.
- Stop questioning once you can safely place the case into a triage level, or label UNCERTAIN if insufficient info.

Triage levels:
- EMERGENCY: needs ER/911 now
- URGENT: same-day urgent care evaluation
- NON_URGENT: see clinician in 1–3 days
- SELF_CARE: home care + monitor
- UNCERTAIN: cannot safely triage; recommend clinician/811

JSON output schema:
{
  "caseStatus": "in_progress|completed|escalated",
  "disclaimer": { "shown": true, "consent": true|false },
  "questions": [ { "id": "string", "question": "string", "answer": "string|null" } ],
  "intake": {
    "pregnant": true|false|"unknown",
    "chiefComplaint": "string",
    "symptoms": ["string"],
    "severity": 0-10|"unknown",
    "onset": "string",
    "pattern": "string",
    "redFlags": { "any": true|false|"unknown", "details": ["string"] },
    "history": { "conditions": ["string"], "meds": ["string"], "allergies": ["string"] },
    "vitals": { "tempC": "number|unknown", "hr": "number|unknown", "spo2": "number|unknown" }
  },
  "assessment": {
    "triageLevel": "EMERGENCY|URGENT|NON_URGENT|SELF_CARE|UNCERTAIN",
    "confidence": 0.0-1.0,
    "reasons": ["string"],
    "nextSteps": ["string"],
    "monitoringPlan": ["string"],
    "escalationTriggers": ["string"],
    "intakeSummary": "string"
  },
  "nextQuestion": { "id": "string", "question": "string" } | null
}`;

interface GeminiResponse {
  caseStatus: 'in_progress' | 'completed' | 'escalated';
  disclaimer: { shown: boolean; consent: boolean };
  questions: Array<{ id: string; question: string; answer: string | null }>;
  intake: {
    pregnant?: boolean | 'unknown';
    chiefComplaint?: string;
    symptoms: string[];
    severity?: number | 'unknown';
    onset?: string;
    pattern?: string;
    redFlags: { any: boolean | 'unknown'; details: string[] };
    history: { conditions: string[]; meds: string[]; allergies: string[] };
    vitals: { tempC?: number | 'unknown'; hr?: number | 'unknown'; spo2?: number | 'unknown' };
  };
  assessment?: {
    triageLevel: 'EMERGENCY' | 'URGENT' | 'NON_URGENT' | 'SELF_CARE' | 'UNCERTAIN';
    confidence: number;
    reasons: string[];
    nextSteps: string[];
    monitoringPlan: string[];
    escalationTriggers: string[];
    intakeSummary: string;
  };
  nextQuestion: { id: string; question: string } | null;
}

// Helper function to check if a question type has already been asked
function hasQuestionBeenAsked(
  questionsAsked: Array<{ id: string; question: string; answer: string | null }>,
  questionId: string,
  questionText?: string
): boolean {
  // Check by ID
  const foundById = questionsAsked.some(q => 
    q.id.toLowerCase() === questionId.toLowerCase() ||
    q.id.toLowerCase().includes(questionId.toLowerCase()) ||
    questionId.toLowerCase().includes(q.id.toLowerCase())
  );
  
  if (foundById) return true;
  
  // Check by content for specific question types
  if (questionId.includes('severity') || questionId.includes('scale')) {
    return questionsAsked.some(q => 
      q.id.toLowerCase().includes('severity') ||
      q.id.toLowerCase().includes('scale') ||
      q.question.toLowerCase().includes('scale') ||
      q.question.toLowerCase().includes('0-10') ||
      q.question.toLowerCase().includes('1-10')
    );
  }
  
  if (questionId.includes('location') || questionId.includes('bodyPart') || questionId.includes('where')) {
    return questionsAsked.some(q => 
      q.id.toLowerCase().includes('location') ||
      q.id.toLowerCase().includes('bodypart') ||
      q.id.toLowerCase().includes('where') ||
      q.question.toLowerCase().includes('where is the pain') ||
      q.question.toLowerCase().includes('location') ||
      q.question.toLowerCase().includes('body part')
    );
  }
  
  // Check by question text if provided
  if (questionText) {
    const questionLower = questionText.toLowerCase();
    if (questionLower.includes('scale') && (questionLower.includes('0-10') || questionLower.includes('1-10'))) {
      return questionsAsked.some(q => {
        const qLower = q.question.toLowerCase();
        return qLower.includes('scale') && (qLower.includes('0-10') || qLower.includes('1-10'));
      });
    }
    if (questionLower.includes('where') && questionLower.includes('pain')) {
      return questionsAsked.some(q => {
        const qLower = q.question.toLowerCase();
        return qLower.includes('where') && qLower.includes('pain');
      });
    }
  }
  
  return false;
}

function mockGeminiResponse(caseData: CaseDocument, answer: string): GeminiResponse {
  const questionCount = caseData.assistant.questionsAsked.length;
  
  // Question sequence (max 8 questions):
  // 0: Consent
  // 1: Chief Complaint (with body diagram)
  // 2: Severity (0-10 scale)
  // 3: Onset (when did it start)
  // 4: Associated Symptoms
  // 5: Red Flags (emergency screening)
  // 6: Medical History
  // 7: Medications
  // Then: Complete with assessment
  
  if (questionCount === 0) {
    // After consent, go directly to chief complaint (age is always provided externally)
    return {
      caseStatus: 'in_progress',
      disclaimer: { shown: true, consent: true },
      questions: [{ id: 'consent', question: 'Do you consent to using this pre-triage tool?', answer: answer }],
      intake: {
        symptoms: [],
        redFlags: { any: 'unknown', details: [] },
        history: { conditions: [], meds: [], allergies: [] },
        vitals: {},
      },
      nextQuestion: { id: 'chiefComplaint', question: 'What is your main concern or symptom today?' },
    };
  }
  
  if (questionCount === 1) {
    // This is the chief complaint answer (after consent)
    // Check if severity has already been asked
    const severityAlreadyAsked = hasQuestionBeenAsked(caseData.assistant.questionsAsked, 'severity');
    const nextQ = severityAlreadyAsked 
      ? { id: 'onset', question: 'When did this symptom start? (e.g., "2 hours ago", "yesterday morning", "3 days ago")' }
      : { id: 'severity', question: 'On a scale of 0-10, how severe is this symptom? (0 = no discomfort, 10 = worst possible)' };
    
    return {
      caseStatus: 'in_progress',
      disclaimer: { shown: true, consent: true },
      questions: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes' },
        { id: 'chiefComplaint', question: 'What is your main concern?', answer: answer },
      ],
      intake: {
        chiefComplaint: answer,
        symptoms: [answer],
        redFlags: { any: 'unknown', details: [] },
        history: { conditions: [], meds: [], allergies: [] },
        vitals: {},
      },
      nextQuestion: nextQ,
    };
  }
  
  if (questionCount === 2) {
    // This is the severity answer (after consent + chief complaint)
    // Check if severity was actually asked, or if we need to ask it now
    const severityAlreadyAsked = hasQuestionBeenAsked(caseData.assistant.questionsAsked, 'severity');
    const severityValue = severityAlreadyAsked 
      ? (caseData.intake.severity || parseInt(answer) || 'unknown')
      : (parseInt(answer) || 'unknown');
    
    // If severity wasn't asked yet, we just answered it, so ask onset next
    // If severity was already asked, we might have answered something else, check what to ask next
    const onsetAlreadyAsked = hasQuestionBeenAsked(caseData.assistant.questionsAsked, 'onset');
    const nextQ = onsetAlreadyAsked
      ? { id: 'associatedSymptoms', question: 'Are there any other symptoms you\'re experiencing? (e.g., fever, nausea, dizziness)' }
      : { id: 'onset', question: 'When did this symptom start? (e.g., "2 hours ago", "yesterday morning", "3 days ago")' };
    
    return {
      caseStatus: 'in_progress',
      disclaimer: { shown: true, consent: true },
      questions: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes' },
        { id: 'chiefComplaint', question: 'What is your main concern?', answer: caseData.intake.chiefComplaint || 'Headache' },
        { id: severityAlreadyAsked ? 'onset' : 'severity', question: severityAlreadyAsked ? 'When did this start?' : 'Severity?', answer: answer },
      ],
      intake: {
        chiefComplaint: caseData.intake.chiefComplaint || 'Headache',
        symptoms: [caseData.intake.chiefComplaint || 'Headache'],
        severity: severityValue,
        redFlags: { any: 'unknown', details: [] },
        history: { conditions: [], meds: [], allergies: [] },
        vitals: {},
      },
      nextQuestion: nextQ,
    };
  }
  
  if (questionCount === 3) {
    // This is the onset answer
    return {
      caseStatus: 'in_progress',
      disclaimer: { shown: true, consent: true },
      questions: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes' },
        { id: 'chiefComplaint', question: 'What is your main concern?', answer: caseData.intake.chiefComplaint || 'Headache' },
        { id: 'severity', question: 'Severity?', answer: String(caseData.intake.severity || '5') },
        { id: 'onset', question: 'When did this start?', answer: answer },
      ],
      intake: {
        chiefComplaint: caseData.intake.chiefComplaint || 'Headache',
        symptoms: [caseData.intake.chiefComplaint || 'Headache'],
        severity: caseData.intake.severity || 'unknown',
        onset: answer,
        redFlags: { any: 'unknown', details: [] },
        history: { conditions: [], meds: [], allergies: [] },
        vitals: {},
      },
      nextQuestion: { id: 'associatedSymptoms', question: 'Are there any other symptoms you\'re experiencing? (e.g., fever, nausea, dizziness)' },
    };
  }
  
  if (questionCount === 4) {
    // This is the associatedSymptoms answer
    return {
      caseStatus: 'in_progress',
      disclaimer: { shown: true, consent: true },
      questions: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes' },
        { id: 'chiefComplaint', question: 'What is your main concern?', answer: caseData.intake.chiefComplaint || 'Headache' },
        { id: 'severity', question: 'Severity?', answer: String(caseData.intake.severity || '5') },
        { id: 'onset', question: 'When did this start?', answer: caseData.intake.onset || 'Today' },
        { id: 'associatedSymptoms', question: 'Other symptoms?', answer: answer },
      ],
      intake: {
        chiefComplaint: caseData.intake.chiefComplaint || 'Headache',
        symptoms: [caseData.intake.chiefComplaint || 'Headache', ...(answer.toLowerCase() !== 'no' && answer.toLowerCase() !== 'none' ? [answer] : [])],
        severity: caseData.intake.severity || 'unknown',
        onset: caseData.intake.onset || 'Today',
        redFlags: { any: 'unknown', details: [] },
        history: { conditions: [], meds: [], allergies: [] },
        vitals: {},
      },
      nextQuestion: { id: 'redFlags', question: 'Are you experiencing any of the following: chest pain, severe difficulty breathing, loss of consciousness, severe allergic reaction, uncontrolled bleeding, or signs of stroke? (Yes/No)' },
    };
  }
  
  if (questionCount === 5) {
    // This is the redFlags answer
    const hasRedFlags = answer.toLowerCase().includes('yes') || answer.toLowerCase().includes('y');
    return {
      caseStatus: hasRedFlags ? 'escalated' : 'in_progress',
      disclaimer: { shown: true, consent: true },
      questions: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes' },
        { id: 'chiefComplaint', question: 'What is your main concern?', answer: caseData.intake.chiefComplaint || 'Headache' },
        { id: 'severity', question: 'Severity?', answer: String(caseData.intake.severity || '5') },
        { id: 'onset', question: 'When did this start?', answer: caseData.intake.onset || 'Today' },
        { id: 'associatedSymptoms', question: 'Other symptoms?', answer: caseData.intake.symptoms.slice(1).join(', ') || 'None' },
        { id: 'redFlags', question: 'Emergency red flags?', answer: answer },
      ],
      intake: {
        chiefComplaint: caseData.intake.chiefComplaint || 'Headache',
        symptoms: caseData.intake.symptoms || [],
        severity: caseData.intake.severity || 'unknown',
        onset: caseData.intake.onset || 'Today',
        redFlags: { any: hasRedFlags, details: hasRedFlags ? [answer] : [] },
        history: { conditions: [], meds: [], allergies: [] },
        vitals: {},
      },
      nextQuestion: hasRedFlags ? null : { id: 'history', question: 'Do you have any existing medical conditions we should know about? (If none, type "none")' },
      assessment: hasRedFlags ? {
        triageLevel: 'EMERGENCY' as const,
        confidence: 0.9,
        reasons: ['Emergency red flags identified'],
        nextSteps: ['Call 911 or local emergency services immediately', 'Do not drive yourself if unsafe'],
        monitoringPlan: [],
        escalationTriggers: [],
        intakeSummary: 'Emergency red flags present. Immediate medical attention required.',
      } : undefined,
    };
  }
  
  if (questionCount === 6) {
    // This is the history answer
    return {
      caseStatus: 'in_progress',
      disclaimer: { shown: true, consent: true },
      questions: [
        { id: 'consent', question: 'Do you consent?', answer: 'yes' },
        { id: 'chiefComplaint', question: 'What is your main concern?', answer: caseData.intake.chiefComplaint || 'Headache' },
        { id: 'severity', question: 'Severity?', answer: String(caseData.intake.severity || '5') },
        { id: 'onset', question: 'When did this start?', answer: caseData.intake.onset || 'Today' },
        { id: 'associatedSymptoms', question: 'Other symptoms?', answer: caseData.intake.symptoms.slice(1).join(', ') || 'None' },
        { id: 'redFlags', question: 'Emergency red flags?', answer: 'No' },
        { id: 'history', question: 'Medical conditions?', answer: answer },
      ],
      intake: {
        chiefComplaint: caseData.intake.chiefComplaint || 'Headache',
        symptoms: caseData.intake.symptoms || [],
        severity: caseData.intake.severity || 'unknown',
        onset: caseData.intake.onset || 'Today',
        redFlags: { any: false, details: [] },
        history: { conditions: answer.toLowerCase() !== 'none' ? [answer] : [], meds: [], allergies: [] },
        vitals: {},
      },
      nextQuestion: { id: 'medications', question: 'Are you currently taking any medications? (If none, type "none")' },
    };
  }
  
  // Complete after 7+ questions (medications is the last question - 8 questions total including consent)
  return {
    caseStatus: 'completed',
    disclaimer: { shown: true, consent: true },
    questions: [
      { id: 'consent', question: 'Do you consent?', answer: 'yes' },
      { id: 'chiefComplaint', question: 'What is your main concern?', answer: caseData.intake.chiefComplaint || 'Headache' },
      { id: 'severity', question: 'Severity?', answer: String(caseData.intake.severity || '5') },
      { id: 'onset', question: 'When did this start?', answer: caseData.intake.onset || 'Today' },
      { id: 'associatedSymptoms', question: 'Other symptoms?', answer: caseData.intake.symptoms.slice(1).join(', ') || 'None' },
      { id: 'redFlags', question: 'Emergency red flags?', answer: 'No' },
      { id: 'history', question: 'Medical conditions?', answer: caseData.intake.history?.conditions.join(', ') || 'None' },
      { id: 'medications', question: 'Medications?', answer: answer },
    ],
    intake: {
      chiefComplaint: caseData.intake.chiefComplaint || 'Headache',
      symptoms: caseData.intake.symptoms || [],
      severity: caseData.intake.severity || 'unknown',
      onset: caseData.intake.onset || 'Today',
      redFlags: { any: false, details: [] },
      history: {
        conditions: caseData.intake.history?.conditions || [],
        meds: answer.toLowerCase() !== 'none' ? [answer] : [],
        allergies: [],
      },
      vitals: {},
    },
    assessment: {
      triageLevel: 'NON_URGENT',
      confidence: 0.75,
      reasons: ['Mild to moderate symptoms without emergency red flags', 'No concerning medical history'],
      nextSteps: ['Monitor symptoms at home', 'Consider over-the-counter pain relief if appropriate', 'See a healthcare provider if symptoms worsen or persist beyond 48 hours'],
      monitoringPlan: ['Watch for worsening symptoms', 'Note any new symptoms', 'Track symptom severity'],
      escalationTriggers: ['Severe worsening of symptoms', 'New concerning symptoms develop', 'Symptoms persist beyond 48 hours', 'Fever develops'],
      intakeSummary: `Patient (age: ${caseData.user.age || 'unknown'}) presents with ${caseData.intake.chiefComplaint || 'symptoms'}, moderate severity (${caseData.intake.severity || 'unknown'}/10), onset ${caseData.intake.onset || 'recently'}. No emergency red flags identified. Medical history: ${caseData.intake.history?.conditions.join(', ') || 'none'}. Recommend non-urgent follow-up.`,
    },
    nextQuestion: null,
  };
}

export async function callGemini(caseData: CaseDocument, lastAnswer: string): Promise<GeminiResponse> {
  if (TEST_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return mockGeminiResponse(caseData, lastAnswer);
  }

  if (!GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY is not set');
  }

  const genAI = new GoogleGenerativeAI(GEMINI_API_KEY);
  
  // The SDK v0.24.1 uses v1beta API which may not support newer models
  // Try 'models/gemini-pro' format or enable TEST_MODE in .env.local
  // For now, we'll catch the error and provide helpful message
  const model = genAI.getGenerativeModel({ model: 'gemini-2.5-flash' });

  const caseJson = JSON.stringify({
    status: caseData.status,
    user: caseData.user,
    intake: caseData.intake,
    assistant: {
      questionsAsked: caseData.assistant.questionsAsked,
      triageLevel: caseData.assistant.triageLevel,
    },
  }, null, 2);

  const prompt = `${SYSTEM_PROMPT}

Current case data:
${caseJson}

Last answer provided: "${lastAnswer}"

Based on the current case data and the last answer, return the next question or final assessment as valid JSON only. No markdown, no code blocks, just the raw JSON object.`;

  let response;
  let text;
  let parsed: GeminiResponse;

  try {
    response = await model.generateContent(prompt);
    text = response.response.text();
    
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      text = jsonMatch[0];
    }
    
    parsed = JSON.parse(text);
  } catch (error: any) {
    if (error.message?.includes('JSON')) {
      const retryPrompt = `${prompt}\n\nIMPORTANT: Return valid JSON only. No markdown, no code blocks, no explanations. Just the raw JSON object.`;
      try {
        response = await model.generateContent(retryPrompt);
        text = response.response.text();
        
        const jsonMatch = text.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          text = jsonMatch[0];
        }
        
        parsed = JSON.parse(text);
      } catch (retryError) {
        throw new Error(`Failed to parse Gemini response after retry: ${retryError}`);
      }
    } else if (error.message?.includes('404') || error.message?.includes('not found')) {
      // Model not found - the SDK v0.24.1 uses v1beta API which doesn't support newer models
      const errorMsg = `
Gemini API Error: Model not found for API version v1beta.

QUICK FIX - Enable TEST_MODE in .env.local:
Add this line: TEST_MODE=true
This will use mocked responses so you can continue development.

PERMANENT FIX - Update the SDK:
Run: npm install @google/generative-ai@latest
Then restart your dev server.

The SDK version 0.24.1 uses v1beta API which doesn't support:
- gemini-1.5-flash
- gemini-1.5-pro  
- gemini-3-pro-preview

After updating, these models should work.

Original error: ${error.message}
      `.trim();
      throw new Error(errorMsg);
    } else {
      throw new Error(`Gemini API error: ${error.message}`);
    }
  }

  // Validate that we're not asking duplicate questions
  if (parsed.nextQuestion) {
    const questionId = parsed.nextQuestion.id.toLowerCase();
    const questionText = parsed.nextQuestion.question.toLowerCase();
    
    // Check if this is a severity/scale question that's already been asked
    if ((questionId.includes('severity') || questionId.includes('scale') || 
         questionText.includes('scale') && (questionText.includes('0-10') || questionText.includes('1-10')))) {
      if (hasQuestionBeenAsked(caseData.assistant.questionsAsked, 'severity', parsed.nextQuestion.question)) {
        // Skip this question and move to next or complete
        if (caseData.assistant.questionsAsked.length >= 5) {
          // We have enough questions, provide assessment
          parsed.nextQuestion = null;
          if (!parsed.assessment) {
            parsed.assessment = {
              triageLevel: 'NON_URGENT',
              confidence: 0.7,
              reasons: ['Initial assessment completed'],
              nextSteps: ['Monitor symptoms'],
              monitoringPlan: [],
              escalationTriggers: [],
              intakeSummary: 'Assessment completed based on provided information.',
            };
            parsed.caseStatus = 'completed';
          }
        } else {
          // Try to get a different question - this shouldn't happen often with proper AI
          parsed.nextQuestion = { id: 'onset', question: 'When did this symptom start?' };
        }
      }
    }
    
    // Check if this is a location/body part question that's already been asked
    if (questionId.includes('location') || questionId.includes('bodypart') || questionId.includes('where') ||
        (questionText.includes('where') && questionText.includes('pain'))) {
      if (parsed.nextQuestion && hasQuestionBeenAsked(caseData.assistant.questionsAsked, 'location', parsed.nextQuestion.question)) {
        // Skip this question and move to next
        if (caseData.assistant.questionsAsked.length >= 5) {
          parsed.nextQuestion = null;
          if (!parsed.assessment) {
            parsed.assessment = {
              triageLevel: 'NON_URGENT',
              confidence: 0.7,
              reasons: ['Initial assessment completed'],
              nextSteps: ['Monitor symptoms'],
              monitoringPlan: [],
              escalationTriggers: [],
              intakeSummary: 'Assessment completed based on provided information.',
            };
            parsed.caseStatus = 'completed';
          }
        } else {
          parsed.nextQuestion = { id: 'onset', question: 'When did this symptom start?' };
        }
      }
    }
  }

  return parsed;
}

