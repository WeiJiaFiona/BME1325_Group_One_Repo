# TriageAI - Product Requirements Document

> **Version:** 0.1.0 (Draft)
> **Last Updated:** January 2026
> **Status:** Active Development

---

## 1. Executive Summary

TriageAI is an AI-powered patient triage system that transforms how healthcare providers handle patient intake and routing. The system uses conversational AI to collect symptoms, assess severity using clinical algorithms, and route patients to appropriate care levels.

### 1.1 Vision

**Reduce time-to-treatment by 60%** through intelligent pre-consultation triage that:
- Captures complete patient context before doctor interaction
- Surfaces urgent cases immediately
- Matches patients to the right specialty
- Provides full audit trail for compliance

### 1.2 Target Users

| User Type | Primary Need | Success Metric |
|-----------|--------------|----------------|
| **Patients** | Quick, easy symptom reporting | < 5 min to complete intake |
| **Doctors** | Pre-qualified queue with context | 40% less time on wrong-specialty cases |
| **Nurses/Staff** | Automated prioritization | Zero manual queue sorting |
| **Administrators** | Compliance + analytics | 100% audit coverage |

---

## 2. Functional Requirements

### 2.1 Patient Intake Module

#### FR-001: Conversational Symptom Collection
- **Description:** Natural language interface for patients to describe symptoms
- **Input:** Free-text symptom description
- **Output:** Structured symptom data (location, duration, severity, associated factors)
- **Acceptance Criteria:**
  - [ ] Handles typos and colloquial language
  - [ ] Asks clarifying follow-up questions
  - [ ] Supports multiple symptoms in one session
  - [ ] Works on mobile browsers (responsive)

#### FR-002: Patient History Linking
- **Description:** Connect intake to existing patient records
- **Input:** Patient identifier (email, phone, or MRN)
- **Output:** Linked patient profile with relevant history
- **Acceptance Criteria:**
  - [ ] Retrieves relevant past conditions
  - [ ] Flags medication interactions
  - [ ] Shows allergy alerts

#### FR-003: Multi-Channel Support
- **Description:** Accept intake from multiple channels
- **Channels:**
  - Web application (primary)
  - Mobile-responsive web
  - SMS (future)
  - WhatsApp (future)
- **Acceptance Criteria:**
  - [ ] Consistent experience across channels
  - [ ] Session continuity if channel switches

---

### 2.2 Triage Engine

#### FR-010: Severity Assessment
- **Description:** AI-powered severity scoring based on symptoms
- **Algorithm Components:**
  1. Symptom pattern matching (clinical guidelines)
  2. LLM reasoning for complex/ambiguous cases
  3. Red flag detection (chest pain, difficulty breathing, etc.)
- **Output:** Severity score (1-5) with confidence level
- **Acceptance Criteria:**
  - [ ] 95% accuracy on standard presentations
  - [ ] 100% sensitivity on red flag conditions
  - [ ] Explains reasoning for audit trail

#### FR-011: Urgency Classification
- **Description:** Classify cases by required response time
- **Categories:**
  | Level | Response Time | Examples |
  |-------|---------------|----------|
  | Emergency | Immediate | Chest pain, stroke symptoms |
  | Urgent | < 1 hour | High fever, severe pain |
  | Semi-Urgent | < 4 hours | Moderate symptoms, worsening |
  | Standard | Same day | Routine concerns |
  | Non-Urgent | Scheduled | Follow-ups, minor issues |
- **Acceptance Criteria:**
  - [ ] Never under-classifies emergencies
  - [ ] Reduces over-classification by 30%

#### FR-012: Specialty Matching
- **Description:** Match patient to appropriate medical specialty
- **Input:** Triaged symptom data
- **Output:** Ranked list of suitable specialties
- **Acceptance Criteria:**
  - [ ] Primary specialty match accuracy > 90%
  - [ ] Considers doctor availability
  - [ ] Handles multi-specialty cases

#### FR-013: Red Flag Detection
- **Description:** Immediately surface life-threatening symptoms
- **Red Flags Include:**
  - Chest pain with radiation
  - Difficulty breathing
  - Sudden severe headache
  - Loss of consciousness
  - Signs of stroke (FAST criteria)
  - Severe allergic reaction
- **Acceptance Criteria:**
  - [ ] 100% detection rate
  - [ ] < 1 second response time
  - [ ] Automatic escalation to emergency queue

---

### 2.3 Queue Management

#### FR-020: Priority Queue System
- **Description:** Maintain doctor queues ordered by urgency and wait time
- **Sorting Logic:**
  1. Urgency level (primary)
  2. Deterioration risk (secondary)
  3. Wait time (tertiary)
- **Acceptance Criteria:**
  - [ ] Real-time queue updates
  - [ ] Automatic reordering on new intakes
  - [ ] Visual urgency indicators

#### FR-021: Wait Time Estimation
- **Description:** Provide accurate wait time estimates to patients
- **Factors:**
  - Current queue depth
  - Average consultation duration
  - Doctor availability
- **Acceptance Criteria:**
  - [ ] Estimates within 20% of actual
  - [ ] Updates in real-time
  - [ ] Communicates delays proactively

#### FR-022: Doctor Assignment
- **Description:** Assign patients to specific doctors
- **Assignment Logic:**
  - Specialty match
  - Current workload balance
  - Patient preference (if applicable)
  - Continuity of care
- **Acceptance Criteria:**
  - [ ] Fair workload distribution
  - [ ] Respects doctor preferences
  - [ ] Handles reassignment gracefully

---

