# Triage / Pre-consultation Agent Workflow

## 1. Clarify the Roles of Each Part

- `VS Code` is the development environment. We use it to write code, run the project, debug APIs, manage prompts, and maintain rules.
- `UI` is the user-facing page or chat window. It can be a simple web page, a desktop view, or even a test panel inside the project.
- `API` is not the same as UI. API is the backend interface that receives user input, calls the LLM, runs the rule engine, stores session context, and returns structured results.
- `LLM` is responsible for language understanding and multi-turn dialogue, such as symptom collection, follow-up questioning, summarization, and department pre-classification.
- `Rules Engine` is the medical safety layer. It does not replace the LLM, but double-checks red flags, hidden emergency signs, age/sex boundaries, and department assignment safety.

In short:

`UI -> API -> LLM + Rules Engine -> Structured Triage Result`

## 2. Recommended System Modules

### 2.1 Frontend / UI Layer

- Chat input box
- Basic patient info form
- Vital signs input
- Pain score input
- Temperature input as a mandatory field
- Final triage result display

### 2.2 Backend / API Layer

- `POST /session/start`
  - Create a triage session
  - Initialize Session Context
- `POST /session/message`
  - Receive each patient utterance
  - Trigger LLM follow-up
  - Update extracted symptoms and risk factors
- `POST /triage/evaluate`
  - Run final triage evaluation
  - Call rules engine for red-flag confirmation
  - Output handover sheet
- `GET /session/{id}`
  - Query current session context and triage progress

### 2.3 Core Service Layer

- Dialogue Manager
- Symptom Extractor
- Session Context Manager
- Triage Decision Service
- Department Routing Service
- Rule Engine
- Audit / Logging Service

## 3. Core Session Context

The session context should continuously accumulate structured data:

- `chief_complaint`
- `age`
- `sex`
- `temperature`
- `vital_signs`
- `pain_score`
- `symptoms`
- `onset_time`
- `duration`
- `severity`
- `associated_symptoms`
- `trauma_history`
- `pregnancy_related_info` when relevant
- `pediatric_flag`
- `risk_flags`
- `triage_level`
- `need_emergency_transfer`
- `recommended_outpatient_entry`
- `missing_required_fields`

Important rule:

- `temperature` must be collected and stored as a required field. If not provided, the agent should explicitly ask for it again before finalizing triage, unless an emergency transfer is already triggered.

## 4. End-to-End Runtime Workflow

### Step 1. Start Session

Patient enters:

- Chief complaint
- Age
- Sex
- Vital signs if available
- Pain score

System action:

- Create `session_id`
- Initialize empty Session Context
- Check whether temperature is missing

### Step 2. First-Turn Safety Scan

The API sends the first batch of information to:

- LLM for symptom understanding
- Rules engine for immediate red-flag scan

The system immediately checks for obvious emergency signs, such as:

- Chest pain with breathing difficulty
- Loss of consciousness
- Active severe bleeding
- Stroke-like symptoms
- High fever with convulsion
- Severe trauma

If triggered:

- Set `triage_level = Red`
- Set `need_emergency_transfer = true`
- Skip ordinary outpatient routing

### Step 3. Multi-Turn Symptom Collection

If no immediate red-zone condition is found, the Dialogue Manager asks follow-up questions:

- When did it start
- Where is the pain or discomfort
- How severe is it
- Is it getting worse
- Any fever
- Any trauma
- Any vomiting, bleeding, fainting, dyspnea, or drowsiness
- Relevant age/sex questions

The LLM is responsible for:

- Understanding free-text patient answers
- Asking the next best question
- Extracting structured fields from each reply

After every patient turn:

- Update Session Context
- Re-run risk detection
- Re-check missing required fields

### Step 4. Hidden Critical Sign Detection

The LLM should detect non-obvious risk combinations and pass them into structured flags.

Example:

- Car accident + extreme thirst + drowsiness

This may indicate occult bleeding or shock risk. The system should create a `risk_flag`, then the rules engine confirms whether it meets red-zone criteria.

This is a key principle:

- LLM finds suspicious patterns
- Rules engine confirms high-risk decisions

### Step 5. Boundary Error Prevention

Before assigning department, the system must check high-confusion scenarios.

