# Formwise Backend

Phase 2 implements the profile and private document-vault foundation used by the future form-filling agent.

## Included

- FastAPI API foundation and health endpoint
- User profile CRUD boundary
- Address and education storage boundaries
- Private document upload, metadata, download, and soft-delete
- Per-user ownership checks on every protected resource query
- Filename, MIME-type/extension, and upload-size validation
- SHA-256 integrity fingerprint for every uploaded document
- Private filesystem storage with path-traversal protection and no public URLs
- Audit records for profile/document/address/education actions
- Alembic migration for the complete Phase 2 schema
- Unit tests for upload/storage security and integration tests for profile isolation and document IDOR protection

## Run locally

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS
alembic upgrade head
uvicorn app.main:app --reload
```

Health check: `GET /health`

Protected endpoints currently use the temporary `X-User-ID` identity adapter. This is intentionally not production authentication. A verified session/JWT adapter must replace it before real users or sensitive production data are enabled.

## Tests

```bash
cd backend
pytest -q
```

## Phase 2 intentionally excludes

OCR, embeddings, LLM reasoning, Playwright browser automation, form detection/mapping, OTP/CAPTCHA handling, payments, legal declarations, and final form submission. Those belong to later phases and must not be implemented by bypassing website security controls.
