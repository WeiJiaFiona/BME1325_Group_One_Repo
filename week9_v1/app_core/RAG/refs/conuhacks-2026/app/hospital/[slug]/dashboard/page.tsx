'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';

type WorkflowStatus = 'confirmed_hospital' | 'on_route' | 'checked_in';

interface Patient {
  _id: string;
  createdAt: string;
  workflowStatus?: WorkflowStatus;
  hospitalRouting?: {
    hospitalId?: string;
    hospitalName?: string;
    hospitalAddress?: string;
    routedAt?: string;
    patientConfirmedRoute?: boolean;
    patientConfirmedAt?: string;
    estimatedArrival?: string;
    checkedInAt?: string;
  };
  location?: {
    latitude?: number;
    longitude?: number;
  };
  estimatedArrival?: string | null;
  estimatedMinutes?: number | null;
  distanceKm?: number | null;
  intake: {
    chiefComplaint?: string;
    symptoms: string[];
    severity?: number | string;
    onset?: string;
    redFlags: {
      any: boolean | string;
      details: string[];
    };
    history: {
      conditions: string[];
      meds: string[];
      allergies: string[];
    };
  };
  assistant: {
    triageLevel?: string;
    intakeSummary?: string;
    nextSteps: string[];
  };
  adminReview?: {
    adminTriageLevel?: string;
    adminNotes?: string;
  };
  user: {
    ageRange?: string;
  };
}

interface Hospital {
  _id: string;
  name: string;
  address: string;
  phone?: string;
  maxCapacity: number;
  currentPatients: number;
  availableCapacity: number;
}

interface EmergencyAlert {
  caseId: string;
  patientName: string;
  chiefComplaint: string;
  triageLevel: string;
  escalatedAt: string;
  workflowStatus?: string;
  symptoms: string[];
  severity: number | string;
  redFlags: string[];
}

