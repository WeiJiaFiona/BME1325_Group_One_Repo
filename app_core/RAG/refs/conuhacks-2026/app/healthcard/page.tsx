'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { useState, useRef, useEffect } from 'react';

interface ExtractedData {
  name?: string;
  healthCardNumber?: string;
  versionCode?: string;
  dateOfBirth?: string;
  sex?: string;
  expiryDate?: string;
  age?: number;
  ageSet?: boolean;
  confidence?: string;
}

function HealthCardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseId = searchParams.get('caseId');
  const hospitalSlug = searchParams.get('hospitalSlug');
  const [image, setImage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [extractedData, setExtractedData] = useState<ExtractedData | null>(null);
  const [showVerification, setShowVerification] = useState(false);
  const [verifiedData, setVerifiedData] = useState<ExtractedData>({});
  const [saving, setSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [showCamera, setShowCamera] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      setImage(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
      });
      setStream(mediaStream);
      setShowCamera(true);
    } catch (error) {
      console.error('Error accessing camera:', error);
      alert('Could not access camera. Please upload a photo instead.');
    }
  };

  // Handle video stream setup when camera is shown
  useEffect(() => {
    if (showCamera && stream && videoRef.current) {
      videoRef.current.srcObject = stream;
      videoRef.current.play().catch(error => {
        console.error('Error playing video:', error);
      });
    }
    
    // Cleanup function
    return () => {
      if (videoRef.current && !showCamera) {
        videoRef.current.srcObject = null;
      }
    };
  }, [showCamera, stream]);

  const capturePhoto = () => {
    if (!videoRef.current) return;

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0);
      const imageData = canvas.toDataURL('image/jpeg');
      setImage(imageData);
      stopCamera();
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
    setShowCamera(false);
  };

  const handleScan = async () => {
    if (!image || !caseId) return;

    setUploading(true);
    try {
      // Send image to backend for OCR processing
      const response = await fetch('/api/scan-healthcard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          caseId,
          image 
        }),
      });

      const data = await response.json();
      
      if (response.ok && data.success) {
        // Show verification screen with extracted data
        setExtractedData(data.extractedData);
        setVerifiedData({
          name: data.rawData?.name || '',
          healthCardNumber: data.rawData?.healthCardNumber || '',
          versionCode: data.rawData?.versionCode || '',
          dateOfBirth: data.rawData?.dateOfBirth || '',
          sex: data.rawData?.sex || '',
          expiryDate: data.rawData?.expiryDate || '',
        });
        setShowVerification(true);
      } else {
        // OCR failed or couldn't read card
        alert('Could not read health card clearly. Please continue manually or try another photo.');
        setImage(null); // Allow user to try again
      }
    } catch (error) {
      console.error('Error scanning health card:', error);
      alert('Error processing health card. Please continue manually.');
      const contactUrl = hospitalSlug 
        ? `/contact?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
        : `/contact?caseId=${caseId}`;
      router.push(contactUrl);
    } finally {
      setUploading(false);
    }
  };

  const handleVerifyAndContinue = async () => {
    if (!caseId) return;

    setSaving(true);
    try {
      // Save verified data to backend
      const response = await fetch('/api/verify-healthcard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          caseId,
          verifiedData
        }),
      });

      if (response.ok) {
        const contactUrl = hospitalSlug 
        ? `/contact?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
        : `/contact?caseId=${caseId}`;
      router.push(contactUrl);
      } else {
        throw new Error('Failed to save verified data');
      }
    } catch (error) {
      console.error('Error saving verified data:', error);
      alert('Error saving data. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = () => {
    if (!caseId) return;
    router.push(`/contact?caseId=${caseId}`);
  };

  if (!caseId) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <p className="text-red-600">Invalid case ID</p>
      </div>
    );
  }

  if (showCamera) {
    return (
      <div className="min-h-screen bg-black flex flex-col">
        <div className="flex-1 relative">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-[90%] max-w-md aspect-[1.6/1] border-4 border-white/50 rounded-2xl"></div>
          </div>
        </div>
        <div className="p-6 bg-gradient-to-t from-black/80 to-transparent">
          <p className="text-white text-center mb-4 text-sm">
            Position your health card within the frame
          </p>
          <div className="flex gap-3">
            <button
              onClick={stopCamera}
              className="flex-1 bg-gray-600 hover:bg-gray-700 text-white font-semibold py-4 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={capturePhoto}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-xl transition-colors shadow-lg"
            >
              Capture
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 text-center mb-2">
            Scan Health Card
          </h1>
          <p className="text-sm text-gray-600 text-center">
            Optional - helps us fill in your information faster
          </p>
        </div>

        {!image && (
          <>
            <div className="space-y-3 mb-6">
              <button
                onClick={startCamera}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-5 rounded-xl transition-colors shadow-lg active:scale-95 flex items-center justify-center text-lg"
              >
                Take Photo
              </button>

              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-4 rounded-xl transition-colors active:scale-95"
              >
                Upload Photo
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

            <button
              onClick={handleSkip}
              className="w-full bg-white hover:bg-gray-50 text-gray-600 font-semibold py-3 rounded-xl transition-colors border border-gray-300"
            >
              Skip - Enter Manually
            </button>
          </>
        )}

        {image && !extractedData && (
          <>
            <div className="mb-6">
              <img
                src={image}
                alt="Health card"
                className="w-full rounded-xl border-2 border-gray-200"
              />
            </div>

            <div className="space-y-3">
              <button
                onClick={handleScan}
                disabled={uploading}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold py-5 rounded-xl transition-colors shadow-lg active:scale-95"
              >
                {uploading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Scanning...
                  </span>
                ) : 'Scan and Continue'}
              </button>

              <button
                onClick={() => setImage(null)}
                disabled={uploading}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 rounded-xl transition-colors active:scale-95"
              >
                Take Another Photo
              </button>
            </div>
          </>
        )}

        {showVerification && extractedData && (
          <div className="space-y-4">
            <div className="bg-blue-50 rounded-xl p-4 mb-4">
              <p className="font-bold text-blue-900 text-center mb-2">Verify Your Information</p>
              <p className="text-sm text-blue-800 text-center">
                Please review and correct any information if needed
              </p>
              {extractedData.confidence && (
                <p className="text-xs text-blue-700 text-center mt-2">
                  Scan Confidence: <strong className="uppercase">{extractedData.confidence}</strong>
                </p>
              )}
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  value={verifiedData.name || ''}
                  onChange={(e) => setVerifiedData({...verifiedData, name: e.target.value})}
                  placeholder="Enter your full name"
                  className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Health Card Number
                </label>
                <input
                  type="text"
                  value={verifiedData.healthCardNumber || ''}
                  onChange={(e) => setVerifiedData({...verifiedData, healthCardNumber: e.target.value})}
                  placeholder="Enter health card number"
                  className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Version Code
                </label>
                <input
                  type="text"
                  value={verifiedData.versionCode || ''}
                  onChange={(e) => setVerifiedData({...verifiedData, versionCode: e.target.value})}
                  placeholder="Enter version code"
                  className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Date of Birth (YYYY-MM-DD)
                </label>
                <input
                  type="text"
                  value={verifiedData.dateOfBirth || ''}
                  onChange={(e) => setVerifiedData({...verifiedData, dateOfBirth: e.target.value})}
                  placeholder="YYYY-MM-DD"
                  className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Sex
                </label>
                <select
                  value={verifiedData.sex || ''}
                  onChange={(e) => setVerifiedData({...verifiedData, sex: e.target.value})}
                  className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Select</option>
                  <option value="M">Male</option>
                  <option value="F">Female</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Expiry Date (YYYY-MM-DD)
                </label>
                <input
                  type="text"
                  value={verifiedData.expiryDate || ''}
                  onChange={(e) => setVerifiedData({...verifiedData, expiryDate: e.target.value})}
                  placeholder="YYYY-MM-DD"
                  className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div className="space-y-3 pt-2">
              <button
                onClick={handleVerifyAndContinue}
                disabled={saving}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold py-4 rounded-xl transition-colors shadow-lg active:scale-95"
              >
                {saving ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Saving...
                  </span>
                ) : 'Confirm and Continue'}
              </button>

              <button
                onClick={() => {
                  setShowVerification(false);
                  setImage(null);
                  setExtractedData(null);
                }}
                disabled={saving}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 rounded-xl transition-colors active:scale-95"
              >
                ← Scan Again
              </button>

              <button
                onClick={handleSkip}
                disabled={saving}
                className="w-full bg-white hover:bg-gray-50 text-gray-600 font-semibold py-3 rounded-xl transition-colors border border-gray-300"
              >
                Skip - Enter Manually
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function HealthCardPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <HealthCardContent />
    </Suspense>
  );
}

