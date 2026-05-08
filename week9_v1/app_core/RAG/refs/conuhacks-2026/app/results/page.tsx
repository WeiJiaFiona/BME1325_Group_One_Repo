'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect, Suspense } from 'react';

interface Hospital {
  id: string;
  name: string;
  address: string;
  distance: number | null;
  currentWait: number;
  capacity: string;
  phone: string;
  latitude: number;
  longitude: number;
}

interface CaseData {
  _id: string;
  assessmentType: 'in_hospital' | 'remote';
  workflowStatus?: string;
  location?: {
    latitude?: number;
    longitude?: number;
  };
  assistant: {
    triageLevel?: string;
    confidence?: number;
    reasons: string[];
    nextSteps: string[];
    monitoringPlan: string[];
    escalationTriggers: string[];
    intakeSummary?: string;
  };
}

function ResultsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseId = searchParams.get('caseId');
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingHospitals, setLoadingHospitals] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!caseId) return;

    const fetchCase = async () => {
      try {
        const response = await fetch(`/api/cases/${caseId}`);
        if (!response.ok) throw new Error('Failed to fetch case');
        const data = await response.json();
        
        // CRITICAL: In-hospital patients should NEVER see results page - redirect to waiting room immediately
        // Check both assessmentType and hospitalRouting as indicators
        const isInHospital = data.case.assessmentType === 'in_hospital' || 
                            data.case.hospitalRouting?.hospitalId ||
                            data.case.hospitalRouting?.hospitalName;
        
        if (isInHospital) {
          console.log('In-hospital patient detected, redirecting to waiting room', {
            assessmentType: data.case.assessmentType,
            hasHospitalRouting: !!data.case.hospitalRouting
          });
          const waitingUrl = `/waiting?caseId=${caseId}`;
          router.replace(waitingUrl); // Use replace instead of push
          return;
        }
        
        setCaseData(data.case);

        // Fetch nearby hospitals for all assessments
        // Try to get user's location if not already stored
        let latitude = data.case.location?.latitude;
        let longitude = data.case.location?.longitude;
        
        if (!latitude || !longitude) {
          // Try to get current location
          if (navigator.geolocation) {
            try {
              const position = await new Promise<GeolocationPosition>((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
              });
              latitude = position.coords.latitude;
              longitude = position.coords.longitude;
            } catch (err) {
              console.log('Could not get location, using default Montreal location:', err);
              // Default to Montreal coordinates if location not available
              latitude = 45.5017;
              longitude = -73.5673;
            }
          } else {
            // Default to Montreal coordinates
            latitude = 45.5017;
            longitude = -73.5673;
          }
        }

        setLoadingHospitals(true);
        try {
          console.log('Fetching hospitals with location:', { latitude, longitude });
          const hospitalResponse = await fetch(
            `/api/hospitals?latitude=${latitude}&longitude=${longitude}&activeOnly=true`
          );
          if (hospitalResponse.ok) {
            const hospitalData = await hospitalResponse.json();
            console.log('Fetched hospitals response:', hospitalData);
            if (hospitalData.hospitals && Array.isArray(hospitalData.hospitals)) {
              console.log(`Setting ${hospitalData.hospitals.length} hospitals`);
              setHospitals(hospitalData.hospitals);
            } else {
              console.error('Invalid hospitals data format:', hospitalData);
            }
          } else {
            const errorText = await hospitalResponse.text();
            console.error('Failed to fetch hospitals:', hospitalResponse.status, errorText);
          }
        } catch (err) {
          console.error('Error fetching hospitals:', err);
        } finally {
          setLoadingHospitals(false);
        }
      } catch (error) {
        console.error('Error fetching case:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCase();
  }, [caseId]);

  const getTriageColor = (level?: string) => {
    switch (level) {
      case 'EMERGENCY':
        return 'bg-triage-emergency text-white';
      case 'URGENT':
        return 'bg-triage-urgent text-white';
      case 'NON_URGENT':
        return 'bg-triage-non-urgent text-white';
      case 'SELF_CARE':
        return 'bg-triage-self-care text-white';
      case 'UNCERTAIN':
        return 'bg-triage-uncertain text-white';
      default:
        return 'bg-clinical-gray-600 text-white';
    }
  };

  const getTriageLabel = (level?: string) => {
    switch (level) {
      case 'EMERGENCY':
        return 'Emergency - Call 911 Now';
      case 'URGENT':
        return 'Urgent - Same-Day Care Recommended';
      case 'NON_URGENT':
        return 'Non-Urgent - See Clinician in 1-3 Days';
      case 'SELF_CARE':
        return 'Self-Care - Monitor at Home';
      case 'UNCERTAIN':
        return 'Uncertain - Consult Healthcare Provider';
      default:
        return 'Assessment Pending';
    }
  };

  const handleCopySummary = async () => {
    if (!caseData?.assistant?.intakeSummary) return;

    try {
      await navigator.clipboard.writeText(caseData.assistant.intakeSummary);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
      alert('Failed to copy. Please select and copy manually.');
    }
  };

  const handleDownload = () => {
    if (!caseData) return;

    const summary = `
PRE-TRIAGE ASSESSMENT SUMMARY
Generated: ${new Date().toLocaleString()}

TRIAGE LEVEL: ${getTriageLabel(caseData.assistant?.triageLevel)}
Confidence: ${caseData.assistant?.confidence ? (caseData.assistant.confidence * 100).toFixed(0) + '%' : 'N/A'}

REASONS:
${caseData.assistant?.reasons.map((r) => `• ${r}`).join('\n')}

NEXT STEPS:
${caseData.assistant?.nextSteps.map((s) => `• ${s}`).join('\n')}

MONITORING PLAN:
${caseData.assistant?.monitoringPlan.map((m) => `• ${m}`).join('\n')}

ESCALATION TRIGGERS:
${caseData.assistant?.escalationTriggers.map((e) => `• ${e}`).join('\n')}

INTAKE SUMMARY:
${caseData.assistant?.intakeSummary || 'N/A'}

---
DISCLAIMER: This is NOT a diagnosis. This tool is for informational purposes only and does not provide medical advice, diagnosis, or treatment. If you are experiencing a medical emergency, call 911 or your local emergency services immediately.
    `.trim();

    const blob = new Blob([summary], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pretriage-summary-${caseId}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-clinical-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-medical-blue mx-auto mb-4"></div>
          <p className="text-clinical-gray-600">Loading results...</p>
        </div>
      </div>
    );
  }

  if (!caseData || !caseData.assistant?.triageLevel) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-clinical-gray-50">
        <p className="text-triage-emergency">Results not available</p>
      </div>
    );
  }

  const isEmergency = caseData.assistant.triageLevel === 'EMERGENCY';
  const isPendingReview = caseData.workflowStatus === 'pending_review';

  return (
    <div className="min-h-screen bg-clinical-gray-50 py-4 px-4">
      <div className="max-w-md mx-auto">
        {/* Pending Review Banner */}
        {isPendingReview && (
          <div className="bg-white border-2 border-medical-blue rounded-lg p-6 mb-4 shadow-sm">
            <div className="flex items-center justify-center space-x-2 mb-2">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-medical-blue"></div>
              <h2 className="text-lg font-bold text-clinical-gray-900">Pending Review</h2>
            </div>
            <p className="text-sm text-clinical-gray-700 text-center">
              Your assessment has been submitted and is being reviewed by a healthcare professional. 
              You will be notified when an update is available.
            </p>
          </div>
        )}

        {isEmergency && (
          <div className="bg-triage-emergency text-white p-6 rounded-lg shadow-lg mb-4 border-4 border-triage-emergency-dark">
            <h2 className="text-2xl font-bold mb-3 text-center uppercase tracking-wide">EMERGENCY</h2>
            <p className="text-lg font-semibold text-center mb-2">
              Call 911 immediately
            </p>
            <p className="text-sm text-center mb-4">Do not drive yourself if unsafe. Call an ambulance.</p>
            <a
              href="tel:911"
              className="block w-full bg-white text-triage-emergency text-center font-bold py-4 rounded-lg mt-4 shadow-sm"
            >
              Call 911 Now
            </a>
          </div>
        )}

        <div className="bg-white rounded-lg border border-clinical-gray-200 shadow-sm p-6 mb-4">
          {/* Assessment Type Indicator */}
          <div className="text-center mb-4">
            <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${caseData.assessmentType === 'in_hospital' ? 'bg-primary-light text-medical-blue' : 'bg-triage-self-care-bg text-triage-self-care'}`}>
              {caseData.assessmentType === 'in_hospital' ? 'In-Hospital Assessment' : 'Remote Assessment'}
            </span>
          </div>

          {/* Hospital Recommendations - Always Show */}
          {hospitals.length > 0 && (
            <div className="mb-5">
              <h2 className="text-lg font-bold text-gray-900 mb-3">
                {caseData.assessmentType === 'in_hospital' ? 'Nearby Hospitals' : 'Hospitals'}
              </h2>
              {caseData.assessmentType === 'remote' && (
                <div className="mb-3 bg-primary-light border-l-4 border-l-medical-blue rounded p-4">
                  <p className="text-sm text-clinical-gray-800 font-semibold mb-2">
                    Please wait for review
                  </p>
                  <p className="text-xs text-clinical-gray-700">
                    Your assessment is being reviewed by a healthcare professional. Please wait for their recommendation. However, if anything changes and you need to seek immediate care, here are nearby hospitals:
                  </p>
                </div>
              )}
              {caseData.assessmentType === 'in_hospital' && (
                <div className="mb-3 bg-primary-light border-l-4 border-l-medical-blue rounded p-4">
                  <p className="text-xs text-clinical-gray-700">
                    Alternative hospitals if needed for follow-up or specialized care
                  </p>
                </div>
              )}
              <div className="space-y-3">
                {hospitals.slice(0, 3).map((hospital, idx) => (
                  <div key={hospital.id} className={`rounded-lg p-4 border ${idx === 0 ? 'bg-triage-self-care-bg border-triage-self-care-dark border-2' : 'bg-clinical-gray-50 border-clinical-gray-200'}`}>
                    {idx === 0 && (
                      <div className="inline-block bg-triage-self-care text-white text-xs font-bold px-2 py-1 rounded mb-2">
                        CLOSEST
                      </div>
                    )}
                    <h3 className="font-bold text-clinical-gray-900 text-base mb-1">{hospital.name}</h3>
                    <p className="text-sm text-clinical-gray-700 mb-2">{hospital.address}</p>
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="text-clinical-gray-600">
                        {hospital.distance !== null ? (
                          <strong>{hospital.distance} km</strong>
                        ) : (
                          <span className="text-clinical-gray-500">Distance unavailable</span>
                        )}
                        {hospital.distance !== null && <span className="ml-1">away</span>}
                      </span>
                      <span className={`font-semibold ${hospital.currentWait < 45 ? 'text-triage-self-care' : hospital.currentWait < 75 ? 'text-triage-non-urgent' : 'text-triage-emergency'}`}>
                        ~{hospital.currentWait} min wait
                      </span>
                    </div>
                    <a
                      href={`https://www.google.com/maps/dir/?api=1&destination=${hospital.latitude},${hospital.longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`block w-full ${idx === 0 ? 'bg-triage-self-care hover:bg-triage-self-care-dark' : 'bg-medical-blue hover:bg-medical-blue-dark'} text-white text-center font-semibold py-2 rounded-lg transition-colors text-sm shadow-sm`}
                    >
                      Get Directions
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Loading State for Hospitals */}
          {loadingHospitals && (
            <div className="mb-5 text-center py-6 bg-clinical-gray-50 rounded-lg border border-clinical-gray-200">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-medical-blue mx-auto"></div>
              <p className="text-sm text-clinical-gray-600 mt-2">Finding nearby hospitals...</p>
            </div>
          )}

          {/* No Hospitals Found Message */}
          {!loadingHospitals && hospitals.length === 0 && (
            <div className="mb-5 bg-triage-non-urgent-bg border-l-4 border-l-triage-non-urgent rounded p-4">
              <p className="text-sm text-clinical-gray-900 font-semibold mb-1">
                Hospital Information
              </p>
              <p className="text-sm text-clinical-gray-700">
                Unable to determine nearby hospitals. Please contact your local healthcare provider or call 911 in case of emergency.
              </p>
            </div>
          )}

          <div className="space-y-4">
            <section className="bg-primary-light border border-clinical-gray-200 border-l-4 border-l-medical-blue rounded-lg p-4">
              <h2 className="text-base font-bold text-clinical-gray-900 mb-2">
                Assessment Reasons
              </h2>
              <ul className="space-y-2 text-clinical-gray-800 text-sm">
                {caseData.assistant.reasons.map((reason, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="mr-2 mt-0.5">•</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="bg-triage-self-care-bg border border-clinical-gray-200 border-l-4 border-l-triage-self-care rounded-lg p-4">
              <h2 className="text-base font-bold text-clinical-gray-900 mb-2">
                Next Steps
              </h2>
              <ul className="space-y-2 text-clinical-gray-800 text-sm">
                {caseData.assistant.nextSteps.map((step, idx) => (
                  <li key={idx} className="flex items-start">
                    <span className="mr-2 mt-0.5 text-triage-self-care font-bold">{idx + 1}.</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ul>
            </section>

            {caseData.assistant.monitoringPlan.length > 0 && (
              <section className="bg-triage-non-urgent-bg border border-clinical-gray-200 border-l-4 border-l-triage-non-urgent rounded-lg p-4">
                <h2 className="text-base font-bold text-clinical-gray-900 mb-2">
                  Monitoring Plan
                </h2>
                <ul className="space-y-2 text-clinical-gray-800 text-sm">
                  {caseData.assistant.monitoringPlan.map((item, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="mr-2 mt-0.5">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {caseData.assistant.escalationTriggers.length > 0 && (
              <section className="bg-triage-emergency-bg border border-clinical-gray-200 border-l-4 border-l-triage-emergency rounded-lg p-4">
                <h2 className="text-base font-bold text-clinical-gray-900 mb-2">
                  Seek Immediate Care If
                </h2>
                <ul className="space-y-2 text-clinical-gray-800 text-sm">
                  {caseData.assistant.escalationTriggers.map((trigger, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="mr-2 mt-0.5">•</span>
                      <span>{trigger}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {caseData.assistant.intakeSummary && (
              <section className="bg-clinical-gray-50 border border-clinical-gray-200 rounded-lg p-4">
                <h2 className="text-base font-bold text-clinical-gray-900 mb-2">
                  Summary
                </h2>
                <p className="text-clinical-gray-700 text-sm whitespace-pre-wrap leading-relaxed">{caseData.assistant.intakeSummary}</p>
              </section>
            )}
          </div>
        </div>

        <div className="bg-triage-emergency-bg border-l-4 border-l-triage-emergency rounded p-4">
          <p className="text-clinical-gray-900 font-bold mb-1 text-sm">Important</p>
          <p className="text-clinical-gray-700 text-xs mb-2">
            <strong>This is NOT a diagnosis.</strong> This is for informational purposes only.
          </p>
          <p className="text-clinical-gray-700 text-xs">
            <strong>Emergency? Call 911 immediately.</strong>
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <ResultsContent />
    </Suspense>
  );
}

