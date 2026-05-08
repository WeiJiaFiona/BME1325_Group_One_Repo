/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {

        // Primary medical blue
        'medical-blue': {
          DEFAULT: '#0C5BA3',
          dark: '#094780',
          light: '#1976D2',
        },
        
        // Clinical backgrounds and text
        'clinical-gray': {
          50: '#F9FAFB',
          100: '#F3F4F6',
          200: '#E5E7EB',
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
        },
        
        // Triage status colors (clinical-grade)
        'triage': {
          emergency: {
            DEFAULT: '#991B1B',
            dark: '#7F1D1D',
            light: '#DC2626',
            bg: '#FEE2E2',
          },
          urgent: {
            DEFAULT: '#B45309',
            dark: '#92400E',
            light: '#D97706',
            bg: '#FEF3C7',
          },
          'non-urgent': {
            DEFAULT: '#CA8A04',
            dark: '#A16207',
            light: '#EAB308',
            bg: '#FEF9C3',
          },
          'self-care': {
            DEFAULT: '#047857',
            dark: '#065F46',
            light: '#059669',
            bg: '#D1FAE5',
          },
          uncertain: {
            DEFAULT: '#4B5563',
            dark: '#374151',
            light: '#6B7280',
            bg: '#F3F4F6',
          },
        },
        
        // Legacy support (maps to new clinical colors)
        emergency: '#991B1B',
        urgent: '#B45309',
        'non-urgent': '#CA8A04',
        'self-care': '#047857',
        uncertain: '#4B5563',
        
        // Primary color for navigation and buttons
        primary: '#2563EB', // Blue-600
        'primary-light': '#EFF6FF', // Blue-50
        'primary-dark': '#1E40AF', // Blue-800

      },
    },
  },
  plugins: [],
}

