import { NextRequest, NextResponse } from 'next/server';
import connectDB from '@/lib/mongodb';
import Case from '@/models/Case';
import { callGemini } from '@/lib/gemini';

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await connectDB();

    const { id } = params;
    const body = await request.json();
    const { answer, questionId, question } = body;

    if (!answer || answer === null || answer === undefined) {
      return NextResponse.json({ error: 'Answer is required' }, { status: 400 });
    }

    const caseDoc = await Case.findById(id);

    if (!caseDoc) {
      return NextResponse.json({ error: 'Case not found' }, { status: 404 });
    }

    // Check if this question has already been asked
    const questionsAsked = caseDoc.assistant.questionsAsked || [];
    const questionIdLower = (questionId || '').toLowerCase();
    const questionTextLower = (question || '').toLowerCase();
    
    // Check for duplicate severity/scale questions
    if (questionIdLower.includes('severity') || questionIdLower.includes('scale') ||
        (questionTextLower.includes('scale') && (questionTextLower.includes('0-10') || questionTextLower.includes('1-10')))) {
      const alreadyAsked = questionsAsked.some((q: { id: string; question: string; answer: string | null }) => {
        const qId = q.id.toLowerCase();
        const qText = q.question.toLowerCase();
        return qId.includes('severity') || qId.includes('scale') ||
               (qText.includes('scale') && (qText.includes('0-10') || qText.includes('1-10')));
      });
      if (alreadyAsked) {
        return NextResponse.json({ 
          error: 'This question has already been asked. Please continue with the next question.',
          case: caseDoc 
        }, { status: 400 });
      }
    }
    
    // Check for duplicate location/body part questions
    if (questionIdLower.includes('location') || questionIdLower.includes('bodypart') || questionIdLower.includes('where') ||
        (questionTextLower.includes('where') && questionTextLower.includes('pain'))) {
      const alreadyAsked = questionsAsked.some((q: { id: string; question: string; answer: string | null }) => {
        const qId = q.id.toLowerCase();
        const qText = q.question.toLowerCase();
        return qId.includes('location') || qId.includes('bodypart') || qId.includes('where') ||
               (qText.includes('where') && qText.includes('pain'));
      });
      if (alreadyAsked) {
        return NextResponse.json({ 
          error: 'This question has already been asked. Please continue with the next question.',
          case: caseDoc 
        }, { status: 400 });
      }
    }

    const answerStr = typeof answer === 'string' ? answer : JSON.stringify(answer);

    const questionAsked = {
      id: questionId || `q${Date.now()}`,
      question: question || 'Question',
      answer: answerStr,
      timestamp: new Date(),
    };

    caseDoc.assistant.questionsAsked.push(questionAsked);
    await caseDoc.save();

    const geminiResponse = await callGemini(caseDoc, answerStr);

    if (geminiResponse.intake) {
      if (geminiResponse.intake.pregnant !== undefined) {
        caseDoc.user.pregnant = geminiResponse.intake.pregnant;
      }
      if (geminiResponse.intake.chiefComplaint) {
        caseDoc.intake.chiefComplaint = geminiResponse.intake.chiefComplaint;
      }
      if (geminiResponse.intake.symptoms) {
        caseDoc.intake.symptoms = geminiResponse.intake.symptoms;
      }
      if (geminiResponse.intake.severity !== undefined) {
        caseDoc.intake.severity = geminiResponse.intake.severity;
      }
      if (geminiResponse.intake.onset) {
        caseDoc.intake.onset = geminiResponse.intake.onset;
      }
      if (geminiResponse.intake.pattern) {
        caseDoc.intake.pattern = geminiResponse.intake.pattern;
      }
      if (geminiResponse.intake.redFlags) {
        caseDoc.intake.redFlags = geminiResponse.intake.redFlags;
      }
      if (geminiResponse.intake.history) {
        caseDoc.intake.history = geminiResponse.intake.history;
      }
      if (geminiResponse.intake.vitals) {
        caseDoc.intake.vitals = geminiResponse.intake.vitals;
      }
    }

    // Only set assessment if we have enough information (at least 5 questions asked: consent + chief complaint + severity + onset + associated symptoms + red flags)
    // Exception: EMERGENCY cases should be allowed immediately
    // Cap: Force completion after 8 questions maximum
    const minQuestionsRequired = 5;
    const maxQuestionsAllowed = 8;
    const isEmergencyCase = geminiResponse.assessment?.triageLevel === 'EMERGENCY';
    const hasEnoughQuestions = caseDoc.assistant.questionsAsked.length >= minQuestionsRequired;
    const reachedMaxQuestions = caseDoc.assistant.questionsAsked.length >= maxQuestionsAllowed;
    
    // Force completion if we've reached the max questions, even if Gemini didn't provide an assessment
    if (reachedMaxQuestions && !geminiResponse.assessment) {
      // Generate a default assessment if we've hit the limit
      geminiResponse.assessment = {
        triageLevel: 'NON_URGENT',
        confidence: 0.7,
        reasons: ['Completed initial assessment', 'No emergency red flags identified'],
        nextSteps: ['Monitor symptoms at home', 'Consider follow-up with healthcare provider if symptoms worsen'],
        monitoringPlan: ['Track symptom changes', 'Note any new symptoms'],
        escalationTriggers: ['Severe worsening', 'New concerning symptoms'],
        intakeSummary: `Initial triage assessment completed. Patient presents with ${caseDoc.intake.chiefComplaint || 'symptoms'}.`
      };
      geminiResponse.nextQuestion = null;
      caseDoc.status = 'completed';
    }
    
    if (geminiResponse.assessment && (hasEnoughQuestions || isEmergencyCase || reachedMaxQuestions)) {
      caseDoc.assistant.triageLevel = geminiResponse.assessment.triageLevel;
      caseDoc.assistant.confidence = geminiResponse.assessment.confidence;
      caseDoc.assistant.reasons = geminiResponse.assessment.reasons;
      caseDoc.assistant.nextSteps = geminiResponse.assessment.nextSteps;
      caseDoc.assistant.monitoringPlan = geminiResponse.assessment.monitoringPlan;
      caseDoc.assistant.escalationTriggers = geminiResponse.assessment.escalationTriggers;
      caseDoc.assistant.intakeSummary = geminiResponse.assessment.intakeSummary;
      caseDoc.status = geminiResponse.caseStatus as 'in_progress' | 'completed' | 'escalated';
      
      // When triage is completed, set workflowStatus to pending_review
      // (unless already assigned to hospital via QR code)
      if (caseDoc.status === 'completed' && !caseDoc.hospitalRouting?.hospitalId) {
        caseDoc.workflowStatus = 'pending_review';
      }
    }

    caseDoc.assistant.disclaimerShown = geminiResponse.disclaimer.shown;
    await caseDoc.save();

    return NextResponse.json({
      case: caseDoc,
      nextQuestion: geminiResponse.nextQuestion,
    });
  } catch (error: any) {
    console.error('Error processing answer:', error);
    return NextResponse.json({ error: error.message || 'Failed to process answer' }, { status: 500 });
  }
}

