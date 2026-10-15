# AGENTS.md — gmail-pubsub

## Purpose
Autonomous Cloud Run API that receives Gmail push notifications via Pub/Sub,
fetches new messages, and runs pluggable Python logic in `app/process_email.py`.
See `docs/architecture.md` for the diagram and request flow.

## How to run checks

```bash
# install (uv preferred, pip also works)
uv sync                    # or: pip install -r requirements.txt && pip install ruff mypy pytest pytest-asyncio httpx faker pytest-cov

# tests
pytest -q
pytest --cov=src --cov=app --cov-report=term-missing  # coverage
uv run test             # exercise process_email with dummy payload (app/dummy_data.py)

# lint / typecheck
ruff check .
ruff format --check .
mypy src app --ignore-missing-imports

# local server
uv run python main.py   # :8080, requires GOOGLE_SERVICE_ACCOUNT_JSON or Secret Manager
```

No `npm run check` / `go vet` in this repo; CI runs pytest + ruff + mypy.

## Project conventions

- Python 3.11, FastAPI + Cloud Run. Entrypoint `main.py:fapp`.
- Gmail parsing helpers: `src/utils/email_utils.py`. Business logic stays in `app/process_email.py`.
- DB is optional (`DATABASE_URL`; defaults to disabled). SQLAlchemy models in `app/models.py`.
- Secrets: `GOOGLE_SERVICE_ACCOUNT_JSON` (base64), `GMAIL_OAUTH_TOKEN_JSON`, Secret Manager in prod. Never commit `.env` or `service-account.json`.
- Keep diffs minimal; reuse `src/config.py` and `src/utils/*`.

## Branch and PR workflow

- No direct push to `master`. Open a branch `feat/...` or `chore/...`, push, open PR with `gh pr create`.
- PR checks must pass (`ci` workflow: pytest + ruff + mypy) before merge.

## Permissions and scope

- Read `docs/03-tenantflex.md` in the profile-cleanup workspace for context on TenantFlex: do not publish private TenantFlex code. This repo is standalone — keep it that way.
- Do not add network calls in tests; mock Gmail/Secret Manager.

## Skills

- Use `skill-search` to find relevant skills before coding. Prefer project-local `.pi/skills/*` if present.
