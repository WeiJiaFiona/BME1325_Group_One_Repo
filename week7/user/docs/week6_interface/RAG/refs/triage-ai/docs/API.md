# TriageAI API Documentation

> **Version:** v1
> **Base URL:** `https://api.triageai.dev/v1`

---

## Authentication

All API requests require a Bearer token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

Tokens are obtained through the Auth0/Cognito integration. Contact your administrator for API credentials.

---

## Endpoints

### Intake Service

#### Start Intake Session

```http
POST /intake/start
```

Start a new patient intake session.

**Request:**
```json
{
  "patient_id": "uuid (optional - creates guest if not provided)",
  "channel": "web | sms | whatsapp"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "active",
  "initial_prompt": "Hello! I'm here to help understand your symptoms. What brings you in today?"
}
```

---

#### Send Message

```http
POST /intake/message
```

Send a message in an active intake conversation.

**Request:**
```json
{
  "session_id": "uuid",
  "message": "I've had a headache for 3 days"
}
```

**Response:**
```json
{
  "response": "I understand you've been experiencing a headache for 3 days. Can you describe the pain? Is it constant or does it come and go?",
  "symptoms_extracted": [
    {
      "symptom": "headache",
      "duration": "3 days",
      "severity": null
    }
  ],
  "progress": 0.3,
  "next_required": ["severity", "location", "associated_symptoms"]
}
```

---

#### Complete Intake

```http
POST /intake/complete
```

Mark intake as complete and trigger triage.

**Request:**
```json
{
  "session_id": "uuid"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "completed",
  "triage_id": "uuid",
  "redirect_to": "/queue/status/{queue_entry_id}"
}
```

---

### Triage Service

#### Get Triage Result

```http
GET /triage/result/:triage_id
```

Get the result of a triage assessment.

**Response:**
```json
{
  "triage_id": "uuid",
  "severity_score": 3,
  "urgency_level": "semi-urgent",
  "specialty": "neurology",
  "red_flags": [],
  "summary": "Patient presents with persistent headache (3 days), moderate severity, no red flag symptoms. Recommended for neurology evaluation.",
  "confidence": 0.87,
  "created_at": "2026-01-04T10:30:00Z"
}
```

---

#### Doctor Override

```http
POST /triage/override
```

Allow a doctor to override AI triage decision.

**Request:**
```json
{
  "triage_id": "uuid",
  "new_severity": 4,
  "new_urgency": "urgent",
  "new_specialty": "emergency",
  "reason_code": "clinical_judgment",
  "notes": "Patient appears more distressed than AI assessment indicated"
}
```

**Response:**
```json
{
  "override_id": "uuid",
  "original": {
    "severity": 3,
    "urgency": "semi-urgent"
  },
  "updated": {
    "severity": 4,
    "urgency": "urgent"
  },
  "audited": true
}
```

---

### Queue Service

#### Get Doctor's Queue

```http
GET /queue/doctor/:doctor_id
```

Get the current queue for a doctor.

**Response:**
```json
{
  "doctor_id": "uuid",
  "queue": [
    {
      "queue_entry_id": "uuid",
      "patient_summary": "45F, headache 3 days, no red flags",
      "severity_score": 3,
      "urgency_level": "semi-urgent",
      "wait_time_minutes": 23,
      "priority_score": 3023,
      "triage_id": "uuid"
    }
  ],
  "total_waiting": 5,
  "estimated_clear_time": "2026-01-04T14:30:00Z"
}
```

---

#### Get Queue Position (Patient)

```http
GET /queue/position/:queue_entry_id
```

Get patient's position in queue.

**Response:**
```json
{
  "queue_entry_id": "uuid",
  "position": 3,
  "estimated_wait_minutes": 25,
  "doctor_name": "Dr. Sarah Chen",
  "specialty": "Neurology",
  "status": "waiting"
}
```

---

### Real-Time Updates (WebSocket)

#### Connect to Queue Updates

```
WS /queue/live
```

**Connection:**
```javascript
const ws = new WebSocket('wss://api.triageai.dev/v1/queue/live', {
  headers: { 'Authorization': 'Bearer <token>' }
});
```

**Events Received:**
```json
{
  "event": "queue_update",
  "data": {
    "queue_entry_id": "uuid",
    "new_position": 2,
    "estimated_wait_minutes": 15
  }
}
```

```json
{
  "event": "called",
  "data": {
    "queue_entry_id": "uuid",
    "message": "Please proceed to Room 3"
  }
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Session ID is required",
    "details": {
      "field": "session_id"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Invalid or missing token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 400 | Invalid request body |
| `SESSION_EXPIRED` | 410 | Intake session has expired |
| `RATE_LIMITED` | 429 | Too many requests |
| `AI_UNAVAILABLE` | 503 | AI service temporarily unavailable |

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/intake/*` | 100 | 1 minute |
| `/triage/*` | 50 | 1 minute |
| `/queue/*` | 200 | 1 minute |
| WebSocket | 10 connections | per user |

---

## Webhooks (Coming Soon)

Subscribe to events:
- `intake.completed`
- `triage.completed`
- `queue.position_changed`
- `queue.patient_called`

---

*For API access or support, contact api-support@triageai.dev*
