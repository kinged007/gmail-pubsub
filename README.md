# gmail-pubsub

[![CI](https://github.com/kinged007/gmail-pubsub/actions/workflows/ci.yml/badge.svg)](https://github.com/kinged007/gmail-pubsub/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

Autonomous Gmail → Pub/Sub → Cloud Run pipeline. A FastAPI service receives Gmail push notifications, fetches new messages, and runs pluggable Python logic per email — with automatic watch renewal via Cloud Scheduler.

Built for Cloud Run + Pub/Sub with background-task ACKs, BeautifulSoup body parsing, and an optional SQLAlchemy persistence layer.

## Architecture

```
Gmail ──watch──> Pub/Sub topic ──push──> Cloud Run (FastAPI: /email-notify)
                                              │  BackgroundTasks
                                              ▼
                                    Gmail API history.list → messages.get
                                              │
                                              ▼
                                    app/process_email.py  ──> Telegram / DB / custom
                                              ▲
                                    Cloud Scheduler ──POST /renew-watch──┘ (every 6 days)
```

Full diagram and request flow: [`docs/architecture.md`](./docs/architecture.md).

## Install

Prerequisites: Python 3.11, `uv`, `gcloud` CLI, a GCP project with billing.

```bash
git clone https://github.com/kinged007/gmail-pubsub.git
cd gmail-pubsub
uv sync
# or: pip install -r requirements.txt
```

## Usage

```bash
# 1. Initialise GCP resources (project/APIs, topic+subscription, service account)
uv run init

# 2. Edit your business logic (the only file most users change)
#    app/process_email.py :: process_email(message)

# 3. Test locally with the dummy Gmail payload
uv run test

# 4. Deploy to Cloud Run + wire Pub/Sub push + Scheduler renewal
uv run deploy

# 5. Local dev server
uv run python main.py   # :8080 — /health, /watch-status

# 6. Reset
uv run reset            # local or full wipe of GCP resources
```

Environment: copy `.env.example` to `.env` and set `GMAIL_WATCH_LABELS`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN` etc. Secrets can also come from Secret Manager (`GOOGLE_SERVICE_ACCOUNT_JSON` base64).

### Configuration

Resources are named from the topic you enter at `uv run init`:

| Resource | Pattern | Example |
|---|---|---|
| Topic | `{topic}` | `autochartist-signal` |
| Subscription | `{topic}-sub` | `autochartist-signal-sub` |
| Service account | `{topic}-service-account` | `autochartist-signal-service-account` |
| Cloud Run service | `{topic}` | `autochartist-signal` |

### API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health + DB check |
| `/email-notify` | POST | Pub/Sub push (base64 `historyId`) — enqueues background fetch |
| `/renew-watch` | POST | Renew `users.watch` (called by Scheduler) |
| `/watch-status` | GET | Current watch/profile |
| `/stop-watch` | POST | Stop watch (cleanup/reset) |

Supports personal Gmail (OAuth `GMAIL_OAUTH_TOKEN_JSON`) and Workspace domain-wide delegation — see Authentication section below.

## How it is tested

```bash
pytest -q
pytest --cov=src --cov=app --cov-report=term-missing
ruff check .
mypy src app --ignore-missing-imports
```

18 tests cover email parsing (`get_headers`, `extract_message_body`, `extract_attachments`), date/hash utils, DB manager (sqlite/memory), and FastAPI endpoints (`/health`, `/email-notify` with mocked Gmail). CI runs `pytest + ruff + mypy` on push/PR to `master`.

## Customize email processing

`app/process_email.py::process_email(message)` receives the full Gmail message. Helpers in `src/utils/email_utils.py`:

- `get_headers(message)` — lower-cased header dict
- `extract_message_body(message, html_part, strip_html)` — text/HTML decoding
- `extract_attachments(message)` — list of attachments

```python
headers = get_headers(message)
subject, sender = headers.get("subject", ""), headers.get("from", "")
body = extract_message_body(message, html_part=True, strip_html=True)
if "invoice" in subject.lower():
    handle_invoice(body)
```

## Project structure

```
app/process_email.py   # ← edit this
app/dummy_data.py      # DUMMY_EMAIL_PAYLOAD for uv run test
app/models.py          # SQLAlchemy sample table
src/gmail_handler.py   # history.list / messages.get
src/watch_manager.py   # users.watch / users.stop
src/utils/email_utils.py
src/utils/telegram_utils.py
src/database.py        # optional DB (DATABASE_URL)
scripts/init.py deploy.py test.py
main.py                # FastAPI (fapp), BackgroundTasks
```

## Authentication

- **Personal Gmail**: `uv run init` runs OAuth, stores `GMAIL_CLIENT_SECRET_JSON` + `GMAIL_OAUTH_TOKEN_JSON` (base64) in `.env`.
- **Workspace**: enable domain-wide delegation for the service account, set `WORKSPACE_DOMAIN` and `DELEGATED_USER_EMAIL`.
- **Service account**: `GOOGLE_SERVICE_ACCOUNT_JSON` (base64) or Secret Manager `gmail-service-account`.

## Debugging

```bash
curl https://<cloud-run-url>/health
curl https://<cloud-run-url>/watch-status
gcloud run services logs read <service> --region <region> --limit 50
```

## License

MIT — see [LICENSE](./LICENSE).