export default function HospitalDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const pathname = usePathname();
  
  // Extract slug from params - handle both array and string formats
  let hospitalSlug: string | undefined = undefined;
  
  if (params) {
    const slugValue = (params as any).slug;
    if (Array.isArray(slugValue)) {
      hospitalSlug = slugValue[0];
    } else if (typeof slugValue === 'string') {
      hospitalSlug = slugValue;
    }
  }
  
  // Fallback: extract from pathname if params don't work
  if (!hospitalSlug && pathname) {
    const pathnameMatch = pathname.match(/\/hospital\/([^\/]+)/);
    if (pathnameMatch) {
      hospitalSlug = pathnameMatch[1];
      console.log('Extracted slug from pathname:', hospitalSlug);
    }
  }
  
  // Debug logging
  useEffect(() => {
    console.log('Params object:', params);
    console.log('Pathname:', pathname);
    console.log('Extracted slug:', hospitalSlug);
    if (!hospitalSlug) {
      console.warn('Hospital slug is undefined. Params:', params, 'Type:', typeof params);
    }
  }, [hospitalSlug, params, pathname]);
  
  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'checked_in' | 'on_route' | 'confirmed_hospital'>('all');
  const [emergencyAlerts, setEmergencyAlerts] = useState<EmergencyAlert[]>([]);
  const [shownAlertIds, setShownAlertIds] = useState<Set<string>>(new Set());
  const [currentAlert, setCurrentAlert] = useState<EmergencyAlert | null>(null);
  // Use ref to track dismissed alerts so it's always current in intervals
  const dismissedAlertIdsRef = useRef<Set<string>>(new Set());
  const [closingCaseId, setClosingCaseId] = useState<string | null>(null);

  // Load dismissed alerts from localStorage on mount
  useEffect(() => {
    if (hospitalSlug && typeof window !== 'undefined') {
      const storageKey = `dismissed-alerts-${hospitalSlug}`;
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        try {
          const dismissedIds = JSON.parse(saved) as string[];
          const dismissedSet = new Set<string>(dismissedIds);
          setShownAlertIds(dismissedSet);
          dismissedAlertIdsRef.current = dismissedSet;
        } catch (error) {
          console.error('Error loading dismissed alerts:', error);
        }
      }
    }
  }, [hospitalSlug]);

  // Keep ref in sync with state
  useEffect(() => {
    dismissedAlertIdsRef.current = shownAlertIds;
  }, [shownAlertIds]);

  // Save dismissed alerts to localStorage whenever they change
  useEffect(() => {
    if (hospitalSlug && typeof window !== 'undefined' && shownAlertIds.size > 0) {
      const storageKey = `dismissed-alerts-${hospitalSlug}`;
      localStorage.setItem(storageKey, JSON.stringify(Array.from(shownAlertIds)));
    }
  }, [shownAlertIds, hospitalSlug]);

  const fetchHospitalData = useCallback(async () => {
    if (!hospitalSlug) {
      console.warn('Cannot fetch hospital data: slug is undefined');
      return;
    }
    try {
      setLoading(true);
      const url = `/api/hospitals/${encodeURIComponent(hospitalSlug)}/patients`;
      console.log('Fetching hospital data from:', url);
      const response = await fetch(url);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to fetch hospital data:', response.status, errorText);
        throw new Error(`Failed to fetch hospital data: ${response.status}`);
      }
      const data = await response.json();
      setHospital(data.hospital);
      setPatients(data.patients || []);
    } catch (error) {
      console.error('Error fetching hospital data:', error);
    } finally {
      setLoading(false);
    }
  }, [hospitalSlug]);

  const checkEmergencyAlerts = useCallback(async () => {
    if (!hospitalSlug) {
      console.warn('Cannot check emergency alerts: slug is undefined');
      return;
    }
    try {
      const url = `/api/hospitals/${encodeURIComponent(hospitalSlug)}/emergency-alerts?since=60`;
      console.log('Fetching emergency alerts from:', url);
      const response = await fetch(url);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Failed to fetch emergency alerts:', response.status, errorText);
        throw new Error(`Failed to fetch emergency alerts: ${response.status}`);
      }
      const data = await response.json();
      
      if (data.alerts && data.alerts.length > 0) {
        setEmergencyAlerts(data.alerts);
        
        // Use ref to get the most current dismissed list (always up-to-date)
        const dismissedIds = dismissedAlertIdsRef.current;
        
        // Find new alerts that haven't been shown/dismissed yet
        // Only show alerts that are NOT in the dismissed list
        const newAlerts = data.alerts.filter((alert: EmergencyAlert) => 
          !dismissedIds.has(alert.caseId)
        );
        
        // Only show a new alert if there's no current alert displayed
        // This prevents showing multiple alerts at once
        if (newAlerts.length > 0 && !currentAlert) {
          const latestAlert = newAlerts.sort((a: EmergencyAlert, b: EmergencyAlert) => 
            new Date(b.escalatedAt).getTime() - new Date(a.escalatedAt).getTime()
          )[0];
          
          setCurrentAlert(latestAlert);
          // Immediately mark as shown to prevent duplicate displays
          const updated = new Set([...dismissedIds, latestAlert.caseId]);
          dismissedAlertIdsRef.current = updated;
          setShownAlertIds(updated);
          // Persist to localStorage immediately
          if (typeof window !== 'undefined') {
            const storageKey = `dismissed-alerts-${hospitalSlug}`;
            localStorage.setItem(storageKey, JSON.stringify(Array.from(updated)));
          }
        }
      }
    } catch (error) {
      console.error('Error checking emergency alerts:', error);
    }
  }, [hospitalSlug]);

  useEffect(() => {
    if (!hospitalSlug) {
      console.warn('Hospital slug not available yet, skipping fetch');
      return;
    }
    
    // Initial fetch
    fetchHospitalData();
    checkEmergencyAlerts();
    
    // Refresh every 30 seconds to get updated ETAs
    const interval = setInterval(() => {
      if (hospitalSlug) {
        fetchHospitalData();
      }
    }, 30000);
    
    // Check for emergency alerts every 10 seconds
    const alertInterval = setInterval(() => {
      if (hospitalSlug) {
        checkEmergencyAlerts();
      }
    }, 10000);
    
    return () => {
      clearInterval(interval);
      clearInterval(alertInterval);
    };
  }, [hospitalSlug, fetchHospitalData, checkEmergencyAlerts]);

  const markAlertAsDismissed = (caseId: string) => {
    // Mark this alert as dismissed permanently
    const updated = new Set([...dismissedAlertIdsRef.current, caseId]);
    dismissedAlertIdsRef.current = updated;
    setShownAlertIds(updated);
    // Persist to localStorage immediately
    if (typeof window !== 'undefined') {
      const storageKey = `dismissed-alerts-${hospitalSlug}`;
      localStorage.setItem(storageKey, JSON.stringify(Array.from(updated)));
    }
  };

  const handleDismissAlert = () => {
    if (currentAlert) {
      // Permanently mark this alert as dismissed
      markAlertAsDismissed(currentAlert.caseId);
    }
    setCurrentAlert(null);
  };

  const handleViewCase = (caseId: string) => {
    if (currentAlert) {
      // Permanently mark this alert as dismissed
      markAlertAsDismissed(currentAlert.caseId);
    }
    router.push(`/dashboard?caseId=${caseId}`);
    setCurrentAlert(null);
  };

  const handleCloseCase = async (caseId: string) => {
    if (!hospitalSlug) {
      console.error('Cannot close case: hospital slug is undefined');
      return;
    }

    if (!confirm('Are you sure you want to close this case? This action cannot be undone.')) {
      return;
    }

    try {
      setClosingCaseId(caseId);
      const response = await fetch(`/api/cases/${caseId}/close`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          hospitalSlug,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to close case');
      }

      // Refresh the hospital data to reflect the closed case
      await fetchHospitalData();
    } catch (error: any) {
      console.error('Error closing case:', error);
      alert(`Failed to close case: ${error.message}`);
    } finally {
      setClosingCaseId(null);
    }
  };

  const getTriageColor = (level?: string) => {
    switch (level) {
      case 'EMERGENCY':
        return 'bg-emergency text-white';
      case 'URGENT':
        return 'bg-urgent text-white';
      case 'NON_URGENT':
        return 'bg-non-urgent text-white';
      case 'SELF_CARE':
        return 'bg-self-care text-white';
      case 'UNCERTAIN':
        return 'bg-uncertain text-white';
      default:
        return 'bg-slate-500 text-white';
    }
  };

  const getTriageLevel = (patient: Patient) => {
    return patient.adminReview?.adminTriageLevel || patient.assistant.triageLevel || 'UNCERTAIN';
  };

  const formatETA = (estimatedArrival: string | null | undefined, estimatedMinutes: number | null | undefined) => {
    if (estimatedArrival) {
      const arrival = new Date(estimatedArrival);
      const now = new Date();
      const minutes = Math.ceil((arrival.getTime() - now.getTime()) / (1000 * 60));
      
      if (minutes <= 0) {
        return 'Arrived';
      } else if (minutes < 60) {
        return `${minutes} min`;
      } else {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        return `${hours}h ${mins}m`;
      }
    }
    if (estimatedMinutes !== null && estimatedMinutes !== undefined) {
      if (estimatedMinutes < 60) {
        return `~${estimatedMinutes} min`;
      } else {
        const hours = Math.floor(estimatedMinutes / 60);
        const mins = estimatedMinutes % 60;
        return `~${hours}h ${mins}m`;
      }
    }
    return 'Calculating...';
  };

  const filteredPatients = filter === 'all' 
    ? patients 
    : patients.filter(p => p.workflowStatus === filter);

  const checkedInPatients = patients.filter(p => p.workflowStatus === 'checked_in');
  const onRoutePatients = patients.filter(p => p.workflowStatus === 'on_route');
  const confirmedPatients = patients.filter(p => p.workflowStatus === 'confirmed_hospital');

  if (loading && !hospital) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-slate-600">Loading hospital dashboard...</p>
        </div>
      </div>
    );
  }

  if (!hospital) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 text-lg">Hospital not found</p>
          <Link href="/workflow" className="text-primary hover:underline mt-4 inline-block">
            ← Back to Workflow
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Emergency Alert Popup */}
      {currentAlert && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full border-4 border-red-600 animate-pulse">
            <div className="bg-red-600 text-white p-6 rounded-t-xl">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-3xl font-bold">EMERGENCY ALERT</h2>
                  <p className="text-red-100 mt-1">Patient requires immediate attention</p>
                </div>
                <button
                  onClick={handleDismissAlert}
                  className="text-white hover:text-red-200 transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            
            <div className="p-6 space-y-4">
              <div className="bg-red-50 border-l-4 border-red-600 p-4 rounded">
                <div className="text-sm font-semibold text-red-900 mb-2">Patient Information</div>
                <div className="text-lg font-bold text-red-900">{currentAlert.patientName}</div>
                <div className="text-sm text-red-700 mt-1">
                  Chief Complaint: {currentAlert.chiefComplaint}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Triage Level</div>
                  <div className="text-lg font-bold text-red-600">{currentAlert.triageLevel}</div>
                </div>
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase mb-1">Severity</div>
                  <div className="text-lg font-bold text-slate-900">{currentAlert.severity}/10</div>
                </div>
              </div>

              {currentAlert.symptoms.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase mb-2">Symptoms</div>
                  <div className="flex flex-wrap gap-2">
                    {currentAlert.symptoms.map((symptom, idx) => (
                      <span key={idx} className="px-3 py-1 bg-slate-100 rounded-lg text-sm text-slate-900">
                        {symptom}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {currentAlert.redFlags.length > 0 && (
                <div className="bg-red-50 border-l-4 border-red-600 p-4 rounded">
                  <div className="text-sm font-semibold text-red-900 mb-2">Red Flags</div>
                  <ul className="text-sm text-red-900 space-y-1">
                    {currentAlert.redFlags.map((flag, idx) => (
                      <li key={idx}>• {flag}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="text-xs text-slate-500">
                Alert triggered at: {new Date(currentAlert.escalatedAt).toLocaleString()}
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => handleViewCase(currentAlert.caseId)}
                  className="flex-1 bg-red-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-red-700 transition-colors"
                >
                  View Case Details
                </button>
                <button
                  onClick={handleDismissAlert}
                  className="px-6 py-3 bg-slate-200 text-slate-700 rounded-lg font-semibold hover:bg-slate-300 transition-colors"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation Header */}
      <div className="bg-white border-b border-slate-200/80 shadow-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <Image 
                    src="/Logo-no-text.png" 
                    alt="Care Flow" 
                    width={28} 
                    height={28}
                    className="object-contain"
                  />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-900 tracking-tight">Care Flow</h1>
                  <p className="text-xs text-slate-500 font-medium">Hospital Dashboard</p>
                </div>
              </div>
              <div className="h-6 w-px bg-slate-200"></div>
              <div className="flex gap-2">
                <Link
                  href="/dashboard"
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-200 ${
                    pathname === '/dashboard'
                      ? 'bg-primary text-white shadow-sm hover:shadow-md hover:bg-primary-dark'
                      : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Dashboard
                </Link>
                <Link
                  href="/workflow"
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-200 ${
                    pathname === '/workflow'
                      ? 'bg-primary text-white shadow-sm hover:shadow-md hover:bg-primary-dark'
                      : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Workflow
                </Link>
                <Link
                  href="/hospitals"
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-200 ${
                    pathname === '/hospitals'
                      ? 'bg-primary text-white shadow-sm hover:shadow-md hover:bg-primary-dark'
                      : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Hospitals
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Hospital Header */}
        <div className="mb-8">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-3xl font-bold text-slate-900 mb-2">{hospital.name}</h1>
                <p className="text-slate-600 mb-1">{hospital.address}</p>
                {hospital.phone && (
                  <p className="text-slate-600">📞 {hospital.phone}</p>
                )}
              </div>
              <div className="text-right">
                <div className="text-sm text-slate-500 mb-1">Capacity</div>
                <div className="text-2xl font-bold text-slate-900">
                  {hospital.currentPatients} / {hospital.maxCapacity}
                </div>
                <div className="text-sm text-primary font-semibold mt-1">
                  {hospital.availableCapacity} available
                </div>
                <div className="w-32 bg-slate-200 rounded-full h-2 mt-2">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      (hospital.currentPatients / hospital.maxCapacity) * 100 < 70
                        ? 'bg-self-care'
                        : (hospital.currentPatients / hospital.maxCapacity) * 100 < 90
                        ? 'bg-urgent'
                        : 'bg-emergency'
                    }`}
                    style={{ width: `${Math.min(100, (hospital.currentPatients / hospital.maxCapacity) * 100)}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Currently Here</div>
            <div className="text-3xl font-bold text-self-care">{checkedInPatients.length}</div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">On Route</div>
            <div className="text-3xl font-bold text-urgent">{onRoutePatients.length}</div>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
            <div className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Confirmed</div>
            <div className="text-3xl font-bold text-primary">{confirmedPatients.length}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-6 p-5">
          <div className="flex flex-wrap gap-2.5">
            {(['all', 'checked_in', 'on_route', 'confirmed_hospital'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-5 py-2.5 rounded-lg font-semibold transition-all duration-200 text-sm ${
                  filter === f
                    ? f === 'checked_in' ? 'bg-self-care text-white shadow-md hover:shadow-lg'
                    : f === 'on_route' ? 'bg-urgent text-white shadow-md hover:shadow-lg'
                    : f === 'confirmed_hospital' ? 'bg-primary text-white shadow-md hover:shadow-lg'
                    : 'bg-slate-700 text-white shadow-md hover:shadow-lg'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 border border-slate-200'
                }`}
              >
                {f === 'all' ? 'All Patients' : f === 'checked_in' ? 'Currently Here' : f === 'on_route' ? 'On Route' : 'Confirmed'}
                {f !== 'all' && (
                  <span className={`ml-2 px-2 py-0.5 rounded-full text-xs font-bold ${
                    filter === f ? 'bg-white/30' : 'bg-slate-200/50'
                  }`}>
                    {f === 'checked_in' ? checkedInPatients.length
                    : f === 'on_route' ? onRoutePatients.length
                    : confirmedPatients.length}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Patients List */}
        <div className="space-y-4">
          {filteredPatients.length === 0 ? (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
              <p className="text-slate-500 text-lg">No patients in this category</p>
            </div>
          ) : (
            filteredPatients.map((patient) => (
              <div key={patient._id} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 hover:shadow-md transition-all">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-bold text-slate-900">
                        {patient.intake.chiefComplaint || 'No chief complaint'}
                      </h3>
                      <span className={`px-3 py-1 rounded-lg text-sm font-bold ${getTriageColor(getTriageLevel(patient))}`}>
                        {getTriageLevel(patient)}
                      </span>
                      <span className={`px-3 py-1 rounded-lg text-sm font-bold ${
                        patient.workflowStatus === 'checked_in' ? 'bg-self-care text-white'
                        : patient.workflowStatus === 'on_route' ? 'bg-urgent text-white'
                        : 'bg-primary text-white'
                      }`}>
                        {patient.workflowStatus === 'checked_in' ? 'Here' 
                        : patient.workflowStatus === 'on_route' ? 'On Route'
                        : 'Confirmed'}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-slate-600">
                      <span>Age: <strong className="text-slate-900">{patient.user.ageRange || 'Unknown'}</strong></span>
                      <span>Severity: <strong className="text-slate-900">{patient.intake.severity || 'N/A'}/10</strong></span>
                      {patient.intake.onset && (
                        <span>Onset: <strong className="text-slate-900">{patient.intake.onset}</strong></span>
                      )}
                    </div>
                  </div>
                  {(patient.workflowStatus === 'on_route' || patient.workflowStatus === 'confirmed_hospital') && (
                    <div className="text-right ml-4">
                      <div className="text-xs text-slate-500 mb-1">Estimated Arrival</div>
                      <div className="text-lg font-bold text-urgent">
                        {formatETA(patient.estimatedArrival, patient.estimatedMinutes)}
                      </div>
                      {patient.distanceKm && (
                        <div className="text-xs text-slate-500 mt-1">
                          {patient.distanceKm.toFixed(1)} km away
                        </div>
                      )}
                    </div>
                  )}
                  {patient.workflowStatus === 'checked_in' && patient.hospitalRouting?.checkedInAt && (
                    <div className="text-right ml-4">
                      <div className="text-xs text-slate-500 mb-1">Checked In</div>
                      <div className="text-sm font-semibold text-self-care">
                        {new Date(patient.hospitalRouting.checkedInAt).toLocaleString()}
                      </div>
                    </div>
                  )}
                </div>

                {/* Symptoms */}
                {patient.intake.symptoms.length > 0 && (
                  <div className="mb-4">
                    <div className="text-sm font-semibold text-slate-700 mb-2">Symptoms:</div>
                    <div className="flex flex-wrap gap-2">
                      {patient.intake.symptoms.map((symptom, idx) => (
                        <span key={idx} className="px-3 py-1 bg-primary-light rounded-lg text-sm text-slate-900">
                          {symptom}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Summary */}
                {patient.assistant.intakeSummary && (
                  <div className="bg-blue-50 border-l-4 border-primary p-4 rounded-r-lg mb-4">
                    <div className="text-sm font-semibold text-slate-900 mb-1">AI Assessment:</div>
                    <p className="text-sm text-slate-700">{patient.assistant.intakeSummary}</p>
                  </div>
                )}

                {/* Red Flags */}
                {patient.intake.redFlags.any && patient.intake.redFlags.details.length > 0 && (
                  <div className="bg-red-50 border-l-4 border-emergency p-4 rounded-r-lg mb-4">
                    <div className="text-sm font-semibold text-red-900 mb-1">⚠️ Red Flags:</div>
                    <ul className="text-sm text-red-900 space-y-1">
                      {patient.intake.redFlags.details.map((flag, idx) => (
                        <li key={idx}>• {flag}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Medical History */}
                {(patient.intake.history.conditions.length > 0 || 
                  patient.intake.history.meds.length > 0 || 
                  patient.intake.history.allergies.length > 0) && (
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    {patient.intake.history.conditions.length > 0 && (
                      <div>
                        <div className="text-xs text-slate-500 uppercase mb-1">Conditions</div>
                        <div className="text-slate-900 font-medium">
                          {patient.intake.history.conditions.join(', ') || 'None'}
                        </div>
                      </div>
                    )}
                    {patient.intake.history.meds.length > 0 && (
                      <div>
                        <div className="text-xs text-slate-500 uppercase mb-1">Medications</div>
                        <div className="text-slate-900 font-medium">
                          {patient.intake.history.meds.join(', ') || 'None'}
                        </div>
                      </div>
                    )}
                    {patient.intake.history.allergies.length > 0 && (
                      <div>
                        <div className="text-xs text-slate-500 uppercase mb-1">Allergies</div>
                        <div className="text-slate-900 font-medium">
                          {patient.intake.history.allergies.join(', ') || 'None'}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Admin Notes */}
                {patient.adminReview?.adminNotes && (
                  <div className="mt-4 pt-4 border-t border-slate-200">
                    <div className="text-sm font-semibold text-slate-700 mb-1">Admin Notes:</div>
                    <p className="text-sm text-slate-600">{patient.adminReview.adminNotes}</p>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="mt-4 pt-4 border-t border-slate-200 flex justify-end gap-3">
                  <button
                    onClick={() => handleCloseCase(patient._id)}
                    disabled={closingCaseId === patient._id}
                    className={`px-4 py-2 rounded-lg font-semibold text-sm transition-all duration-200 ${
                      closingCaseId === patient._id
                        ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                        : 'bg-slate-700 text-white hover:bg-slate-800 hover:shadow-md'
                    }`}
                  >
                    {closingCaseId === patient._id ? (
                      <span className="flex items-center gap-2">
                        <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Closing...
                      </span>
                    ) : (
                      'Close Case'
                    )}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

