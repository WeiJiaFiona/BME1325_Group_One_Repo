# TriageAI - System Architecture

> **Version:** 0.1.0
> **Last Updated:** January 2026
> **Status:** Design Phase

---

## 1. Architecture Overview

TriageAI follows a **microservices architecture** designed for healthcare-grade reliability, security, and scalability.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│   │  Patient    │    │   Doctor    │    │   Admin     │    │   Mobile    │  │
│   │  Web App    │    │  Dashboard  │    │   Portal    │    │    PWA      │  │
│   │  (React)    │    │  (React)    │    │  (React)    │    │  (React)    │  │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│          │                  │                  │                  │         │
└──────────┼──────────────────┼──────────────────┼──────────────────┼─────────┘
           │                  │                  │                  │
           └──────────────────┴─────────┬────────┴──────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│                         (AWS API Gateway + WAF)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Rate Limiting (100 req/min per user)                                     │
│  • JWT Validation (Auth0/Cognito)                                           │
│  • Request Logging                                                          │
│  • DDoS Protection (AWS Shield)                                             │
│  • API Versioning (/v1/, /v2/)                                              │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   INTAKE SERVICE    │  │   TRIAGE SERVICE    │  │   QUEUE SERVICE     │
│   (Node.js/Express) │  │   (Node.js/Express) │  │   (Node.js/Express) │
├─────────────────────┤  ├─────────────────────┤  ├─────────────────────┤
│                     │  │                     │  │                     │
│  • Conversation     │  │  • Severity Calc    │  │  • Priority Queue   │
│    Management       │  │  • LLM Integration  │  │  • Doctor Matching  │
│  • Symptom NLP      │  │  • Red Flag Check   │  │  • Wait Estimation  │
│  • History Lookup   │  │  • Specialty Match  │  │  • Assignment       │
│  • Session State    │  │  • Audit Logging    │  │  • Notifications    │
│                     │  │                     │  │                     │
└─────────┬───────────┘  └─────────┬───────────┘  └─────────┬───────────┘
          │                        │                        │
          │                        ▼                        │
          │              ┌─────────────────────┐            │
          │              │    AI LAYER         │            │
          │              │    (LLM API)        │            │
          │              ├─────────────────────┤            │
          │              │  • Symptom Parser   │            │
          │              │  • Triage Reasoner  │            │
          │              │  • Summary Gen      │            │
          │              └─────────────────────┘            │
          │                                                 │
          └─────────────────────┬───────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   PostgreSQL    │  │     Redis       │  │    S3 Bucket    │             │
│  │   (RDS)         │  │   (ElastiCache) │  │   (Audit Logs)  │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • Patient Data  │  │ • Session State │  │ • Immutable Logs│             │
│  │ • Triage History│  │ • Queue State   │  │ • Decision Audit│             │
│  │ • Doctor Prefs  │  │ • Cache Layer   │  │ • Compliance    │             │
│  │ • Audit Trail   │  │ • Pub/Sub       │  │ • Long-term     │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Service Breakdown

### 2.1 Intake Service

**Purpose:** Handle patient symptom collection through conversational interface.

**Responsibilities:**
- Manage multi-turn conversations
- Parse natural language symptoms
- Validate and structure input
- Link to patient history
- Hand off to Triage Service

**Key Endpoints:**
```
POST /v1/intake/start          # Start new intake session
POST /v1/intake/message        # Send message in conversation
GET  /v1/intake/session/:id    # Get session state
POST /v1/intake/complete       # Mark intake complete
```

**Data Flow:**
```
Patient Input → NLP Parser → Structured Symptoms → Validation → Store
                    │
                    ▼
              Follow-up Questions (if needed)
```

---

### 2.2 Triage Service

**Purpose:** Assess severity and route patients appropriately.

**Responsibilities:**
- Calculate severity score (1-5)
- Detect red flags immediately
- Match to specialty
- Generate clinical summary
- Log all decisions for audit

