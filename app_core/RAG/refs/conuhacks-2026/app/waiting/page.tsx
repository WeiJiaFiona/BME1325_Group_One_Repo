'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect, useRef, Suspense } from 'react';

interface CaseData {
  _id: string;
  assessmentType: 'in_hospital' | 'remote';
  workflowStatus?: string;
  hospitalRouting?: {
    hospitalId?: string;
    hospitalSlug?: string;
    hospitalName?: string;
    hospitalAddress?: string;
  checkedInAt?: string | Date;
  notifications?: Array<{
    id: string;
    type: string;
    message: string;
    timestamp: Date | string;
    read: boolean;
    metadata?: any;
  }>;
};
  assistant: {
    triageLevel?: string;
    confidence?: number;
    reasons: string[];
    nextSteps: string[];
    monitoringPlan: string[];
    escalationTriggers: string[];
  };
  healthChecks?: {
    timestamp: Date;
    symptomsWorsened: boolean;
    newSymptoms: string[];
    painLevel?: number;
    notes?: string;
  }[];
}

interface WaitEstimate {
  estimatedWaitMinutes: number;
  estimatedWaitRange: {
    min: number;
    max: number;
  };
  queuePosition: number;
  totalPatientsInQueue: number;
  patientsAhead: {
    emergency: number;
    urgent: number;
    nonUrgent: number;
    selfCare: number;
    uncertain: number;
  };
  hospitalCapacity?: {
    current: number;
    max: number;
    available: number;
    utilizationPercent: string;
  };
  treatmentTimes?: {
    userLevel: number;
    averagePerPatient: number;
  };
  message: string;
}

function WaitingRoomContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseId = searchParams.get('caseId');
  const hospitalSlug = searchParams.get('hospitalSlug');
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [waitEstimate, setWaitEstimate] = useState<WaitEstimate | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCheckIn, setShowCheckIn] = useState(false);
  const [submittingCheck, setSubmittingCheck] = useState(false);
  const [showEmergencyAlert, setShowEmergencyAlert] = useState(false);
  const [markingArrival, setMarkingArrival] = useState(false);
  
  // Check-in form state
  const [symptomsWorsened, setSymptomsWorsened] = useState(false);
  const [painLevel, setPainLevel] = useState<number>(5);
  const [notes, setNotes] = useState('');
  const [newSymptoms, setNewSymptoms] = useState('');
  const [lastAutoUpdate, setLastAutoUpdate] = useState<Date | null>(null);
  const [nextUpdateIn, setNextUpdateIn] = useState<number>(600); // 10 minutes in seconds
  const [notifications, setNotifications] = useState<Array<{
    id: string;
    type: string;
    message: string;
    timestamp: Date | string;
    read: boolean;
    metadata?: any;
  }>>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Refs to always get latest form values in interval
  const formValuesRef = useRef({ symptomsWorsened, painLevel, notes, newSymptoms });
  
  // Update ref whenever form values change
  useEffect(() => {
    formValuesRef.current = { symptomsWorsened, painLevel, notes, newSymptoms };
  }, [symptomsWorsened, painLevel, notes, newSymptoms]);

  // Function to fetch wait estimate
  const fetchWaitEstimate = async (hospitalId: any, triageLevel: string | undefined, slug?: string | null) => {
    if ((!hospitalId && !slug) || !triageLevel) {
      console.log('Cannot fetch wait estimate - missing data:', { hospitalId, slug, triageLevel });
      return;
    }

    try {
      // Build URL - Use the [id] route which handles both IDs and slugs
      // Pass slug as a query parameter as fallback
      let url: string;
      if (slug) {
        // Use slug in path - the [id] route will try to match it as a slug
        url = `/api/hospitals/${slug}/wait-estimate?triageLevel=${encodeURIComponent(triageLevel)}&slug=${encodeURIComponent(slug)}`;
        console.log('Using slug for wait estimate:', url);
      } else if (hospitalId) {
        // Use ID
        const hospitalIdStr = typeof hospitalId === 'string' 
          ? hospitalId 
          : hospitalId?.toString?.() || String(hospitalId);
        url = `/api/hospitals/${hospitalIdStr}/wait-estimate?triageLevel=${encodeURIComponent(triageLevel)}`;
        console.log('Using hospital ID for wait estimate:', hospitalIdStr);
      } else {
        console.error('No hospital identifier available');
        return;
      }
      
      console.log('Fetching wait estimate:', url, { hospitalId, slug, triageLevel });
      
      const waitResponse = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      console.log('Wait estimate response status:', waitResponse.status, waitResponse.statusText);
      
      if (waitResponse.ok) {
        const waitData = await waitResponse.json();
        console.log('Wait estimate received:', waitData);
        if (waitData.estimate) {
          console.log('Setting wait estimate:', waitData.estimate);
          setWaitEstimate(waitData.estimate);
        } else {
          console.error('Wait estimate data missing estimate field:', waitData);
          console.error('Full response:', JSON.stringify(waitData, null, 2));
        }
      } else {
        const errorText = await waitResponse.text();
        console.error('Wait estimate API error:', waitResponse.status, errorText);
        try {
          const errorData = JSON.parse(errorText);
          console.error('Parsed error:', errorData);
          
          // If ID lookup failed and we have a slug, try with slug
          if (waitResponse.status === 404 && slug && hospitalId) {
            console.log('Retrying with slug instead of ID...');
            const slugUrl = `/api/hospitals/${slug}/wait-estimate?triageLevel=${encodeURIComponent(triageLevel)}`;
            const retryResponse = await fetch(slugUrl);
            if (retryResponse.ok) {
              const retryData = await retryResponse.json();
              if (retryData.estimate) {
                setWaitEstimate(retryData.estimate);
                return;
              }
            }
          }
        } catch (e) {
          console.error('Could not parse error response:', errorText);
        }
      }
    } catch (err) {
      console.error('Error fetching wait estimate:', err);
      console.error('Error details:', {
        message: err instanceof Error ? err.message : 'Unknown error',
        stack: err instanceof Error ? err.stack : undefined
      });
    }
  };

  useEffect(() => {
    if (!caseId) return;

    const fetchCase = async () => {
      try {
        const response = await fetch(`/api/cases/${caseId}`);
        if (!response.ok) throw new Error('Failed to fetch case');
        const data = await response.json();
        setCaseData(data.case);
        
        // Fetch notifications
        const notificationsResponse = await fetch(`/api/cases/${caseId}/notifications`);
        if (notificationsResponse.ok) {
          const notificationsData = await notificationsResponse.json();
          setNotifications(notificationsData.notifications || []);
          setUnreadCount(notificationsData.unreadCount || 0);
        }

        // Fetch wait estimate if hospital is linked
        let hospitalId = data.case.hospitalRouting?.hospitalId;
        // Prioritize slug from hospitalRouting over URL param
        let effectiveHospitalSlug = data.case.hospitalRouting?.hospitalSlug || hospitalSlug;
        const triageLevel = data.case.assistant?.triageLevel;
        
        // If hospitalRouting is missing but we have hospitalSlug, look up the hospital
        if (!hospitalId && effectiveHospitalSlug) {
          console.log('hospitalRouting missing, looking up hospital by slug:', effectiveHospitalSlug);
          try {
            const hospitalResponse = await fetch(`/api/hospitals?slug=${effectiveHospitalSlug}`);
            if (hospitalResponse.ok) {
              const hospitalData = await hospitalResponse.json();
              console.log('Hospital lookup response:', hospitalData);
              if (hospitalData.hospitals && hospitalData.hospitals.length > 0) {
                const foundHospital = hospitalData.hospitals[0];
                // Get the actual hospital ID from the database
                // The _id might be an ObjectId, so convert to string
                const actualHospitalId = foundHospital._id?.toString() || String(foundHospital._id);
                hospitalId = actualHospitalId;
                console.log('Found hospital by slug:', {
                  id: actualHospitalId,
                  name: foundHospital.name,
                  slug: foundHospital.slug,
                  fullHospital: foundHospital,
                  idType: typeof actualHospitalId
                });
                
                // Update the case with hospitalRouting if it's missing
                // Only update if it's truly missing to avoid infinite loops
                if (!data.case.hospitalRouting || !data.case.hospitalRouting.hospitalId) {
                  try {
                    const updateResponse = await fetch(`/api/cases/${caseId}`, {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({
                        hospitalRouting: {
                          hospitalId: hospitalId,
                          hospitalSlug: foundHospital.slug,
                          hospitalName: foundHospital.name,
                          hospitalAddress: foundHospital.address,
                          routedAt: new Date(),
                          routedBy: 'qr-code-intake',
                        }
                      }),
                    });
                    
                    if (updateResponse.ok) {
                      // Update local case data without triggering another fetch
                      const updatedCase = { ...data.case };
                      updatedCase.hospitalRouting = {
                        hospitalId: hospitalId,
                        hospitalSlug: foundHospital.slug,
                        hospitalName: foundHospital.name,
                        hospitalAddress: foundHospital.address,
                      };
                      setCaseData(updatedCase);
                    }
                  } catch (updateError) {
                    console.error('Failed to update case with hospitalRouting:', updateError);
                  }
                }
              } else {
                console.error('No hospitals found with slug:', effectiveHospitalSlug);
              }
            } else {
              console.error('Failed to fetch hospital by slug:', hospitalResponse.status);
            }
          } catch (lookupError) {
            console.error('Error looking up hospital by slug:', lookupError);
          }
        }
        
        // Also check if hospitalId exists but is wrong format
        if (hospitalId) {
          console.log('Using hospitalId:', hospitalId, 'Type:', typeof hospitalId);
        }
        
        console.log('Case loaded - Wait estimate check:', {
          hospitalId,
          triageLevel,
          hospitalSlug: effectiveHospitalSlug,
          hospitalRouting: data.case.hospitalRouting,
          assessmentType: data.case.assessmentType
        });
        
        // Fetch wait estimate - prioritize slug from hospitalRouting over URL param, then ID
        if (triageLevel) {
          if (effectiveHospitalSlug) {
            // Use slug directly - it's more reliable
            console.log('Using hospital slug for wait estimate:', effectiveHospitalSlug);
            fetchWaitEstimate(null, triageLevel, effectiveHospitalSlug);
          } else if (hospitalId) {
            // Fallback to ID if no slug
            console.log('Using hospital ID for wait estimate:', hospitalId);
            fetchWaitEstimate(hospitalId, triageLevel, null);
          } else {
            console.warn('Cannot fetch wait estimate - missing hospital info:', {
              hasHospitalId: !!hospitalId,
              hasTriageLevel: !!triageLevel,
              hasHospitalSlug: !!effectiveHospitalSlug,
              hospitalRouting: data.case.hospitalRouting
            });
          }
        }
      } catch (error) {
        console.error('Error fetching case:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCase();

    // Auto-refresh every 10 seconds - use a ref to avoid stale closures
    const interval = setInterval(() => {
      // Re-fetch case data
      fetch(`/api/cases/${caseId}`)
        .then(res => res.json())
        .then(data => {
          setCaseData(data.case);
          // Refresh wait estimate if we have the data
          const hospitalId = data.case.hospitalRouting?.hospitalId;
          const effectiveSlug = data.case.hospitalRouting?.hospitalSlug || hospitalSlug;
          const triageLevel = data.case.assistant?.triageLevel;
          if (triageLevel && (effectiveSlug || hospitalId)) {
            fetchWaitEstimate(hospitalId, triageLevel, effectiveSlug);
          }
        })
        .catch(err => console.error('Error refreshing case:', err));
      
      // Also fetch notifications
      fetch(`/api/cases/${caseId}/notifications`)
        .then(res => res.json())
        .then(data => {
          setNotifications(data.notifications || []);
          setUnreadCount(data.unreadCount || 0);
        })
        .catch(err => console.error('Error fetching notifications:', err));
    }, 10000); // Reduced from 30 seconds to 10 seconds for faster updates
    
    return () => clearInterval(interval);
  }, [caseId, hospitalSlug]); // Only depend on caseId and hospitalSlug, not caseData

  // Prompt for check-in every 15 minutes
  useEffect(() => {
    const checkInInterval = setInterval(() => {
      setShowCheckIn(true);
    }, 15 * 60 * 1000); // 15 minutes

    return () => clearInterval(checkInInterval);
  }, []);

  // Auto-update condition every 10 minutes
  useEffect(() => {
    if (!caseId) return;

    const autoUpdateCondition = async () => {
      // Get latest form values from ref
      const current = formValuesRef.current;
      const currentNotes = current.notes.trim() || `Auto-update at ${new Date().toLocaleTimeString()}`;
      const currentNewSymptoms = current.newSymptoms.trim() || undefined;

      try {
        const response = await fetch(`/api/cases/${caseId}/health-check`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symptomsWorsened: current.symptomsWorsened,
            painLevel: current.painLevel,
            notes: currentNotes,
            newSymptoms: currentNewSymptoms,
          }),
        });

        if (response.ok) {
          console.log('Condition auto-updated successfully');
          setLastAutoUpdate(new Date());
          setNextUpdateIn(600); // Reset to 10 minutes
        }
      } catch (error) {
        console.error('Error auto-updating condition:', error);
      }
    };

    // Update immediately on mount, then every 10 minutes
    autoUpdateCondition();
    const autoUpdateInterval = setInterval(autoUpdateCondition, 10 * 60 * 1000); // 10 minutes

    return () => clearInterval(autoUpdateInterval);
  }, [caseId]); // Only depend on caseId, not form values

  // Countdown timer for next auto-update
  useEffect(() => {
    const countdownInterval = setInterval(() => {
      setNextUpdateIn((prev) => {
        if (prev <= 1) {
          return 600; // Reset to 10 minutes
        }
        return prev - 1;
      });
    }, 1000); // Update every second

    return () => clearInterval(countdownInterval);
  }, [lastAutoUpdate]);

  const handleEmergencyAlert = async () => {
    if (!caseId) return;

    try {
      const response = await fetch(`/api/emergency-alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caseId }),
      });

      if (response.ok) {
        alert('Emergency alert sent! Staff have been notified and will come to assist you immediately.');
        setShowEmergencyAlert(false);
      } else {
        throw new Error('Failed to send alert');
      }
    } catch (error) {
      console.error('Error sending emergency alert:', error);
      alert('Please go to the registration desk immediately or call for help.');
    }
  };

  const handleMarkArrival = async () => {
    if (!caseId) return;
    setMarkingArrival(true);

    try {
      const response = await fetch(`/api/cases/${caseId}/workflow`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflowStatus: 'checked_in',
          checkedInBy: 'patient',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to mark arrival');
      }

      const data = await response.json();
      setCaseData(data.case);
      alert('Arrival confirmed! Staff has been notified.');
    } catch (error) {
      console.error('Error marking arrival:', error);
      alert('Failed to mark arrival. Please notify staff at the desk.');
    } finally {
      setMarkingArrival(false);
    }
  };

  const handleCheckIn = async () => {
    if (!caseId) return;

    setSubmittingCheck(true);
    try {
      const response = await fetch(`/api/cases/${caseId}/health-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symptomsWorsened,
          newSymptoms: newSymptoms ? newSymptoms.split(',').map(s => s.trim()) : [],
          painLevel,
          notes,
          timestamp: new Date(),
        }),
      });

      if (!response.ok) throw new Error('Failed to submit check-in');
      
      const data = await response.json();
      
      if (data.escalated) {
        alert('Your condition has been flagged for urgent review. Staff will see you shortly.');
      } else {
        alert('Check-in recorded. Thank you for updating us on your condition.');
      }

      // Reset form
      setSymptomsWorsened(false);
      setPainLevel(5);
      setNotes('');
      setNewSymptoms('');
      setShowCheckIn(false);

      // Refresh case data
      const caseResponse = await fetch(`/api/cases/${caseId}`);
      if (caseResponse.ok) {
        const caseData = await caseResponse.json();
        setCaseData(caseData.case);
      }
    } catch (error) {
      console.error('Error submitting check-in:', error);
      alert('Failed to submit check-in. Please notify staff at the desk.');
    } finally {
      setSubmittingCheck(false);
    }
  };

  const getTriageColor = (level?: string) => {
    switch (level) {
      case 'EMERGENCY': return 'bg-triage-emergency';
      case 'URGENT': return 'bg-triage-urgent';
      case 'NON_URGENT': return 'bg-triage-non-urgent';
      case 'SELF_CARE': return 'bg-triage-self-care';
      case 'UNCERTAIN': return 'bg-triage-uncertain';
      default: return 'bg-clinical-gray-600';
    }
  };

  const getTriageLabel = (level?: string) => {
    switch (level) {
      case 'EMERGENCY': return 'Emergency';
      case 'URGENT': return 'Urgent';
      case 'NON_URGENT': return 'Non-Urgent';
      case 'SELF_CARE': return 'Routine';
      default: return 'Assessment Pending';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-blue-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-blue-50">
        <p className="text-red-600">Case not found</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-clinical-gray-50 py-4 px-4">
      <div className="max-w-md mx-auto">
        {/* Manual Refresh Button */}
        <div className="mb-4">
          <button
            onClick={async () => {
              if (!caseId) return;
              try {
                // Refresh case data
                const caseResponse = await fetch(`/api/cases/${caseId}`);
                if (caseResponse.ok) {
                  const caseData = await caseResponse.json();
                  setCaseData(caseData.case);
                  
                  // Refresh wait estimate if we have the data
                  const hospitalId = caseData.case.hospitalRouting?.hospitalId;
                  const effectiveSlug = caseData.case.hospitalRouting?.hospitalSlug || hospitalSlug;
                  const triageLevel = caseData.case.assistant?.triageLevel;
                  if (triageLevel && (effectiveSlug || hospitalId)) {
                    fetchWaitEstimate(hospitalId, triageLevel, effectiveSlug);
                  }
                }
                
                // Refresh notifications
                const notificationsResponse = await fetch(`/api/cases/${caseId}/notifications`);
                if (notificationsResponse.ok) {
                  const notificationsData = await notificationsResponse.json();
                  setNotifications(notificationsData.notifications || []);
                  setUnreadCount(notificationsData.unreadCount || 0);
                }
              } catch (error) {
                console.error('Error refreshing:', error);
              }
            }}
            className="w-full bg-clinical-gray-200 hover:bg-clinical-gray-300 text-clinical-gray-900 font-semibold py-2 px-4 rounded-lg text-sm transition-colors"
          >
            🔄 Refresh Updates
          </button>
        </div>

        {/* Notifications Section */}
        {notifications.length > 0 && (
          <div className="mb-4 bg-white rounded-lg border border-clinical-gray-200 shadow-sm p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-clinical-gray-900">Updates</h3>
              {unreadCount > 0 && (
                <span className="bg-medical-blue text-white text-xs font-bold px-2 py-1 rounded-full">
                  {unreadCount} new
                </span>
              )}
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`p-3 rounded-lg border ${
                    notification.read
                      ? 'bg-clinical-gray-50 border-clinical-gray-200'
                      : 'bg-primary-light border-medical-blue border-l-4'
                  }`}
                >
                  <p className="text-sm text-clinical-gray-900">{notification.message}</p>
                  <p className="text-xs text-clinical-gray-500 mt-1">
                    {new Date(notification.timestamp).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={async () => {
                  const response = await fetch(`/api/cases/${caseId}/notifications`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ markAllRead: true }),
                  });
                  if (response.ok) {
                    const data = await response.json();
                    setUnreadCount(data.unreadCount || 0);
                    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
                  }
                }}
                className="mt-3 text-sm text-medical-blue hover:text-medical-blue-dark font-semibold"
              >
                Mark all as read
              </button>
            )}
          </div>
        )}

        {/* Emergency Alert Button - Always Visible */}
        <div className="mb-4">
          <button
            onClick={() => setShowEmergencyAlert(true)}
            className="w-full bg-triage-emergency hover:bg-triage-emergency-dark text-white font-bold py-4 px-6 rounded-lg shadow-sm transition-colors"
          >
            EMERGENCY - Need Immediate Help
          </button>
        </div>

        {/* Arrival Button - Show when on_route */}
        {caseData.workflowStatus === 'on_route' && !caseData.hospitalRouting?.checkedInAt && (
          <div className="mb-4">
            <button
              onClick={handleMarkArrival}
              disabled={markingArrival}
              className="w-full bg-triage-self-care hover:bg-triage-self-care-dark disabled:bg-clinical-gray-300 disabled:text-clinical-gray-500 text-white font-bold py-4 px-6 rounded-lg shadow-sm transition-colors"
            >
              {markingArrival ? 'Confirming Arrival...' : "I've Arrived at the Hospital"}
            </button>
          </div>
        )}

        {/* Arrival Confirmation - Show when checked in */}
        {caseData.workflowStatus === 'checked_in' && caseData.hospitalRouting?.checkedInAt && (
          <div className="mb-4 bg-triage-self-care-bg border border-triage-self-care-dark border-l-4 border-l-triage-self-care rounded-lg p-4">
            <div className="flex items-center justify-center space-x-2">
              <span className="text-triage-self-care font-bold text-lg">✓</span>
              <p className="text-clinical-gray-900 font-bold text-center">
                Arrival Confirmed
              </p>
            </div>
            <p className="text-sm text-clinical-gray-700 text-center mt-2">
              You checked in at {new Date(caseData.hospitalRouting.checkedInAt).toLocaleTimeString()}. Staff has been notified.
            </p>
          </div>
        )}

        {/* Quick Condition Update - Always Visible */}
        <div className="bg-white rounded-lg border border-clinical-gray-200 shadow-sm p-6 mb-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-bold text-clinical-gray-900">Update Your Condition</h3>
              <div className="text-xs text-clinical-gray-500 mt-1">
                {lastAutoUpdate ? (
                  <span>
                    Last auto-update: {lastAutoUpdate.toLocaleTimeString()} • Next in: {Math.floor(nextUpdateIn / 60)}:{(nextUpdateIn % 60).toString().padStart(2, '0')}
                  </span>
                ) : (
                  <span>Auto-updates every 10 minutes</span>
                )}
              </div>
            </div>
            <button
              onClick={async () => {
                if (!caseId) return;
                const quickPain = painLevel;
                const quickWorsened = symptomsWorsened;
                const quickNotes = notes.trim() || 'Quick update';
                
                try {
                  const response = await fetch(`/api/cases/${caseId}/health-check`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      symptomsWorsened: quickWorsened,
                      painLevel: quickPain,
                      notes: quickNotes,
                      newSymptoms: newSymptoms.trim() || undefined,
                    }),
                  });

                  if (response.ok) {
                    // Show success feedback
                    const button = document.querySelector('[data-quick-update]') as HTMLElement;
                    if (button) {
                      const originalText = button.textContent;
                      button.textContent = 'Updated!';
                      button.classList.add('bg-green-500');
                      setTimeout(() => {
                        button.textContent = originalText;
                        button.classList.remove('bg-green-500');
                      }, 2000);
                    }
                    // Clear form
                    setNotes('');
                    setNewSymptoms('');
                    setSymptomsWorsened(false);
                    setPainLevel(5);
                  }
                } catch (error) {
                  console.error('Error updating condition:', error);
                  alert('Failed to update. Please try again.');
                }
              }}
              data-quick-update
              className="bg-medical-blue hover:bg-medical-blue-dark text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors shadow-sm"
            >
              Update Now
            </button>
          </div>
          
          <div className="space-y-4">
            {/* Pain Level */}
            <div>
              <label className="block text-sm font-semibold text-clinical-gray-900 mb-2">
                Pain Level: {painLevel}/10
              </label>
              <input
                type="range"
                min="0"
                max="10"
                value={painLevel}
                onChange={(e) => setPainLevel(parseInt(e.target.value))}
                className="w-full h-2 bg-clinical-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-clinical-gray-500 mt-1">
                <span>No Pain</span>
                <span>Moderate</span>
                <span>Severe</span>
              </div>
            </div>

            {/* Symptoms Worsened */}
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="symptomsWorsened"
                checked={symptomsWorsened}
                onChange={(e) => setSymptomsWorsened(e.target.checked)}
                className="w-4 h-4 text-triage-emergency border-clinical-gray-300 rounded focus:ring-triage-emergency"
              />
              <label htmlFor="symptomsWorsened" className="text-sm font-medium text-clinical-gray-900">
                My symptoms have worsened
              </label>
            </div>

            {/* Quick Notes */}
            <div>
              <input
                type="text"
                placeholder="Quick note about your condition (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full px-4 py-3 border border-clinical-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-medical-blue focus:border-medical-blue text-clinical-gray-900 placeholder-clinical-gray-500"
              />
            </div>
          </div>
        </div>

        {/* Hospital Assignment - Prominent Display */}
        {caseData.workflowStatus === 'confirmed_hospital' && caseData.hospitalRouting?.hospitalName && (
          <div className="mb-4 bg-primary-light border-2 border-medical-blue rounded-lg p-5 shadow-sm">
            <div className="flex items-center justify-center space-x-2 mb-2">
              <span className="text-medical-blue font-bold text-xl">📍</span>
              <h2 className="text-xl font-bold text-clinical-gray-900">Hospital Assigned</h2>
            </div>
            <h3 className="text-lg font-semibold text-clinical-gray-900 text-center mb-2">
              {caseData.hospitalRouting.hospitalName}
            </h3>
            {caseData.hospitalRouting.hospitalAddress && (
              <p className="text-sm text-clinical-gray-700 text-center mb-3">
                {caseData.hospitalRouting.hospitalAddress}
              </p>
            )}
            <p className="text-sm text-clinical-gray-600 text-center mb-4">
              Please proceed to this hospital for your care.
            </p>
            {/* I've Arrived Button */}
            {!caseData.hospitalRouting?.checkedInAt && (
              <button
                onClick={handleMarkArrival}
                disabled={markingArrival}
                className="w-full bg-triage-self-care hover:bg-triage-self-care-dark disabled:bg-clinical-gray-300 disabled:text-clinical-gray-500 text-white font-bold py-3 px-6 rounded-lg shadow-sm transition-colors"
              >
                {markingArrival ? 'Confirming Arrival...' : "I've Arrived at the Hospital"}
              </button>
            )}
          </div>
        )}

        {/* Hospital Info */}
        <div className="bg-white rounded-lg border border-clinical-gray-200 shadow-sm p-6 mb-4">
          <div className="text-center mb-4">
            <h1 className="text-2xl font-bold text-clinical-gray-900">
              {caseData.hospitalRouting?.hospitalName || 'Hospital Waiting Room'}
            </h1>
            {caseData.hospitalRouting?.hospitalAddress && (
              <p className="text-sm text-clinical-gray-600 mt-1">{caseData.hospitalRouting.hospitalAddress}</p>
            )}
          </div>

          {/* Triage Level */}
          <div className={`${getTriageColor(caseData.assistant?.triageLevel)} text-white px-4 py-3 rounded-lg text-center mb-4`}>
            <p className="text-sm font-medium">Your Priority Level</p>
            <p className="text-xl font-bold">{getTriageLabel(caseData.assistant?.triageLevel)}</p>
          </div>

          {/* Wait Time Estimate - Enhanced */}
          {waitEstimate ? (
            <div className="bg-clinical-gray-50 border border-clinical-gray-200 rounded-lg p-5 mb-4">
              <div className="mb-4">
                <h3 className="text-lg font-bold text-clinical-gray-900 mb-3">Your Estimated Wait Time</h3>
                
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-white rounded-lg p-4 border border-clinical-gray-200">
                    <p className="text-xs font-semibold text-clinical-gray-500 uppercase mb-1 tracking-wide">Estimated Wait</p>
                    <p className="text-4xl font-bold text-medical-blue">
                      {waitEstimate.estimatedWaitMinutes}
                    </p>
                    <p className="text-xs text-clinical-gray-600 mt-1">minutes</p>
                    <p className="text-xs text-clinical-gray-500 mt-2">
                      Range: {waitEstimate.estimatedWaitRange.min}-{waitEstimate.estimatedWaitRange.max} min
                    </p>
                  </div>
                  
                  <div className="bg-white rounded-lg p-4 border border-clinical-gray-200">
                    <p className="text-xs font-semibold text-clinical-gray-500 uppercase mb-1 tracking-wide">Your Position</p>
                    <p className="text-4xl font-bold text-clinical-gray-900">
                      #{waitEstimate.queuePosition}
                    </p>
                    <p className="text-xs text-clinical-gray-600 mt-1">in queue</p>
                    <p className="text-xs text-clinical-gray-500 mt-2">
                      {waitEstimate.queuePosition === 0 
                        ? 'You\'re next!' 
                        : waitEstimate.queuePosition === 1
                        ? '1 patient ahead'
                        : `${waitEstimate.queuePosition} patients ahead`}
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Detailed Queue Breakdown */}
              <div className="bg-white rounded-lg p-4 mb-3 border border-clinical-gray-200">
                <p className="text-sm font-bold text-clinical-gray-900 mb-3">Patients Ahead of You by Priority:</p>
                <div className="space-y-2">
                  {waitEstimate.patientsAhead.emergency > 0 && (
                    <div className="flex items-center justify-between p-3 bg-triage-emergency-bg rounded-lg border border-triage-emergency-dark">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-clinical-gray-900">Emergency Priority:</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xl font-bold text-triage-emergency">{waitEstimate.patientsAhead.emergency}</span>
                        <span className="text-xs text-clinical-gray-600 ml-1">
                          {waitEstimate.patientsAhead.emergency === 1 ? 'patient' : 'patients'}
                        </span>
                      </div>
                    </div>
                  )}
                  {waitEstimate.patientsAhead.urgent > 0 && (
                    <div className="flex items-center justify-between p-3 bg-triage-urgent-bg rounded-lg border border-triage-urgent-dark">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-clinical-gray-900">Urgent Priority:</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xl font-bold text-triage-urgent">{waitEstimate.patientsAhead.urgent}</span>
                        <span className="text-xs text-clinical-gray-600 ml-1">
                          {waitEstimate.patientsAhead.urgent === 1 ? 'patient' : 'patients'}
                        </span>
                      </div>
                    </div>
                  )}
                  {waitEstimate.patientsAhead.nonUrgent > 0 && (
                    <div className="flex items-center justify-between p-3 bg-triage-non-urgent-bg rounded-lg border border-triage-non-urgent-dark">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-clinical-gray-900">Non-Urgent Priority:</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xl font-bold text-triage-non-urgent">{waitEstimate.patientsAhead.nonUrgent}</span>
                        <span className="text-xs text-clinical-gray-600 ml-1">
                          {waitEstimate.patientsAhead.nonUrgent === 1 ? 'patient' : 'patients'}
                        </span>
                      </div>
                    </div>
                  )}
                  {waitEstimate.patientsAhead.selfCare > 0 && (
                    <div className="flex items-center justify-between p-3 bg-triage-self-care-bg rounded-lg border border-triage-self-care-dark">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-clinical-gray-900">Routine Priority:</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xl font-bold text-triage-self-care">{waitEstimate.patientsAhead.selfCare}</span>
                        <span className="text-xs text-clinical-gray-600 ml-1">
                          {waitEstimate.patientsAhead.selfCare === 1 ? 'patient' : 'patients'}
                        </span>
                      </div>
                    </div>
                  )}
                  {waitEstimate.patientsAhead.uncertain > 0 && (
                    <div className="flex items-center justify-between p-3 bg-triage-uncertain-bg rounded-lg border border-triage-uncertain-dark">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-clinical-gray-900">Uncertain Priority:</span>
                      </div>
                      <div className="text-right">
                        <span className="text-xl font-bold text-triage-uncertain">{waitEstimate.patientsAhead.uncertain}</span>
                        <span className="text-xs text-clinical-gray-600 ml-1">
                          {waitEstimate.patientsAhead.uncertain === 1 ? 'patient' : 'patients'}
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {/* Total Summary */}
                  <div className="mt-3 pt-3 border-t border-clinical-gray-200">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-clinical-gray-900">Total Patients Ahead:</span>
                      <span className="text-lg font-bold text-clinical-gray-900">
                        {waitEstimate.queuePosition} {waitEstimate.queuePosition === 1 ? 'patient' : 'patients'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Hospital Capacity Info */}
              {waitEstimate.hospitalCapacity && (
                <div className="bg-clinical-gray-50 rounded-lg p-4 mb-3 border border-clinical-gray-200">
                  <p className="text-xs font-semibold text-clinical-gray-900 mb-2 uppercase tracking-wide">Hospital Capacity:</p>
                  <div className="flex items-center justify-between text-sm mb-2">
                    <span className="text-clinical-gray-700">Current Patients:</span>
                    <span className="font-bold text-clinical-gray-900">{waitEstimate.hospitalCapacity.current} / {waitEstimate.hospitalCapacity.max}</span>
                  </div>
                  <div className="w-full bg-clinical-gray-200 rounded-full h-2 mt-2">
                    <div
                      className={`h-2 rounded-full ${
                        parseFloat(waitEstimate.hospitalCapacity.utilizationPercent) < 60 ? 'bg-triage-self-care' :
                        parseFloat(waitEstimate.hospitalCapacity.utilizationPercent) < 80 ? 'bg-triage-non-urgent' :
                        'bg-triage-emergency'
                      }`}
                      style={{ width: `${waitEstimate.hospitalCapacity.utilizationPercent}%` }}
                    ></div>
                  </div>
                  <p className="text-xs text-clinical-gray-600 mt-2">
                    {waitEstimate.hospitalCapacity.utilizationPercent}% capacity • {waitEstimate.hospitalCapacity.available} beds available
                  </p>
                </div>
              )}

              {/* Wait Time Explanation */}
              <div className="bg-primary-light border border-medical-blue/20 border-l-4 border-l-medical-blue rounded-lg p-4">
                <p className="text-xs font-semibold text-clinical-gray-900 mb-2">How This Estimate Works:</p>
                <ul className="text-xs text-clinical-gray-700 space-y-1.5">
                  <li>• <strong>Higher priority patients</strong> (Emergency, Urgent) are seen first</li>
                  <li>• Your wait time is based on <strong>{waitEstimate.queuePosition} patients</strong> ahead with same or higher priority</li>
                  {waitEstimate.treatmentTimes && (
                    <>
                      <li>• Average treatment time for your priority: <strong>{waitEstimate.treatmentTimes.userLevel} minutes</strong></li>
                      <li>• Average time per patient ahead: <strong>{waitEstimate.treatmentTimes.averagePerPatient} minutes</strong></li>
                    </>
                  )}
                  <li>• <strong>Total patients in queue:</strong> {waitEstimate.totalPatientsInQueue}</li>
                  <li>• Times update every 30 seconds as the queue changes</li>
                </ul>
              </div>

              {/* Status Message */}
              <div className="mt-3 text-center">
                <p className={`text-sm font-semibold ${
                  waitEstimate.estimatedWaitMinutes < 30 ? 'text-triage-self-care' :
                  waitEstimate.estimatedWaitMinutes < 60 ? 'text-triage-non-urgent' :
                  'text-triage-urgent'
                }`}>
                  {waitEstimate.message}
                </p>
              </div>
            </div>
          ) : (
            // Fallback when wait estimate is not available - show basic info
            <div className="bg-clinical-gray-50 border border-clinical-gray-200 rounded-lg p-5 mb-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <h3 className="text-lg font-bold text-clinical-gray-900">Wait Time Information</h3>
                </div>
                <button
                  onClick={() => {
                    const effectiveSlug = caseData?.hospitalRouting?.hospitalSlug || hospitalSlug;
                    if (caseData?.assistant?.triageLevel && (caseData?.hospitalRouting?.hospitalId || effectiveSlug)) {
                      console.log('Manual refresh clicked');
                      fetchWaitEstimate(caseData.hospitalRouting?.hospitalId, caseData.assistant.triageLevel, effectiveSlug);
                    } else {
                      // Reload case data first
                      fetch(`/api/cases/${caseId}`)
                        .then(res => res.json())
                        .then(data => {
                          setCaseData(data.case);
                          const reloadSlug = data.case.hospitalRouting?.hospitalSlug || hospitalSlug;
                          if (data.case.assistant?.triageLevel && (data.case.hospitalRouting?.hospitalId || reloadSlug)) {
                            fetchWaitEstimate(data.case.hospitalRouting?.hospitalId, data.case.assistant.triageLevel, reloadSlug);
                          }
                        });
                    }
                  }}
                  className="text-xs bg-triage-non-urgent-bg hover:bg-triage-non-urgent-bg/80 px-3 py-1 rounded-lg font-semibold text-clinical-gray-900 transition-colors border border-triage-non-urgent-dark"
                >
Refresh
                </button>
                {caseData?.assistant?.triageLevel && (caseData?.hospitalRouting?.hospitalId || caseData?.hospitalRouting?.hospitalSlug || hospitalSlug) && (
                  <button
                    onClick={() => {
                      const effectiveSlug = caseData.hospitalRouting?.hospitalSlug || hospitalSlug;
                      fetchWaitEstimate(caseData.hospitalRouting?.hospitalId, caseData.assistant?.triageLevel, effectiveSlug);
                    }}
                    className="text-xs bg-primary-light hover:bg-primary-light/80 px-3 py-1 rounded-lg font-semibold text-clinical-gray-900 transition-colors border border-medical-blue/30 ml-2"
                  >
Retry Wait Time
                  </button>
                )}
              </div>
              
              {/* Show basic wait time estimate based on triage level */}
              {caseData.assistant?.triageLevel && (
                <div className="bg-white rounded-lg p-4 mb-3 border border-clinical-gray-200">
                  <p className="text-sm font-semibold text-clinical-gray-900 mb-2">Estimated Wait Based on Your Priority:</p>
                  {caseData.assistant.triageLevel === 'EMERGENCY' && (
                    <div>
                      <p className="text-2xl font-bold text-triage-emergency">15-30 minutes</p>
                      <p className="text-xs text-clinical-gray-600 mt-1">Emergency cases are seen immediately</p>
                    </div>
                  )}
                  {caseData.assistant.triageLevel === 'URGENT' && (
                    <div>
                      <p className="text-2xl font-bold text-triage-urgent">30-60 minutes</p>
                      <p className="text-xs text-clinical-gray-600 mt-1">Urgent cases are prioritized</p>
                    </div>
                  )}
                  {caseData.assistant.triageLevel === 'NON_URGENT' && (
                    <div>
                      <p className="text-2xl font-bold text-triage-non-urgent">60-90 minutes</p>
                      <p className="text-xs text-clinical-gray-600 mt-1">Non-urgent cases may have longer waits</p>
                    </div>
                  )}
                  {caseData.assistant.triageLevel === 'SELF_CARE' && (
                    <div>
                      <p className="text-2xl font-bold text-triage-self-care">90-120 minutes</p>
                      <p className="text-xs text-clinical-gray-600 mt-1">Routine cases have the longest wait times</p>
                    </div>
                  )}
                  {caseData.assistant.triageLevel === 'UNCERTAIN' && (
                    <div>
                      <p className="text-2xl font-bold text-triage-uncertain">45-75 minutes</p>
                      <p className="text-xs text-clinical-gray-600 mt-1">Estimated wait time</p>
                    </div>
                  )}
                </div>
              )}
              
              <p className="text-sm text-clinical-gray-700 mb-2">
                We're calculating your precise wait time based on the current queue.
              </p>
              
              {caseData.hospitalRouting?.hospitalId && !caseData.assistant?.triageLevel && (
                <div className="bg-triage-non-urgent-bg border border-triage-non-urgent-dark rounded-lg p-3 mt-2">
                  <p className="text-xs text-clinical-gray-800">
                    Waiting for triage assessment to complete before calculating wait time...
                  </p>
                </div>
              )}
              {!caseData.hospitalRouting?.hospitalId && (
                <div className="bg-triage-non-urgent-bg border border-triage-non-urgent-dark rounded-lg p-3 mt-2">
                  <p className="text-xs text-clinical-gray-800">
                    Hospital information not linked to your case. Please contact the registration desk.
                  </p>
                </div>
              )}
              {caseData.hospitalRouting?.hospitalId && caseData.assistant?.triageLevel && (
                <div className="bg-primary-light border border-medical-blue/20 rounded-lg p-3 mt-2">
                  <p className="text-xs text-clinical-gray-800">
                    Detailed wait time calculation is in progress. Click refresh to update.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Status Message */}
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg mb-4">
            <p className="text-sm font-semibold text-blue-900 mb-2">Please remain in the waiting area</p>
            <p className="text-sm text-blue-800">
              Staff will call you when ready. If your condition worsens, use the emergency button above.
            </p>
          </div>

          {/* What to Watch For */}
          {caseData.assistant?.escalationTriggers && caseData.assistant.escalationTriggers.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">Seek immediate help if you experience:</h3>
              <ul className="space-y-1">
                {caseData.assistant.escalationTriggers.map((trigger, index) => (
                  <li key={index} className="text-sm text-gray-700 flex items-start">
                    <span className="text-red-600 mr-2">•</span>
                    <span>{trigger}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Health Check-In Button */}
        <button
          onClick={() => setShowCheckIn(true)}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-xl shadow-md mb-4 transition"
        >
          📋 Update My Condition
        </button>

        {/* Recent Check-Ins */}
        {caseData.healthChecks && caseData.healthChecks.length > 0 && (
          <div className="bg-white rounded-xl shadow-md p-4">
            <h3 className="font-semibold text-gray-900 mb-3">Recent Updates</h3>
            <div className="space-y-2">
              {caseData.healthChecks.slice(-3).reverse().map((check, index) => (
                <div key={index} className="bg-gray-50 p-3 rounded-lg text-sm">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-medium text-gray-900">
                      {check.symptomsWorsened ? 'Symptoms Worsened' : 'Check-in'}
                    </span>
                    <span className="text-gray-500 text-xs">
                      {new Date(check.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  {check.painLevel && (
                    <p className="text-gray-700">Pain Level: {check.painLevel}/10</p>
                  )}
                  {check.notes && (
                    <p className="text-gray-600 text-xs mt-1">{check.notes}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Emergency Alert Modal */}
        {showEmergencyAlert && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl">
              <div className="text-center mb-4">
                <h2 className="text-2xl font-bold text-red-600">Emergency Alert</h2>
              </div>
              <p className="text-gray-700 mb-6 text-center">
                This will immediately notify hospital staff that you need urgent assistance.
              </p>
              <div className="space-y-3">
                <button
                  onClick={handleEmergencyAlert}
                  className="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-3 rounded-lg"
                >
                  Send Emergency Alert
                </button>
                <button
                  onClick={() => setShowEmergencyAlert(false)}
                  className="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 rounded-lg"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Health Check-In Modal */}
        {showCheckIn && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto">
            <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl my-8">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">Health Check-In</h2>
              
              <div className="space-y-4">
                {/* Symptoms Worsened */}
                <div>
                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={symptomsWorsened}
                      onChange={(e) => setSymptomsWorsened(e.target.checked)}
                      className="w-5 h-5 text-red-600 rounded focus:ring-red-500"
                    />
                    <span className="text-gray-900 font-medium">My symptoms have gotten worse</span>
                  </label>
                </div>

                {/* Pain Level */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Current Pain Level: {painLevel}/10
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={painLevel}
                    onChange={(e) => setPainLevel(Number(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>1 (Mild)</span>
                    <span>10 (Severe)</span>
                  </div>
                </div>

                {/* New Symptoms */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Any new symptoms? (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={newSymptoms}
                    onChange={(e) => setNewSymptoms(e.target.value)}
                    placeholder="e.g., dizziness, nausea"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                {/* Notes */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Additional notes (optional)
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Any other changes you've noticed?"
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>

              <div className="mt-6 space-y-2">
                <button
                  onClick={handleCheckIn}
                  disabled={submittingCheck}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold py-3 rounded-lg transition"
                >
                  {submittingCheck ? 'Submitting...' : 'Submit Check-In'}
                </button>
                <button
                  onClick={() => setShowCheckIn(false)}
                  disabled={submittingCheck}
                  className="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 rounded-lg"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function WaitingRoomPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <WaitingRoomContent />
    </Suspense>
  );
}

