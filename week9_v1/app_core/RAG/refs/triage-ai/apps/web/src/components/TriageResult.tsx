import { motion } from 'framer-motion';
import { TriageSession } from '../lib/api';
import { urgencyConfig, severityLabels, cn } from '../lib/utils';
import { RedFlagAlert } from './RedFlagAlert';
import { DoctorSummary } from './DoctorSummary';

interface TriageResultProps {
  result: TriageSession;
  onReset: () => void;
}

export function TriageResult({ result, onReset }: TriageResultProps) {
  const { result: triage, doctorSummary } = result;

  // Defensive handling for missing or invalid urgency
  const urgencyKey = triage?.urgency || 'STANDARD';
  const urgency = urgencyConfig[urgencyKey as keyof typeof urgencyConfig] || urgencyConfig.STANDARD;

  // Defensive handling for missing fields
  const severity = triage?.severity ?? 3;
  const confidence = triage?.confidence ?? 0.5;
  const redFlags = triage?.redFlags || { detected: false, flags: [] };
  const specialtyMatch = triage?.specialtyMatch || [];
  const reasoning = triage?.reasoning || 'Assessment complete.';
  const recommendations = triage?.recommendations || ['Consult your healthcare provider'];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6 p-4 overflow-y-auto chat-scroll"
    >
      {/* Red Flags Alert - Most Prominent */}
      {redFlags.detected && redFlags.flags.length > 0 && (
        <RedFlagAlert flags={redFlags.flags} />
      )}

      {/* Triage Assessment Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="card p-6"
      >
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Triage Assessment
        </h2>

        {/* Severity and Urgency Grid */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* Severity */}
          <div className="bg-gray-50 rounded-xl p-4 text-center">
            <div className="text-sm text-gray-500 mb-1">Severity</div>
            <div className="text-3xl font-bold text-gray-900">
              {severity}/5
            </div>
            <div
              className={cn(
                'inline-block mt-2 px-3 py-1 rounded-full text-sm font-medium',
                severity >= 4
                  ? 'bg-red-100 text-red-700'
                  : severity >= 3
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-green-100 text-green-700'
              )}
            >
              {severityLabels[severity] || 'Assessed'}
            </div>
          </div>

          {/* Urgency */}
          <div className="bg-gray-50 rounded-xl p-4 text-center">
            <div className="text-sm text-gray-500 mb-1">Urgency</div>
            <div
              className={cn(
                'inline-block mt-2 px-4 py-2 rounded-full text-white font-semibold text-lg',
                urgency.color
              )}
            >
              {urgency.label}
            </div>
            <div className="text-xs text-gray-500 mt-2">
              {urgency.description}
            </div>
          </div>
        </div>

        {/* Confidence */}
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-500">Confidence</span>
            <span className="font-medium text-gray-700">
              {Math.round(confidence * 100)}%
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${confidence * 100}%` }}
              transition={{ duration: 0.8, delay: 0.3 }}
              className="h-full bg-primary-500 rounded-full"
            />
          </div>
        </div>

        {/* Recommended Specialties */}
        {specialtyMatch.length > 0 && (
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Recommended Specialties
            </h4>
            <div className="flex flex-wrap gap-2">
              {specialtyMatch.map((specialty) => (
                <span
                  key={specialty}
                  className="px-3 py-1 bg-primary-50 text-primary-700 rounded-full text-sm font-medium"
                >
                  {specialty}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* AI Reasoning */}
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Assessment Reasoning
          </h4>
          <p className="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
            {reasoning}
          </p>
        </div>

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Recommendations
            </h4>
            <ul className="space-y-2">
              {recommendations.map((rec, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                  <svg
                    className="w-5 h-5 text-primary-500 flex-shrink-0 mt-0.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}
      </motion.div>

      {/* Doctor Summary */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <DoctorSummary summary={doctorSummary} />
      </motion.div>

      {/* Reset Button */}
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        onClick={onReset}
        className="w-full py-3 text-primary-600 hover:bg-primary-50 rounded-xl font-medium transition-colors"
      >
        Start New Assessment
      </motion.button>

      {/* Session ID */}
      <div className="text-center text-xs text-gray-400">
        Session ID: {result.id}
      </div>
    </motion.div>
  );
}
