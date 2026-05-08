'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, usePathname } from 'next/navigation';

type WorkflowStatus = 'pending_review' | 'confirmed_hospital' | 'watching' | 'on_route' | 'checked_in' | 'discharged';

interface Hospital {
  _id: string;
  name: string;
  slug: string;
  address: string;
  phone?: string;
  maxCapacity: number;
  currentPatients: number;
  availableCapacity: number;
  capacityPercentage: number;
  isActive: boolean;
}

interface Case {
  _id: string;
  createdAt: string;
  workflowStatus?: WorkflowStatus;
  hospitalRouting?: {
    hospitalId?: string;
    hospitalName?: string;
    hospitalAddress?: string;
    routedAt?: string;
    patientConfirmedRoute?: boolean;
    estimatedArrival?: string;
    checkedInAt?: string;
  };
  intake: {
    chiefComplaint?: string;
  };
  user: {
    ageRange?: string;
  };
}

interface DashboardData {
  cases: Case[];
  counts: {
    pendingReview: number;
    confirmedHospital: number;
    watching: number;
    onRoute: number;
    checkedIn: number;
    discharged: number;
  };
}

// Patient Routing Card - For routing patients to hospitals
function PatientRoutingCard({ caseItem, hospitals, onUpdate }: { caseItem: Case; hospitals: Hospital[]; onUpdate: () => void }) {
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>(caseItem.workflowStatus || 'pending_review');
  const [hospitalId, setHospitalId] = useState<string>(caseItem.hospitalRouting?.hospitalId || '');
  const [updating, setUpdating] = useState(false);
  const [showHospitalSelect, setShowHospitalSelect] = useState(false);

  // Auto-select hospital when status changes to confirmed_hospital
  useEffect(() => {
    if (workflowStatus === 'confirmed_hospital' && !hospitalId) {
      // Find hospital with most available capacity
      const bestHospital = hospitals
        .filter(h => h.isActive)
        .sort((a, b) => b.availableCapacity - a.availableCapacity)[0];
      if (bestHospital) {
        setHospitalId(bestHospital._id);
      }
    }
  }, [workflowStatus, hospitals, hospitalId]);

  const handleUpdate = async () => {
    // Allow confirmed_hospital without hospital - backend will auto-suggest
    if (!hospitalId && (workflowStatus === 'on_route' || workflowStatus === 'checked_in')) {
      alert('Please select a hospital');
      return;
    }

    setUpdating(true);
    try {
      const selectedHospital = hospitals.find(h => h._id === hospitalId);
      
      const response = await fetch(`/api/cases/${caseItem._id}/workflow`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflowStatus,
          hospitalId: hospitalId || undefined,
          hospitalName: selectedHospital?.name || undefined,
          hospitalAddress: selectedHospital?.address || undefined,
          routedBy: 'admin',
        }),
      });

      if (!response.ok) throw new Error('Failed to update');

      const updatedCase = await response.json();
      
      // Update local state with the returned case (which may have auto-suggested hospital)
      if (updatedCase.case?.hospitalRouting?.hospitalId && !hospitalId) {
        setHospitalId(updatedCase.case.hospitalRouting.hospitalId);
      }

      if (workflowStatus === 'confirmed_hospital') {
        await fetch(`/api/cases/${caseItem._id}/notify`, { method: 'POST' });
      }

      onUpdate();
    } catch (error) {
      alert('Failed to update');
    } finally {
      setUpdating(false);
    }
  };

  const getStatusColor = (status?: WorkflowStatus) => {
    const colors: { [key: string]: string } = {
      pending_review: 'bg-uncertain text-white',
      confirmed_hospital: 'bg-primary text-white',
      watching: 'bg-urgent text-white',
      on_route: 'bg-urgent text-white',
      checked_in: 'bg-self-care text-white',
      discharged: 'bg-uncertain text-white',
    };
    return colors[status || 'pending_review'] || 'bg-uncertain text-white';
  };

  const needsHospital = workflowStatus === 'confirmed_hospital' || workflowStatus === 'on_route' || workflowStatus === 'checked_in';
  const selectedHospital = hospitals.find(h => h._id === hospitalId);

  return (
    <div className="bg-bg-main rounded-lg shadow-sm border border-border-default p-4 hover:shadow-md transition-shadow">
      <div className="mb-4">
        <h3 className="font-semibold text-text-primary text-sm mb-2">{caseItem.intake.chiefComplaint || 'No complaint'}</h3>
        <div className="flex items-center gap-2 mb-2">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(caseItem.workflowStatus)}`}>
            {caseItem.workflowStatus?.replace('_', ' ') || 'Pending'}
          </span>
          <span className="text-xs text-text-muted">{caseItem.user.ageRange || 'Unknown'}</span>
        </div>
        {caseItem.hospitalRouting?.hospitalName && (
          <div className="text-xs text-primary mt-1 font-medium">🏥 {caseItem.hospitalRouting.hospitalName}</div>
        )}
        {caseItem.hospitalRouting?.estimatedArrival && (
          <div className="text-xs text-urgent mt-1">
            ⏱️ ETA: {new Date(caseItem.hospitalRouting.estimatedArrival).toLocaleString()}
          </div>
        )}
      </div>

      <div className="space-y-3">
        {/* Status Select */}
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">Status</label>
          <select
            value={workflowStatus}
            onChange={(e) => {
              setWorkflowStatus(e.target.value as WorkflowStatus);
              if (e.target.value === 'confirmed_hospital' && !hospitalId) {
                setShowHospitalSelect(true);
              }
            }}
            className="w-full px-3 py-2 border border-border-default rounded-md text-sm focus:ring-2 focus:ring-focus-ring focus:border-primary bg-bg-main"
          >
            <option value="confirmed_hospital">Confirmed - Send to Hospital</option>
            <option value="on_route">On Route</option>
            <option value="checked_in">Checked In</option>
            <option value="discharged">Discharged</option>
          </select>
        </div>

        {/* Hospital Select - Improved UI */}
        {needsHospital && (
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1">Hospital</label>
            {selectedHospital ? (
              <div className="border border-border-default rounded-md p-2 bg-primary-light">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="text-sm font-medium text-text-primary">{selectedHospital.name}</div>
                    <div className="text-xs text-text-secondary mt-0.5">{selectedHospital.address}</div>
                    <div className="text-xs text-primary mt-1">
                      {selectedHospital.availableCapacity} beds available
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setHospitalId('');
                      setShowHospitalSelect(true);
                    }}
                    className="ml-2 text-xs text-primary hover:text-primary-dark font-medium"
                  >
                    Change
                  </button>
                </div>
              </div>
            ) : (
              <select
                value={hospitalId}
                onChange={(e) => {
                  setHospitalId(e.target.value);
                  setShowHospitalSelect(false);
                }}
                className="w-full px-3 py-2 border border-border-default rounded-md text-sm focus:ring-2 focus:ring-focus-ring focus:border-primary bg-bg-main"
                autoFocus={showHospitalSelect}
              >
                <option value="">Select hospital...</option>
                {hospitals
                  .filter(h => h.isActive)
                  .sort((a, b) => b.availableCapacity - a.availableCapacity)
                  .map((h) => (
                    <option key={h._id} value={h._id}>
                      {h.name} - {h.availableCapacity} available
                    </option>
                  ))}
              </select>
            )}
          </div>
        )}

        <button
          onClick={handleUpdate}
          disabled={updating || ((workflowStatus === 'on_route' || workflowStatus === 'checked_in') && !hospitalId)}
          className="w-full bg-primary hover:bg-primary-dark text-white py-2 rounded-md text-sm font-medium disabled:bg-text-disabled disabled:cursor-not-allowed transition-colors"
        >
          {updating ? 'Updating...' : workflowStatus === 'confirmed_hospital' && !hospitalId ? 'Confirm & Auto-Select Hospital' : 'Update Status'}
        </button>
      </div>
    </div>
  );
}

export default function WorkflowPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [data, setData] = useState<DashboardData | null>(null);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  const fetchCases = async () => {
    try {
      // For patient routing, only show confirmed_hospital and later statuses
      let filterParam = filter === 'all' ? 'all' : filter;
      if (filter === 'all') {
        // Fetch all confirmed cases
        filterParam = 'confirmed_hospital';
      }
      const response = await fetch(`/api/cases/dashboard?filter=${filterParam}`);
      if (!response.ok) throw new Error('Failed to fetch cases');
      const fetchedData = await response.json();
      
      // Filter to only show confirmed cases and later
      fetchedData.cases = fetchedData.cases.filter((c: Case) => 
        c.workflowStatus === 'confirmed_hospital' || 
        c.workflowStatus === 'on_route' || 
        c.workflowStatus === 'checked_in' || 
        c.workflowStatus === 'discharged'
      );
      
      setData(fetchedData);
    } catch (error) {
      console.error('Error fetching cases:', error);
    }
  };


  const fetchHospitals = async () => {
    try {
      const response = await fetch('/api/hospitals?activeOnly=false');
      if (!response.ok) throw new Error('Failed to fetch hospitals');
      const data = await response.json();
      setHospitals(data.hospitals || []);
    } catch (error) {
      console.error('Error fetching hospitals:', error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchCases(), fetchHospitals()]);
      setLoading(false);
    };
    loadData();
  }, [filter]);

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
            {data && (
              <div className="flex items-center space-x-6 text-sm">
                <div className="text-center">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Pending</div>
                  <div className="text-lg font-bold text-slate-900">{data.counts.pendingReview || 0}</div>
                </div>
                <div className="h-8 w-px bg-slate-200"></div>
                <div className="text-center">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">On Route</div>
                  <div className="text-lg font-bold text-urgent">{data.counts.onRoute || 0}</div>
                </div>
                <div className="h-8 w-px bg-slate-200"></div>
                <div className="text-center">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Checked In</div>
                  <div className="text-lg font-bold text-self-care">{data.counts.checkedIn || 0}</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 mb-2 tracking-tight">Workflow Management</h1>
            <p className="text-slate-600 text-lg">Manage patient routing</p>
          </div>

          {/* Info Banner */}
          <div className="bg-primary-light border-l-4 border-primary p-4 rounded-r-lg mb-4">
            <p className="text-sm text-text-primary">
              <strong>Auto-Routing:</strong> Patients sent from the Dashboard are automatically routed to the nearest hospital with available capacity to ensure even distribution.
            </p>
          </div>

          {/* Filters */}
          <div className="bg-bg-main rounded-lg shadow-sm p-4 mb-4">
            <div className="flex flex-wrap gap-2">
              {['all', 'confirmed_hospital', 'on_route', 'checked_in', 'discharged'].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    filter === f
                      ? 'bg-primary text-white'
                      : 'bg-primary-light text-text-secondary hover:bg-primary-light/80'
                  }`}
                >
                  {f === 'all' ? 'All Confirmed' : f.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Cases List */}
          <div className="bg-bg-main rounded-lg shadow-sm p-6">
            {loading ? (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-3"></div>
                <p className="text-text-secondary">Loading cases...</p>
              </div>
            ) : !data || data.cases.length === 0 ? (
              <div className="text-center py-12 text-text-muted">
                <p>No cases found in this category.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {data.cases.map((caseItem) => (
                  <PatientRoutingCard key={caseItem._id} caseItem={caseItem} hospitals={hospitals} onUpdate={fetchCases} />
                ))}
              </div>
            )}
          </div>

      </div>
    </div>
  );
}
