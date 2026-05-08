import { motion } from 'framer-motion';
import { DoctorSummary as DoctorSummaryType } from '../lib/api';

interface DoctorSummaryProps {
  summary: DoctorSummaryType;
}

export function DoctorSummary({ summary }: DoctorSummaryProps) {
  return (
    <div className="card p-6 border-l-4 border-l-primary-500">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-primary-100 rounded-full flex items-center justify-center">
          <svg
            className="w-5 h-5 text-primary-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        <div>
          <h3 className="font-semibold text-gray-900">Pre-Consultation Summary</h3>
          <p className="text-sm text-gray-500">For healthcare provider</p>
        </div>
      </div>

      {/* Headline */}
      <div className="bg-primary-50 rounded-xl p-4 mb-4">
        <p className="font-medium text-primary-900">{summary.headline}</p>
      </div>

      {/* Key Symptoms */}
      {summary.keySymptoms.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Key Symptoms</h4>
          <ul className="space-y-1">
            {summary.keySymptoms.map((symptom, i) => (
              <motion.li
                key={i}
                initial={{ x: -10, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center gap-2 text-sm text-gray-600"
              >
                <span className="w-1.5 h-1.5 bg-primary-400 rounded-full" />
                {symptom}
              </motion.li>
            ))}
          </ul>
        </div>
      )}

      {/* Red Flags for Doctor */}
      {summary.redFlags.length > 0 && (
        <div className="mb-4 bg-red-50 rounded-lg p-3">
          <h4 className="text-sm font-medium text-red-700 mb-2 flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            Red Flags
          </h4>
          <ul className="space-y-1">
            {summary.redFlags.map((flag, i) => (
              <li key={i} className="text-sm text-red-600">
                {flag}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Suggested Questions */}
      {summary.suggestedQuestions.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Suggested Questions
          </h4>
          <ul className="space-y-2">
            {summary.suggestedQuestions.slice(0, 4).map((question, i) => (
              <li
                key={i}
                className="text-sm text-gray-600 flex items-start gap-2"
              >
                <span className="text-primary-500 font-medium">{i + 1}.</span>
                {question}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Differential Diagnosis */}
      {summary.differentialDiagnosis.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Differential Diagnoses to Consider
          </h4>
          <div className="flex flex-wrap gap-2">
            {summary.differentialDiagnosis.map((dx, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
              >
                {dx}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
