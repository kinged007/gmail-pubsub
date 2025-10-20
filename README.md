# Gmail Pub/Sub Processing API

A fully-autonomous Cloud Run API that receives Gmail push notifications, processes new messages through custom Python logic, and automatically renews Gmail watch subscriptions.

## 🏗️ Architecture

- **Gmail API**: Detects new mail and notifies Pub/Sub
- **Pub/Sub Topic**: Transports Gmail events
- **Cloud Run API**: Single service with multiple endpoints
- **Cloud Scheduler**: Automatically renews Gmail watch every 6 days
- **Service Account**: Handles authentication for Gmail API & Pub/Sub

## 🚀 Quick Start

### Prerequisites

1. Google Cloud Project with billing enabled
2. `gcloud` CLI installed and authenticated
3. `uv` (Python package manager) installed

### Installation

1. **Clone and setup the project:**
   ```bash
   git clone <your-repo>
   cd gmail-pubsub
   uv sync
   ```

2. **Initialize the project (Steps 1-3):**
   ```bash
   uv run init
   ```
   This will:
   - Set up Google Cloud project and enable APIs
   - Prompt for a **topic name** (all other resource names are auto-derived)
   - Create Pub/Sub topic and subscription
   - Create service account with proper permissions

3. **Customize email processing:**
   Edit `app/process_email.py` to implement your custom email processing logic.

4. **Test your email processing logic:**
   ```bash
   uv run test
   ```
   This will run your `process_email()` function with a dummy Gmail message payload. You can modify the `DUMMY_EMAIL_PAYLOAD` in `app/process_email.py` to test different scenarios.

5. **Deploy the application (Steps 6-7):**
   ```bash
   uv run deploy
   ```
   This will:
   - Deploy the Cloud Run service
   - Configure Pub/Sub subscription with the endpoint
   - Set up Cloud Scheduler for automatic watch renewal
   - Initialize Gmail watch subscription

### 📝 Resource Naming Convention

When you enter a topic name during initialization, all other resources are automatically named:

| Resource | Naming Pattern | Example |
|----------|----------------|---------|
| **Topic Name** | `{topic_name}` | `autochartist-signal` |
| **Subscription** | `{topic_name}-sub` | `autochartist-signal-sub` |
| **Service Account** | `{topic_name}-service-account` | `autochartist-signal-service-account` |
| **Cloud Run Service** | `{topic_name}` | `autochartist-signal` |

This ensures consistent naming across all Google Cloud resources.

## 📁 Project Structure

```
gmail-pubsub/
├── app/
│   ├── config.py           # Configuration management
│   ├── gmail_handler.py    # Gmail API operations
│   ├── watch_manager.py    # Gmail watch management
│   ├── process_email.py    # Custom email processing logic
│   └── utils/
│       ├── logger.py       # Logging utilities
│       └── email_utils.py  # Email parsing utilities
├── scripts/
│   ├── init.py            # Initialization script
│   ├── deploy.py          # Deployment script
│   └── test.py            # Test script for email processing
├── main.py                # FastAPI application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── pyproject.toml        # UV project configuration
└── config.yaml           # Generated configuration file
```

## 🔧 Configuration

The project uses a `config.yaml` file to store configuration. This file is automatically created and managed by the scripts. You'll be prompted for values that aren't already configured.

### Environment Variables

You can optionally create a `.env` file for additional environment variables:

```env
# Optional environment variables
LOG_LEVEL=INFO
CUSTOM_SETTING=value
```

The `.env` file will be automatically included in the Cloud Run deployment if it exists.

## 🛠️ Available Scripts

| Command | Description |
|---------|-------------|
| `uv run init` | Initialize Google Cloud project and resources (Steps 1-3) |
| `uv run deploy` | Deploy application to Cloud Run (Steps 6-7) |
| `uv run test` | Test your email processing logic with dummy data |
| `uv run reset` | Reset project configuration and optionally destroy all resources |

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/email-notify` | POST | Handles Pub/Sub push notifications |
| `/renew-watch` | POST | Renews Gmail watch subscription |
| `/watch-status` | GET | Gets current Gmail watch status |
| `/stop-watch` | POST | Stops Gmail watch subscription |

## 🔄 Reset and Cleanup

The project includes a comprehensive reset tool with two options:

### Option 1: Complete Wipe
**⚠️ DESTRUCTIVE - Permanently destroys ALL Google Cloud resources**

```bash
uv run reset
# Choose option 1: Complete Wipe
```

This will:
- Stop Gmail watch subscription
- Destroy Cloud Run service and container images
- Destroy Cloud Scheduler job
- Destroy Pub/Sub topic and subscription
- Destroy service account and all IAM permissions
- Clear local gcloud authentication and configuration
- Remove config.yaml file
- Clear all mapped environment variables from .env

### Option 2: Local Reset
**Safe - Only clears local configuration**

```bash
uv run reset
# Choose option 2: Local Reset
```

This will:
- Clear local gcloud authentication and configuration
- Remove config.yaml file
- Clear mapped environment variables from .env file
- Preserve all Google Cloud resources
- Preserve custom environment variables (LOG_LEVEL, GMAIL_WATCH_LABELS, TELEGRAM_*)

### When to Use Each Option

- **Complete Wipe**: When you want to completely remove the project and start fresh
- **Local Reset**: When you want to reconfigure authentication or switch Google Cloud projects

## 🔄 Email Processing

The main email processing logic is in `app/process_email.py`. This file contains:

- `process_email(message)`: Main function called for each new email
- Uses utility functions from `app/utils/email_utils.py` for parsing Gmail messages
- Clean, focused implementation for your custom business logic

The `app/utils/email_utils.py` module provides:
- `get_headers()`: Extract email headers
- `extract_message_body()`: Extract text content from email body
- `extract_attachments()`: Extract attachment information

### Example Customizations

```python
def process_email(message: Dict[str, Any]) -> None:
    headers = get_headers(message)
    subject = headers.get('subject', '')
    sender = headers.get('from', '')
    body_text = extract_message_body(message)
    
    # Custom logic examples:
    
    # 1. Filter by sender
    if 'important@company.com' in sender:
        handle_important_email(message, body_text)
    
    # 2. Parse invoice emails
    if 'invoice' in subject.lower():
        invoice_data = parse_invoice_email(body_text)
        store_invoice(invoice_data)
    
    # 3. Send notifications
    if 'urgent' in subject.lower():
        send_slack_notification(subject, sender)
