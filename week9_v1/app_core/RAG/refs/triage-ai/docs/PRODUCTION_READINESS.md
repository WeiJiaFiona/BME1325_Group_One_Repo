# TriageAI Production Readiness Assessment

> **Document Version**: 1.0
> **Last Updated**: January 2025
> **Status**: Pre-production / Demo

---

## Executive Summary

This document outlines the production readiness considerations for deploying TriageAI in Australian healthcare environments. It covers technical requirements, regulatory compliance, safety validation, and operational considerations.

---

## 1. Safety Architecture Assessment

### 1.1 Current Implementation

| Layer | Status | Description |
|-------|--------|-------------|
| Layer 1: Keyword Detection | ✅ Complete | <1ms deterministic red flag detection |
| Layer 2: Clinical Rules | ✅ Complete | Age-adjusted thresholds, vital signs |
| Layer 3: LLM Reasoning | ✅ Complete | LLM API with fallback |
| Layer 4: Safety Envelope | ✅ Complete | Prevents LLM under-triage |

### 1.2 Safety Guarantees

**Implemented:**
- Red flag conditions detected in <1ms (deterministic)
- LLM cannot recommend lower category than guardrails
- Complete audit trail for every decision
- Graceful degradation if LLM unavailable

**Required for Production:**
- [ ] Clinical validation study with ED physicians
- [ ] Sensitivity/specificity analysis on real patient data
- [ ] Edge case testing with clinical scenarios
- [ ] Adversarial testing (prompt injection, manipulation attempts)

### 1.3 Failure Modes

| Failure Mode | Current Handling | Risk Level |
|--------------|------------------|------------|
| LLM API unavailable | Fall back to guardrails-only | Low |
| Invalid input | Zod validation rejection | Low |
| Unrecognized symptoms | Default to safe category | Low |
| Keyword bypass attempts | LLM catches context | Medium |
| Multi-language input | English only currently | Medium |

---

## 2. Australian Regulatory Compliance

### 2.1 Therapeutic Goods Administration (TGA)

**Classification**: Medical Device Software (Class IIa - Rule 5.1)

> Software intended to provide information used in making decisions for diagnostic or therapeutic purposes is classified as Class IIa if the decisions do not have a high-risk impact.

**Requirements:**
- [ ] TGA notification (MD registration not required for Class IIa)
- [ ] Technical documentation per EN 62304 (Software lifecycle)
- [ ] Risk management per ISO 14971
- [ ] Quality management system per ISO 13485

### 2.2 Privacy Act 1988 (Australia)

**Compliance Areas:**

| Requirement | Status | Notes |
|-------------|--------|-------|
| Consent for collection | ⚠️ Required | User consent flow needed |
| Purpose limitation | ⚠️ Required | Privacy policy documentation |
| Data security | ✅ Designed | Encryption at rest/transit |
| Cross-border transfer | ⚠️ Required | LLM API may be US-based |
| Access and correction | ⚠️ Required | Data access endpoints needed |
| Breach notification | ⚠️ Required | Incident response plan needed |

**Australian Privacy Principles (APPs) Checklist:**
- [ ] APP 1: Open and transparent management
- [ ] APP 3: Collection of solicited personal information
- [ ] APP 5: Notification of collection
- [ ] APP 6: Use or disclosure of personal information
- [ ] APP 11: Security of personal information
- [ ] APP 12: Access to personal information

### 2.3 My Health Records Act 2012

**If integrating with My Health Record:**
- [ ] Registered Healthcare Provider Organisation (RHPO) status
- [ ] Conformance with My Health Record system specifications
- [ ] Data handling per healthcare identifiers regulations

### 2.4 State-Specific Regulations

| State | Key Regulation | Notes |
|-------|---------------|-------|
| NSW | Health Records and Information Privacy Act 2002 | Additional privacy requirements |
| VIC | Health Records Act 2001 | HPPs apply |
| QLD | Information Privacy Act 2009 | IPPs apply |
| WA | Health Services Act 2016 | Records management |
| SA | Health Care Act 2008 | Clinical governance |

---

## 3. Technical Requirements

### 3.1 Infrastructure

**Recommended Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS Sydney Region                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐                                            │
│  │   CloudFront    │  WAF + DDoS protection                     │
│  └────────┬────────┘                                            │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │  API Gateway    │  Rate limiting, auth                       │
│  └────────┬────────┘                                            │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  ECS Fargate Cluster                    │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │    │
│  │  │ Intake   │  │ Triage   │  │  Queue   │              │    │
│  │  │ Service  │  │ Service  │  │ Service  │              │    │
│  │  └──────────┘  └──────────┘  └──────────┘              │    │
│  └─────────────────────────────────────────────────────────┘    │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   RDS Postgres  │  │   ElastiCache   │  │   S3 (Audit)    │  │
│  │   Multi-AZ      │  │     Redis       │  │   7yr retention │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Requirements:**
- [ ] Deploy to AWS ap-southeast-2 (Sydney) for data sovereignty
- [ ] Multi-AZ deployment for high availability
- [ ] Auto-scaling based on queue depth
- [ ] VPC isolation for sensitive data

