import { motion } from 'framer-motion';
import { cn } from '../lib/utils';

/**
 * ATS Category Configuration
 * Based on Australasian College for Emergency Medicine guidelines
 */
const ATS_CATEGORIES = {
  ATS1: {
    name: 'Resuscitation',
    maxWait: 'Immediate',
    color: 'bg-red-600',
    textColor: 'text-red-600',
    bgLight: 'bg-red-50',
    borderColor: 'border-red-600',
    description: 'Immediately life-threatening',
    icon: '🚨',
  },
  ATS2: {
    name: 'Emergency',
    maxWait: '10 minutes',
    color: 'bg-orange-500',
    textColor: 'text-orange-500',
    bgLight: 'bg-orange-50',
    borderColor: 'border-orange-500',
    description: 'Imminently life-threatening',
    icon: '⚠️',
  },
  ATS3: {
    name: 'Urgent',
    maxWait: '30 minutes',
    color: 'bg-yellow-500',
    textColor: 'text-yellow-600',
    bgLight: 'bg-yellow-50',
    borderColor: 'border-yellow-500',
    description: 'Potentially life-threatening',
    icon: '⏱️',
  },
  ATS4: {
    name: 'Semi-urgent',
    maxWait: '60 minutes',
    color: 'bg-green-500',
    textColor: 'text-green-600',
    bgLight: 'bg-green-50',
    borderColor: 'border-green-500',
    description: 'Potentially serious',
    icon: '📋',
  },
  ATS5: {
    name: 'Non-urgent',
    maxWait: '120 minutes',
    color: 'bg-blue-500',
    textColor: 'text-blue-600',
    bgLight: 'bg-blue-50',
    borderColor: 'border-blue-500',
    description: 'Less urgent',
    icon: '✓',
  },
} as const;

type ATSCategoryType = keyof typeof ATS_CATEGORIES;

export interface ATSTriageResultData {
  category: ATSCategoryType;
  confidence: number;
  redFlagsDetected: Array<{
    id: string;
    name: string;
    evidence: string;
    action: string;
  }>;
  clinicalReasoning: string;
  discriminatorsUsed: string[];
  recommendations: string[];
  escalationNotes?: string;
  auditTrail: Array<{
    step: string;
    result: string;
    timestamp: string;
  }>;
  doctorSummary?: {
    headline: string;
    keyFindings: string[];
    suggestedQuestions: string[];
    differentialDiagnosis: string[];
    immediateActions: string[];
  };
}

interface ATSTriageResultProps {
  result: ATSTriageResultData;
  onReset: () => void;
  showAuditTrail?: boolean;
}

