# Security policy

OAK interacts with trading terminals, local credentials, Telegram, and optional external AI services. Please treat suspected vulnerabilities as sensitive until a fix is available.

## Supported versions

Security fixes target the latest published release and the current `main` branch. Older versions may not receive backports.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability. Use [GitHub private vulnerability reporting](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/security/advisories/new) and include:

- affected version and component;
- minimal reproduction steps;
- expected and observed impact;
- whether credentials, orders, profiles, or user data may be exposed;
- a suggested mitigation, if known.

The maintainer will acknowledge a complete report as soon as practical, validate the impact, and coordinate disclosure after a fix or mitigation is available. Please do not access accounts or data that are not your own.

## Security invariants

- Real trades require direct user confirmation.
- Secrets must not be written to source bundles, logs, or dashboard payloads.
- Profile-scoped workers must not cross account or terminal boundaries.
- Build and backup outputs must exclude runtime credentials by default.
