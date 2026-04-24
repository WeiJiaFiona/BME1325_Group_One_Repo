'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import Image from 'next/image';

export default function LandingPage() {
  const router = useRouter();
  const [anonymousId, setAnonymousId] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [showEmergencyAlert, setShowEmergencyAlert] = useState(false);

  useEffect(() => {
    let id = localStorage.getItem('pretriage_anonymous_id');
    if (!id) {
      id = uuidv4();
      localStorage.setItem('pretriage_anonymous_id', id);
    }
    setAnonymousId(id);
  }, []);

  const handleStartIntake = async () => {
    if (!anonymousId) return;
    setIsStarting(true);

    try {
      // Get user location for hospital recommendations
      let location = undefined;
      if (navigator.geolocation) {
        try {
          const position = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
          });
          location = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          };
        } catch (err) {
          console.log('Could not get location:', err);
        }
      }

      // Use AbortController with a longer timeout (60 seconds for MongoDB connection)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

      try {
        const response = await fetch('/api/cases', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            anonymousId,
            assessmentType: 'remote',
            location
          }),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        // Handle 499 (Client Closed Request) - operation may have succeeded
        if (response.status === 499) {
          const data = await response.json();
          console.warn('Request was closed but may have succeeded:', data);
          // Still try to proceed - the case might have been created
          alert('Connection was interrupted, but your case may have been created. Please check your dashboard or try again.');
          setIsStarting(false);
          return;
        }

        if (!response.ok) {
          throw new Error('Failed to create case');
        }

        const data = await response.json();
        router.push(`/consent?caseId=${data.case._id}`);
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        if (fetchError.name === 'AbortError') {
          throw new Error('Request timed out. The database connection is taking longer than expected. Please try again.');
        }
        throw fetchError;
      }
    } catch (error: any) {
      console.error('Error starting intake:', error);
      alert(error.message || 'Failed to start. Please try again.');
      setIsStarting(false);
    }
  };

  const handleEmergency = () => {
    setShowEmergencyAlert(true);
  };

  if (showEmergencyAlert) {
    return (
      <div className="min-h-screen bg-triage-emergency flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-2xl p-6 sm:p-8">
          <div className="text-center mb-6">
            <div className="w-20 h-20 bg-triage-emergency rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse">
              <span className="text-4xl text-white">🚨</span>
            </div>
            <h1 className="text-3xl font-bold text-triage-emergency mb-3">CALL 911 NOW</h1>
            <p className="text-lg text-clinical-gray-900 font-semibold mb-2">
              This is a medical emergency
            </p>
          </div>

          <div className="bg-triage-emergency-bg rounded-lg p-4 mb-6">
            <p className="text-clinical-gray-700 text-sm text-center">
              If you are experiencing a medical emergency, please call 911 or go to the nearest emergency room immediately.
            </p>
          </div>

          <a
            href="tel:911"
            className="block w-full bg-triage-emergency hover:bg-triage-emergency-dark text-white text-xl font-bold py-4 rounded-lg text-center mb-3 transition-colors"
          >
            📞 Call 911
          </a>

          <button
            onClick={() => setShowEmergencyAlert(false)}
            className="w-full bg-clinical-gray-200 hover:bg-clinical-gray-300 text-clinical-gray-900 font-semibold py-3 rounded-lg transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="border-b border-clinical-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
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
            <div className="flex items-center gap-4">
              <button
                onClick={handleStartIntake}
                disabled={!anonymousId || isStarting}
                className="bg-medical-blue hover:bg-medical-blue-dark disabled:bg-clinical-gray-300 disabled:cursor-not-allowed text-white text-sm font-semibold py-2 px-4 rounded-lg transition-all duration-200"
              >
                {isStarting ? 'Starting...' : 'Start Intake'}
              </button>
              <button
                onClick={handleEmergency}
                className="text-sm text-triage-emergency hover:text-triage-emergency-dark font-semibold transition-colors"
              >
                Emergency
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative bg-gradient-to-b from-clinical-gray-50 to-white py-20 sm:py-32">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold text-clinical-gray-900 mb-6 tracking-tight">
              Smart Medical
              <br />
              <span className="text-medical-blue">Pre-Triage</span>
            </h1>
            <p className="text-xl sm:text-2xl text-clinical-gray-600 mb-4 max-w-3xl mx-auto font-medium">
              Get instant symptom assessment and personalized guidance for your healthcare needs
            </p>
            <p className="text-lg text-clinical-gray-500 mb-12 max-w-2xl mx-auto">
              Powered by AI to help you understand your symptoms and determine the appropriate level of care
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <button
                onClick={handleStartIntake}
                disabled={!anonymousId || isStarting}
                className="w-full sm:w-auto bg-medical-blue hover:bg-medical-blue-dark disabled:bg-clinical-gray-300 disabled:cursor-not-allowed text-white text-lg font-bold py-4 px-10 rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl active:scale-[0.98] min-w-[200px]"
              >
                {isStarting ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Starting...
                  </span>
                ) : (
                  'Start Medical Assessment'
                )}
              </button>
            </div>
            <p className="text-sm text-clinical-gray-400 mt-6">
              No account required • Takes 2-3 minutes • Completely confidential
            </p>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-clinical-gray-900 mb-4">
              Why Choose Care Flow?
            </h2>
            <p className="text-lg text-clinical-gray-600 max-w-2xl mx-auto">
              Streamline your healthcare journey with intelligent pre-triage technology
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="bg-clinical-gray-50 rounded-lg p-8 border border-clinical-gray-200 hover:shadow-lg transition-shadow">
              <div className="w-12 h-12 bg-medical-blue/10 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-medical-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-clinical-gray-900 mb-3">Instant Assessment</h3>
              <p className="text-clinical-gray-600">
                Get immediate symptom evaluation using advanced AI technology. No waiting, no appointments needed.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="bg-clinical-gray-50 rounded-lg p-8 border border-clinical-gray-200 hover:shadow-lg transition-shadow">
              <div className="w-12 h-12 bg-medical-blue/10 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-medical-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-clinical-gray-900 mb-3">Secure & Private</h3>
              <p className="text-clinical-gray-600">
                Your health information is encrypted and stored securely. We prioritize your privacy above all else.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="bg-clinical-gray-50 rounded-lg p-8 border border-clinical-gray-200 hover:shadow-lg transition-shadow">
              <div className="w-12 h-12 bg-medical-blue/10 rounded-lg flex items-center justify-center mb-4">
                <svg className="w-6 h-6 text-medical-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-clinical-gray-900 mb-3">Actionable Results</h3>
              <p className="text-clinical-gray-600">
                Receive clear triage recommendations and next steps tailored to your specific situation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 bg-clinical-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold text-clinical-gray-900 mb-4">
              How It Works
            </h2>
            <p className="text-lg text-clinical-gray-600 max-w-2xl mx-auto">
              Simple, fast, and designed with your health in mind
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <div className="text-center">
              <div className="w-16 h-16 bg-medical-blue text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                1
              </div>
              <h3 className="text-lg font-bold text-clinical-gray-900 mb-2">Answer Questions</h3>
              <p className="text-clinical-gray-600">
                Our AI assistant will ask you a few simple questions about your symptoms
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-medical-blue text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                2
              </div>
              <h3 className="text-lg font-bold text-clinical-gray-900 mb-2">Get Assessment</h3>
              <p className="text-clinical-gray-600">
                Receive an instant triage level and personalized recommendations
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-medical-blue text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                3
              </div>
              <h3 className="text-lg font-bold text-clinical-gray-900 mb-2">Take Action</h3>
              <p className="text-clinical-gray-600">
                Follow the guidance provided and share results with healthcare providers if needed
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-medical-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Ready to Get Started?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Take control of your health with a quick, confidential assessment
          </p>
          <button
            onClick={handleStartIntake}
            disabled={!anonymousId || isStarting}
            className="bg-white hover:bg-clinical-gray-50 disabled:bg-clinical-gray-300 disabled:cursor-not-allowed text-medical-blue text-lg font-bold py-4 px-10 rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl active:scale-[0.98]"
          >
            {isStarting ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-medical-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Starting...
              </span>
            ) : (
              'Start Your Assessment Now'
            )}
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-clinical-gray-900 text-clinical-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
            <div>
              <div className="mb-4">
                <Image 
                  src="/Logo-no-text.png" 
                  alt="Care Flow Logo" 
                  width={100} 
                  height={33}
                  className="object-contain h-8"
                />
              </div>
              <p className="text-sm">
                Intelligent medical pre-triage for better healthcare decisions.
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Important</h4>
              <p className="text-sm mb-2">
                This tool is for informational purposes only and does not provide medical diagnosis or treatment.
              </p>
              <p className="text-sm">
                For medical emergencies, call 911 immediately.
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Privacy</h4>
              <p className="text-sm">
                Your information is encrypted and stored securely. We never share your data with third parties.
              </p>
            </div>
          </div>
          <div className="border-t border-clinical-gray-800 pt-8 text-center text-sm">
            <p>&copy; {new Date().getFullYear()} Care Flow. All rights reserved.</p>
        </div>
      </div>
      </footer>
    </div>
  );
}

