# Formwise Agent — A-to-Z Post-Merge Status Report

**Target repository:** `https://github.com/Shailendra76-sk/formwise-agent`  
**Source imported:** `https://github.com/vivekdubey19854-ux/fromaaply`  
**Source commit:** `1add3c6ec84b859b9d9478801f48607dec7141ae`  
**Target baseline:** `181c8ce6d44f1f2b08e14844e8254b936f5ab70d`  
**Working branch:** `merge/zip-import-20261026`  
**Pull Request:** `https://github.com/Shailendra76-sk/formwise-agent/pull/26`  
**Report date:** 1 November 2026  
**Scope:** post-merge audit; main branch was not pushed or merged.

## A. One-page summary — Hinglish

Formwise Agent ek privacy-first assistant hai jo user ke approved personal data aur documents se online forms ko **research, prepare aur review** karta hai. Ye CAPTCHA solver, OTP thief, payment bot ya blind auto-submit tool nahi hai. User example: “SSC CHSL ka form bhar do.” System pehle official information dhoondta hai, user se confirmation leta hai, private document vault check karta hai, approved website open karta hai, OTP/CAPTCHA par rukta hai, fields inspect/map karta hai, sensitive values ke liye approval leta hai, screenshots banata hai aur final Submit user khud karta hai.

**Real completion estimate: 55–65% for a safe first release.** Code breadth high hai, lekin production readiness low-to-medium hai: local suite 152 tests pass karti hai, par PostgreSQL, Redis, Docker, Tesseract, external auth/AI/storage/payment providers aur real government portals ka complete staging E2E run nahi hua. Isliye “feature implemented” ko “real-world verified” nahi maana gaya.

**Top 5 blockers:** (1) production infrastructure aur secrets/staging integration, (2) first portal ke liye written authorization/terms review aur portal-specific E2E, (3) real auth/OAuth/phone OTP/email tests, (4) document privacy/DPDP retention-deletion controls ka operational proof, (5) dependency and warning cleanup plus restore drill.

**Shortest safe first-release path:** one authorized portal or local demo only; PostgreSQL + Redis staging; strong secrets and HTTPS/WSS; email/password auth first; CAPTCHA/OTP human gates; no payment in v1; upload/OCR limited to selected document types; run migration/backup/restore; perform a human-supervised test; then release to a small allowlist.

**Current verdict:** `IMPLEMENTED-UNTESTED` for many production adapters, not ready for unrestricted real users. `VERIFIED` means the stated test ran; it does not mean external service behavior was verified.

## B. End-user journey: “SSC CHSL ka form bhar do” to manual Submit

| Step | User sees | System does / code | Status + evidence |
|---|---|---|---|
| 1. Request | User enters natural-language request | `POST /v1/workflows`; `orchestrator.py:create_workflow` identifies exam/year and creates workflow | **VERIFIED**: orchestrator tests |
| 2. Research | Official facts, dates, fees, eligibility summary | `research.py`, `universal_research.py`; Serper if configured, DuckDuckGo fallback; official-domain preference | **PARTIAL**: local/demo and unit coverage; live current SSC research not run |
| 3. Confirmation | User reviews target, facts and requirements | `/confirm` re-checks readiness and keeps verification gate | **VERIFIED** for control flow; external facts not verified |
| 4. Document vault | User uploads/selects documents | `/v1/documents`; `routes.py`; private storage; SHA-256 metadata | **IMPLEMENTED-UNTESTED** for production storage |
| 5. OCR/extraction | User explicitly starts Extract/OCR | `document_intelligence.py:extract_document`; PyMuPDF, image OCR via Tesseract | **PARTIAL**: text/unit tests; Tesseract unavailable in runtime audit |
| 6. Open site | Browser session/live view opens | `/open`; `browser_agent.py:create_session`; URL safety and private-network blocking | **VERIFIED** on local demo; real portals not run |
| 7. Human gate | OTP/CAPTCHA modal says user must act | `/otp`, `/human`; user supplies OTP or uses live browser; no solver | **VERIFIED**: safety tests and UI copy |
| 8. Inspect/map | User sees fields and suggested mapping | `/plan`, `/inspect`; `form_mapping.py`, `form_execution.py`; confidence and ambiguity checks | **VERIFIED** locally; portal selectors generic |
| 9. Sensitive approval | User approves phone/address/category/etc. | `/v1/approvals`; `approval_engine.py`; verified-data gateway | **VERIFIED** by tests; production policy review pending |
| 10. Fill | Field-by-field fill and screenshots | `/fill`; `fill_control`, screenshot storage; blocked signals fail closed | **VERIFIED** local; external portal not run |
| 11. Final review | System says “review and click Submit yourself” | `/final-approval` only returns manual action; `/submit` cannot perform final click | **VERIFIED**: `orchestrator.py` and final-control tests |
| 12. Manual Submit | User clicks official Submit/Confirm | Browser remains human-controlled at final step | **VERIFIED safety boundary**; actual portal submission not run |

## C. Architecture in simple words

```text
React/Vite frontend
  -> FastAPI routes (/v1)
      -> auth + ownership + approval checks
      -> SQLAlchemy models / Alembic migrations
          -> SQLite local OR PostgreSQL production
      -> private storage adapter (local/S3-compatible registry)
      -> Playwright browser agent + live browser token
      -> research and verified-data gateway
      -> AI provider adapter with bounded failover
      -> Redis queue -> durable task worker -> checkpoint/retry/dead-letter
      -> payment/notification adapters (only when configured)
```

**Folders:** `backend/app` contains routes, domain services, browser controls, auth, models and workers. `backend/migrations` is the schema history. `backend/tests` contains unit/integration tests. `frontend/src` contains React screens and API wiring. `demo-target-site` is a local safe form. `deploy` contains Nginx and backup helper. `.github/workflows` contains CI. `docs` contains design, security, deployment and import notes.

Frontend calls FastAPI. FastAPI checks identity/ownership and delegates to services. The database stores profile, documents, workflow/task state, audit events, provider registries and payment ledger. Redis is intended for task queue/lease coordination but was not available in the audit environment. Browser sessions are Playwright sessions. AI providers are adapters; no provider call was made in this audit. Storage is private by default and credentials are encrypted before registry storage.