**Key Endpoints:**
```
POST /v1/triage/assess         # Perform triage assessment
GET  /v1/triage/result/:id     # Get triage result
POST /v1/triage/override       # Doctor override (authenticated)
GET  /v1/triage/audit/:id      # Get audit trail
```

**Triage Algorithm:**
```
┌─────────────────────────────────────────────────────────────┐
│                     TRIAGE PIPELINE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. RED FLAG CHECK (Rule-based, <100ms)                     │
│     ├── Chest pain patterns                                 │
│     ├── Breathing difficulty                                │
│     ├── Stroke symptoms (FAST)                              │
│     └── If ANY match → EMERGENCY (bypass rest)              │
│                                                             │
│  2. SYMPTOM PATTERN MATCH (Clinical guidelines)             │
│     ├── Match against known presentations                   │
│     ├── Calculate base severity score                       │
│     └── Identify specialty indicators                       │
│                                                             │
│  3. LLM REASONING (LLM API)                                 │
│     ├── Complex/ambiguous cases only                        │
│     ├── Consider symptom combinations                       │
│     ├── Factor in patient history                           │
│     └── Generate reasoning explanation                      │
│                                                             │
│  4. FINAL SCORING                                           │
│     ├── Combine rule-based + LLM scores                     │
│     ├── Apply confidence weighting                          │
│     └── Output: Severity, Urgency, Specialty                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### 2.3 Queue Service

**Purpose:** Manage patient queues and doctor assignments.

**Responsibilities:**
- Maintain priority queues per doctor/specialty
- Calculate wait times
- Handle doctor assignments
- Send notifications
- Support real-time updates (WebSocket)

**Key Endpoints:**
```
GET  /v1/queue/doctor/:id      # Get doctor's queue
POST /v1/queue/assign          # Assign patient to doctor
POST /v1/queue/complete        # Mark consultation complete
GET  /v1/queue/stats           # Queue analytics

# WebSocket
WS   /v1/queue/live            # Real-time queue updates
```

**Queue Priority Algorithm:**
```python
def calculate_priority(patient):
    # Primary: Urgency level (1=Emergency, 5=Non-urgent)
    base_score = (6 - patient.urgency_level) * 1000

    # Secondary: Deterioration risk
    deterioration_bonus = patient.deterioration_risk * 100

    # Tertiary: Wait time (older = higher priority)
    wait_minutes = (now - patient.intake_time).minutes
    wait_bonus = min(wait_minutes, 120)  # Cap at 2 hours

    return base_score + deterioration_bonus + wait_bonus
```

---

## 3. AI Layer Architecture

### 3.1 LLM API Integration

**Model Selection:**
- **Production:** Groq API with Llama 3.3 70B (fast, free tier)
- **Local Development:** Ollama with Llama 3.2 (offline capable)
- **Flexible:** Supports any OpenAI-compatible API

**Prompt Engineering:**
```
┌─────────────────────────────────────────────────────────────┐
│                    PROMPT STRUCTURE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SYSTEM PROMPT                                              │
│  ├── Role: Medical triage assistant                         │
│  ├── Constraints: Never diagnose, always explain            │
│  ├── Output format: Structured JSON                         │
│  └── Safety: Err on side of caution                         │
│                                                             │
│  USER PROMPT                                                │
│  ├── Structured symptom data                                │
│  ├── Relevant patient history                               │
│  ├── Specific question to answer                            │
│  └── Required output schema                                 │
│                                                             │
│  RESPONSE                                                   │
│  ├── Severity score with confidence                         │
│  ├── Urgency classification                                 │
│  ├── Specialty recommendation                               │
│  └── Reasoning (for audit trail)                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Fallback Strategy:**
1. Primary: LLM API (Groq/Ollama)
2. Fallback: Rule-based triage (always available)
3. Emergency: Surface to human immediately

---

## 4. Data Architecture

### 4.1 Database Schema (PostgreSQL)