export function ATSTriageResult({ result, onReset, showAuditTrail = false }: ATSTriageResultProps) {
  const category = ATS_CATEGORIES[result.category];
  const isHighPriority = result.category === 'ATS1' || result.category === 'ATS2';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6 p-4 overflow-y-auto"
    >
      {/* Red Flags Alert */}
      {result.redFlagsDetected.length > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-red-50 border-2 border-red-500 rounded-2xl p-6"
        >
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center flex-shrink-0">
              <svg className="w-7 h-7 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-red-700 mb-2">Red Flags Detected</h3>
              <ul className="space-y-2">
                {result.redFlagsDetected.map((flag, index) => (
                  <li key={flag.id || index} className="flex items-start gap-2 text-red-600">
                    <span className="font-medium">{flag.name}:</span>
                    <span className="text-red-700">{flag.action}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </motion.div>
      )}

      {/* ATS Category Hero Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className={cn(
          "rounded-2xl p-6 border-2",
          category.bgLight,
          category.borderColor
        )}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{category.icon}</span>
            <div>
              <div className="text-sm font-medium text-gray-500">Australian Triage Scale</div>
              <div className={cn("text-2xl font-bold", category.textColor)}>
                {result.category}
              </div>
            </div>
          </div>
          <div className={cn(
            "px-4 py-2 rounded-xl text-white font-bold text-lg",
            category.color
          )}>
            {category.name}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white/70 rounded-xl p-4">
            <div className="text-sm text-gray-500 mb-1">Maximum Wait Time</div>
            <div className={cn("text-xl font-bold", category.textColor)}>
              {category.maxWait}
            </div>
          </div>
          <div className="bg-white/70 rounded-xl p-4">
            <div className="text-sm text-gray-500 mb-1">Confidence</div>
            <div className="text-xl font-bold text-gray-900">
              {Math.round(result.confidence * 100)}%
            </div>
          </div>
        </div>

        <div className="mt-4 text-sm text-gray-600">
          {category.description}
        </div>

        {/* Escalation Notice */}
        {result.escalationNotes && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-xl">
            <div className="flex items-center gap-2 text-amber-700">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
              <span className="font-medium">Category Escalated</span>
            </div>
            <p className="text-sm text-amber-600 mt-1">{result.escalationNotes}</p>
          </div>
        )}
      </motion.div>

      {/* Clinical Reasoning Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm"
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          Clinical Reasoning
        </h3>
        <p className="text-gray-600 whitespace-pre-wrap">{result.clinicalReasoning}</p>

        {/* Clinical Discriminators Used */}
        {result.discriminatorsUsed.length > 0 && (
          <div className="mt-4">
            <div className="text-sm font-medium text-gray-500 mb-2">Clinical Discriminators</div>
            <div className="flex flex-wrap gap-2">
              {result.discriminatorsUsed.map((disc, i) => (
                <span
                  key={i}
                  className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                >
                  {disc}
                </span>
              ))}
            </div>
          </div>
        )}
      </motion.div>

      {/* Recommendations */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm"
      >
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          Recommendations
        </h3>
        <ul className="space-y-3">
          {result.recommendations.map((rec, i) => (
            <li key={i} className="flex items-start gap-3">
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
                isHighPriority ? "bg-red-100" : "bg-primary-100"
              )}>
                <svg
                  className={cn(
                    "w-4 h-4",
                    isHighPriority ? "text-red-600" : "text-primary-600"
                  )}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <span className="text-gray-700">{rec}</span>
            </li>
          ))}
        </ul>
      </motion.div>

      {/* Doctor Summary */}
      {result.doctorSummary && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-gradient-to-br from-primary-50 to-primary-100 rounded-2xl border border-primary-200 p-6"
        >
          <h3 className="text-lg font-semibold text-primary-900 mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Doctor Pre-Consultation Summary
          </h3>

          <div className="bg-white rounded-xl p-4 mb-4">
            <p className="text-primary-800 font-medium">{result.doctorSummary.headline}</p>
          </div>

          <div className="grid gap-4">
            {result.doctorSummary.keyFindings.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-primary-700 mb-2">Key Findings</h4>
                <ul className="space-y-1">
                  {result.doctorSummary.keyFindings.map((finding, i) => (
                    <li key={i} className="text-sm text-primary-600">• {finding}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.doctorSummary.suggestedQuestions.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-primary-700 mb-2">Suggested Questions</h4>
                <ul className="space-y-1">
                  {result.doctorSummary.suggestedQuestions.map((q, i) => (
                    <li key={i} className="text-sm text-primary-600">• {q}</li>
                  ))}
                </ul>
              </div>
            )}

            {result.doctorSummary.differentialDiagnosis.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-primary-700 mb-2">Differential Diagnosis</h4>
                <div className="flex flex-wrap gap-2">
                  {result.doctorSummary.differentialDiagnosis.map((dx, i) => (
                    <span key={i} className="px-2 py-1 bg-primary-200/50 text-primary-700 rounded text-sm">
                      {dx}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Audit Trail (Expandable) */}
      {showAuditTrail && result.auditTrail.length > 0 && (
        <motion.details
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="bg-gray-50 rounded-2xl border border-gray-200 overflow-hidden"
        >
          <summary className="px-6 py-4 cursor-pointer text-sm font-medium text-gray-700 hover:bg-gray-100">
            View Decision Audit Trail ({result.auditTrail.length} steps)
          </summary>
          <div className="px-6 pb-4 space-y-2">
            {result.auditTrail.map((entry, i) => (
              <div key={i} className="text-xs font-mono bg-white p-3 rounded-lg border border-gray-100">
                <div className="flex justify-between mb-1">
                  <span className="font-bold text-primary-600">{entry.step}</span>
                  <span className="text-gray-400">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-gray-600">{entry.result}</div>
              </div>
            ))}
          </div>
        </motion.details>
      )}

      {/* Guardrails Architecture Visualization */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="bg-slate-900 rounded-2xl p-6 text-white"
      >
        <h4 className="text-sm font-medium text-slate-300 mb-4">Safety Architecture</h4>
        <div className="flex items-center gap-2 text-xs">
          <div className="flex-1 text-center p-2 bg-slate-800 rounded-lg">
            <div className="text-slate-400 mb-1">Layer 1</div>
            <div className="text-green-400 font-medium">Keyword Detection</div>
            <div className="text-slate-500">{'<'}1ms</div>
          </div>
          <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <div className="flex-1 text-center p-2 bg-slate-800 rounded-lg">
            <div className="text-slate-400 mb-1">Layer 2</div>
            <div className="text-blue-400 font-medium">Clinical Rules</div>
            <div className="text-slate-500">{'<'}5ms</div>
          </div>
          <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <div className="flex-1 text-center p-2 bg-slate-800 rounded-lg">
            <div className="text-slate-400 mb-1">Layer 3</div>
            <div className="text-purple-400 font-medium">LLM Reasoning</div>
            <div className="text-slate-500">~2s</div>
          </div>
          <svg className="w-4 h-4 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <div className="flex-1 text-center p-2 bg-slate-800 rounded-lg">
            <div className="text-slate-400 mb-1">Layer 4</div>
            <div className="text-amber-400 font-medium">Safety Envelope</div>
            <div className="text-slate-500">{'<'}1ms</div>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-4 text-center">
          Deterministic guardrails ensure critical conditions are never missed
        </p>
      </motion.div>

      {/* Reset Button */}
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7 }}
        onClick={onReset}
        className="w-full py-4 text-primary-600 hover:bg-primary-50 rounded-xl font-medium transition-colors border border-primary-200"
      >
        Start New Assessment
      </motion.button>
    </motion.div>
  );
}