## D. One-by-one feature reports

### D1. Research and official-information lookup

- **What it is:** Find official application information before opening a form.
- **How it works:** `research.py` builds SSC-focused searches and prefers official domains; `universal_research.py` accepts a user-supplied URL and marks verification required. Serper is optional; DuckDuckGo HTML is fallback.
- **Files/functions:** `backend/app/research.py:search_web`, `research_exam`, `backend/app/universal_research.py`.
- **Database tables:** Workflow state/audit tables; no dedicated research fact table was proven in the inspected models.
- **API endpoints:** `POST /v1/workflows`, `POST /v1/workflows/{id}/confirm`, `POST /v1/research/research`.
- **Status + evidence:** **PARTIAL** — code and local-demo tests exist; live current SSC notice was not run.
- **Problems:** Search freshness, source correctness and portal-specific eligibility are not proven automatically.
- **Next:** Add source snapshots/citations and a human fact-confirmation screen. Effort: 2–4 days.
- **Test yourself:** Set a Serper key in a disposable staging environment, run a workflow, inspect returned sources, verify every date/fee against the official notice.

### D2. User confirmation and approval engine

- **What it is:** User remains decision-maker before consequential actions.
- **How it works:** Approval records and exact-payload final tokens gate sensitive/final actions.
- **Files/functions:** `approval_engine.py`, `approval_routes.py`, `orchestrator.py:final_approval`, `form_execution.py`.
- **Database tables:** `approvals`, `audit_logs`, workflow/task tables.
- **API endpoints:** `POST/GET /v1/approvals`, `POST /v1/approvals/{approval_id}/approve`, workflow confirmation/final-approval endpoints.
- **Status + evidence:** **VERIFIED** — approval/final-control tests pass; full 152-test suite passes.
- **Problems:** Production UI and policy matrix need manual review.
- **Next:** Add policy tests for every sensitive field and replay/expiry tests. Effort: 1–2 days.
- **Test yourself:** Try to fill a phone/CAPTCHA/legal/submit control without approval; expect pause or `BrowserSafetyError`.

### D3. Document vault, upload and deletion

- **What it is:** Private user documents such as identity, education, address proof, photo/signature.
- **How it works:** Upload metadata is stored; content goes through storage adapter; size/type/hash checks apply; download is authenticated; delete route exists.
- **Files/functions:** `routes.py:upload_document, download_document, delete_document`, `storage_service.py:upload_bytes/download_bytes/delete_object`.
- **Database tables:** `documents`, `audit_logs`; storage provider registries.
- **API endpoints:** `POST/GET /v1/documents`, `GET /v1/documents/{id}`, `GET /download`, `DELETE /v1/documents/{id}`.
- **Status + evidence:** **IMPLEMENTED-UNTESTED** — routes/services and ownership tests exist; production S3/Postgres not run.
- **Problems:** Retention schedule, user deletion workflow and verified deletion from every failover copy are not demonstrated.
- **Next:** Add deletion job, retention columns, deletion receipt and restore/delete drill. Effort: 3–5 days.
- **Test yourself:** Upload a synthetic PDF, extract, download, delete, then confirm metadata/object is gone; never use real Aadhaar in development.

### D4. OCR and document intelligence

- **What it is:** Extract likely fields from PDF/image documents.
- **How it works:** PyMuPDF extracts PDF text; scanned pages render and pass to Tesseract; regex detects email/phone/date/name-like fields.
- **Files/functions:** `document_intelligence.py:extract_document, _ocr_image, _fields_from_text`.
- **Database tables:** `documents` and extraction metadata in document records.
- **API endpoints:** `POST /v1/documents/{id}/extract`, `GET /v1/documents/{id}/extraction`.
- **Status + evidence:** **PARTIAL** — unit tests pass; Tesseract was not installed and no real document was used.
- **Problems:** OCR errors can create wrong suggestions; no production accuracy benchmark.
- **Next:** Create synthetic redacted benchmark set, confidence thresholds and human correction screen. Effort: 3–7 days.
- **Test yourself:** Use synthetic PDFs/images containing known dummy values and compare extraction to ground truth.

### D5. Browser automation, inspection and field mapping

- **What it is:** Open approved pages, inspect controls and fill safe non-submit controls.
- **How it works:** Playwright session has URL safety, private-network blocking, page/control inspection, deterministic mapping and fail-closed ambiguity behavior.
- **Files/functions:** `browser_agent.py:create_session, inspect_session, fill_control`, `form_mapping.py:map_controls`, `form_execution.py`.
- **Database tables:** `browser_sessions`, `browser_session_events`, `workflow_events`.
- **API endpoints:** `POST /v1/browser/sessions`, navigate, inspect, screenshot, human and delete routes; workflow plan/fill routes.
- **Status + evidence:** **VERIFIED** — local demo test passes; browser safety tests pass.
- **Problems:** Generic selectors are not evidence of portal compatibility; browser binaries/services need deployment validation.
- **Next:** Build per-portal contract tests with synthetic fixtures. Effort: 3–5 days per portal.
- **Test yourself:** Run `pytest -q` with Playwright Chromium installed; inspect local demo and verify submit control is blocked.

### D6. Live browser view and human gateway

- **What it is:** User can see/control a browser during OTP/CAPTCHA/legal gates.
- **How it works:** Live token endpoint, frame/input policy and Human Gateway UI; secure transport can be required by config.
- **Files/functions:** `live_browser_routes.py`, `LiveBrowserCanvas.tsx`, `HumanGatewayModal.jsx`, `HumanGatewayScreen.jsx`.
- **Database tables:** `browser_sessions`, events/audit logs.
- **API endpoints:** `/v1/live-browser/sessions/{id}/live-token`, `/live/agent-state`, browser human/screenshot routes.
- **Status + evidence:** **IMPLEMENTED-UNTESTED** — code and protocol docs exist; real WSS/live session not run.
- **Problems:** Defaults include `live_require_secure_transport=false`; production must force HTTPS/WSS and verify origin/auth.
- **Next:** Run browser-to-frontend staging test and security review. Effort: 2–4 days.
- **Test yourself:** Use local dev only; in staging confirm expired token, wrong user and insecure transport are rejected.