```sql
-- Core patient table
CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_mrn VARCHAR(100),          -- Link to EMR
    email VARCHAR(255),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Intake sessions
CREATE TABLE intake_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id),
    status VARCHAR(20) DEFAULT 'active',  -- active, completed, abandoned
    channel VARCHAR(20) NOT NULL,         -- web, sms, whatsapp
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    conversation JSONB                     -- Full conversation history
);

-- Triage results
CREATE TABLE triage_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES intake_sessions(id),
    severity_score INTEGER CHECK (severity_score BETWEEN 1 AND 5),
    urgency_level VARCHAR(20),
    specialty VARCHAR(50),
    red_flags TEXT[],
    ai_reasoning TEXT,
    confidence DECIMAL(3,2),
    model_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Queue entries
CREATE TABLE queue_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    triage_id UUID REFERENCES triage_results(id),
    doctor_id UUID REFERENCES doctors(id),
    priority_score INTEGER,
    status VARCHAR(20) DEFAULT 'waiting',  -- waiting, in_progress, completed
    queued_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Audit log (append-only)
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    actor_id UUID,
    actor_type VARCHAR(20),               -- patient, doctor, system
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX idx_queue_doctor_status ON queue_entries(doctor_id, status);
CREATE INDEX idx_triage_urgency ON triage_results(urgency_level);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
```

### 4.2 Redis Data Structures

```
# Session state (TTL: 24 hours)
session:{session_id} = {
    patient_id: UUID,
    conversation: [...],
    current_step: "symptoms",
    last_activity: timestamp
}

# Doctor queue (Sorted Set)
queue:doctor:{doctor_id} = [
    (priority_score, patient_id),
    ...
]

# Real-time pub/sub channels
channel:queue:{doctor_id}    # Queue updates
channel:alerts               # System-wide alerts
```

### 4.3 S3 Audit Storage

```
s3://triageai-audit-logs/
├── year=2026/
│   ├── month=01/
│   │   ├── day=04/
│   │   │   ├── triage_decisions_00.parquet
│   │   │   ├── triage_decisions_01.parquet
│   │   │   └── ...
```

**Format:** Parquet (compressed, queryable with Athena)
**Retention:** 7 years (HIPAA requirement)
**Access:** Read-only after write (immutable)

---

## 5. Security Architecture

### 5.1 Authentication Flow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  User   │────▶│   Auth0 /   │────▶│ API Gateway │────▶│  Services   │
│         │     │   Cognito   │     │  (Validate) │     │             │
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                      │
                      ▼
                ┌─────────────┐
                │   JWT with  │
                │   Claims    │
                └─────────────┘
