'use client';

import { useState, useEffect, useRef, useMemo, memo } from 'react';
import Image from 'next/image';
import { usePathname } from 'next/navigation';

type WorkflowStatus = 'pending_review' | 'confirmed_hospital' | 'watching' | 'on_route' | 'checked_in' | 'discharged';

interface Case {
  _id: string;
  createdAt: string;
  status: string;
  workflowStatus?: WorkflowStatus;
  hospitalRouting?: {
    hospitalId?: string;
    hospitalName?: string;
    hospitalAddress?: string;
    routedAt?: string;
    routedBy?: string;
    patientConfirmedRoute?: boolean;
    patientConfirmedAt?: string;
    estimatedArrival?: string;
    checkedInAt?: string;
    checkedInBy?: string;
  };
  user: {
    anonymousId: string;
    ageRange?: string;
    pregnant?: boolean | string;
    phone?: string;
  };
  intake: {
    chiefComplaint?: string;
    symptoms: string[];
    severity?: number | string;
    onset?: string;
    pattern?: string;
    redFlags: {
      any: boolean | string;
      details: string[];
    };
    history: {
      conditions: string[];
      meds: string[];
      allergies: string[];
    };
    vitals: {
      tempC?: number | string;
      hr?: number | string;
      spo2?: number | string;
    };
    uploadedImages?: string[];
    additionalComments?: string;
  };
  assistant: {
    triageLevel?: string;
    confidence?: number;
    reasons: string[];
    nextSteps: string[];
    monitoringPlan: string[];
    escalationTriggers: string[];
    intakeSummary?: string;
    questionsAsked: Array<{
      id: string;
      question: string;
      answer: string | null;
      timestamp: string;
    }>;
  };
  adminReview?: {
    reviewed: boolean;
    reviewedAt?: string;
    reviewedBy?: string;
    adminTriageLevel?: string;
    adminNotes?: string;
    onWatchList?: boolean;
    watchListReason?: string;
  };
  healthChecks?: Array<{
    timestamp: string;
    symptomsWorsened: boolean;
    newSymptoms: string[];
    painLevel?: number;
    notes?: string;
  }>;
}

interface DashboardData {
  cases: Case[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
  counts: {
    emergency: number;
    urgent: number;
    nonUrgent: number;
    selfCare: number;
    uncertain: number;
    watchList: number;
    pendingReview?: number;
    confirmedHospital?: number;
    watching?: number;
    onRoute?: number;
    checkedIn?: number;
    discharged?: number;
    total: number;
  };
}

// Helper functions for workflow status - defined outside components for reuse
const getWorkflowColor = (status?: WorkflowStatus) => {
  switch (status) {
    case 'pending_review':
      return 'bg-uncertain text-white';
    case 'confirmed_hospital':
      return 'bg-primary text-white';
    case 'watching':
      return 'bg-urgent text-white';
    case 'on_route':
      return 'bg-urgent text-white';
    case 'checked_in':
      return 'bg-self-care text-white';
    case 'discharged':
      return 'bg-uncertain text-white';
    default:
      return 'bg-uncertain text-white';
  }
};

const getWorkflowLabel = (status?: WorkflowStatus) => {
  switch (status) {
    case 'pending_review':
      return 'Pending Review';
    case 'confirmed_hospital':
      return 'Confirmed Hospital';
    case 'watching':
      return 'Watching Symptoms';
    case 'on_route':
      return 'On Route to Hospital';
    case 'checked_in':
      return 'Checked In at Hospital';
    case 'discharged':
      return 'Discharged';
    default:
      return 'Pending Review';
  }
};

function CaseItem({ caseItem, onClick, onDelete }: { caseItem: Case; onClick: () => void; onDelete: (e: React.MouseEvent) => void }) {
  const getTriageLevel = (caseItem: Case) => {
    return caseItem.adminReview?.adminTriageLevel || caseItem.assistant.triageLevel || 'UNCERTAIN';
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
        return 'bg-uncertain text-white';
    }
  };


  const triageLevel = getTriageLevel(caseItem);
  const workflowStatus = caseItem.workflowStatus || 'pending_review';

