# Security

Scoped appropriately for a portfolio/demonstration project, not an institution handling real
client capital. What's in scope is implemented properly; what's out of scope is named explicitly
rather than half-implemented or silently ignored.

## In scope, implemented

- **No hardcoded credentials anywhere in source.** All configuration (`config.py`) is loaded via
  `pydantic-settings` from environment variables / `.env`. `.env` is gitignored and has never been
  committed (verified: `git log --all --full-history -- .env` returns nothing).
- **`.env.example`** documents every required/optional variable with placeholder values.
- **API-key authentication on all write endpoints** (`X-API-Key` header, checked via a FastAPI
  dependency, `api/deps.py::require_api_key`). Read endpoints are open.
- **Pydantic input validation** on every API request body -- required for the API to function
  correctly in the first place, so this is "free" defense-in-depth, not bolted on.
- **Parameterised queries only.** All DB access goes through SQLAlchemy's ORM/query builder; no
  raw string-formatted SQL anywhere in the codebase.
- **Dependency vulnerability scanning:** `pip-audit` run as part of `.github/workflows/ci.yml` on
  every push (also run manually during development -- see the Phase 16 commit history; the one
  flagged package, `setuptools`, was upgraded and the scan is now clean).
- **Long-only enforcement at the schema level:** `PositionIn.quantity` has `gt=0` in the Pydantic
  schema, not just a convention.

## Explicitly out of scope (named, not ignored)

- **Multi-user auth / RBAC.** A single shared API key gates writes; there is no per-user identity,
  session, or role model. A real institution would need this; it is a meaningful separate project,
  not a 30-minute addition.
- **Encryption at rest / TLS termination.** Left to the deployment environment (e.g. a reverse
  proxy terminating TLS in front of the container, and the hosting provider's disk encryption) --
  not configured inside this application.
- **Rate limiting.** Not implemented at the application layer.
- **A real audit-logging compliance regime** (tamper-evident logs, retention policy, SOC2-style
  controls). The `risk_runs`/`model_configs`/`data_snapshot_hash` schema provides a *reproducibility*
  audit trail (see `docs/QUANTITATIVE_METHODOLOGY.md` Section 9), which is a different property from
  a compliance audit log.

## Reporting a concern

This is a portfolio/demonstration project; there is no formal security disclosure process. If
reviewing this code for a real deployment, treat the "explicitly out of scope" list above as the
starting checklist of what would need to be added first.
