# Formwise Agent

> Privacy-first AI agent for helping users fill online forms using their approved personal data and documents.

## Project Status

**Phase 1 — Architecture & Project Foundation**

The project is being developed in controlled phases. Each phase is implemented, tested, reviewed, and only then followed by the next phase.

## Product Vision

A user should be able to securely provide their personal information and documents once, then request tasks such as:

> “SSC ka form bhar do.”

Formwise will prepare the task, retrieve only approved information, navigate supported websites, map verified data to form fields, and require human approval before sensitive actions such as OTP, CAPTCHA, payment, or final submission.

## Core Safety Rule

**Never guess personal data.** A field may only be filled when there is an approved source, adequate confidence, and a valid mapping. Otherwise Formwise asks the user.

## High-Level Architecture

- Web application
- Backend/API
- Agent orchestration
- AI/model provider abstraction
- Document intelligence
- Personal knowledge/retrieval layer
- Browser automation
- Form mapping engine
- Policy, permission, and approval engine
- Secure storage and credential vault
- Audit and observability

## Development Phases

1. Architecture + PRD + Project Foundation
2. Profile + Secure Document Vault + Upload
3. OCR + Document Intelligence + Data Extraction
4. Personal Knowledge Base + Retrieval
5. AI Agent / Reasoning Engine
6. Playwright Browser Agent
7. Form Detection + Field Mapping Engine
8. Approval + Permission + Safety Engine
9. Real End-to-End Form Filling
10. Security + Audit + Reliability + Recovery
11. Full Testing + Production Deployment

## Important Security Principles

- User data isolation
- Private document storage
- Encryption at rest and in transit
- No public document URLs
- Separate credential handling from documents
- Least-privilege access
- Explicit approval for high-impact actions
- Complete audit trail
- Kill switch and task cancellation
- Configurable confidence thresholds

## Current Phase Scope

Phase 1 defines the product contract, architecture, security model, repository structure, API boundaries, and implementation roadmap. It does **not** implement OCR, AI autonomy, browser automation, or real form submission.
