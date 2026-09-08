# Phase 11 Release Checklist

- [ ] Backend test suite passes in CI.
- [ ] Production JWT secret is configured outside source control.
- [ ] `FORMWISE_ALLOW_LEGACY_USER_HEADER=false` in production.
- [ ] Production environment startup security validation succeeds.
- [ ] Database migrations are applied with Alembic.
- [ ] Private storage permissions are restricted to the application service account.
- [ ] Browser runtime has the required Playwright browser installed.
- [ ] Browser private-network blocking remains enabled.
- [ ] CAPTCHA/anti-bot bypass remains prohibited.
- [ ] OTP, payment, legal declarations and final submission remain human-controlled.
- [ ] No personal document or API secret is committed to Git.
- [ ] Audit logs contain no raw personal field values.
- [ ] Backup and restore procedure has been tested.
- [ ] Rate limiting and reverse-proxy HTTPS are enabled at deployment.
- [ ] Site-specific form adapters are reviewed before being enabled.

A green checklist means the code is release-ready for the configured environment; it does not mean every third-party website is automatically supported.
