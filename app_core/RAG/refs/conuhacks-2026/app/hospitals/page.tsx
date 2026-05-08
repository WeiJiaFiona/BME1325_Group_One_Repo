'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useRouter, usePathname } from 'next/navigation';

interface Hospital {
  _id: string;
  name: string;
  slug: string;
  address: string;
  city: string;
  phone?: string;
  specialties: string[];
  maxCapacity: number;
  currentPatients: number;
  availableCapacity: number;
  capacityPercentage: number;
  isActive: boolean;
}

export default function HospitalsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'inactive'>('all');

  useEffect(() => {
    fetchHospitals();
  }, [filter]);

  const fetchHospitals = async () => {
    try {
      setLoading(true);
      const activeOnly = filter === 'active';
      const response = await fetch(`/api/hospitals?activeOnly=${activeOnly}`);
      if (!response.ok) throw new Error('Failed to fetch hospitals');
      const data = await response.json();
      
      const hospitalsWithCapacity = (data.hospitals || []).map((h: any) => ({
        ...h,
        specialties: h.specialties || [], // Ensure specialties is always an array
        availableCapacity: Math.max(0, h.maxCapacity - (h.currentPatients || 0)),
        capacityPercentage: ((h.currentPatients || 0) / h.maxCapacity) * 100,
      }));
      
      setHospitals(hospitalsWithCapacity);
    } catch (error) {
      console.error('Error fetching hospitals:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleHospitalClick = (slug: string) => {
    router.push(`/hospital/${slug}/dashboard`);
  };

  const handleToggleActive = async (slug: string, isActive: boolean, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const response = await fetch(`/api/hospitals/${slug}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ isActive }),
      });
      if (!response.ok) throw new Error('Failed to update hospital');
      await fetchHospitals();
    } catch (error) {
      alert('Failed to update hospital status');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-slate-600">Loading hospitals...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Navigation Header */}
      <div className="bg-white border-b border-slate-200/80 shadow-sm sticky top-0 z-40">
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
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2 tracking-tight">Hospitals</h1>
          <p className="text-slate-600 text-lg">View and manage all hospitals</p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 mb-6 p-5">
          <div className="flex flex-wrap gap-2.5">
            {(['all', 'active', 'inactive'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-5 py-2.5 rounded-lg font-semibold transition-all duration-200 text-sm ${
                  filter === f
                    ? 'bg-primary text-white shadow-md hover:shadow-lg'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 hover:text-slate-900 border border-slate-200'
                }`}
              >
                {f === 'all' ? 'All Hospitals' : f === 'active' ? 'Active' : 'Inactive'}
              </button>
            ))}
          </div>
        </div>

        {/* Hospitals Grid */}
        {hospitals.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
            <p className="text-slate-500 text-lg">No hospitals found</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {hospitals.map((hospital) => {
              const percent = hospital.capacityPercentage || 0;
              const color = percent < 70 ? 'bg-self-care' : percent < 90 ? 'bg-urgent' : 'bg-emergency';
              
              return (
                <div
                  key={hospital._id}
                  className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 hover:shadow-md hover:border-primary/30 transition-all cursor-pointer"
                  onClick={() => handleHospitalClick(hospital.slug)}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex-1">
                      <h3 className="text-xl font-bold text-slate-900 mb-1">{hospital.name}</h3>
                      <p className="text-sm text-slate-600 mb-1">{hospital.address}</p>
                      {hospital.phone && (
                        <p className="text-sm text-slate-600">📞 {hospital.phone}</p>
                      )}
                    </div>
                    <span className={`px-3 py-1 rounded-lg text-xs font-bold ${
                      hospital.isActive ? 'bg-self-care-light text-self-care' : 'bg-emergency-light text-emergency'
                    }`}>
                      {hospital.isActive ? 'Active' : 'Inactive'}
                    </span>
                  </div>

                  {/* Specialties */}
                  {hospital.specialties && hospital.specialties.length > 0 && (
                    <div className="mb-4">
                      <div className="flex flex-wrap gap-1.5">
                        {hospital.specialties.slice(0, 3).map((specialty: string, idx: number) => (
                          <span key={idx} className="px-2 py-1 bg-primary-light rounded text-xs text-slate-700 font-medium">
                            {specialty}
                          </span>
                        ))}
                        {hospital.specialties.length > 3 && (
                          <span className="px-2 py-1 bg-slate-100 rounded text-xs text-slate-500">
                            +{hospital.specialties.length - 3}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Capacity */}
                  <div className="mb-4">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-semibold text-slate-700">Capacity</span>
                      <span className="text-sm font-bold text-slate-900">
                        {hospital.currentPatients} / {hospital.maxCapacity}
                      </span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-3">
                      <div
                        className={`${color} h-3 rounded-full transition-all duration-500`}
                        style={{ width: `${Math.min(100, percent)}%` }}
                      ></div>
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      <span className="text-xs text-slate-500">
                        {percent.toFixed(0)}% full
                      </span>
                      <span className="text-sm font-semibold text-primary">
                        {hospital.availableCapacity} available
                      </span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 pt-4 border-t border-slate-200">
                    <button
                      onClick={(e) => handleToggleActive(hospital.slug, !hospital.isActive, e)}
                      className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors ${
                        hospital.isActive 
                          ? 'bg-emergency hover:bg-emergency/90 text-white' 
                          : 'bg-self-care hover:bg-green-600 text-white'
                      }`}
                    >
                      {hospital.isActive ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleHospitalClick(hospital.slug);
                      }}
                      className="flex-1 py-2 rounded-lg text-sm font-semibold bg-primary hover:bg-primary-dark text-white transition-colors"
                    >
                      View Dashboard
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

