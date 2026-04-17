import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });
}

export const urgencyConfig = {
  EMERGENCY: {
    label: 'Emergency',
    color: 'bg-red-600',
    textColor: 'text-red-600',
    bgLight: 'bg-red-50',
    borderColor: 'border-red-200',
    description: 'Seek immediate medical attention',
  },
  URGENT: {
    label: 'Urgent',
    color: 'bg-orange-500',
    textColor: 'text-orange-600',
    bgLight: 'bg-orange-50',
    borderColor: 'border-orange-200',
    description: 'See a doctor within 1 hour',
  },
  SEMI_URGENT: {
    label: 'Semi-Urgent',
    color: 'bg-yellow-500',
    textColor: 'text-yellow-600',
    bgLight: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
    description: 'See a doctor within 4 hours',
  },
  STANDARD: {
    label: 'Standard',
    color: 'bg-green-500',
    textColor: 'text-green-600',
    bgLight: 'bg-green-50',
    borderColor: 'border-green-200',
    description: 'Schedule an appointment today',
  },
  NON_URGENT: {
    label: 'Non-Urgent',
    color: 'bg-slate-400',
    textColor: 'text-slate-600',
    bgLight: 'bg-slate-50',
    borderColor: 'border-slate-200',
    description: 'Can be scheduled for later',
  },
} as const;

export const severityLabels: Record<number, string> = {
  1: 'Minimal',
  2: 'Mild',
  3: 'Moderate',
  4: 'Severe',
  5: 'Critical',
};
