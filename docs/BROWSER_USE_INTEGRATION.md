# Browser Use Integration

Formwise integrates the open-source Browser Use Python library as an optional browser-agent adapter.

Browser Use is MIT licensed. Formwise keeps the existing Playwright browser and approval engine as the safety authority.

## Design

- Browser Use adapter is disabled by default.
- An approved target URL is mandatory.
- CAPTCHA/anti-bot bypass is not exposed by the adapter.
- OTP, payment, legal declarations, and final submission remain human-controlled.
- Existing Formwise provenance, approval, audit, and ownership controls remain authoritative.
- Browser Use is an enhancement for semantic browser navigation, not a replacement for Formwise safety controls.

## Enablement

Set `FORMWISE_BROWSER_USE_ENABLED=true` only after the operator has configured a supported model/API key. The adapter currently uses the configured OpenAI model through Browser Use's `ChatOpenAI` wrapper and defaults to `gpt-5.6-luna`.

The dependency is pinned to the current compatible `browser-use` 0.13.x line. Review upstream releases before upgrading because Browser Use evolves independently from Formwise.

## License

The upstream Browser Use library is MIT licensed. When distributing substantial copied upstream code, retain the upstream copyright and license notice. Formwise currently depends on the package rather than copying its source tree.