### D7. OTP and CAPTCHA gates

- **What it is:** Human-only barriers for one-time codes and anti-bot challenges.
- **How it works:** Backend identifies OTP/CAPTCHA controls and pauses; user supplies OTP or uses live canvas. No solver is present.
- **Files/functions:** `orchestrator.py:_otp_control/_human_control`, `browser_agent.py`, Human Gateway screens.
- **Database tables:** browser/workflow events; OTP provider challenge tables for phone auth are separate.
- **API endpoints:** workflow `/otp`, browser `/human`, live browser token/state.
- **Status + evidence:** **VERIFIED safety boundary** — tests assert OTP/CAPTCHA remain human gates.
- **Problems:** Real provider/portal challenge behavior not tested; terms may forbid automation even with human input.
- **Next:** Obtain written portal authorization and test only in an allowed sandbox. Effort: decision + 1–3 days.
- **Test yourself:** Try an OTP/CAPTCHA field through fill endpoint; expected response is pause/block, not automatic value.

### D8. Sensitive fields, final review and manual submit

- **What it is:** Prevent high-impact values and final legal submission from being automated.
- **How it works:** Verified-data gateway supplies only provenance-backed values; sensitive fields need approval; final endpoint returns manual instruction and never clicks.
- **Files/functions:** `verified_data_service.py`, `verified_data_repository.py`, `approval_engine.py`, `orchestrator.py:final_submit`.
- **Database tables:** approvals, audit logs, profile/documents, workflow events.
- **API endpoints:** `/v1/approvals`, workflow `/fill`, `/final-approval`, `/submit`.
- **Status + evidence:** **VERIFIED** — final-control and worker integration tests pass.
- **Problems:** Legal declaration semantics vary by portal and are generic.
- **Next:** Add explicit declaration review UI and audit receipt. Effort: 1–2 days.
- **Test yourself:** Call final submit without exact approval; expect `submitted:false` and manual action message.

### D9. Authentication: email/password, Google, Firebase, Supabase, Clerk, Stytch, Descope and phone OTP

- **What it is:** Application identity plus optional external login providers.
- **How it works:** Password hash/JWT/session rotation; OAuth exchange; external token verification; identity mappings; phone OTP challenge/verify.
- **Files/functions:** `auth.py`, `auth_routes.py`, `auth_provider_service.py`.
- **Database tables:** `auth_users`, `revoked_tokens`, `auth_action_tokens`, `auth_identity_mappings`, `auth_provider_registry`, `auth_otp_challenges`.
- **API endpoints:** `/v1/auth/signup`, login, refresh, dev-token, logout, verification, password reset, providers, OAuth start/callback/exchange, provider token, OTP request/verify, link/linked.
- **Status + evidence:** Email/password/session rotation **VERIFIED** by tests; Google/external providers/phone OTP **IMPLEMENTED-UNTESTED**.
- **Problems:** External callback secrets, redirect allowlists and live provider behavior require staging. Legacy header is unsafe in production if enabled.
- **Next:** Configure one provider at a time, test account linking and revocation. Effort: 2–5 days/provider.
- **Test yourself:** Use synthetic staging account; verify refresh rotation revokes old token and wrong provider token is rejected.

### D10. Sessions and refresh tokens

- **What it is:** Short access tokens plus revocable refresh sessions.
- **How it works:** `issue_session`, `rotate_session`, `revoke_session`; revoked-token table and expiry checks.
- **Database tables:** `auth_sessions`, `revoked_tokens`.
- **Status + evidence:** **VERIFIED** — `test_real_authentication.py` and auth tests pass.
- **Problems:** Secure cookie/HTTPS production settings are configuration decisions, not local proof.
- **Next:** Security review of browser storage/cookie strategy. Effort: 1–2 days.
- **How to test:** Login, refresh once, reuse old refresh token; old token must fail.

### D11. Durable tasks and Redis worker

- **What it is:** Queue-backed resumable work with retries and dead-letter behavior.
- **How it works:** Tasks transition through allowed states; worker claims lease, checkpoints steps, retries transient failures and dead-letters after limit.
- **Files/functions:** `task_service.py`, `task_worker.py`, `task_routes.py`, `orchestrator.py`.
- **Database tables:** `form_tasks`, `task_steps`, `task_locks`, workflow events; Redis queue.
- **API endpoints:** `/v1/tasks`, `/{task_id}`, claim, transition, enqueue, human-resume, heartbeat, lock delete.
- **Status + evidence:** State/checkpoint logic **VERIFIED**; real Redis worker **IMPLEMENTED-UNTESTED**.
- **Problems:** Redis unavailable in audit environment; duplicate delivery and restart need staging test.
- **Next:** Run Redis chaos test: kill worker during lease and confirm recovery. Effort: 1–2 days.
- **How to test:** Start Redis, enqueue synthetic task, kill worker, restart, verify checkpoint and dead-letter.

### D12. Verified data and provenance

- **What it is:** Prevent invented or cross-user personal data.
- **How it works:** Requested fields are fetched on demand; provenance/ownership/conflict checks return `VERIFIED`, `NOT_FOUND` or `CONFLICT`; no fallback invention.
- **Files/functions:** `verified_data_service.py`, `verified_data_repository.py`, `form_execution.py`.
- **Tables:** profiles, addresses, education, documents and audit/workflow tables.
- **Status + evidence:** **VERIFIED** — verified-data and gateway tests pass.
- **Problems:** Human correctness of uploaded source documents is not proven by hash/provenance.
- **Next:** Add source-document review and correction trail. Effort: 2–3 days.
- **How to test:** Request another user’s field or conflicting value; expect denial/pause.

### D13. Website registry and health worker

