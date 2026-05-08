'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, Suspense } from 'react';

function ContactContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseId = searchParams.get('caseId');
  const hospitalSlug = searchParams.get('hospitalSlug');
  const [phone, setPhone] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const formatPhoneNumber = (value: string) => {
    // Remove all non-numeric characters
    const phoneNumber = value.replace(/\D/g, '');
    
    // Format as (XXX) XXX-XXXX
    if (phoneNumber.length <= 3) {
      return phoneNumber;
    } else if (phoneNumber.length <= 6) {
      return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3)}`;
    } else {
      return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3, 6)}-${phoneNumber.slice(6, 10)}`;
    }
  };

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatPhoneNumber(e.target.value);
    setPhone(formatted);
    setError('');
  };

  const validatePhone = (phoneStr: string) => {
    const digits = phoneStr.replace(/\D/g, '');
    return digits.length === 10;
  };

  const handleContinue = async () => {
    if (!caseId) return;

    // Validate phone if provided
    if (phone && !validatePhone(phone)) {
      setError('Please enter a valid 10-digit phone number');
      return;
    }

    setSaving(true);
    try {
      // Update case with phone number
      if (phone) {
        const phoneDigits = phone.replace(/\D/g, '');
        const response = await fetch(`/api/cases/${caseId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            phone: phoneDigits,
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to save phone number');
        }
      }

      // Continue to intake - preserve hospital slug
      const intakeUrl = hospitalSlug 
        ? `/intake?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
        : `/intake?caseId=${caseId}`;
      router.push(intakeUrl);
    } catch (error) {
      console.error('Error saving phone:', error);
      setError('Failed to save. Please try again.');
      setSaving(false);
    }
  };

  const handleSkip = () => {
    if (!caseId) return;
    const intakeUrl = hospitalSlug 
      ? `/intake?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
      : `/intake?caseId=${caseId}`;
    router.push(intakeUrl);
  };

  if (!caseId) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <p className="text-red-600">Invalid case ID</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
            Contact Information
          </h1>
          <p className="text-sm text-gray-600 text-center">
            Optional - helps us reach you with updates
          </p>
        </div>

        <div className="bg-blue-50 rounded-xl p-5 mb-6">
          <p className="text-sm text-gray-700 leading-relaxed mb-3">
            <strong>Why provide your phone number?</strong>
          </p>
          <ul className="text-sm text-gray-700 space-y-1">
            <li>• Receive updates about your visit</li>
            <li>• Get notified when it's your turn</li>
            <li>• Allow staff to contact you if needed</li>
          </ul>
          <p className="text-xs text-gray-600 mt-3">
            🔒 Your phone number is kept confidential and only used for this visit.
          </p>
        </div>

        <div className="mb-6">
          <label htmlFor="phone" className="block text-sm font-semibold text-gray-700 mb-2">
            Phone Number
          </label>
          <input
            type="tel"
            id="phone"
            value={phone}
            onChange={handlePhoneChange}
            placeholder="(555) 123-4567"
            maxLength={14}
            className={`w-full px-4 py-4 text-lg border-2 ${
              error ? 'border-red-500' : 'border-gray-300'
            } rounded-xl focus:outline-none focus:border-blue-500 transition`}
          />
          {error && (
            <p className="mt-2 text-sm text-red-600">{error}</p>
          )}
          <p className="mt-2 text-xs text-gray-500">
            Format: (XXX) XXX-XXXX
          </p>
        </div>

        <div className="space-y-3">
          <button
            onClick={handleContinue}
            disabled={saving}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold py-5 rounded-xl transition-colors shadow-lg active:scale-95"
          >
            {saving ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Saving...
              </span>
            ) : (
              'Continue'
            )}
          </button>

          <button
            onClick={handleSkip}
            disabled={saving}
            className="w-full bg-white hover:bg-gray-50 text-gray-600 font-semibold py-3 rounded-xl transition-colors border border-gray-300 disabled:opacity-50"
          >
            Skip for Now
          </button>
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={() => router.back()}
            disabled={saving}
            className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-50"
          >
            ← Go Back
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ContactPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <ContactContent />
    </Suspense>
  );
}

