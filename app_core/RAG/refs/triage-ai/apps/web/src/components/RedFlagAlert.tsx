import { motion } from 'framer-motion';

interface RedFlagAlertProps {
  flags: Array<{
    condition: string;
    evidence: string;
    action: string;
  }>;
}

export function RedFlagAlert({ flags }: RedFlagAlertProps) {
  return (
    <motion.div
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      className="bg-gradient-to-r from-red-600 to-red-700 text-white rounded-2xl p-6 shadow-lg"
    >
      <div className="flex items-start gap-4">
        {/* Pulsing warning icon */}
        <motion.div
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ repeat: Infinity, duration: 2 }}
          className="w-14 h-14 bg-white/20 backdrop-blur rounded-full flex items-center justify-center flex-shrink-0"
        >
          <svg
            className="w-8 h-8 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </motion.div>

        <div className="flex-1">
          <h3 className="text-xl font-bold mb-1">Urgent: Red Flags Detected</h3>
          <p className="text-red-100 mb-4">
            Based on your symptoms, immediate medical attention may be required.
          </p>

          <div className="space-y-3">
            {flags.map((flag, i) => (
              <motion.div
                key={i}
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: i * 0.1 }}
                className="bg-white/10 backdrop-blur rounded-xl p-4"
              >
                <div className="font-semibold text-white">{flag.condition}</div>
                <div className="text-red-100 text-sm mt-1">{flag.action}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-6 pt-4 border-t border-white/20"
      >
        <div className="flex items-center gap-2 text-white font-medium">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
            />
          </svg>
          <span>Call emergency services or go to the nearest emergency room</span>
        </div>
      </motion.div>
    </motion.div>
  );
}
