'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, Suspense } from 'react';

function ConsentContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseId = searchParams.get('caseId');
  const hospitalSlug = searchParams.get('hospitalSlug');

  const handleContinue = async () => {
    if (!caseId) return;

    try {
      const response = await fetch(`/api/cases/${caseId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answer: 'yes',
          questionId: 'consent',
          question: 'Do you consent to using this pre-triage tool?',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to process consent');
      }

      const data = await response.json();
      
      // Store nextQuestion in sessionStorage if available
      if (data.nextQuestion) {
        sessionStorage.setItem(`nextQuestion_${caseId}`, JSON.stringify(data.nextQuestion));
      }
      
      // Redirect to health card scanning (optional step) - preserve hospital slug
      const healthcardUrl = hospitalSlug 
        ? `/healthcard?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
        : `/healthcard?caseId=${caseId}`;
      router.push(healthcardUrl);
    } catch (error) {
      console.error('Error processing consent:', error);
      alert('Failed to proceed. Please try again.');
    }
  };

  if (!caseId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-red-600">Invalid case ID</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">Before We Start</h1>
          <p className="text-sm text-gray-600 text-center">Quick information about this tool</p>
        </div>

        <div className="space-y-3 mb-6">
          <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-5">
            <p className="font-bold text-gray-900 mb-1">This tool will:</p>
            <p className="text-sm text-gray-700 leading-relaxed">
              Ask questions about your symptoms, assess urgency, and create a summary for healthcare providers
            </p>
          </div>

          <div className="bg-gradient-to-r from-yellow-50 to-yellow-100 rounded-xl p-5">
            <p className="font-bold text-gray-900 mb-1">Important:</p>
            <p className="text-sm text-gray-700 leading-relaxed">
              This is <strong>not a diagnosis</strong>. It's for information only and doesn't replace a doctor's care.
            </p>
          </div>

          <div className="bg-gradient-to-r from-green-50 to-green-100 rounded-xl p-5">
            <p className="font-bold text-gray-900 mb-1">Privacy:</p>
            <p className="text-sm text-gray-700 leading-relaxed">
              Your answers are stored anonymously and securely
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <button
            onClick={handleContinue}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-5 rounded-xl transition-colors shadow-lg active:scale-95 text-lg"
          >
            Accept and Continue
          </button>
          <button
            onClick={() => router.push('/')}
            className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 rounded-xl transition-colors active:scale-95"
          >
            ← Go Back
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ConsentPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <ConsentContent />
    </Suspense>
  );
}