```

**JWT Claims:**
```json
{
  "sub": "user_id",
  "role": "doctor|patient|admin",
  "org_id": "organization_id",
  "permissions": ["read:patients", "write:triage"],
  "exp": 1704412800
}
```

### 5.2 Data Encryption

| Data State | Method | Key Management |
|------------|--------|----------------|
| At Rest | AES-256 | AWS KMS |
| In Transit | TLS 1.3 | AWS Certificate Manager |
| In Logs | Field-level encryption | Custom keys |

### 5.3 Access Control Matrix

| Role | Patients | Triage | Queue | Audit |
|------|----------|--------|-------|-------|
| Patient | Own only | View own | View position | None |
| Doctor | Assigned | Full | Own queue | View own |
| Nurse | Assigned | View | All queues | None |
| Admin | All | All | All | All |

---

## 6. Deployment Architecture

### 6.1 AWS Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS VPC                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Public Subnet                                 │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │   │
│  │  │  CloudFront   │  │  API Gateway  │  │     ALB       │            │   │
│  │  │  (Static)     │  │  (REST API)   │  │  (WebSocket)  │            │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Private Subnet                                │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │                    ECS Fargate Cluster                         │  │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                     │  │   │
│  │  │  │ Intake   │  │ Triage   │  │  Queue   │                     │  │   │
│  │  │  │ Service  │  │ Service  │  │ Service  │                     │  │   │
│  │  │  │ (x3)     │  │ (x3)     │  │ (x3)     │                     │  │   │
│  │  │  └──────────┘  └──────────┘  └──────────┘                     │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Data Subnet                                   │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │   │
│  │  │  RDS Postgres │  │  ElastiCache  │  │   S3 Bucket   │            │   │
│  │  │  (Multi-AZ)   │  │   (Redis)     │  │  (Audit Logs) │            │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Scaling Strategy

| Component | Scaling Trigger | Min | Max |
|-----------|-----------------|-----|-----|
| Intake Service | CPU > 70% | 2 | 10 |
| Triage Service | Queue depth > 100 | 2 | 10 |
| Queue Service | Connections > 1000 | 2 | 6 |
| RDS | Read replicas | 1 | 3 |
| Redis | Memory > 80% | 1 | 3 |

---

## 7. Monitoring & Observability

### 7.1 Key Metrics

**Business Metrics:**
- Intake completion rate
- Triage accuracy (vs doctor override)
- Average wait time
- Queue depth by urgency

**Technical Metrics:**
- API latency (p50, p95, p99)
- Error rates by service
- AI API latency
- Database query times

### 7.2 Alerting Rules

| Metric | Warning | Critical |
|--------|---------|----------|
| API p99 latency | > 2s | > 5s |
| Error rate | > 1% | > 5% |
| Queue depth (Emergency) | > 5 | > 10 |
| AI API availability | < 99% | < 95% |

### 7.3 Logging

**Structured JSON logs:**
```json
{
  "timestamp": "2026-01-04T10:30:00Z",
  "level": "info",
  "service": "triage-service",
  "trace_id": "abc123",
  "event": "triage_completed",
  "patient_id": "uuid",
  "severity": 3,
  "latency_ms": 1234
}
```

**Log destinations:**
- CloudWatch Logs (real-time)
- S3 (long-term, compliance)
- DataDog/NewRelic (dashboards)

---

## 8. Development Workflow

### 8.1 Local Development

```bash
# Start local stack
docker-compose up -d postgres redis

# Run services
npm run dev:intake    # Port 3001
npm run dev:triage    # Port 3002
npm run dev:queue     # Port 3003

# Run tests
npm test
npm run test:integration
```

### 8.2 CI/CD Pipeline

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Push   │───▶│  Lint   │───▶│  Test   │───▶│  Build  │───▶│ Deploy  │
│         │    │ + Type  │    │ + Cover │    │ Docker  │    │  (Env)  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                                                                  │
                                                    ┌─────────────┴─────────────┐
                                                    │                           │
                                              ┌─────▼─────┐             ┌───────▼───────┐
                                              │  Staging  │────Manual───▶│  Production   │
                                              │  (Auto)   │   Approval   │   (Manual)    │
                                              └───────────┘              └───────────────┘
```

---

## 9. Technology Decisions

### 9.1 Why These Choices

| Choice | Alternatives Considered | Reasoning |
|--------|------------------------|-----------|
| Node.js | Python, Go | Async I/O, JS ecosystem, rapid development |
| PostgreSQL | MongoDB, DynamoDB | HIPAA compliance, relational integrity |
| Redis | Memcached | Pub/sub, sorted sets for queues |
| Groq/Llama | OpenAI, local models | Fast inference, free tier, safety focus |
| AWS | GCP, Azure | Healthcare compliance, mature |
| React | Vue, Svelte | Team expertise, ecosystem |

### 9.2 Technical Debt Backlog

| Item | Priority | Notes |
|------|----------|-------|
| Move to TypeScript strict mode | Medium | Currently using loose mode |
| Add request tracing | High | Needed for debugging |
| Implement circuit breaker for AI | High | Graceful degradation |
| Database query optimization | Medium | N+1 queries in queue service |

---

*Architecture document maintained by the TriageAI engineering team.*
