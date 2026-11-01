# Import Notes — fromaaply to formwise-agent

**Target:** `https://github.com/Shailendra76-sk/formwise-agent`  
**Source:** `https://github.com/vivekdubey19854-ux/fromaaply`  
**Source commit:** `1add3c6ec84b859b9d9478801f48607dec7141ae`  
**Target baseline:** `181c8ce6d44f1f2b08e14844e8254b936f5ab70d`  
**Branch:** `merge/zip-import-20261026`  
**PR:** `https://github.com/Shailendra76-sk/formwise-agent/pull/26`

## Imported

The branch imports the source repository's useful production control-plane work: authentication/provider adapters, durable tasks and Redis worker code, verified-data repository, website registry and health worker, AI usage/provider controls, migrations `0008` through `0018`, production Dockerfiles/Compose/Nginx/backup assets, production validation workflow, frontend and demo lockfiles, and live-data admin/frontend wiring.

## Preserved from target

The target repository's stronger demo-browser GitHub Actions workflow was retained. Existing browser safety, human OTP/CAPTCHA gates, sensitive-field approval flow, and manual final Submit boundary were retained. No target-only tracked source file was deleted.

## Skipped

- `AUDIT_REPORT.md`: historical audit artifact, not runtime code.
- `frontend/dist/**`: generated build output; CI/build should produce it.
- Source repository's older/shorter `demo-browser-e2e.yml`: target workflow explicitly installs and starts the demo target and was stronger.
- Working-copy generated PDF/text reports, caches, databases, private storage, `node_modules`, `.env` files and other runtime artifacts: not tracked/imported.

## Additional merge fixes

- `backend/tests/test_demo_browser.py` now starts a self-contained static local demo HTTP server fixture; plain pytest no longer depends on a manually running Node server.
- Root `pytest.ini` sets `backend` on the Python path and points pytest at `backend/tests`, so the documented `pytest -q` command works from the repository root or backend directory.

## Safety review

No imported code is intended to solve/bypass CAPTCHA, auto-fill OTP, auto-click final Submit/Confirm, make payment without explicit user approval, or fill sensitive fields outside the approval engine. These boundaries remain release gates and must be manually reviewed before merging the PR.
