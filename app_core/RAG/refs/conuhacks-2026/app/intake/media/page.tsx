'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect, useRef, Suspense } from 'react';

interface CaseData {
  _id: string;
  assessmentType: 'in_hospital' | 'remote';
  intake: {
    uploadedImages?: string[];
    additionalComments?: string;
  };
  assistant: {
    triageLevel?: string;
  };
}

function MediaUploadContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const caseId = searchParams.get('caseId');
  const hospitalSlug = searchParams.get('hospitalSlug');
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [images, setImages] = useState<string[]>([]);
  const [comments, setComments] = useState('');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [showCamera, setShowCamera] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);

  useEffect(() => {
    if (!caseId) return;

    const fetchCase = async () => {
      try {
        const response = await fetch(`/api/cases/${caseId}`);
        if (!response.ok) throw new Error('Failed to fetch case');
        const data = await response.json();
        setCaseData(data.case);
        
        // Load existing images and comments
        if (data.case.intake?.uploadedImages) {
          setImages(data.case.intake.uploadedImages);
        }
        if (data.case.intake?.additionalComments) {
          setComments(data.case.intake.additionalComments);
        }

        // Don't auto-redirect - let user see the media upload page even if case is completed
        // They can still upload images/comments before proceeding
      } catch (error) {
        console.error('Error fetching case:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchCase();
  }, [caseId, router]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please upload an image file');
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert('Image size must be less than 5MB');
      return;
    }

    // Check image limit
    if (images.length >= 5) {
      alert('Maximum 5 images allowed');
      return;
    }

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64Image = reader.result as string;
      setImages([...images, base64Image]);
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
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (error) {
      console.error('Error accessing camera:', error);
      alert('Could not access camera. Please upload a photo instead.');
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;

    // Check image limit
    if (images.length >= 5) {
      alert('Maximum 5 images allowed');
      stopCamera();
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(videoRef.current, 0, 0);
      const imageData = canvas.toDataURL('image/jpeg', 0.8);
      setImages([...images, imageData]);
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

  const removeImage = (index: number) => {
    setImages(images.filter((_, i) => i !== index));
  };

  const handleContinue = async () => {
    if (!caseId) return;

    setUploading(true);
    try {
      const response = await fetch(`/api/cases/${caseId}/upload-media`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          images,
          additionalComments: comments.trim() || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to save media');
      }

      // Fetch latest case data to ensure we have correct assessmentType
      const caseResponse = await fetch(`/api/cases/${caseId}`);
      if (caseResponse.ok) {
        const freshCaseData = await caseResponse.json();
        const assessmentType = freshCaseData.case.assessmentType;
        console.log('Media upload - Fresh case data:', { assessmentType, hospitalSlug, caseId });
        
        // CRITICAL: In-hospital ALWAYS goes to waiting room, NEVER results
        // Also check hospitalSlug as backup indicator
        if (assessmentType === 'in_hospital' || hospitalSlug) {
          const waitingUrl = hospitalSlug 
            ? `/waiting?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
            : `/waiting?caseId=${caseId}`;
          console.log('Redirecting in-hospital patient to waiting room:', waitingUrl);
          router.replace(waitingUrl);
        } else {
          console.log('Redirecting remote patient to results');
          router.replace(`/results?caseId=${caseId}`);
        }
      } else {
        // Fallback: if hospitalSlug exists, definitely in-hospital
        console.log('Case fetch failed, using hospitalSlug as indicator:', hospitalSlug);
        if (hospitalSlug || caseData?.assessmentType === 'in_hospital') {
          const waitingUrl = hospitalSlug 
            ? `/waiting?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
            : `/waiting?caseId=${caseId}`;
          console.log('Fallback: Redirecting to waiting room');
          router.replace(waitingUrl);
        } else {
          console.log('Fallback: Redirecting to results');
          router.replace(`/results?caseId=${caseId}`);
        }
      }
    } catch (error) {
      console.error('Error saving media:', error);
      alert('Failed to save. Please try again.');
      setUploading(false);
    }
  };

  const handleSkip = async () => {
    // Skip this step and continue - fetch latest case to ensure correct assessmentType
    if (!caseId) return;
    
    try {
      const caseResponse = await fetch(`/api/cases/${caseId}`);
      if (caseResponse.ok) {
        const freshCaseData = await caseResponse.json();
        const assessmentType = freshCaseData.case.assessmentType;
        console.log('Skip - Fresh case data:', { assessmentType, hospitalSlug, caseId });
        
        // CRITICAL: In-hospital ALWAYS goes to waiting room, NEVER results
        if (assessmentType === 'in_hospital' || hospitalSlug) {
          // If hospitalSlug exists, definitely in-hospital even if assessmentType not set
          const waitingUrl = hospitalSlug 
            ? `/waiting?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
            : `/waiting?caseId=${caseId}`;
          console.log('Skip: Redirecting in-hospital patient to waiting room');
          router.replace(waitingUrl);
        } else {
          console.log('Skip: Redirecting remote patient to results');
          router.replace(`/results?caseId=${caseId}`);
        }
      } else {
        // Fallback: if hospitalSlug exists, assume in-hospital
        console.log('Skip - Case fetch failed, using hospitalSlug as indicator:', hospitalSlug);
        if (hospitalSlug || caseData?.assessmentType === 'in_hospital') {
          const waitingUrl = hospitalSlug 
            ? `/waiting?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
            : `/waiting?caseId=${caseId}`;
          console.log('Skip fallback: Redirecting to waiting room');
          router.replace(waitingUrl);
        } else {
          console.log('Skip fallback: Redirecting to results');
          router.replace(`/results?caseId=${caseId}`);
        }
      }
    } catch (error) {
      // Final fallback: if hospitalSlug exists, go to waiting room
      console.log('Skip error fallback:', error, 'hospitalSlug:', hospitalSlug);
      if (hospitalSlug || caseData?.assessmentType === 'in_hospital') {
        const waitingUrl = hospitalSlug 
          ? `/waiting?caseId=${caseId}&hospitalSlug=${hospitalSlug}`
          : `/waiting?caseId=${caseId}`;
        router.replace(waitingUrl);
      } else {
        router.replace(`/results?caseId=${caseId}`);
      }
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

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white py-4 px-4">
      <div className="max-w-md mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Additional Information</h1>
          <p className="text-sm text-gray-600 mb-6">
            You can optionally upload photos of your symptoms or add any additional comments that might help our assessment.
          </p>

          {/* Image Upload Section */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              Upload Photos (Optional)
            </label>
            
            {/* Image Preview Grid */}
            {images.length > 0 && (
              <div className="grid grid-cols-2 gap-3 mb-4">
                {images.map((img, index) => (
                  <div key={index} className="relative group">
                    <img
                      src={img}
                      alt={`Upload ${index + 1}`}
                      className="w-full h-32 object-cover rounded-lg border-2 border-gray-200"
                    />
                    <button
                      onClick={() => removeImage(index)}
                      className="absolute top-2 right-2 bg-red-600 text-white rounded-full w-6 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Upload Buttons */}
            <div className="flex gap-3">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition"
              >
                Upload Photo
              </button>
              <button
                onClick={showCamera ? stopCamera : startCamera}
                className="flex-1 bg-gray-600 hover:bg-gray-700 text-white font-semibold py-3 px-4 rounded-lg transition"
              >
                {showCamera ? 'Stop Camera' : 'Take Photo'}
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />
            <p className="text-xs text-gray-500 mt-2">
              You can upload up to 5 images. Max size: 5MB each.
            </p>
          </div>

          {/* Camera View */}
          {showCamera && (
            <div className="mb-6 bg-black rounded-lg overflow-hidden">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                className="w-full h-64 object-cover"
              />
              <div className="p-4 bg-gray-900 flex justify-center">
                <button
                  onClick={capturePhoto}
                  className="bg-white rounded-full w-16 h-16 flex items-center justify-center shadow-lg hover:bg-gray-100 transition"
                >
                  <span className="text-2xl">●</span>
                </button>
              </div>
            </div>
          )}

          {/* Additional Comments Section */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              Additional Comments (Optional)
            </label>
            <textarea
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="Is there anything else you'd like to tell us about your condition? Any other symptoms, concerns, or relevant information?"
              rows={5}
              className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
            />
            <p className="text-xs text-gray-500 mt-2">
              {comments.length} characters
            </p>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3">
            <button
              onClick={handleContinue}
              disabled={uploading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold py-4 px-6 rounded-lg transition shadow-lg"
            >
              {uploading ? 'Saving...' : 'Continue'}
            </button>
            <button
              onClick={handleSkip}
              disabled={uploading}
              className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold py-3 px-6 rounded-lg transition"
            >
              Skip This Step
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MediaUploadPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    }>
      <MediaUploadContent />
    </Suspense>
  );
}