### 3.2 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Red flag detection | <1ms | ✅ <1ms |
| Full triage (with LLM) | <5s | ~3s |
| API p99 latency | <3s | TBD |
| Availability | 99.9% | TBD |
| Concurrent sessions | 1000+ | TBD |

### 3.3 Security Requirements

**Implemented:**
- [x] HTTPS/TLS 1.3 for all traffic
- [x] Helmet.js security headers
- [x] CORS configuration
- [x] Input validation (Zod)

**Required for Production:**
- [ ] AWS WAF with managed rules
- [ ] Rate limiting per user/IP
- [ ] JWT authentication (Auth0/Cognito)
- [ ] Field-level encryption for PHI
- [ ] Key rotation policy (KMS)
- [ ] Penetration testing
- [ ] SOC 2 Type II certification

### 3.4 Data Retention

| Data Type | Retention Period | Storage |
|-----------|------------------|---------|
| Triage decisions | 7 years | S3 (immutable) |
| Audit logs | 7 years | S3 + Athena |
| Session data | 24 hours | Redis |
| Patient identifiers | As required | RDS (encrypted) |

---

## 4. Clinical Validation

### 4.1 Validation Study Design

**Recommended Approach:**

1. **Retrospective Study**
   - Apply TriageAI to historical ED presentations
   - Compare with human triage decisions
   - Measure sensitivity/specificity per ATS category

2. **Prospective Study**
   - Run TriageAI in parallel with human triage
   - Blinded comparison
   - Statistical significance testing

**Key Metrics:**
- Sensitivity for ATS1-2 (critical cases): Target >99%
- Specificity overall: Target >85%
- Under-triage rate: Target <1%
- Over-triage rate: Acceptable <15%

### 4.2 Clinical Advisory Board

**Recommended Composition:**
- Emergency Medicine Physician (FACEM)
- Triage Nurse (CNE/CNC)
- Clinical Informaticist
- Medical Director
- Consumer representative

---

## 5. Operational Readiness

### 5.1 Monitoring and Alerting

**Key Alerts:**

| Alert | Threshold | Severity |
|-------|-----------|----------|
| ATS1 detection rate spike | >2x baseline | Critical |
| LLM API latency | >5s | High |
| Error rate | >1% | High |
| Under-triage override rate | >5% | Medium |

**Dashboards:**
- [ ] Real-time triage volume by category
- [ ] Red flag detection rates
- [ ] LLM confidence distribution
- [ ] Doctor override rates

### 5.2 Incident Response

**Severity Levels:**

| Level | Description | Response Time |
|-------|-------------|---------------|
| P1 | Safety-critical failure | <15 min |
| P2 | Service degradation | <1 hour |
| P3 | Minor issues | <4 hours |
| P4 | Improvements | Next sprint |

### 5.3 Change Management

- All changes to guardrails require clinical review
- Staged rollout (canary deployment)
- Automated rollback on error rate increase
- Change log with clinical sign-off

---

## 6. Integration Requirements

### 6.1 EMR/EHR Integration

**Target Systems:**
- [ ] Cerner Millennium (common in AU hospitals)
- [ ] Epic (growing presence)
- [ ] Best Practice (GP clinics)
- [ ] Medical Director (GP clinics)

**Integration Approach:**
- FHIR R4 API for interoperability
- HL7v2 for legacy systems
- Patient matching via HI Service (Medicare)

### 6.2 Identity Management

- [ ] My Health Record IHI validation
- [ ] Medicare provider integration
- [ ] Single Sign-On (SSO) for clinicians

---

## 7. Go-Live Checklist

### Phase 1: Pilot (Limited Release)
- [ ] Single site deployment
- [ ] <100 patients/day
- [ ] 100% human review of AI decisions
- [ ] Weekly clinical review meetings

### Phase 2: Controlled Release
- [ ] Multi-site (3-5 sites)
- [ ] <1000 patients/day
- [ ] Sampling-based human review (20%)
- [ ] Fortnightly clinical review

### Phase 3: General Availability
- [ ] Full rollout
- [ ] Exception-based human review
- [ ] Continuous monitoring
- [ ] Quarterly clinical audit

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM under-triages critical case | Low | Critical | 4-layer safety architecture |
| Data breach | Medium | High | Encryption, access controls |
| API downtime | Low | High | Failover to rule-based triage |
| Regulatory non-compliance | Medium | High | Legal review, compliance program |
| Clinical rejection | Medium | Medium | Clinical advisory board |

---

## 9. Next Steps

### Immediate (0-4 weeks)
1. Complete demo with realistic scenarios
2. Prepare clinical validation study protocol
3. Engage TGA regulatory consultant
4. Begin privacy impact assessment

### Short-term (1-3 months)
1. Run retrospective validation study
2. Establish clinical advisory board
3. Complete security penetration testing
4. Develop EMR integration specification

### Medium-term (3-6 months)
1. Complete prospective validation study
2. Achieve TGA compliance
3. Pilot deployment at partner site
4. SOC 2 Type II certification

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2025 | Pranjal Gupta | Initial draft |

---

*This document is confidential and intended for internal use and potential investor/partner evaluation.*