- **What it is:** Admin registry of approved websites with health status and enable/disable controls.
- **How it works:** HTTPS/domain allowlist/verified flag checks; health worker records failures and can disable unhealthy sites.
- **Files/functions:** `website_health_service.py`, `website_health_worker.py`, admin routes.
- **Tables:** `website_registry`, `website_health_history`.
- **Status + evidence:** Registry migrations and service **VERIFIED at unit/control level**; scheduled real worker **IMPLEMENTED-UNTESTED**.
- **Problems:** Seeded portals are registry metadata, not proof of automation permission or selectors.
- **Next:** Portal-by-portal owner approval and contract fixture. Effort: 3–5 days/portal.
- **How to test:** Register synthetic HTTPS site, check it, simulate failures, verify health history and disable behavior.

### D14. AI provider gateway

- **What it is:** Capability-aware provider routing with bounded failover and usage policy.
- **How it works:** `MultiAIProviderAdapter` loads encrypted credentials, checks policy/health/quota and dispatches direct/OpenAI-compatible/gateway adapters.
- **Catalog:** Gemini, Groq, OpenAI, Anthropic, DeepSeek, xAI/Grok, OpenRouter, Hugging Face, Mistral, Cerebras, NVIDIA NIM, Together AI, Fireworks AI, Cohere, Perplexity, Qwen/Alibaba, DeepInfra, Novita, SiliconFlow, Hyperbolic, Z.ai/GLM, Moonshot/Kimi, MiniMax, SambaNova and OmniRoute gateway. `base64_ai` and Azure/AWS document routes also appear in configured routing aliases; catalog/wiring must be checked before enabling.
- **Files/functions:** `ai_provider_adapter.py`, admin provider routes, credential crypto, usage ledger.
- **Tables:** `ai_provider_registry`, `ai_model_registry`, `ai_provider_health`, `ai_provider_policy`, `ai_usage_ledger`.
- **API endpoints:** `/v1/admin/providers`, provider update/credential/test/model-discover, provider policy routes.
- **Status + evidence:** Adapter/catalog **IMPLEMENTED-UNTESTED**; no live provider request was made.
- **Problems:** “Catalog entry” is not “working credential”; data residency and model output quality need decisions.
- **Next:** Enable one provider with synthetic prompt and budget alerts. Effort: 1–2 days/provider family.
- **How to test:** Configure staging credential, send non-personal prompt, inspect latency/usage/audit/failover.

### D15. Storage providers

- **What it is:** Local or private S3-compatible storage with priority/failover.
- **How it works:** `StorageServiceAdapter` reads enabled nodes, decrypts credentials at client creation, uploads/downloads/deletes and creates signed URLs.
- **Catalog:** S3-compatible endpoint, Oracle Object Storage, Cloudflare R2, Backblaze B2, Firebase Storage, Supabase Storage records are supported by registry metadata; live connectivity is untested.
- **Tables:** `multi_cloud_storage_nodes`, `storage_provider_registry`, documents.
- **Status + evidence:** **IMPLEMENTED-UNTESTED** — adapter and encrypted credential paths exist; no real bucket used.
- **Problems:** Failover consistency and deletion across replicas need proof.
- **Next:** Staging bucket upload/download/delete/restore drill. Effort: 2–3 days.
- **How to test:** Use synthetic file, verify private ACL, signed URL expiry and deletion.

### D16. Payments, wallet, credits, coupons and referrals

- **What it is:** Razorpay order/payment lifecycle, credit ledger, coupons/referral rewards and refunds.
- **How it works:** Order creation, signature verification, webhook idempotency, paid/failed state, wallet credit, reconciliation, refund request and admin preview-confirm path.
- **Files/functions:** `razorpay_gateway.py`, `payment_service.py`, `payment_webhook_service.py`, `coupon_service.py`, payment/admin routes.
- **Tables:** `transactions`, `wallets`, `wallet_ledger`, `coupons`, `coupon_redemptions`, `referrals`, `payment_refunds`, `payment_reconciliation`, provider keys.
- **API endpoints:** `/v1/payments/orders`, `/verify`, `/retry`, `/razorpay/webhook`; admin refund/reconcile routes.
- **Status + evidence:** Code/state logic **IMPLEMENTED-UNTESTED**; no Razorpay credentials, live order, webhook or refund run.
- **Problems:** Financial/legal impact; refund and reconciliation need staging/sandbox proof. No automatic payment should be enabled without explicit approval.
- **Next:** Razorpay test-mode order → verify → webhook replay → refund → reconciliation. Effort: 2–4 days.
- **How to test:** Use provider sandbox only; verify duplicate webhook does not double-credit.

### D17. Notifications: email/SMS

- **What it is:** Transactional email and provider-backed phone OTP.
- **How it works:** Brevo REST sender handles welcome, OTP alert, verification, reset and receipt; phone OTP uses configured provider URLs.
- **Status + evidence:** **IMPLEMENTED-UNTESTED** — `notification_service.py` and auth provider code exist; no external send.
- **Problems:** `.env.example` disables email delivery; SMS vendor is not fixed; message privacy/retention not reviewed.
- **Next:** Configure sandbox sender and test templates/rate limits. Effort: 1–2 days.
- **How to test:** Use test mailbox/number, never real user documents or OTPs.

### D18. Admin panel and Admin AI assistant

- **What it is:** Super Admin control plane for users, tasks, browser sessions, payments, storage, websites, providers, branding and marketing.
- **Screens/data classification:** `AdminDashboard.tsx` is live API-wired for summary/users/AI usage/tasks/sessions/audit/payments/storage/health/provider policy/websites/providers/storage/auth/worker/branding/marketing. Some Stitch commercial screens are presentation/preview surfaces. Admin AI `/assistant/query` provides operational summaries; `/assistant/preview` and `/confirm` enforce preview-confirm for consequential actions.
- **Status + evidence:** **IMPLEMENTED-UNTESTED** — routes and frontend wiring inspected; live admin staging session not run.
- **Problems:** Must verify server-side admin role, audit trail, idempotency and no masked-secret leakage.
- **Next:** Staging admin acceptance test with least-privilege roles. Effort: 2–4 days.
- **How to test:** Login as normal user and admin; confirm every admin route rejects normal user; verify credentials are masked.

