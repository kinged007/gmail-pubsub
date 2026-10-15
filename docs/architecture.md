# Architecture

```
Gmail ──watch──> Pub/Sub topic ──push──> Cloud Run (FastAPI)
                                              │
                                 ┌────────────┼────────────┐
                                 │            │            │
                           /health   /email-notify  /renew-watch
                                 │            │       ▲
                                 │      Gmail API     │  Cloud Scheduler
                                 │      history.list  │  (every 6 days)
                                 │            │       │
                                 └────────────┼───────┘
                                              ▼
                                    app/process_email.py
                                              │
                                    ┌─────────┴─────────┐
                                    │ Telegram / DB /    │
                                    │ custom logic       │
                                    └───────────────────┘
```

## Components

| Component | What it does |
|---|---|
| **Gmail watch** | `users.watch` subscribes the inbox to a Pub/Sub topic; expires after ~7 days. |
| **Pub/Sub** | transports the `historyId` notification; push subscription calls `/email-notify`. |
| **Cloud Run (FastAPI)** | single service with `/health`, `/email-notify`, `/renew-watch`, `/watch-status`, `/stop-watch`. History fetch + body parsing runs in a `BackgroundTasks` task so the push ACK is fast. |
| **Cloud Scheduler** | `POST /renew-watch` every 6 days; renews the watch before expiry. |
| **Email parsing** | `src/utils/email_utils.py` decodes base64 parts, strips HTML via BeautifulSoup, extracts attachments. |
| **Business logic** | `app/process_email.py::process_email` — the only file most users edit. |
| **State** | `gmail_state.json` stores `last_history_id`; optional SQLAlchemy DB (`app/models.py`) for persistence. |

## Request flow for a new email

1. Gmail delivers `{"emailAddress","historyId"}` to the Pub/Sub topic.
2. Pub/Sub POSTs base64 JSON to `/email-notify`.
3. Handler decodes, validates, and enqueues `process_gmail_history_background(historyId)`.
4. Background task: `history.list(startHistoryId=last) → messages.get → process_email(message)`.
5. `process_email` parses headers/body, fans out to Telegram/DB/custom code.
