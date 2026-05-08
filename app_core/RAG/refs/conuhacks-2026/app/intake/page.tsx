'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect, Suspense } from 'react';
import BodyDiagram from '../components/BodyDiagram';

interface Question {
  id: string;
  question: string;
}

interface CaseData {
  _id: string;
  status: string;
  assessmentType: 'in_hospital' | 'remote';
  user: {
    age?: number;
    healthCardScan?: {
      scanned: boolean;
      ageSet: boolean;
      dateOfBirth?: string;
      name?: string;
      sex?: string;
      healthCardNumber?: string;
      versionCode?: string;
      expiryDate?: string;
      confidence?: 'high' | 'medium' | 'low';
      scannedAt?: string;
      fieldsExtracted?: {
        name: boolean;
        dateOfBirth: boolean;
        sex: boolean;
        expiryDate: boolean;
        healthCardNumber: boolean;
        versionCode: boolean;
      };
    };
  };
  assistant: {
    questionsAsked: Array<{ id: string; question: string; answer: string | null }>;
    triageLevel?: string;
  };
}

function IntakeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseId = searchParams.get('caseId');
  const hospitalSlug = searchParams.get('hospitalSlug');
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedBodyParts, setSelectedBodyParts] = useState<string[]>([]);
  const [showBodyDiagram, setShowBodyDiagram] = useState(false);
  const [sliderTouched, setSliderTouched] = useState(false);

  useEffect(() => {
    if (!caseId) return;

    const fetchCase = async () => {
      try {
        // Check sessionStorage for nextQuestion first
        const storedNextQuestion = sessionStorage.getItem(`nextQuestion_${caseId}`);
        
        const response = await fetch(`/api/cases/${caseId}`);
        if (!response.ok) throw new Error('Failed to fetch case');
        const data = await response.json();
        setCaseData(data.case);

        const questionsAsked = data.case.assistant?.questionsAsked || [];
        const lastQuestion = questionsAsked[questionsAsked.length - 1];

        if (data.case.status === 'completed' || data.case.assistant?.triageLevel) {
          // ALWAYS go to media upload step first - preserve hospital slug
          const mediaUrl = hospitalSlug 
            ? `/intake/media?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
            : `/intake/media?caseId=${caseId}`;
          router.replace(mediaUrl); // Use replace to prevent back button issues
          return;
        }

        if (storedNextQuestion) {
          const nextQ = JSON.parse(storedNextQuestion);
          setCurrentQuestion(nextQ);
          sessionStorage.removeItem(`nextQuestion_${caseId}`);
          setSliderTouched(false); // Reset slider state for new question
        } else {
          // If we don't have a current question yet (and didn't get one from sessionStorage), check if there's an unanswered question
          if (lastQuestion && !lastQuestion.answer) {
            setCurrentQuestion({ id: lastQuestion.id, question: lastQuestion.question });
            setSliderTouched(false); // Reset slider state
          } else if (questionsAsked.length === 0) {
            // No questions asked yet, this shouldn't happen but handle it
            setError('No questions available. Please start over.');
          }
        }
      } catch (err: any) {
        setError(err.message);
      }
    };

    fetchCase();
  }, [caseId, hospitalSlug, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Use body diagram selection if available, otherwise use text answer
    const finalAnswer = selectedBodyParts.length > 0 
      ? selectedBodyParts.join(', ') 
      : answer.trim();
    
    if (!caseId || !currentQuestion || !finalAnswer) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/cases/${caseId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answer: finalAnswer,
          questionId: currentQuestion.id,
          question: currentQuestion.question,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to submit answer');
      }

      const data = await response.json();
      setCaseData(data.case);

      if (data.nextQuestion) {
        setCurrentQuestion(data.nextQuestion);
        setAnswer('');
        setSelectedBodyParts([]);
        setSliderTouched(false);
      } else if (data.case.status === 'completed' || data.case.assistant?.triageLevel) {
        // ALWAYS go to media upload step first - preserve hospital slug
        // Check assessmentType from fresh data
        console.log('Assessment complete, assessmentType:', data.case.assessmentType, 'hospitalSlug:', hospitalSlug);
        const mediaUrl = hospitalSlug 
          ? `/intake/media?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
          : `/intake/media?caseId=${caseId}`;
        router.replace(mediaUrl); // Use replace to prevent back button issues
        return;
      } else {
        // If no next question but not completed, wait a moment and check again
        setTimeout(async () => {
          try {
            const retryResponse = await fetch(`/api/cases/${caseId}`);
            if (retryResponse.ok) {
              const retryData = await retryResponse.json();
              if (retryData.case.status === 'completed' || retryData.case.assistant?.triageLevel) {
                // ALWAYS go to media upload step first - preserve hospital slug
                const mediaUrl = hospitalSlug 
                  ? `/intake/media?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
                  : `/intake/media?caseId=${caseId}`;
                router.replace(mediaUrl); // Use replace to prevent back button issues
              } else {
                setError('Assessment is being processed. Please wait...');
              }
            }
          } catch (err) {
            setError('Failed to get next question. Please try again.');
          }
        }, 1000);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBodyPartSelect = (bodyPart: string) => {
    if (selectedBodyParts.includes(bodyPart)) {
      // Deselect if already selected
      setSelectedBodyParts(selectedBodyParts.filter(part => part !== bodyPart));
    } else {
      // Add to selection
      setSelectedBodyParts([...selectedBodyParts, bodyPart]);
    }
  };

  // Update answer when body parts change
  useEffect(() => {
    if (selectedBodyParts.length > 0 && showBodyDiagram) {
      setAnswer(selectedBodyParts.join(', '));
    }
  }, [selectedBodyParts, showBodyDiagram]);

  // Check if current question should show body diagram
  useEffect(() => {
    if (currentQuestion) {
      const questionText = currentQuestion.question.toLowerCase();
      const shouldShow = 
        questionText.includes('where') ||
        questionText.includes('location') ||
        questionText.includes('body part') ||
        questionText.includes('area') ||
        currentQuestion.id.includes('location') ||
        currentQuestion.id.includes('chiefComplaint') ||
        currentQuestion.id.includes('bodyPart');
      setShowBodyDiagram(shouldShow);
    }
  }, [currentQuestion]);

  const handleBack = () => {
    if (!caseData || !caseId) return;

    const questionsAsked = caseData.assistant?.questionsAsked || [];
    if (questionsAsked.length > 1) {
      const previousQuestion = questionsAsked[questionsAsked.length - 2];
      setCurrentQuestion({ id: previousQuestion.id, question: previousQuestion.question });
      setAnswer(previousQuestion.answer || '');
      setSelectedBodyParts([]);
      // If going back to a previously answered question (including slider), mark as touched
      setSliderTouched(!!previousQuestion.answer);
    } else {
      router.push(`/consent?caseId=${caseId}`);
    }
  };

  if (!caseId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-red-600">Invalid case ID</p>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading question...</p>
        </div>
      </div>
    );
  }

  const questionCount = caseData?.assistant?.questionsAsked?.length || 0;
  const estimatedTotal = 8; // Maximum 8 questions

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white py-4 px-4">
      <div className="max-w-md mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-6">
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase">Progress</span>
              <span className="text-sm font-bold text-blue-600">
                {questionCount + 1}/{estimatedTotal}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-300 shadow-sm"
                style={{ width: `${Math.min(((questionCount + 1) / estimatedTotal) * 100, 100)}%` }}
              ></div>
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border-l-4 border-red-500 p-3 mb-4 rounded-r-xl">
              <p className="text-red-700 text-sm font-medium">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-lg font-bold text-gray-900 mb-4 leading-tight">
                {currentQuestion.question}
              </label>

              {showBodyDiagram && (
                <div className="mb-6">
                  <BodyDiagram
                    onBodyPartSelect={handleBodyPartSelect}
                    selectedParts={selectedBodyParts}
                  />
                  {selectedBodyParts.length > 0 && (
                    <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                      <p className="text-sm text-blue-900 font-medium mb-1">Selected areas:</p>
                      <p className="text-sm text-blue-800">{selectedBodyParts.join(', ')}</p>
                    </div>
                  )}
                  <div className="mt-3">
                    <p className="text-sm text-gray-600 mb-2">Or describe it below:</p>
                  </div>
                </div>
              )}

              {currentQuestion.id.includes('severity') || currentQuestion.question.toLowerCase().includes('scale') ? (
                <div className="space-y-4">
                  <div className="bg-gradient-to-r from-green-100 via-yellow-100 to-red-100 rounded-xl p-4">
                    <input
                      type="range"
                      min="0"
                      max="10"
                      value={answer || '5'}
                      onChange={(e) => {
                        setAnswer(e.target.value);
                        setSliderTouched(true);
                      }}
                      className="w-full h-3 bg-transparent rounded-lg appearance-none cursor-pointer"
                      style={{
                        background: `linear-gradient(to right, #10b981 0%, #fbbf24 50%, #ef4444 100%)`
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600 font-medium">0<br/><span className="text-xs">None</span></span>
                    <span className="font-bold text-2xl text-blue-600">{answer || '5'}</span>
                    <span className="text-gray-600 font-medium">10<br/><span className="text-xs">Severe</span></span>
                  </div>
                  {!sliderTouched && (
                    <p className="text-sm text-orange-600 font-medium text-center">
                      ⚠️ Please move the slider to indicate your pain level
                    </p>
                  )}
                </div>
              ) : currentQuestion.id.includes('pregnant') || currentQuestion.question.toLowerCase().includes('pregnant') ? (
                <div className="space-y-3">
                  {['Yes', 'No', 'Not applicable'].map((option) => (
                    <label key={option} className={`flex items-center space-x-3 p-4 border-2 rounded-xl cursor-pointer transition-all active:scale-95 ${answer === (option === 'Yes' ? 'true' : option === 'No' ? 'false' : 'unknown') ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:border-gray-300 bg-white'}`}>
                      <input
                        type="radio"
                        name="pregnant"
                        value={option === 'Yes' ? 'true' : option === 'No' ? 'false' : 'unknown'}
                        checked={answer === (option === 'Yes' ? 'true' : option === 'No' ? 'false' : 'unknown')}
                        onChange={(e) => setAnswer(e.target.value)}
                        className="w-5 h-5 text-blue-600"
                      />
                      <span className={`font-semibold ${answer === (option === 'Yes' ? 'true' : option === 'No' ? 'false' : 'unknown') ? 'text-blue-900' : 'text-gray-700'}`}>{option}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder="Type your answer here..."
                  className="w-full px-4 py-4 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none text-base"
                  rows={5}
                  required
                />
              )}
            </div>

            <div className="space-y-3 pt-2">
              <button
                type="submit"
                disabled={
                  loading || 
                  (!answer.trim() && selectedBodyParts.length === 0) ||
                  ((currentQuestion.id.includes('severity') || currentQuestion.question.toLowerCase().includes('scale')) && !sliderTouched)
                }
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500 text-white font-bold py-4 rounded-xl transition-colors shadow-lg active:scale-95"
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processing...
                  </span>
                ) : 'Continue'}
              </button>
              <button
                type="button"
                onClick={handleBack}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 rounded-xl transition-colors active:scale-95"
              >
                ← Back
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function IntakePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <IntakeContent />
    </Suspense>
  );
}