### D19. Branding and marketing

- **What it is:** Durable branding settings, marketing insights and draft-only campaigns.
- **Files:** `admin_routes.py` branding/marketing endpoints; `AdminDashboard.tsx` screens.
- **Status:** **IMPLEMENTED-UNTESTED** — database/API code exists; no production data source validated.
- **Problems:** Marketing drafts must not auto-publish; metrics must not be fabricated.
- **Next:** Connect approved analytics source and keep publish human-confirmed. Effort: 2–3 days.

### D20. Deployment, Docker, Nginx and backups

- **What it is:** Production packaging and operational helpers.
- **Files:** `Dockerfile.api`, `Dockerfile.worker`, `Dockerfile.frontend`, `docker-compose.production.yml`, `deploy/nginx.conf`, `deploy/backup_restore.sh`, `docs/DEPLOYMENT.md`.
- **Status:** **IMPLEMENTED-UNTESTED** — Docker was unavailable; images, TLS and restore were not executed.
- **Problems:** Default development settings are unsafe for production; backup encryption/restore needs an actual drill.
- **Next:** Build/push staging images, run migrations, TLS, health checks and restore. Effort: 2–5 days.
- **How to test:** `docker compose -f docker-compose.production.yml config`, build images, run smoke test, restore to an isolated DB.

### D21. CI workflows

- **What it is:** Automated backend, frontend, demo-browser and production validation checks.
- **Files:** `.github/workflows/backend-tests.yml`, `frontend-build.yml`, target-preserved `demo-browser-e2e.yml`, `production-validation.yml`.
- **Status:** **PARTIAL** — local checks passed; CI runner execution was not performed in this audit.
- **Problems:** Demo workflow uses self-hosted Windows runner; availability/configuration is external.
- **Next:** Open PR checks and fix runner-specific gaps. Effort: 1 day.

## E. Important file inventory

- `backend/app/main.py` — FastAPI app, health/readiness, middleware and route mounting.
- `backend/app/routes.py` — profile, address and document endpoints.
- `backend/app/auth_routes.py` — application and provider authentication endpoints.
- `backend/app/auth_provider_service.py` — OAuth/token/OTP provider logic.
- `backend/app/browser_agent.py` — Playwright safety, inspect/fill/session lifecycle.
- `backend/app/browser_routes.py` — browser session API.
- `backend/app/live_browser_routes.py` — live token and agent-state API.
- `backend/app/form_mapping.py` — deterministic control-to-field mapping.
- `backend/app/form_execution.py` — verified proposal and safe fill pipeline.
- `backend/app/orchestrator.py` — workflow lifecycle and manual final-submit gate.
- `backend/app/research.py` — official research provider/facts.
- `backend/app/universal_research.py` — supplied URL research path.
- `backend/app/document_intelligence.py` — PDF/text/OCR extraction.
- `backend/app/storage_service.py` — multi-node private storage adapter.
- `backend/app/verified_data_service.py` and `verified_data_repository.py` — provenance/ownership gateway.
- `backend/app/task_service.py`, `task_worker.py`, `task_routes.py` — durable queue runtime.
- `backend/app/ai_provider_adapter.py` — provider catalog, routing, policy and failover.
- `backend/app/payment_service.py`, `razorpay_gateway.py`, `payment_webhook_service.py` — payment lifecycle.
- `backend/app/notification_service.py` — Brevo transactional email.
- `backend/app/admin_routes.py` — Super Admin live control-plane APIs.
- `backend/app/db_models.py`, `entities.py`, `models.py` — ORM/API data structures.
- `backend/migrations/versions/0001...0018` — schema history; final head is `0018_platform_control_plane`.
- `frontend/src/main.jsx` — frontend bootstrap, auth/session/API wiring.
- `frontend/src/admin/AdminDashboard.tsx` — admin live-data dashboard.
- `frontend/src/LiveBrowserCanvas.tsx` — live browser surface.
- `frontend/src/stitch/*` — product/workspace/gateway/vault screens.
- `demo-target-site/public/*` — safe local demo form.
- `backend/tests/*` — backend safety, auth, worker, migration and browser tests.
- `deploy/*`, Dockerfiles and Compose — deployment assets.
- `docs/IMPORT_NOTES.md` — source/target traceability.

## F. Database and migration chain

**Chain:** `0001_profile_vault` → `0002_phase1a_commercial_schema` plus `0002_phase5a_provenance` → `0003_phase1a_coupon_referral` → `0004_phase1b_rls_policies` → `0005_phase1b_multi_cloud_storage` → `0006_phase3a_admin_config` → `0007_merge_phase5a_commercial` → `0008_auth_users` → `0009_revoked_tokens` → `0010_website_registry` → `0011_auth_action_tokens` → `0012_durable_task_runtime` → `0013_ai_usage_ledger` → `0014_registry_production` → `0015_final_production_controls` → `0016_unified_provider_control_plane` → `0017_real_authentication` → `0018_platform_control_plane`.

**Important tables:** `auth_users` identity/status/role; `auth_sessions` refresh sessions; `revoked_tokens`; `auth_action_tokens`; `auth_identity_mappings`; `auth_otp_challenges`; `profiles`; `addresses`; `education`; `documents`; `audit_logs`; `form_tasks`; `task_steps`; `browser_sessions`; `browser_session_events`; `workflow_events`; `task_locks`; `website_registry`; `website_health_history`; `ai_provider_registry`; `ai_model_registry`; `ai_provider_health`; `ai_provider_policy`; `ai_usage_ledger`; `storage_provider_registry`; `multi_cloud_storage_nodes`; `auth_provider_registry`; `transactions`; `wallets`; `wallet_ledger`; `coupons`; `coupon_redemptions`; `referrals`; `payment_refunds`; `payment_reconciliation`; branding/marketing/admin configuration tables.

**Evidence:** `alembic heads` returned exactly `0018_platform_control_plane`; `alembic check` returned “No new upgrade operations detected.” **Risk:** a real PostgreSQL upgrade/rollback was not run; SQLite compatibility does not prove PostgreSQL behavior.