  return (
    <div className="p-4 bg-white rounded-lg shadow-sm border border-slate-200 hover:shadow-md hover:border-primary/30 transition-all duration-200 mb-2 group">
      <div className="flex items-start justify-between gap-4">
        <div 
          className="flex-1 min-w-0 cursor-pointer"
          onClick={onClick}
        >
          <div className="flex items-start justify-between mb-2">
            <h3 className="text-base font-semibold text-slate-900 group-hover:text-primary transition-colors pr-2">
              {caseItem.intake.chiefComplaint || 'No chief complaint'}
            </h3>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`px-2.5 py-1 rounded-md text-xs font-bold ${getTriageColor(triageLevel)}`}>
                {triageLevel}
              </span>
              <span className={`px-2.5 py-1 rounded-md text-xs font-bold ${getWorkflowColor(workflowStatus)}`}>
                {getWorkflowLabel(workflowStatus)}
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-4 flex-wrap mb-2">
            <span className="text-sm text-slate-600">
              <span className="font-medium text-slate-700">Age:</span> {caseItem.user.ageRange || 'Unknown'}
            </span>
            <span className="text-sm text-slate-600">
              <span className="font-medium text-slate-700">Severity:</span> {caseItem.intake.severity || 'Unknown'}/10
            </span>
            {caseItem.hospitalRouting?.hospitalName && (
              <span className="text-sm text-primary font-medium">
                🏥 {caseItem.hospitalRouting.hospitalName}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs text-slate-500">
              {new Date(caseItem.createdAt).toLocaleString()}
            </span>
            {caseItem.adminReview?.onWatchList && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700 border border-purple-200">
                ⭐ Watch List
              </span>
            )}
            {caseItem.healthChecks && caseItem.healthChecks.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 border border-blue-200">
                📋 {caseItem.healthChecks.length} check-in{caseItem.healthChecks.length !== 1 ? 's' : ''}
              </span>
            )}
            {caseItem.healthChecks && caseItem.healthChecks.some((check: any) => check.symptomsWorsened) && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 border border-red-200 animate-pulse">
                ⚠️ Worsening
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onDelete}
          className="flex-shrink-0 p-2 hover:bg-red-50 rounded-lg text-red-500 hover:text-red-700 transition-all duration-200"
          title="Delete case"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const pathname = usePathname();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'emergency' | 'urgent' | 'non_urgent' | 'self_care' | 'uncertain' | 'watchlist' | 'all' | 'pending_review' | 'confirmed_hospital' | 'watching' | 'on_route' | 'checked_in' | 'discharged'>('all');
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [reviewTriageLevel, setReviewTriageLevel] = useState<string>('');
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [onWatchList, setOnWatchList] = useState<boolean>(false);
  const [watchListReason, setWatchListReason] = useState<string>('');
  const [reviewing, setReviewing] = useState(false);
  const [caseLoading, setCaseLoading] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ show: boolean; message: string; count: number }>({ show: false, message: '', count: 0 });
  const [lastCaseCount, setLastCaseCount] = useState<number>(0);
  const [deletingCaseId, setDeletingCaseId] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{ show: boolean; caseId: string | null; caseTitle: string }>({ show: false, caseId: null, caseTitle: '' });
  const notificationTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [routing, setRouting] = useState(false);
  const [selectedAction, setSelectedAction] = useState<'stay_home' | 'monitor' | 'clinic' | 'hospital' | ''>('');

  useEffect(() => {
    fetchCases();
    const interval = setInterval(() => {
      checkForNewCases();
    }, 5000); // Check every 5 seconds

    return () => {
      clearInterval(interval);
      if (notificationTimeoutRef.current) {
        clearTimeout(notificationTimeoutRef.current);
      }
    };
  }, [filter]);

  const checkForNewCases = async () => {
    try {
      const response = await fetch(`/api/cases/dashboard?filter=all&limit=1`);
      if (!response.ok) return;
      const data = await response.json();
      
      if (lastCaseCount > 0 && data.counts.total > lastCaseCount) {
        const newCount = data.counts.total - lastCaseCount;
        setNotification({
          show: true,
          message: `${newCount} new case${newCount > 1 ? 's' : ''} received`,
          count: newCount,
        });
        
        // Auto-hide after 5 seconds
        if (notificationTimeoutRef.current) {
          clearTimeout(notificationTimeoutRef.current);
        }
        notificationTimeoutRef.current = setTimeout(() => {
          setNotification(prev => ({ ...prev, show: false }));
        }, 5000);
      }
      
      setLastCaseCount(data.counts.total);
    } catch (error) {
      console.error('Error checking for new cases:', error);
    }
  };

  const getSeverityOrder = (level?: string): number => {
    const order: { [key: string]: number } = {
      'EMERGENCY': 1,
      'URGENT': 2,
      'NON_URGENT': 3,
      'SELF_CARE': 4,
      'UNCERTAIN': 5,
    };
    return order[level || 'UNCERTAIN'] || 6;
  };

  const fetchCases = async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/cases/dashboard?filter=${filter}`, {
        cache: 'no-store', // Ensure fresh data
      });
      if (!response.ok) throw new Error('Failed to fetch cases');
      const data = await response.json();
      
      // Sort cases by severity, then by creation date (newest first)
      const sortedCases = [...data.cases].sort((a, b) => {
        const aLevel = a.adminReview?.adminTriageLevel || a.assistant.triageLevel || 'UNCERTAIN';
        const bLevel = b.adminReview?.adminTriageLevel || b.assistant.triageLevel || 'UNCERTAIN';
        const aOrder = getSeverityOrder(aLevel);
        const bOrder = getSeverityOrder(bLevel);
        
        if (aOrder !== bOrder) {
          return aOrder - bOrder;
        }
        
        // If same severity, sort by date (newest first)
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      });
      
      setData({ ...data, cases: sortedCases });
      setLastCaseCount(data.counts.total);
    } catch (error) {
      console.error('Error fetching cases:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (caseId: string, caseTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteConfirm({ show: true, caseId, caseTitle });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm.caseId) return;

    setDeletingCaseId(deleteConfirm.caseId);
    try {
      const response = await fetch(`/api/cases/${deleteConfirm.caseId}`, {
        method: 'DELETE',
      });

      if (!response.ok) throw new Error('Failed to delete case');

      // If the deleted case was selected, close the modal
      if (selectedCase?._id === deleteConfirm.caseId) {
        setSelectedCase(null);
      }

      setDeleteConfirm({ show: false, caseId: null, caseTitle: '' });
      fetchCases();
    } catch (error) {
      console.error('Error deleting case:', error);
      alert('Failed to delete case. Please try again.');
    } finally {
      setDeletingCaseId(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirm({ show: false, caseId: null, caseTitle: '' });
  };

  const handleReview = async () => {
    if (!selectedCase || !reviewTriageLevel) return;

    setReviewing(true);
    try {
      const response = await fetch(`/api/cases/${selectedCase._id}/review`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          triageLevel: reviewTriageLevel,
          notes: reviewNotes,
          reviewedBy: 'admin',
          onWatchList,
          watchListReason,
        }),
      });

      if (!response.ok) throw new Error('Failed to review case');

      const updated = await response.json();
      setSelectedCase(updated.case);
      fetchCases();
    } catch (error) {
      console.error('Error reviewing case:', error);
      alert('Failed to review case. Please try again.');
    } finally {
      setReviewing(false);
    }
  };

  const handleReviewAndRoute = async () => {
    if (!selectedCase || !reviewTriageLevel || !selectedAction) return;

    setReviewing(true);
    setRouting(true);
    
    try {
      // Step 1: Save the review
      const reviewResponse = await fetch(`/api/cases/${selectedCase._id}/review`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          triageLevel: reviewTriageLevel,
          notes: reviewNotes,
          reviewedBy: 'admin',
          onWatchList,
          watchListReason,
        }),
      });

      if (!reviewResponse.ok) throw new Error('Failed to review case');

      const reviewedCase = await reviewResponse.json();
      
      // Step 2: Route the patient based on selected action
      let routeType: 'monitor' | 'clinic' | 'hospital' | null = null;
      
      if (selectedAction === 'stay_home') {
        // For stay home, set to watching status with a note
        routeType = 'monitor';
        // Add a note about staying home
        const stayHomeNote = reviewNotes 
          ? `${reviewNotes}\n[Action: Stay at Home - Self-care recommended]`
          : '[Action: Stay at Home - Self-care recommended]';
        
        // Update the review with the stay home note
        await fetch(`/api/cases/${selectedCase._id}/review`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            triageLevel: reviewTriageLevel,
            notes: stayHomeNote,
            reviewedBy: 'admin',
            onWatchList,
            watchListReason,
          }),
        });
      } else if (selectedAction === 'monitor') {
        routeType = 'monitor';
      } else if (selectedAction === 'clinic') {
        routeType = 'clinic';
      } else if (selectedAction === 'hospital') {
        routeType = 'hospital';
      }

      if (routeType) {
        const routeResponse = await fetch(`/api/cases/${selectedCase._id}/route`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            routeType,
          }),
        });

        if (!routeResponse.ok) {
          const errorData = await routeResponse.json();
          throw new Error(errorData.error || 'Failed to route case');
        }

        const routedCase = await routeResponse.json();
        setSelectedCase(routedCase.case);
      } else {
        setSelectedCase(reviewedCase.case);
      }

      // Store the current case ID before refreshing
      const currentCaseId = selectedCase._id;
      const actionThatWasSelected = selectedAction;

      // Refresh the cases list
      await fetchCases();

      // Reset form
      setReviewTriageLevel('');
      setReviewNotes('');
      setOnWatchList(false);
      setWatchListReason('');
      setSelectedAction('');

      // If filtering by pending_review, move to next unreviewed case
      if (filter === 'pending_review') {
        // Wait a moment for the list to update, then find next unreviewed case
        setTimeout(async () => {
          const response = await fetch(`/api/cases/dashboard?filter=pending_review`);
          if (response.ok) {
            const updatedData = await response.json();
            const nextCase = updatedData.cases.find((c: Case) => 
              c._id !== currentCaseId && (!c.adminReview?.reviewed || !c.adminReview?.adminTriageLevel)
            ) || updatedData.cases.find((c: Case) => c._id !== currentCaseId);
            
            if (nextCase) {
              // Fetch fresh case data
              try {
                const caseResponse = await fetch(`/api/cases/${nextCase._id}`);
                if (caseResponse.ok) {
                  const caseData = await caseResponse.json();
                  const freshCase = caseData.case;
                  setSelectedCase(freshCase);
                  setReviewTriageLevel(freshCase.adminReview?.adminTriageLevel || '');
                  setReviewNotes(freshCase.adminReview?.adminNotes || '');
                  setOnWatchList(freshCase.adminReview?.onWatchList || false);
                  setWatchListReason(freshCase.adminReview?.watchListReason || '');
                  setSelectedAction('');
                } else {
                  setSelectedCase(null);
                }
              } catch {
                setSelectedCase(null);
              }
            } else {
              // No more unreviewed cases
              setSelectedCase(null);
            }
          } else {
            setSelectedCase(null);
          }
        }, 500);
      } else if (actionThatWasSelected === 'hospital' || actionThatWasSelected === 'clinic') {
        // If hospital or clinic, redirect to workflow page after a brief delay
        setTimeout(() => {
          window.location.href = '/workflow';
        }, 1500);
      } else {
        // For stay home or monitor, close modal after a brief delay
        setTimeout(() => {
          setSelectedCase(null);
        }, 1000);
      }
    } catch (error: any) {
      console.error('Error reviewing and routing case:', error);
      alert(error.message || 'Failed to process case. Please try again.');
    } finally {
      setReviewing(false);
      setRouting(false);
    }
  };

  const handleNextUnreviewed = async () => {
    if (!data || !selectedCase) return;

    const currentIndex = data.cases.findIndex(c => c._id === selectedCase._id);
    const nextCase = data.cases.find((c, index) => 
      index > currentIndex && (!c.adminReview?.reviewed || !c.adminReview?.adminTriageLevel)
    ) || data.cases.find((c) => 
      c._id !== selectedCase._id && (!c.adminReview?.reviewed || !c.adminReview?.adminTriageLevel)
    );

    if (nextCase) {
      try {
        const response = await fetch(`/api/cases/${nextCase._id}`);
        if (response.ok) {
          const caseData = await response.json();
          const freshCase = caseData.case;
          setSelectedCase(freshCase);
          setReviewTriageLevel(freshCase.adminReview?.adminTriageLevel || '');
          setReviewNotes(freshCase.adminReview?.adminNotes || '');
          setOnWatchList(freshCase.adminReview?.onWatchList || false);
          setWatchListReason(freshCase.adminReview?.watchListReason || '');
          setSelectedAction('');
        } else {
          setSelectedCase(nextCase);
          setReviewTriageLevel(nextCase.adminReview?.adminTriageLevel || '');
          setReviewNotes(nextCase.adminReview?.adminNotes || '');
          setOnWatchList(nextCase.adminReview?.onWatchList || false);
          setWatchListReason(nextCase.adminReview?.watchListReason || '');
          setSelectedAction('');
        }
      } catch (error) {
        setSelectedCase(nextCase);
        setReviewTriageLevel(nextCase.adminReview?.adminTriageLevel || '');
        setReviewNotes(nextCase.adminReview?.adminNotes || '');
        setOnWatchList(nextCase.adminReview?.onWatchList || false);
        setWatchListReason(nextCase.adminReview?.watchListReason || '');
        setSelectedAction('');
      }
    }
  };

  const handleRoute = async (routeType: 'monitor' | 'clinic' | 'hospital') => {
    if (!selectedCase) return;

    setRouting(true);
    try {
      const response = await fetch(`/api/cases/${selectedCase._id}/route`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          routeType,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to route case');
      }

      const updated = await response.json();
      
      // Update the selected case with the new workflow status
      setSelectedCase(updated.case);
      
      // Refresh the cases list to show updated workflow status
      await fetchCases();
      
      // If hospital or clinic, redirect to workflow page after a brief delay
      if (routeType === 'hospital' || routeType === 'clinic') {
        setTimeout(() => {
          window.location.href = '/workflow';
        }, 1500);
      } else {
        // For monitor, just close the modal
        setTimeout(() => {
          setSelectedCase(null);
        }, 1000);
      }
    } catch (error: any) {
      console.error('Error routing case:', error);
      alert(error.message || 'Failed to route case. Please try again.');
    } finally {
      setRouting(false);
    }
  };


  const handleWatchListToggle = async () => {
    if (!selectedCase) return;

    try {
      const response = await fetch(`/api/cases/${selectedCase._id}/watchlist`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          onWatchList: !onWatchList,
          watchListReason: watchListReason,
        }),
      });

      if (!response.ok) throw new Error('Failed to update watch list');

      const updated = await response.json();
      setSelectedCase(updated.case);
      fetchCases();
    } catch (error) {
      console.error('Error updating watch list:', error);
      alert('Failed to update watch list. Please try again.');
    }
  };

  const getTriageLevel = (caseItem: Case) => {
    return caseItem.adminReview?.adminTriageLevel || caseItem.assistant.triageLevel || 'UNCERTAIN';
  };

  const getTriageColor = (level?: string) => {
    switch (level) {
      case 'EMERGENCY':
        return 'bg-red-600 text-white border-red-700';
      case 'URGENT':
        return 'bg-orange-600 text-white border-orange-700';
      case 'NON_URGENT':
        return 'bg-yellow-500 text-white border-yellow-600';
      case 'SELF_CARE':
        return 'bg-green-600 text-white border-green-700';
      case 'UNCERTAIN':
        return 'bg-indigo-600 text-white border-indigo-700';
      default:
        return 'bg-uncertain text-white border-uncertain';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const generatePossibleConditions = (caseItem: Case): string[] => {
    const symptoms = caseItem.intake.symptoms.join(' ').toLowerCase();
    const chiefComplaint = (caseItem.intake.chiefComplaint || '').toLowerCase();
    const combined = `${chiefComplaint} ${symptoms}`;

    const conditions: string[] = [];
    
    if (combined.includes('headache')) {
      if (combined.includes('fever') || combined.includes('stiff')) {
        conditions.push('Possible: Migraine, Tension headache, or Meningitis (if severe)');
      } else {
        conditions.push('Possible: Tension headache, Migraine, or Sinusitis');
      }
    }
    if (combined.includes('chest pain')) {
      conditions.push('Possible: Angina, GERD, or Musculoskeletal pain');
    }
    if (combined.includes('fever') && combined.includes('cough')) {
      conditions.push('Possible: Upper respiratory infection, Flu, or COVID-19');
    }
    if (combined.includes('abdominal pain')) {
      conditions.push('Possible: Gastroenteritis, Appendicitis, or Irritable bowel syndrome');
    }
    if (combined.includes('shortness') || combined.includes('breathing')) {
      conditions.push('Possible: Asthma, Anxiety, or Respiratory infection');
    }

    return conditions.length > 0 ? conditions : ['Insufficient information for differential diagnosis'];
  };

  if (loading && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-text-secondary">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Professional Navigation Header */}
      <div className="bg-white border-b border-slate-200/80 shadow-sm backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
                <div className="">
                  <Image 
                    src="/Logo-no-text.png" 
                    alt="Care Flow" 
                    width={36} 
                    height={36}
                    className="object-contain"
                  />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-900 tracking-tight">Care Flow</h1>
                  <p className="text-xs text-slate-500 font-medium">Medical Triage System</p>
                </div>
              </div>
              <div className="h-6 w-px bg-slate-200"></div>
              <div className="flex gap-2">
                <a
                  href="/dashboard"
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-200 ${
                    pathname === '/dashboard'
                      ? 'bg-primary text-white shadow-sm hover:shadow-md hover:bg-primary-dark'
                      : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Dashboard
                </a>
                <a
                  href="/workflow"
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-200 ${
                    pathname === '/workflow'
                      ? 'bg-primary text-white shadow-sm hover:shadow-md hover:bg-primary-dark'
                      : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Workflow
                </a>
                <a
                  href="/hospitals"
                  className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all duration-200 ${
                    pathname === '/hospitals'
                      ? 'bg-primary text-white shadow-sm hover:shadow-md hover:bg-primary-dark'
                      : 'text-slate-700 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  Hospitals
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Notification */}
      {notification.show && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-primary text-white px-6 py-4 rounded-lg shadow-lg flex items-center space-x-3 min-w-[300px]">
            <div className="flex-shrink-0">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </div>
            <div className="flex-1">
              <p className="font-semibold">{notification.message}</p>
              <p className="text-sm text-primary-light">Click to refresh dashboard</p>
            </div>
            <button
              onClick={() => {
                setNotification({ show: false, message: '', count: 0 });
                fetchCases();
              }}
              className="text-primary-light hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="mb-6">
          <h2 className="text-3xl font-bold text-slate-900 mb-1 tracking-tight">Patient Dashboard</h2>
          <p className="text-slate-600">Review and manage patient intake cases</p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-6 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">Filter Cases</h3>
            <span className="text-xs text-slate-500">
              {data ? `${data.cases.length} case${data.cases.length !== 1 ? 's' : ''} shown` : ''}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {(['all', 'pending_review', 'emergency', 'urgent', 'non_urgent', 'self_care', 'uncertain', 'watchlist'] as const).map((f) => (
              <button
                key={f}
                onClick={() => {
                  setFilter(f);
                  setSelectedCase(null);
                }}
                className={`px-4 py-2 rounded-lg font-medium transition-all duration-200 text-sm ${
                  filter === f
                    ? f === 'pending_review' ? 'bg-uncertain text-white shadow-sm'
                    : f === 'emergency' ? 'bg-emergency text-white shadow-sm'
                    : f === 'urgent' ? 'bg-urgent text-white shadow-sm'
                    : f === 'non_urgent' ? 'bg-non-urgent text-white shadow-sm'
                    : f === 'self_care' ? 'bg-self-care text-white shadow-sm'
                    : f === 'uncertain' ? 'bg-uncertain text-white shadow-sm'
                    : f === 'watchlist' ? 'bg-purple-600 text-white shadow-sm'
                    : 'bg-primary text-white shadow-sm'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200'
                }`}
              >
                {f === 'all' ? 'All' : f === 'pending_review' ? 'Needs Review' : f === 'non_urgent' ? 'Non-Urgent' : f === 'self_care' ? 'Self-Care' : f === 'watchlist' ? 'Watch List' : f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Cases List */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          {loading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-text-secondary text-sm">Loading cases...</p>
            </div>
          ) : !data || data.cases.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-sm">No cases found in this category.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {data.cases.map((caseItem) => (
                <CaseItem
                  key={caseItem._id}
                  caseItem={caseItem}
                  onClick={async () => {
                    // Fetch fresh case data to ensure workflow status is up to date
                    try {
                      const response = await fetch(`/api/cases/${caseItem._id}`);
                      if (response.ok) {
                        const data = await response.json();
                        const freshCase = data.case;
                        setSelectedCase(freshCase);
                        setReviewTriageLevel(freshCase.adminReview?.adminTriageLevel || '');
                        setReviewNotes(freshCase.adminReview?.adminNotes || '');
                        setOnWatchList(freshCase.adminReview?.onWatchList || false);
                        setWatchListReason(freshCase.adminReview?.watchListReason || '');
                        // Infer action from workflow status
                        if (freshCase.workflowStatus === 'watching' && freshCase.adminReview?.adminNotes?.includes('Stay at Home')) {
                          setSelectedAction('stay_home');
                        } else if (freshCase.workflowStatus === 'watching') {
                          setSelectedAction('monitor');
                        } else if (freshCase.workflowStatus === 'confirmed_hospital' && freshCase.hospitalRouting?.hospitalId) {
                          // Check if it's a clinic or hospital based on notes or just assume hospital
                          setSelectedAction('hospital');
                        } else {
                          setSelectedAction('');
                        }
                      } else {
                        // Fallback to existing data if fetch fails
                        setSelectedCase(caseItem);
                        setReviewTriageLevel(caseItem.adminReview?.adminTriageLevel || '');
                        setReviewNotes(caseItem.adminReview?.adminNotes || '');
                        setOnWatchList(caseItem.adminReview?.onWatchList || false);
                        setWatchListReason(caseItem.adminReview?.watchListReason || '');
                        // Infer action from workflow status
                        if (caseItem.workflowStatus === 'watching' && caseItem.adminReview?.adminNotes?.includes('Stay at Home')) {
                          setSelectedAction('stay_home');
                        } else if (caseItem.workflowStatus === 'watching') {
                          setSelectedAction('monitor');
                        } else if (caseItem.workflowStatus === 'confirmed_hospital' && caseItem.hospitalRouting?.hospitalId) {
                          setSelectedAction('hospital');
                        } else {
                          setSelectedAction('');
                        }
                      }
                    } catch (error) {
                      // Fallback to existing data on error
                      setSelectedCase(caseItem);
                      setReviewTriageLevel(caseItem.adminReview?.adminTriageLevel || '');
                      setReviewNotes(caseItem.adminReview?.adminNotes || '');
                      setOnWatchList(caseItem.adminReview?.onWatchList || false);
                      setWatchListReason(caseItem.adminReview?.watchListReason || '');
                      setSelectedAction('');
                    }
                  }}
                  onDelete={(e) => handleDeleteClick(caseItem._id, caseItem.intake.chiefComplaint || 'this case', e)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

        {/* Ultra-Fast Case Detail Modal */}
        {selectedCase && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50" style={{ animation: 'fadeIn 0.15s ease-out' }}>
            <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col border border-slate-200">
              {/* Professional Header */}
              <div className="bg-gradient-to-r from-primary via-primary to-primary-dark text-white px-6 py-4 flex justify-between items-center shadow-lg">
                <div className="flex items-center space-x-3">
                  <span className={`px-3 py-1 rounded-full text-sm font-bold ${getTriageColor(getTriageLevel(selectedCase))}`}>
                    {getTriageLevel(selectedCase)}
                  </span>
                  <h2 className="text-xl font-bold tracking-tight">{selectedCase.intake.chiefComplaint || 'Case Details'}</h2>
                  {selectedCase.adminReview?.onWatchList && (
                    <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-white/20 text-white border border-white/30">
                      ⭐ Watch
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleDeleteClick(selectedCase._id, selectedCase.intake.chiefComplaint || 'this case', {} as React.MouseEvent)}
                    className="text-white/80 hover:text-white p-1.5 hover:bg-red-500/20 rounded"
                    title="Delete"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                  <button
                    onClick={() => {
                      setSelectedCase(null);
                      setReviewTriageLevel('');
                      setReviewNotes('');
                      setOnWatchList(false);
                      setWatchListReason('');
                      setSelectedAction('');
                    }}
                    className="text-white/80 hover:text-white"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Simplified Content - Single Column, Large Text */}
              <div className="flex-1 overflow-y-auto p-6 space-y-5">
                {/* AI Summary - Most Important */}
                {selectedCase.assistant.intakeSummary && (
                  <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-bold text-blue-900 text-base">🤖 AI Assessment</h3>
                      {selectedCase.assistant.confidence && (
                        <span className="text-sm text-blue-700 font-semibold">{(selectedCase.assistant.confidence * 100).toFixed(0)}% confidence</span>
                      )}
                    </div>
                    <p className="text-blue-900 text-base leading-relaxed">{selectedCase.assistant.intakeSummary}</p>
                  </div>
                )}

                {/* Key Info - Less Crowded */}
                <div className="flex flex-wrap gap-4">
                  <div className="bg-primary-light px-5 py-3 rounded-lg flex-1 min-w-[140px]">
                    <div className="text-xs text-text-muted uppercase mb-1">Severity</div>
                    <div className="text-xl font-bold text-text-primary">{selectedCase.intake.severity || 'N/A'}/10</div>
                  </div>
                  <div className="bg-primary-light px-5 py-3 rounded-lg flex-1 min-w-[140px]">
                    <div className="text-xs text-text-muted uppercase mb-1">Age</div>
                    <div className="text-lg font-bold text-text-primary">{selectedCase.user.ageRange || 'Unknown'}</div>
                  </div>
                  {selectedCase.intake.onset && (
                    <div className="bg-primary-light px-5 py-3 rounded-lg flex-1 min-w-[140px]">
                      <div className="text-xs text-text-muted uppercase mb-1">Onset</div>
                      <div className="text-sm font-semibold text-text-primary">{selectedCase.intake.onset}</div>
                    </div>
                  )}
                </div>

                {/* Contact Info */}
                {selectedCase.user.phone && (
                  <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <span className="text-blue-600">📞</span>
                      <div>
                        <div className="text-xs text-blue-700 font-semibold uppercase mb-0.5">Contact Phone</div>
                        <a href={`tel:${selectedCase.user.phone}`} className="text-lg font-bold text-blue-900 hover:text-blue-700">
                          {selectedCase.user.phone.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3')}
                        </a>
                      </div>
                    </div>
                  </div>
                )}

                {/* Symptoms - Large & Clear */}
                <div>
                  <h3 className="font-bold text-text-primary text-base mb-3">Symptoms</h3>
                  <div className="bg-primary-light p-5 rounded-lg">
                    <div className="space-y-2.5">
                      {selectedCase.intake.symptoms.length > 0 ? (
                        selectedCase.intake.symptoms.map((symptom, idx) => (
                          <div key={idx} className="text-base text-text-primary font-medium">• {symptom}</div>
                        ))
                      ) : (
                        <div className="text-text-muted">None listed</div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Red Flags - Prominent */}
                {selectedCase.intake.redFlags.any && (
                  <div className="bg-red-50 border-2 border-red-300 p-4 rounded-lg">
                    <h3 className="font-bold text-red-900 text-base mb-2">⚠️ Red Flags</h3>
                    <div className="space-y-1">
                      {selectedCase.intake.redFlags.details.map((flag, idx) => (
                        <div key={idx} className="text-base text-red-900 font-medium">• {flag}</div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Possible Conditions - Compact */}
                <div>
                  <h3 className="font-bold text-gray-900 text-base mb-2">🔍 Possible Conditions</h3>
                  <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-lg">
                    <p className="text-xs text-yellow-800 mb-2 italic">⚠️ NOT a diagnosis. Professional evaluation required.</p>
                    <div className="space-y-1">
                      {generatePossibleConditions(selectedCase).map((condition, idx) => (
                        <div key={idx} className="text-sm text-yellow-900 font-medium">• {condition}</div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Next Steps - Clear */}
                {selectedCase.assistant.nextSteps.length > 0 && (
                  <div>
                    <h3 className="font-bold text-gray-900 text-base mb-2">📋 Next Steps</h3>
                    <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-lg space-y-2">
                      {selectedCase.assistant.nextSteps.map((step, idx) => (
                        <div key={idx} className="text-base text-green-900 font-medium">• {step}</div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Medical History - Compact */}
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-xs text-gray-500 uppercase mb-1">Conditions</div>
                    <div className="text-gray-900 font-medium">{selectedCase.intake.history.conditions.join(', ') || 'None'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 uppercase mb-1">Medications</div>
                    <div className="text-gray-900 font-medium">{selectedCase.intake.history.meds.join(', ') || 'None'}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 uppercase mb-1">Allergies</div>
                    <div className="text-gray-900 font-medium">{selectedCase.intake.history.allergies.join(', ') || 'None'}</div>
                  </div>
                </div>


                {/* Uploaded Images */}
                {selectedCase.intake.uploadedImages && selectedCase.intake.uploadedImages.length > 0 && (
                  <div className="border-t-2 border-gray-200 pt-5">
                  <h3 className="font-bold text-gray-900 text-base mb-3">📷 Patient Uploaded Images</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {selectedCase.intake.uploadedImages.map((img, idx) => (
                      <div key={idx} className="relative group">
                        <img
                          src={img}
                          alt={`Upload ${idx + 1}`}
                          className="w-full h-32 object-cover rounded-lg border-2 border-gray-200 cursor-pointer hover:border-blue-500 transition"
                          onClick={() => window.open(img, '_blank')}
                        />
                        <div className="absolute bottom-2 right-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                          Image {idx + 1}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                )}

                {/* Additional Comments */}
                {selectedCase.intake.additionalComments && (
                  <div className="border-t-2 border-gray-200 pt-5">
                    <h3 className="font-bold text-gray-900 text-base mb-3">💬 Additional Comments</h3>
                    <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg">
                      <p className="text-gray-900 whitespace-pre-wrap">{selectedCase.intake.additionalComments}</p>
                    </div>
                  </div>
                )}

                {/* Workflow Status Display - Consolidated */}
                {selectedCase.workflowStatus && (selectedCase.adminReview?.reviewed || selectedCase.adminReview?.adminTriageLevel) && (
                  <div className="border-t-2 border-slate-200 pt-5">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-bold text-slate-900 text-base">Workflow Status</h3>
                      <a
                        href="/workflow"
                        className="text-sm text-primary hover:text-primary-dark font-medium flex items-center gap-1"
                      >
                        Manage Workflow
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </a>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                      <div className="flex items-center gap-3 mb-3">
                        <span className="text-xs text-slate-600 font-semibold uppercase">Status:</span>
                        <span className={`px-3 py-1 rounded-full text-sm font-bold ${getWorkflowColor(selectedCase.workflowStatus)}`}>
                          {getWorkflowLabel(selectedCase.workflowStatus)}
                        </span>
                      </div>
                      {selectedCase.hospitalRouting?.hospitalName && (
                        <div className="mt-3 pt-3 border-t border-slate-200 space-y-2 text-sm">
                          <div>
                            <span className="font-semibold text-slate-700">Hospital:</span>
                            <span className="ml-2 text-slate-900">{selectedCase.hospitalRouting.hospitalName}</span>
                          </div>
                          {selectedCase.hospitalRouting.hospitalAddress && (
                            <div className="text-slate-600">{selectedCase.hospitalRouting.hospitalAddress}</div>
                          )}
                          {selectedCase.hospitalRouting.patientConfirmedRoute && (
                            <div className="flex items-center gap-2 text-green-700 font-medium">
                              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                              </svg>
                              Patient confirmed on route
                              {selectedCase.hospitalRouting.estimatedArrival && (
                                <span className="text-slate-600 font-normal">
                                  • ETA: {new Date(selectedCase.hospitalRouting.estimatedArrival).toLocaleString()}
                                </span>
                              )}
                            </div>
                          )}
                          {selectedCase.hospitalRouting.routedAt && (
                            <div className="text-slate-500 text-xs">
                              Routed: {new Date(selectedCase.hospitalRouting.routedAt).toLocaleString()}
                            </div>
                          )}
                          {selectedCase.hospitalRouting.checkedInAt && (
                            <div className="flex items-center gap-2 text-green-700 font-medium">
                              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                              </svg>
                              Checked In: {new Date(selectedCase.hospitalRouting.checkedInAt).toLocaleString()}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Review & Decision Section */}
                <div className="border-t-2 border-gray-200 pt-5">
                  <h3 className="font-bold text-gray-900 text-base mb-4">Review & Decide Patient Action</h3>
                  
                  <div className="space-y-5">
                    {/* Triage Level */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Triage Level *
                      </label>
                      <select
                        value={reviewTriageLevel}
                        onChange={(e) => setReviewTriageLevel(e.target.value)}
                        className="w-full px-4 py-3 text-base border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        required
                      >
                        <option value="">Select...</option>
                        <option value="EMERGENCY">EMERGENCY</option>
                        <option value="URGENT">URGENT</option>
                        <option value="NON_URGENT">NON_URGENT</option>
                        <option value="SELF_CARE">SELF_CARE</option>
                        <option value="UNCERTAIN">UNCERTAIN</option>
                      </select>
                    </div>

                    {/* Patient Action Decision */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-3">
                        What should the patient do? *
                      </label>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedAction('stay_home');
                            if (!reviewTriageLevel) setReviewTriageLevel('SELF_CARE');
                          }}
                          className={`p-5 rounded-lg border-2 transition-all text-center ${
                            selectedAction === 'stay_home'
                              ? 'border-primary bg-primary-light'
                              : 'border-gray-300 hover:border-primary/50 bg-white'
                          }`}
                        >
                          <div className="text-3xl mb-2">🏠</div>
                          <div className="font-semibold text-text-primary text-sm">Stay at Home</div>
                          <div className="text-xs text-text-muted mt-1">Self-care</div>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedAction('monitor');
                            if (!reviewTriageLevel) setReviewTriageLevel('NON_URGENT');
                          }}
                          className={`p-5 rounded-lg border-2 transition-all text-center ${
                            selectedAction === 'monitor'
                              ? 'border-primary bg-primary-light'
                              : 'border-gray-300 hover:border-primary/50 bg-white'
                          }`}
                        >
                          <div className="text-3xl mb-2">👁️</div>
                          <div className="font-semibold text-text-primary text-sm">Monitor</div>
                          <div className="text-xs text-text-muted mt-1">Watch symptoms</div>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedAction('clinic');
                            if (!reviewTriageLevel) setReviewTriageLevel('NON_URGENT');
                          }}
                          className={`p-5 rounded-lg border-2 transition-all text-center ${
                            selectedAction === 'clinic'
                              ? 'border-primary bg-primary-light'
                              : 'border-gray-300 hover:border-primary/50 bg-white'
                          }`}
                        >
                          <div className="text-3xl mb-2">🏥</div>
                          <div className="font-semibold text-text-primary text-sm">Send to Clinic</div>
                          <div className="text-xs text-text-muted mt-1">Auto-select nearest</div>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedAction('hospital');
                            if (!reviewTriageLevel) setReviewTriageLevel('URGENT');
                          }}
                          className={`p-5 rounded-lg border-2 transition-all text-center ${
                            selectedAction === 'hospital'
                              ? 'border-primary bg-primary-light'
                              : 'border-gray-300 hover:border-primary/50 bg-white'
                          }`}
                        >
                          <div className="text-3xl mb-2">🚑</div>
                          <div className="font-semibold text-text-primary text-sm">Send to Hospital</div>
                          <div className="text-xs text-text-muted mt-1">Auto-select nearest</div>
                        </button>
                      </div>
                    </div>

                    {/* Watch List */}
                    <div>
                      <label className="flex items-center space-x-3 cursor-pointer bg-purple-50 px-4 py-3 rounded-lg border-2 border-purple-200">
                        <input
                          type="checkbox"
                          checked={onWatchList}
                          onChange={(e) => setOnWatchList(e.target.checked)}
                          className="w-5 h-5 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                        />
                        <span className="text-sm font-semibold text-gray-700">Add to Watch List</span>
                      </label>
                    </div>

                    {onWatchList && (
                      <div>
                        <input
                          type="text"
                          value={watchListReason}
                          onChange={(e) => setWatchListReason(e.target.value)}
                          className="w-full px-4 py-3 text-base border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                          placeholder="Watch list reason..."
                        />
                      </div>
                    )}

                    {/* Notes */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Notes
                      </label>
                      <textarea
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        rows={3}
                        className="w-full px-4 py-3 text-base border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                        placeholder="Add review notes..."
                      />
                    </div>

                    {/* Action Buttons */}
                    <div className="flex space-x-4">
                      <button
                        onClick={() => {
                          setSelectedCase(null);
                          setReviewTriageLevel('');
                          setReviewNotes('');
                          setOnWatchList(false);
                          setWatchListReason('');
                          setSelectedAction('');
                        }}
                        className="flex-1 bg-border-default hover:bg-border-subtle text-text-primary font-semibold py-3 px-6 rounded-lg text-base"
                      >
                        Cancel
                      </button>
                      {filter === 'pending_review' && data && data.cases.length > 1 && (
                        <button
                          onClick={handleNextUnreviewed}
                          disabled={reviewing || routing}
                          className="px-4 bg-gray-200 hover:bg-gray-300 text-text-primary font-semibold py-3 rounded-lg text-base transition-colors"
                          title="Skip to next unreviewed case"
                        >
                          Next →
                        </button>
                      )}
                      <button
                        onClick={handleReviewAndRoute}
                        disabled={!reviewTriageLevel || !selectedAction || reviewing || routing}
                        className="flex-1 bg-primary hover:bg-primary-dark disabled:bg-text-disabled text-white font-semibold py-3 px-6 rounded-lg text-base shadow-md transition-colors"
                      >
                        {(reviewing || routing) ? 'Processing...' : 'Save & Route Patient'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {deleteConfirm.show && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fade-in">
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full animate-scale-in">
              <div className="p-6">
                <div className="flex items-center justify-center w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full">
                  <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h3 className="text-xl font-bold text-gray-900 text-center mb-2">Delete Case?</h3>
                <p className="text-gray-600 text-center mb-1">
                  Are you sure you want to delete
                </p>
                <p className="text-gray-900 font-semibold text-center mb-6">
                  "{deleteConfirm.caseTitle || 'this case'}"?
                </p>
                <p className="text-red-600 text-sm text-center mb-6 bg-red-50 p-3 rounded-lg">
                  ⚠️ This action cannot be undone. All case data will be permanently deleted.
                </p>
                <div className="flex space-x-4">
                  <button
                    onClick={handleDeleteCancel}
                    className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 px-6 rounded-xl transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteConfirm}
                    disabled={deletingCaseId !== null}
                    className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white font-semibold py-3 px-6 rounded-xl transition-all shadow-lg"
                  >
                    {deletingCaseId ? 'Deleting...' : 'Delete Case'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

      <style jsx global>{`
          @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
          @keyframes slide-in {
            from {
              transform: translateX(100%);
              opacity: 0;
            }
            to {
              transform: translateX(0);
              opacity: 1;
            }
          }
          .animate-slide-in {
            animation: slide-in 0.2s ease-out;
          }
      `}</style>
    </div>
  );
}