Examples:

- Girl under 10 with abdominal pain -> Pediatrics first, not Gynecology
- Male patient with lower abdominal pain -> do not route to Gynecology
- Pediatric fever -> Pediatrics, unless emergency signs override
- Trauma-related symptoms -> Emergency / trauma-oriented entry first

This layer protects against incorrect routing caused by superficial keyword matching.

### Step 6. Mandatory Temperature Completion

Before final triage output, system checks:

- Is temperature present in Session Context

If not:

- Ask directly for temperature
- If patient does not know, record `temperature = unknown`
- Mark it in `missing_required_fields` or `data_quality_note`

If emergency signs are present, do not delay emergency transfer just because temperature is missing.

### Step 7. Triage Classification

After enough data is gathered, the Triage Decision Service produces:

- `Red`
  - Critical
  - Immediate emergency attention or transfer
- `Yellow`
  - Urgent
  - Needs fast-track consultation
- `Green`
  - Ordinary
  - Standard outpatient routing

Suggested logic:

- `Red`: confirmed emergency symptoms, severe vital sign abnormality, hidden critical pattern confirmed by rules
- `Yellow`: potentially serious but not immediately critical, worsening symptoms, moderate risk factors
- `Green`: stable, mild, ordinary outpatient pathway

### Step 8. Rule Engine Double Confirmation

All red-flag outcomes should be confirmed by rules engine:

- Emergency transfer decision
- Red-zone triage classification
- High-risk symptom clusters

This creates a safety fallback and reduces missed diagnoses.

### Step 9. Output Triage Handover Sheet

Final structured output:

```json
{
  "triage_level": "Red | Yellow | Green",
  "risk_flags": [
    "possible_occult_bleeding",
    "fever",
    "pediatric_case"
  ],
  "need_emergency_transfer": true,
  "recommended_outpatient_entry": "Emergency | Pediatrics | Internal Medicine | General Surgery"
}
```

Optionally include:

- `session_summary`
- `key_symptoms`
- `missing_data`
- `rule_engine_decision_log`

## 5. Recommended Dialogue Workflow

### 5.1 Dialogue Strategy

The agent should follow this order:

1. Ask the chief complaint
2. Collect age and sex
3. Ask temperature if missing
4. Ask pain score and vital signs if available
5. Explore onset, duration, severity, associated symptoms
6. Screen emergency indicators
7. Fill missing structured fields
8. Produce triage result

### 5.2 Dialogue Control Principle

- Never let the LLM freely diagnose disease
- Keep the LLM focused on symptom collection, triage questioning, and structured output
- Use the rules engine for emergency confirmation and safety boundaries
- Always prefer safer routing when ambiguity is high

## 6. Suggested Technical Workflow in VS Code

Inside `VS Code`, a practical build order is:

1. Create backend project
   - API routes
   - session state
   - triage output schema
2. Add a simple chat UI
   - input box
   - patient info panel
   - triage result card
3. Integrate LLM
   - prompt for symptom extraction
   - prompt for next-question generation
   - prompt for handover summary
4. Add rules engine
   - red-flag rules
   - pediatric/gynecology boundary rules
   - mandatory temperature validation
5. Add logs and test cases
   - normal case
   - hidden emergency case
   - boundary confusion case

## 7. A Simple Architecture View

```text
[Patient/UI]
    ->
[Frontend Chat Page]
    ->
[Backend API]
    ->
[Dialogue Manager]
    -> [LLM Service]
    -> [Session Context Store]
    -> [Rules Engine]
    ->
[Triage Decision Service]
    ->
[Triage Handover Sheet]
```

## 8. Deliverable for Task 2.1.2

For this task, the minimum complete workflow should ensure:

- Multi-turn symptom collection
- Mandatory temperature capture
- Red / Yellow / Green triage
- Hidden critical sign detection
- Rule-engine confirmation of red flags
- Department routing with boundary error prevention
- Structured triage handover output

## 9. What We Should Build Next

After the workflow is confirmed, the next implementation order should be:

1. Define the Session Context data structure
2. Define the triage output JSON schema
3. Design the LLM system prompt and extraction prompt
4. Implement the rule engine
5. Build the simple API
6. Build the simple UI in VS Code project

