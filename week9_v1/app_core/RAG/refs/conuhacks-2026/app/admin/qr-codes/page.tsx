'use client';

import { useEffect, useState } from 'react';

interface Hospital {
  _id: string;
  name: string;
  slug: string;
  address: string;
}

export default function QRCodesPage() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    const fetchHospitals = async () => {
      try {
        const response = await fetch('/api/hospitals');
        const data = await response.json();
        setHospitals(data.hospitals || []);
      } catch (error) {
        console.error('Error fetching hospitals:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchHospitals();
  }, []);

  const copyToClipboard = (text: string, hospitalId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(hospitalId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getQRCodeUrl = (url: string) => {
    // Use Google Charts API to generate QR code
    return `https://api.qrserver.com/v1/create-qr-code/?size=400x400&data=${encodeURIComponent(url)}`;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading hospitals...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Hospital QR Codes</h1>
          <p className="text-gray-600">
            Download QR codes for each hospital. Patients can scan these codes to start triage at the specific location.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {hospitals.map((hospital) => {
            const url = `${typeof window !== 'undefined' ? window.location.origin : ''}/hospitals/${hospital.slug}/intake`;
            const qrCodeUrl = getQRCodeUrl(url);
            
            return (
              <div key={hospital._id} className="bg-white rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-bold text-gray-900 mb-2">{hospital.name}</h2>
                <p className="text-sm text-gray-600 mb-4">{hospital.address}</p>

                <div className="mb-4">
                  <img
                    src={qrCodeUrl}
                    alt={`QR Code for ${hospital.name}`}
                    className="w-full rounded-lg border-2 border-gray-200 bg-white"
                  />
                </div>

                <div className="text-xs text-gray-500 mb-4 p-3 bg-gray-50 rounded break-all">
                  {url}
                </div>

                <div className="space-y-2">
                  <a
                    href={qrCodeUrl}
                    download={`${hospital.name.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-qr-code.png`}
                    className="block w-full px-4 py-2 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition text-center"
                  >
                    Download QR Code
                  </a>
                  <button
                    onClick={() => copyToClipboard(url, hospital._id)}
                    className="w-full px-4 py-2 bg-gray-100 text-gray-700 font-semibold rounded-lg hover:bg-gray-200 transition"
                  >
                    {copiedId === hospital._id ? '✓ Copied!' : 'Copy URL'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {hospitals.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">No hospitals found. Please add hospitals first.</p>
          </div>
        )}
      </div>
    </div>
  );
}

