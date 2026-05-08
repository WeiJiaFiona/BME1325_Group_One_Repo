import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Care Flow - Medical Pre-Triage Assistant',
  description: 'A safe, non-diagnostic pre-triage tool to help assess symptom urgency',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