## G. API reference

The repository contains 122 route decorators. Main groups are listed below; exact method/path/auth enforcement is in the route files named.

- System: `GET /health`, `GET /ready` — public health/readiness; production readiness depends on DB/Redis.
- Auth: `POST /v1/auth/signup`, `/login`, `/refresh`, `/dev-token`, `/logout`, `/verification/request`, `/verification/confirm`, `/password-reset/request`, `/password-reset/confirm`, `/oauth/{provider}/start`, `/oauth/{provider}/callback`, `/oauth/exchange`, `/provider/token`, `/otp/request`, `/otp/verify`, `/link`; `GET /providers`, `/linked`.
- User data: `GET/PUT /v1/profile`; `GET/POST/DELETE /v1/addresses`; `GET/POST /v1/education`; document upload/list/read/extract/extraction/download/delete.
- Research/knowledge: `POST /v1/research/research`; `POST /v1/knowledge/reindex`, `/search`, `/context`.
- Workflows: `POST /v1/workflows`; `GET /v1/workflows/{id}`; `POST /url`, `/confirm`, `/open`, `/human`, `/otp`, `/plan`, `/fill`, `/final-approval`, `/submit`; screenshot GET.
- Browser: session create, navigate, inspect, screenshot, human and delete under `/v1/browser/sessions`.
- Live browser: live token and agent-state under `/v1/live-browser/sessions/{id}`.
- Mapping/execution: `POST /v1/form-mapping/map`, `/fill`; `POST /v1/form-execution/plan`, `/approvals`, `/fill`.
- Approvals: `POST/GET /v1/approvals`, `POST /v1/approvals/{id}/approve`.
- Tasks: create/list/get, claim, transition, enqueue, human-resume, heartbeat, lock delete under `/v1/tasks`.
- Payments: `POST /v1/payments/orders`, `/verify`, `/retry`, `/razorpay/webhook`.
- Admin: pricing, coupons, summary, users, AI usage, tasks, browser sessions, audit logs, payments/reconcile, storage, health, provider policy, websites, providers, storage providers, auth providers, credentials, provider tests/model discovery, workers, branding, marketing, assistant query/preview/confirm.

For a complete endpoint inventory, run: `grep -RInE '@router\\.(get|post|put|patch|delete)|@app\\.(get|post|put|patch|delete)' backend/app`.

## H. Environment variables

