# PreTriage - Medical Pre-Triage Assistant

A safe, non-diagnostic web application that collects symptom intake via guided questions and outputs a conservative triage level with next steps recommendations.

## ⚠️ Important Disclaimer

**This is NOT a diagnosis tool.** PreTriage is for informational purposes only and does not provide medical advice, diagnosis, or treatment. If you are experiencing a medical emergency, call 911 (Canada) or your local emergency services immediately.

## Features

- **Guided Question Flow**: One focused question at a time with appropriate input controls
- **Conservative Triage Assessment**: Five triage levels (EMERGENCY, URGENT, NON_URGENT, SELF_CARE, UNCERTAIN)
- **Safe & Non-Diagnostic**: Never provides diagnoses or names specific conditions
- **Data Persistence**: All intake data stored securely in MongoDB
- **Intake Summary**: Downloadable/copyable summary for sharing with healthcare providers
- **Anonymous Sessions**: Uses localStorage for anonymous session tracking
- **Patient Medical Records**: Comprehensive patient tracking system with visit history and medical records (NEW!)
  - Persistent patient records linked via health card
  - Medical history tracking (conditions, medications, allergies)
  - Visit history across multiple cases
  - Patient search and retrieval
  - Medical history aggregation

## Tech Stack

- **Frontend**: Next.js 14 (App Router), React, Tailwind CSS
- **Backend**: Next.js API Routes
- **Database**: MongoDB with Mongoose
- **LLM**: Google Gemini (server-side only)
- **Language**: TypeScript

## Prerequisites

- Node.js 18+ and npm/yarn
- MongoDB instance (local or MongoDB Atlas)
- Google Gemini API key

## Installation

1. **Clone the repository** (or navigate to the project directory)

2. **Install dependencies**:
   ```bash
   npm install
   # or
   yarn install
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.local.example .env.local
   ```
   
   Edit `.env.local` and add your credentials:
   ```env
   MONGODB_URI=mongodb://localhost:27017/pretriage
   # Or for MongoDB Atlas:
   # MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/pretriage
   
   GEMINI_API_KEY=your_gemini_api_key_here
   
   # Optional: Enable test mode (mocks Gemini responses)
   # TEST_MODE=false
   ```

4. **Start the development server**:
   ```bash
   npm run dev
   # or
   yarn dev
   ```

5. **Open your browser**:
   Navigate to [http://localhost:3000](http://localhost:3000)

## Project Structure

```
pretriage/
├── app/
│   ├── api/
│   │   └── cases/
│   │       ├── route.ts              # POST /api/cases
│   │       └── [id]/
│   │           ├── route.ts          # GET /api/cases/:id
│   │           ├── answer/
│   │           │   └── route.ts      # POST /api/cases/:id/answer
│   │           └── complete/
│   │               └── route.ts      # POST /api/cases/:id/complete
│   ├── consent/
│   │   └── page.tsx                  # Consent screen
│   ├── intake/
│   │   └── page.tsx                  # Question intake UI
│   ├── results/
│   │   └── page.tsx                  # Results page
│   ├── globals.css                   # Global styles
│   ├── layout.tsx                     # Root layout
│   └── page.tsx                      # Landing page
├── lib/
│   ├── mongodb.ts                    # MongoDB connection
│   └── gemini.ts                     # Gemini API integration
├── models/
│   └── Case.ts                       # MongoDB schema
├── .env.local.example                # Environment variables template
├── next.config.js                    # Next.js configuration
├── tailwind.config.js                # Tailwind CSS configuration
├── tsconfig.json                     # TypeScript configuration
└── package.json                      # Dependencies
```

## API Endpoints

### `POST /api/cases`
Creates a new case with an anonymous ID.

**Request Body:**
```json
{
  "anonymousId": "uuid-string"
}
```

**Response:**
```json
{
  "case": {
    "_id": "...",
    "status": "in_progress",
    "user": { "anonymousId": "..." },
    ...
  }
}
```

### `GET /api/cases/:id`
Fetches a case by ID.

**Response:**
```json
{
  "case": { ... }
}
```

### `POST /api/cases/:id/answer`
Submits an answer to a question, processes with Gemini, and returns the next question or final assessment.

**Request Body:**
```json
{
  "answer": "user's answer",
  "questionId": "question-id",
  "question": "question text"
}
```

**Response:**
```json
{
  "case": { ... },
  "nextQuestion": {
    "id": "next-question-id",
    "question": "next question text"
  }
}
```

### `POST /api/cases/:id/complete`
Marks a case as completed.

## Test Mode

For development without API costs, you can enable test mode by setting `TEST_MODE=true` in `.env.local`. This will mock Gemini responses with sample data.

## Safety Features

- **No Diagnosis**: The system explicitly avoids providing diagnoses
- **Conservative Triage**: When uncertain, escalates to UNCERTAIN or URGENT
- **Emergency Detection**: Automatically detects emergency red flags and advises immediate care
- **Age-Appropriate Language**: Adapts language for minors
- **Clear Disclaimers**: Disclaimers shown on landing and results pages

## Data Model

Each case document in MongoDB includes:
- `_id`: Unique case identifier
- `createdAt`, `updatedAt`: Timestamps
- `status`: "in_progress" | "completed" | "escalated"
- `user`: Anonymous ID, age range, pregnancy status
- `intake`: Symptoms, severity, onset, red flags, history, vitals
- `assistant`: Triage level, reasons, next steps, monitoring plan, escalation triggers, intake summary

## Development

### Running in Development Mode
```bash
npm run dev
```

### Building for Production
```bash
npm run build
npm start
```

### Linting
```bash
npm run lint
```

## License

This project is for educational/demonstration purposes. Ensure compliance with healthcare regulations before any production use.

## Patient Medical Records System

This application now includes a comprehensive patient medical records tracking system. For detailed information about the patient records system, see **[PATIENT-RECORDS-GUIDE.md](./PATIENT-RECORDS-GUIDE.md)**.

Key features:
- Automatic patient creation from health card scans
- Visit history tracking across multiple cases
- Medical history aggregation (conditions, medications, allergies)
- Patient search and retrieval APIs
- Statistics and analytics for healthcare administrators

### Quick Start for Patient Records

1. **Test the System**:
   ```bash
   node scripts/test-patient-records.js
   ```

2. **View Patient Medical History**:
   ```
   GET /api/patients/[id]/history
   ```

3. **Search for Patients**:
   ```
   GET /api/patients/search?name=John
   ```

4. **View System Statistics**:
   ```
   GET /api/patients/stats?period=30
   ```

For complete documentation, see the [Patient Records Guide](./PATIENT-RECORDS-GUIDE.md).

## Support

For issues or questions, please refer to the project documentation or contact the development team.

---

**Remember**: This tool is NOT a substitute for professional medical care. Always consult with qualified healthcare providers for medical advice, diagnosis, and treatment.