### 2.4 Doctor Dashboard

#### FR-030: Queue View
- **Description:** Real-time view of assigned patient queue
- **Display Elements:**
  - Patient summary card
  - Urgency indicator
  - Wait time
  - Key symptoms
  - Relevant history flags
- **Acceptance Criteria:**
  - [ ] Updates without page refresh
  - [ ] Expandable patient details
  - [ ] One-click to start consultation

#### FR-031: Patient Context Card
- **Description:** Comprehensive pre-consultation summary
- **Content:**
  - AI-generated symptom summary
  - Triage reasoning
  - Relevant history
  - Red flags highlighted
  - Suggested questions
- **Acceptance Criteria:**
  - [ ] Loads in < 2 seconds
  - [ ] Printable format available
  - [ ] Links to full records

#### FR-032: Override Capabilities
- **Description:** Allow doctors to override AI decisions
- **Override Types:**
  - Change urgency level
  - Reassign specialty
  - Flag AI error
- **Acceptance Criteria:**
  - [ ] All overrides logged
  - [ ] Requires reason selection
  - [ ] Feeds back to model improvement

---

### 2.5 Audit & Compliance

#### FR-040: Complete Audit Trail
- **Description:** Log every AI decision for regulatory compliance
- **Logged Events:**
  - Patient input (timestamped)
  - AI reasoning steps
  - Severity/urgency decisions
  - Queue assignments
  - Doctor overrides
- **Acceptance Criteria:**
  - [ ] Immutable logs
  - [ ] Searchable by patient, date, decision type
  - [ ] Exportable for audits

#### FR-041: HIPAA Compliance
- **Description:** Meet healthcare data protection requirements
- **Requirements:**
  - Encryption at rest and in transit
  - Access controls with audit logging
  - Data retention policies
  - BAA-ready infrastructure
- **Acceptance Criteria:**
  - [ ] Passes security assessment
  - [ ] Documentation for compliance officers
  - [ ] Incident response procedures

---

## 3. Non-Functional Requirements

### 3.1 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Intake completion time | < 5 minutes | End-to-end timing |
| Triage response time | < 3 seconds | AI processing only |
| Dashboard load time | < 2 seconds | First contentful paint |
| System availability | 99.9% | Monthly uptime |

### 3.2 Scalability

- Handle 1,000 concurrent intakes
- Support 100 simultaneous doctor sessions
- Queue depth up to 10,000 patients
- Data retention: 7 years (configurable)

### 3.3 Security

- SOC 2 Type II compliance path
- HIPAA technical safeguards
- Regular penetration testing
- Encrypted data at rest (AES-256)
- TLS 1.3 for data in transit

### 3.4 Reliability

- Graceful degradation if AI unavailable
- Manual triage fallback mode
- Data backup every hour
- RPO: 1 hour, RTO: 4 hours

---

## 4. Integration Requirements

### 4.1 EMR/EHR Systems

| System | Integration Type | Priority |
|--------|------------------|----------|
| Epic | FHIR API | High |
| Cerner | FHIR API | High |
| Allscripts | Custom API | Medium |
| athenahealth | Partner API | Medium |

### 4.2 Authentication

- SSO support (SAML 2.0, OIDC)
- MFA requirement for clinical staff
- Role-based access control
- Session timeout policies

### 4.3 Notifications

- SMS notifications (Twilio)
- Email notifications
- Push notifications (mobile)
- In-app alerts

---

## 5. Success Metrics

### 5.1 Patient Metrics
- Net Promoter Score (NPS) > 50
- Intake completion rate > 85%
- Time to triage < 5 minutes

### 5.2 Clinical Metrics
- Triage accuracy > 95%
- Red flag sensitivity: 100%
- Specialty match accuracy > 90%

### 5.3 Operational Metrics
- Queue wait time reduction: 40%
- Doctor time on wrong-specialty cases: -40%
- Manual triage effort: -70%

---

## 6. Out of Scope (v1)

The following are explicitly **not** in scope for initial release:

- Telemedicine video calls
- Prescription management
- Billing integration
- Multi-language support (English only initially)
- Voice-based intake
- Chronic disease management

These may be added in future versions.

---

## 7. Open Questions

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | Which EMR systems to prioritize? | Product | Open |
| 2 | Regulatory requirements by region? | Legal | Open |
| 3 | AI model hosting (cloud vs edge)? | Engineering | Open |
| 4 | Patient consent workflow details? | Compliance | Open |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **EMR/EHR** | Electronic Medical/Health Record |
| **FHIR** | Fast Healthcare Interoperability Resources (API standard) |
| **MRN** | Medical Record Number |
| **NPS** | Net Promoter Score |
| **RPO** | Recovery Point Objective |
| **RTO** | Recovery Time Objective |
| **Triage** | Process of determining priority of treatment |

---

## Appendix B: User Stories

### Patient Stories
- As a patient, I want to describe my symptoms in my own words so I don't have to navigate medical terminology.
- As a patient, I want to know my estimated wait time so I can plan accordingly.
- As a patient, I want to receive updates if my position changes so I'm not surprised.

### Doctor Stories
- As a doctor, I want to see a summary of the patient's issue before they walk in so I can prepare.
- As a doctor, I want urgent cases highlighted so I don't miss emergencies.
- As a doctor, I want to override AI decisions when my clinical judgment differs.

### Admin Stories
- As an administrator, I want complete audit logs so we can satisfy regulatory requirements.
- As an administrator, I want analytics on triage accuracy so we can improve the system.

---

*Document maintained by the TriageAI team. For questions, contact the product owner.*
