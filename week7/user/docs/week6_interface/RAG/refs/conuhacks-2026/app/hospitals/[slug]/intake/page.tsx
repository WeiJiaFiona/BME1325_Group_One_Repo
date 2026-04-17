'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

interface Hospital {
  _id: string;
  name: string;
  slug: string;
  address: string;
  phone?: string;
  specialties: string[];
  maxCapacity: number;
  currentPatients: number;
  availableCapacity: number;
}

export default function HospitalIntakePage() {
  const params = useParams();
  const router = useRouter();
  const slug = params.slug as string;
  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingTriage, setStartingTriage] = useState(false);

  useEffect(() => {
    const fetchHospital = async () => {
      try {
        const response = await fetch(`/api/hospitals/${slug}`);
        if (!response.ok) {
          throw new Error('Hospital not found');
        }
        const data = await response.json();
        setHospital(data.hospital);
      } catch (err: any) {
        setError(err.message || 'Failed to load hospital information');
      } finally {
        setLoading(false);
      }
    };

    fetchHospital();
  }, [slug]);

  const startTriage = async () => {
    if (!hospital) return;

    setStartingTriage(true);
    try {
      // Get or create anonymous ID
      let anonymousId = localStorage.getItem('pretriage_anonymous_id');
      if (!anonymousId) {
        anonymousId = crypto.randomUUID();
        localStorage.setItem('pretriage_anonymous_id', anonymousId);
      }

      // Create case with hospital already associated
      const response = await fetch('/api/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          anonymousId,
          assessmentType: 'in_hospital',
          hospitalId: hospital._id,
          hospitalSlug: hospital.slug,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to create case');
      }

      const data = await response.json();
      router.push(`/consent?caseId=${data.case._id}&hospitalSlug=${hospital.slug}`);
    } catch (error) {
      console.error('Error starting triage:', error);
      alert('Failed to start triage. Please try again.');
      setStartingTriage(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center p-6">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading hospital information...</p>
        </div>
      </div>
    );
  }

  if (error || !hospital) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Hospital Not Found</h1>
          <p className="text-gray-600 mb-6">
            {error || 'The hospital you\'re looking for could not be found.'}
          </p>
          <button
            onClick={() => router.push('/')}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            Go to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-2xl w-full">
        {/* Hospital Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-10 h-10 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">{hospital.name}</h1>
          <p className="text-gray-600">{hospital.address}</p>
          {hospital.phone && (
            <p className="text-gray-500 mt-1">{hospital.phone}</p>
          )}
        </div>

        {/* Specialties */}
        {hospital.specialties && hospital.specialties.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Specialties:</h3>
            <div className="flex flex-wrap gap-2">
              {hospital.specialties.map((specialty, index) => (
                <span
                  key={index}
                  className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-full border border-blue-200"
                >
                  {specialty}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Capacity Info */}
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Current Capacity</span>
            <span className="text-sm font-semibold text-gray-900">
              {hospital.currentPatients} / {hospital.maxCapacity}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div
              className={`h-2.5 rounded-full transition-all ${
                hospital.availableCapacity / hospital.maxCapacity > 0.5
                  ? 'bg-green-500'
                  : hospital.availableCapacity / hospital.maxCapacity > 0.2
                  ? 'bg-yellow-500'
                  : 'bg-red-500'
              }`}
              style={{ width: `${((hospital.currentPatients / hospital.maxCapacity) * 100)}%` }}
            ></div>
          </div>
          <p className="text-xs text-gray-600 mt-2">
            {hospital.availableCapacity} beds available
          </p>
        </div>

        {/* Welcome Message */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-2">Welcome to {hospital.name}</h2>
          <p className="text-gray-700 mb-4">
            Start your triage assessment to help our medical team understand your condition and prioritize care.
          </p>
          <ul className="space-y-2 text-sm text-gray-600">
            <li className="flex items-start">
              <svg className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Answer a few questions about your symptoms</span>
            </li>
            <li className="flex items-start">
              <svg className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Receive a preliminary assessment</span>
            </li>
            <li className="flex items-start">
              <svg className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Join the appropriate care queue</span>
            </li>
          </ul>
        </div>

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={startTriage}
            disabled={startingTriage}
            className="w-full px-6 py-4 bg-blue-600 text-white text-lg font-semibold rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition shadow-lg hover:shadow-xl"
          >
            {startingTriage ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Starting...
              </span>
            ) : (
              'Start Triage Assessment'
            )}
          </button>
          <button
            onClick={() => router.push('/')}
            disabled={startingTriage}
            className="w-full px-6 py-3 bg-gray-100 text-gray-700 font-medium rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            Cancel
          </button>
        </div>

        {/* Disclaimer */}
        <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-xs text-yellow-800">
            <strong>Emergency:</strong> If you are experiencing a life-threatening emergency (chest pain, difficulty breathing, severe bleeding), 
            please go directly to the emergency desk or call 911 immediately.
          </p>
        </div>
      </div>
    </div>
  );
}