All settings use prefix `FORMWISE_` and are read by `backend/app/config.py`. Core variables: `ENVIRONMENT`, `DATABASE_URL`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `STORAGE_ROOT`, `STORAGE_PROVIDER`, `STORAGE_S3_ENDPOINT_URL`, `STORAGE_S3_BUCKET`, `STORAGE_S3_ACCESS_KEY_ID`, `STORAGE_S3_SECRET_ACCESS_KEY`, `STORAGE_S3_REGION`, `STORAGE_S3_SERVER_SIDE_ENCRYPTION`, `STORAGE_S3_KMS_KEY_ID`, `STORAGE_SIGNED_URL_TTL_SECONDS`, `MAX_UPLOAD_SIZE_BYTES`, `BROWSER_HEADLESS`, `BROWSER_TIMEOUT_MS`, `BROWSER_NAVIGATION_TIMEOUT_MS`, `BROWSER_MAX_SESSIONS_PER_USER`, `BROWSER_MAX_PAGES_PER_SESSION`, `BROWSER_SCREENSHOT_ENABLED`, `BROWSER_BLOCK_PRIVATE_NETWORKS`, `BROWSER_ALLOW_LOCAL_DEMO_TARGET`, `BROWSER_DEMO_TARGET_PORT`, `BROWSER_USE_ENABLED`, `BROWSER_USE_MODEL`, `JWT_SECRET`, `JWT_ALGORITHM`, `ALLOW_LEGACY_USER_HEADER`, `SECURE_COOKIES`, `CSRF_ENABLED`, `SERPER_API_KEY`, `SERPER_URL`, `RESEARCH_TIMEOUT_SECONDS`, `CORS_ORIGINS`, `FRONTEND_BASE_URL`, `EMAIL_PROVIDER`, `EMAIL_DELIVERY_ENABLED`, `REDIS_URL`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_TLS`, `REDIS_CA_FILE`, `REDIS_SOCKET_TIMEOUT_SECONDS`, `REDIS_POOL_MAX_CONNECTIONS`, `TASK_QUEUE_NAME`, `TASK_DEAD_LETTER_QUEUE_NAME`, `TASK_WORKER_LEASE_SECONDS`, `TASK_WORKER_HEARTBEAT_SECONDS`, `TASK_WORKER_CONCURRENCY`, `TASK_WORKER_SHUTDOWN_SECONDS`, `TASK_MAX_RETRIES`, `TASK_RETRY_BASE_SECONDS`, `TASK_RETRY_MAX_SECONDS`, `API_REQUEST_SIZE_LIMIT_BYTES`, `RATE_LIMIT_PER_MINUTE`, `LIVE_BROWSER_ENABLED`, `LIVE_INPUT_ENABLED`, `LIVE_FRAME_INTERVAL_MS`, `LIVE_POLICY_CHECK_INTERVAL_MS`, `LIVE_JPEG_QUALITY`, `LIVE_TOKEN_TTL_SECONDS`, `LIVE_MAX_CONNECTIONS_PER_SESSION`, `LIVE_MAX_MESSAGE_BYTES`, `LIVE_REQUIRE_SECURE_TRANSPORT`, `AI_FAILOVER_BUDGET_SECONDS`, `AI_PROVIDER_TIMEOUT_SECONDS`, `AI_ROUTE_VISION_FORM_READING`, `AI_ROUTE_DOCUMENT_PROCESSING`, `AI_ROUTE_SEMANTIC_ANALYSIS`, `AI_ROUTE_GENERAL`.

Mandatory in production: strong random `JWT_SECRET`, real PostgreSQL `DATABASE_URL`, secure storage/provider credentials via encrypted admin path, Redis URL, HTTPS/WSS origins and provider-specific secrets. Unsafe development defaults: SQLite, `JWT_SECRET=change-me-in-production`, `ALLOW_LEGACY_USER_HEADER=true`, `SECURE_COOKIES=false`, local demo enabled, `LIVE_REQUIRE_SECURE_TRANSPORT=false`, localhost CORS and email delivery disabled. Never put real values in source control.

## I. What the system asks the user

Current flow asks for request/target, confirmation of research, document upload/selection, explicit OCR action, URL/application readiness, OTP when needed, CAPTCHA/legal human action, sensitive-field approval and final review/manual submit.

It should additionally ask, before a real portal: category, domicile/state, income range and certificate, address proof type, photo/signature pixel/size requirements, disability/ex-serviceman status, declarations, fee/payment consent, data retention period, deletion consent, and whether the user authorizes the chosen portal automation. These are not universally collected by the current generic flow; portal-specific forms remain the source of truth.

## J. Portals

| Portal | Registry status | What is verified | Real E2E? | Terms/permission |
|---|---|---|---|---|
| SSC (`ssc.gov.in`) | Seeded as official registry record | HTTPS/domain metadata and required human gates; not selectors | **NOT STARTED** | Must review SSC terms/robots/authorization before automation |
| UPSC (`upsc.gov.in`) | Seeded registry record | Generic domain metadata only | **NOT STARTED** | Written permission/terms review required |
| NSP (`scholarships.gov.in`) | Seeded registry record | Generic scholarship/application metadata only | **NOT STARTED** | Review NSP policy and authorization |
| NTA (`exams.nta.ac.in`) | Seeded registry record | Generic application/payment/human-gate metadata | **NOT STARTED** | Payment and terms risk is high; written permission required |
| Local demo | Verified test target | Synthetic controls and safety behavior | **VERIFIED** | Local-only; no real submission |

The registry seed is not evidence that Formwise may automate any portal. Do not enable a real portal until legal/terms review, owner authorization and portal-specific contract tests are complete.

## K. Testing and coverage

**Baseline commit results:** backend with `PYTHONPATH=.` failed during collection with 11 missing-module errors (including `app.verified_data_repository`); frontend tests passed 4/4; frontend build failed with two Vite invalid Unicode/transform errors; Alembic had one `0007_merge_phase5a_commercial` head and `alembic check` passed. A bare baseline command without `PYTHONPATH` also showed the documented import-path problem.

**Final branch results:** `python3 -m compileall -q app tests` passed from backend; `pytest -q` from backend and root passed **152 tests** with **154 warnings**; frontend tests passed **4/4**; Vite build passed; `alembic heads` returned exactly `0018_platform_control_plane`; `alembic check` passed; `git diff --check` passed; secret scan found no obvious key/private-key literals. `npm audit` exited non-zero with **4 vulnerabilities: 2 moderate, 2 high, 0 critical**.

The self-contained demo fixture is in `backend/tests/test_demo_browser.py`; root `pytest.ini` sets `backend` on the import path. Tests do not cover real PostgreSQL/Redis/Docker/Tesseract, live external providers, portal terms, current notices, production TLS, real documents, real payments or restore operations.

## L. Security, privacy and DPDP gaps

Documents are addressed through private storage metadata and storage adapters; S3 server-side encryption settings and encrypted provider credentials are supported. Local storage is not equivalent to production encryption at rest. OCR output and extracted personal values need retention/deletion policy. Access uses user ownership checks and audit events. Refresh sessions are revocable. Admin secrets are masked/encrypted in the control plane.

India DPDP Act 2023-aligned gaps to close: documented notice/consent purpose, consent withdrawal, deletion workflow, retention schedule, data principal request handling, processor/vendor contracts, breach response, minimisation, child-data handling where applicable, India/region transfer decision, and evidence of security safeguards. This report does not provide legal advice.

Potential autonomous-action review: browser inspection/fill is constrained; final Submit is blocked; CAPTCHA/OTP are human; payment requires configured provider/admin path. Still review live-browser input, admin assistant confirmation, provider credentials and refund paths before production.

## M. Legal and terms risks

Government portals can prohibit scraping, automation, bots, reverse engineering or commercial use. Even human-in-the-loop automation may violate terms. CAPTCHA itself is an anti-automation signal. Payment providers impose webhook/signature/refund rules. AI providers may retain prompts or process data outside India. Storage/email/SMS providers are processors. Obtain written permission, publish privacy/retention terms and use synthetic data for testing. No portal automation should be enabled based solely on registry seeds.

## N. Known bugs, warnings, conflicts and tech debt

| Severity | Finding | Evidence | Fix |
|---|---|---|---|
| Critical | Real portal permission and production privacy proof absent | No portal E2E; registry is generic | Do not release real portal; obtain authorization and DPIA/terms review |
| High | PostgreSQL/Redis/Docker/Tesseract/provider integrations untested | Tools/services unavailable in audit environment | Build staging and run integration matrix |
| High | Unsafe dev defaults if copied to production | `config.py`, `.env.example` | Strong secret manager, HTTPS/WSS, disable legacy header/demo |
| High | 4 frontend dependency vulnerabilities | `npm audit`: 2 moderate, 2 high | Review/update lockfile and rerun tests |
| High | Document retention/deletion/replica deletion not operationally proven | storage/document services | Add retention job and deletion/restore evidence |
| Medium | `datetime.utcnow()` deprecation warnings | 154 pytest warnings include datetime warnings | Replace with timezone-aware UTC |
| Medium | Playwright async cleanup warnings | test output includes event-loop/resource warnings | Close browser contexts/fixtures deterministically |
| Medium | Generic portal selectors and requirements | no real portal contract tests | Build per-portal fixtures only after permission |
| Low | Marketing/provider catalog can look more complete than live wiring | catalog entries without credentials | Label UI provider readiness explicitly |

No CRITICAL safety violation was found in the inspected code: no CAPTCHA solver/bypass, OTP auto-fill, automatic final click or automatic payment was observed. This is a code audit, not a legal certification.

## O. Merge impact

Imported from `fromaaply`: auth/provider control plane, durable tasks/Redis worker, verified-data repository, website registry/health worker, AI usage/provider policy, production migrations `0008–0018`, Docker/Compose/Nginx/backup, live admin wiring and lockfiles.

Kept from target: stronger demo-browser workflow, existing safety gates, final-submit boundary, target tests and target-specific UI/workflow pieces. No target-only tracked runtime file was deleted. Skipped source artifacts: `AUDIT_REPORT.md`, generated `frontend/dist/**`, older weaker demo workflow, caches/databases/private storage/node_modules/env files. Added merge fixes: root `pytest.ini`, self-starting demo fixture, `docs/IMPORT_NOTES.md`.

Source/target tracked-file comparison found no non-generated source file missing from the branch after merge.

## P. Deployment plan

**Local:** install Python requirements; install frontend and demo lockfiles; install Playwright Chromium; use SQLite/local private storage; run backend and Vite; run `pytest -q` from root; use only local demo and synthetic documents.

**Staging:** provision PostgreSQL, Redis, private S3-compatible bucket, secret manager, HTTPS domain and isolated provider sandbox accounts. Set strong env values; disable legacy header/local demo; run Alembic upgrade; start API, worker, frontend and Nginx; run health/readiness, auth, upload/OCR, browser safety, queue recovery, provider and payment sandbox tests.

**Production:** obtain portal authorization; configure backups and encrypted restore; deploy immutable image; migrate after snapshot; verify `/health` and `/ready`; smoke test with synthetic/consented account; enable one portal/provider at a time; monitor audit, queue, storage, health and cost; retain rollback image.

Never executed in this audit: Docker image build, PostgreSQL migration, Redis worker, Nginx TLS, real backup/restore, external provider calls, real portal workflow, Tesseract OCR and real payment.

## Q. What the owner must provide

**Mandatory before real release:** production domain/DNS and TLS; PostgreSQL; Redis; secret manager; private storage; email sender; selected auth provider; monitoring/logging; backup destination; written portal authorization/terms decision; data retention/privacy policy; incident contact; staging test accounts.

**Optional:** Serper key; AI provider key(s); phone OTP/SMS provider; Brevo; Razorpay; S3 failover nodes; analytics provider; WhatsApp/SMS. Get each credential from its official provider dashboard and inject through the secret manager/admin encrypted credential flow, never commit it.

## R. Prioritized plan

**MUST before release:**
1. Freeze scope to local demo or one authorized portal (owner decision, 0.5–1 day).
2. Provision PostgreSQL/Redis/staging secrets and run migration/worker tests (2–4 days).
3. Fix dependency vulnerabilities and datetime/Playwright warnings (1–3 days).
4. Implement retention/deletion/restore evidence and privacy notice/consent (3–5 days plus legal review).
5. Run auth, storage, OCR, browser, live gate and admin authorization acceptance tests (3–5 days).
6. Complete portal terms/authorization and per-portal contract fixture (3–7 days).

**SHOULD:** one real email provider sandbox, one AI provider, payment sandbox only if business requires it, monitoring/cost limits, accessibility/mobile review, rate-limit/load test.

**LATER:** multi-portal selectors, SMS alternatives, AI failover expansion, marketing analytics, storage multi-cloud failover, referral/coupon optimisation.

## S. Questions for the owner

1. Which single portal is the first authorized launch target?
2. Do you have written permission/terms clearance for automation?
3. Is payment in v1, or should it remain disabled?
4. Which auth provider should be production default?
5. Which AI provider may process document-derived data and in which region?
6. What is the retention period for documents, OCR output, screenshots and audit logs?
7. Should users be able to self-delete all data immediately, and how long must financial records remain?
8. Which cloud, PostgreSQL, Redis, object storage and domain will be used?
9. Who is the security/privacy and refund incident owner?
10. What is the launch allowlist and support process?

## T. Glossary — simple Hinglish

- **API:** frontend aur backend ke beech message ka raasta.
- **Alembic migration:** database structure ko version-wise update karne wali file.
- **JWT:** signed login token.
- **Refresh token:** naya short-lived access token lene ka longer-lived token.
- **Redis:** fast queue/cache service.
- **Worker:** background mein task chalane wala process.
- **Lease:** worker ko temporary task ownership.
- **Dead letter:** baar-baar fail task ki holding queue.
- **OCR:** image/PDF se text read karna.
- **Provenance:** value kahan se aayi uska evidence.
- **Fail closed:** doubt ho to action rok dena.
- **Signed URL:** limited-time private download link.
- **Webhook:** provider ka server-to-server event message.
- **Idempotency:** same event repeat hone par duplicate effect na hona.
- **CORS/CSRF:** browser security controls.
- **WSS:** secure WebSocket.
- **CI:** GitHub par automatic tests/build.
- **DPIA:** personal-data risk assessment.
- **E2E:** user journey ka start-to-finish test.

## U. Final verdict and next 10 actions

**Ready for real unrestricted users? NO.** The branch is safe to review and test with synthetic/local data. It is not yet proven safe/legal/operational for unrestricted government-portal users.

1. Owner selects one launch portal or local-only scope.
2. Owner records terms/authorization and privacy/retention decision.
3. Provision staging PostgreSQL, Redis, secret manager and HTTPS.
4. Set production-safe configuration and disable legacy/demo shortcuts.
5. Run Alembic upgrade and backup/restore drill.
6. Run 152-test suite plus Redis, storage, OCR and live-browser staging tests.
7. Fix four frontend audit vulnerabilities and warning debt.
8. Configure one auth provider, one email provider and optionally one AI provider; test with synthetic data.
9. Run portal-specific human-supervised contract test; keep final Submit manual.
10. Review this PR, then owner—not agent—merges PR #26 to `main` after all MUST items pass.

**Final labels:** core safety workflow `VERIFIED`; external integrations `IMPLEMENTED-UNTESTED`; real portal support `NOT STARTED`; generated provider catalog `IMPLEMENTED-UNTESTED`; production release `NOT READY`.