```

## 🔐 Authentication

The application uses a Google Cloud Service Account for authentication. The service account credentials can be provided in several ways:

1. **Secret Manager** (recommended for production)
2. **Environment variable** (`GOOGLE_SERVICE_ACCOUNT_JSON`)

### Gmail Account Types

The application supports both **personal Gmail accounts** and **Google Workspace accounts**:

#### Personal Gmail Accounts

For **personal Gmail accounts** (`@gmail.com`), the init script will automatically run the OAuth 2.0 flow:

1. **Place Client Secret File** in your project root:
   ```bash
   # Download client_secret.json from Google Cloud Console
   # Place it in your project root directory
   ```

2. **Run Initialization**:
   ```bash
   uv run init
   ```

3. **Select Personal Gmail** (Option 1) when prompted for Gmail account type

4. **File Selection**: The script will automatically:
   - Find all `client_secret*.json` files in your project root
   - Let you select which one to use (if multiple found)
   - Base64-encode the client secret for secure storage

5. **OAuth Flow**: The script will automatically:
   - Open a browser for Gmail authentication
   - Generate and store the refresh token as a base64-encoded environment variable

6. **Automatic Configuration**: Everything is stored as base64-encoded environment variables:
   ```env
   GMAIL_CLIENT_SECRET_JSON=eyJ0eXAiOiJKV1Q... (base64-encoded-client-secret)
   GMAIL_OAUTH_TOKEN_JSON=eyJ0b2tlbiI6ICJ5YTI5LmEwQVJyZGE... (base64-encoded-oauth-token)
   GMAIL_ACCOUNT_TYPE=oauth
   ```

**✅ One-Time Setup**: After running `uv run init`, your personal Gmail is fully configured and will work autonomously with automatic token refresh. No manual base64 encoding needed!

#### Google Workspace Accounts (Domain-Wide Delegation)

If you're using a **Google Workspace account** and want the service account to access a **specific user's mailbox**, you'll need Domain-Wide Delegation:

1. **Enable Domain-Wide Delegation** in Google Cloud Console:
   - Go to **IAM & Admin → Service Accounts**
   - Click your service account → **Show Domain-Wide Delegation** → Enable
   - Copy the **Client ID**

2. **Configure in Google Workspace Admin Console**:
   - Go to **Security → API Controls → Domain-wide delegation**
   - Click **Add new client**
   - Enter the Client ID from step 1
   - Add these OAuth scopes:
     ```
     https://www.googleapis.com/auth/gmail.readonly
     ```

3. **Configure during initialization**:
   - When running `uv run init`, answer "y" to "Configure Google Workspace delegation?"
   - Enter your Workspace domain (e.g., `yourcompany.com`)
   - Enter the Gmail address to delegate access to (e.g., `user@yourcompany.com`)

The application will automatically detect if Workspace delegation is configured and use the appropriate authentication method.

## 🔄 Watch Renewal

Gmail watch subscriptions expire after 7 days. The application automatically:

1. Sets up a Cloud Scheduler job to run every 6 days
2. Calls the `/renew-watch` endpoint to refresh the subscription
3. Logs the renewal status for monitoring

## 🐛 Debugging

### Check Service Status
```bash
# Check if the service is running
curl https://your-service-url/health

# Check Gmail watch status
curl https://your-service-url/watch-status
```

### View Logs
```bash
# View Cloud Run logs
gcloud logs read --service=gmail-push-api --limit=50

# Follow logs in real-time
gcloud logs tail --service=gmail-push-api
```

### Test Email Processing
Send a test email to your Gmail account and check the logs to see if it's processed.

## 🔧 Development

### Local Development

1. **Set up service account:**
   ```bash
   # Download service account key
   gcloud iam service-accounts keys create service-account.json \
     --iam-account=gmail-processor@your-project.iam.gserviceaccount.com
   ```

2. **Run locally:**
   ```bash
   uv run python main.py
   ```

3. **Test endpoints:**
   ```bash
   curl http://localhost:8080/health
   ```

### Adding Dependencies

```bash
# Add a new dependency
uv add package-name

# Add development dependency
uv add --dev package-name
```

## 📝 Customization Notes

- The `app/process_email.py` file is added to `.gitignore` after initial creation
- This allows you to customize it without committing sensitive business logic
- The file contains comprehensive examples and helper functions
- All email processing errors are caught and logged to prevent service disruption

## 🚨 Important Security Notes

1. **Service Account**: Keep service account credentials secure
2. **Permissions**: The service account has minimal required permissions
3. **Authentication**: Cloud Run endpoints use IAM authentication for Pub/Sub
4. **Secrets**: Use Secret Manager for production credentials

## 📚 Additional Resources

- [Gmail Push Notifications](https://developers.google.com/gmail/api/guides/push)
- [Google Cloud Pub/Sub](https://cloud.google.com/pubsub/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Scheduler](https://cloud.google.com/scheduler/docs)
