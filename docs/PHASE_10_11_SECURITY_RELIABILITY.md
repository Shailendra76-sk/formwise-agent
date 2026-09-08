# Phase 10–11: Security, Reliability and Release Readiness

## Authentication

All protected endpoints use `require_user_id`. Production requires a signed JWT with a `sub` and `exp` claim. The legacy `X-User-ID` header is development-only and must be disabled in production.

Set:
- `FORMWISE_ENVIRONMENT=production`
- `FORMWISE_JWT_SECRET=<strong random secret, 32+ characters>`
- `FORMWISE_ALLOW_LEGACY_USER_HEADER=false`

The application refuses to start in production if these conditions are unsafe.

## Form safety

Formwise may inspect and fill safe controls, but never automates CAPTCHA/anti-bot bypass, OTP, payment, legal declarations, or final submission. Sensitive personal data requires an exact, short-lived approval bound to the session, field, index and value.

## Reliability boundaries

- Browser sessions are isolated by authenticated user.
- Private/link-local/reserved network destinations are blocked.
- Navigation and operation timeouts are enforced.
- Existing user-entered values are never silently overwritten.
- Form mappings are checked against current control metadata before filling.
- Approval payloads are fingerprinted and cannot be altered after approval.
- Audit events should contain identifiers and outcomes, not raw personal values.
- Private documents and knowledge indexes remain in per-user private storage.

## Release gate

Before production deployment, run the complete backend test suite and verify browser dependencies are installed. Configure JWT secrets through the deployment secret manager; never commit credentials or personal documents.

## Current product boundary

This repository now contains the core end-to-end backend workflow through review-before-submit. A production UI, real identity provider integration, and site-specific adapters can be layered on top without weakening the safety gates.
