#!/usr/bin/env python3
"""
Deployment script for Gmail Pub/Sub project.
Executes steps 6-7: Deploy Cloud Run service and configure Pub/Sub subscription.
"""

import os
import subprocess
import sys
import json
import re
import shlex
import requests
import base64
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import config, env_var_map
from .init import run_command

GCLOUD_PATH = None


def validate_initialization():
    """Validate that initialization has been completed successfully."""
    print("🔍 Validating initialization status...")

    # Check if init.complete is set to true in config.yaml
    config.load_config()
    init_complete = config.config.get('init', {}).get('complete')

    if not init_complete or str(init_complete).lower() != 'true':
        print("❌ Initialization not completed.")
        print("Please run 'uv run init' first to complete the setup process.")
        return False

    print("✅ Initialization completed successfully")
    return True


def validate_env_variables():
    """Validate that all required environment variables are set."""
    print("🔍 Validating environment variables...")

    # Check if .env file exists
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found.")
        print("Please run 'uv run init' to create the .env file.")
        return False

    print("✅ .env file exists")

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Check required environment variables from env_var_map
    missing_vars = []
    required_vars = [
        'GOOGLE_CLOUD_PROJECT',
        'GOOGLE_CLOUD_REGION',
        'CLOUD_RUN_SERVICE_NAME',
        'PUBSUB_TOPIC_NAME',
        'PUBSUB_SUBSCRIPTION_NAME',
        'SERVICE_ACCOUNT_NAME',
        'GOOGLE_SERVICE_ACCOUNT_JSON',
        'GMAIL_ACCOUNT_TYPE',
        'GMAIL_WATCH_LABELS'
    ]

    # Add OAuth-specific variables if using OAuth
    gmail_account_type = os.getenv('GMAIL_ACCOUNT_TYPE', '')
    if gmail_account_type.lower() == 'oauth':
        required_vars.extend([
            'GMAIL_OAUTH_TOKEN_JSON',
            'GMAIL_CLIENT_SECRET_JSON'
        ])

    for var in required_vars:
        value = os.getenv(var)
        if not value or value.strip() == '':
            missing_vars.append(var)

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("Please run 'uv run init' to set up all required variables.")
        return False

    print("✅ All required environment variables are set")
    return True


def get_gmail_service():
    """Get Gmail API service for label validation."""
    try:
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        gmail_account_type = os.getenv('GMAIL_ACCOUNT_TYPE', '')

        if gmail_account_type.lower() == 'oauth':
            # Use OAuth credentials
            token_base64 = os.getenv('GMAIL_OAUTH_TOKEN_JSON')
            if not token_base64:
                raise ValueError("GMAIL_OAUTH_TOKEN_JSON not found")

            token_json = base64.b64decode(token_base64).decode('utf-8')
            token_data = json.loads(token_json)

            credentials = Credentials.from_authorized_user_info(token_data, scopes=[
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/gmail.modify'
            ])
        else:
            # Use service account credentials
            service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
            if not service_account_json:
                raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not found")

            service_account_json = base64.b64decode(service_account_json).decode('utf-8')
            service_account_info = json.loads(service_account_json)

            # Handle double-encoded JSON
            if isinstance(service_account_info, str):
                service_account_info = json.loads(service_account_info)

            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=[
                    'https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/gmail.modify'
                ]
            )

        return build('gmail', 'v1', credentials=credentials)

    except Exception as e:
        print(f"❌ Failed to initialize Gmail service: {e}")
        return None


def validate_gmail_labels():
    """Validate Gmail labels and convert names to IDs."""
    print("🔍 Validating Gmail labels...")

    # Get Gmail service
    service = get_gmail_service()
    if not service:
        return False

    try:
        # Get list of labels from Gmail API
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])

        # Create mapping of label names to IDs
        label_name_to_id = {}
        for label in labels:
            label_name_to_id[label['name']] = label['id']

        print(f"✅ Found {len(labels)} Gmail labels")

        # Get configured watch labels
        watch_labels = config.get_gmail_watch_labels()
        print(f"📋 Configured watch labels: {', '.join(watch_labels)}")

        # Convert label names to IDs
        label_ids = []
        missing_labels = []

        for label_name in watch_labels:
            if label_name in label_name_to_id:
                label_ids.append(label_name_to_id[label_name])
                print(f"✅ Found label '{label_name}' with ID: {label_name_to_id[label_name]}")
            else:
                missing_labels.append(label_name)

        if missing_labels:
            print("❌ The following Gmail labels were not found:")
            for label in missing_labels:
                print(f"  - {label}")
            print("\nAvailable labels:")
            for label in sorted(label_name_to_id.keys()):
                print(f"  - {label}")
            print("\nPlease either:")
            print("1. Create the missing labels in Gmail")
            print("2. Update GMAIL_WATCH_LABELS in .env to use existing labels")
            return False

        # Save label IDs to environment
        config.set_gmail_watch_label_ids(label_ids)
        print(f"✅ Saved label IDs to environment: {', '.join(label_ids)}")

        return True

    except Exception as e:
        print(f"❌ Failed to validate Gmail labels: {e}")
        return False


def run_validation():
    """Run all validation checks before deployment."""
    print("🚀 Running pre-deployment validation...")
    print("=" * 50)

    validation_steps = [
        ("Initialization Status", validate_initialization),
        ("Environment Variables", validate_env_variables),
        ("Gmail Labels", validate_gmail_labels)
    ]

    for step_name, validation_func in validation_steps:
        print(f"\n📋 {step_name}")
        if not validation_func():
            print(f"\n❌ Validation failed at: {step_name}")
            print("Please fix the issues above before proceeding with deployment.")
            return False

    print("\n" + "=" * 50)
    print("✅ All validation checks passed!")
    return True


def confirm_deployment():
    """Ask user to confirm deployment after validation."""
    print("\n🚀 Ready to deploy!")
    print("The following will be deployed:")
    print(f"  • Project: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
    print(f"  • Region: {os.getenv('GOOGLE_CLOUD_REGION')}")
    print(f"  • Service: {os.getenv('CLOUD_RUN_SERVICE_NAME')}")
    print(f"  • Topic: {os.getenv('PUBSUB_TOPIC_NAME')}")
    print(f"  • Labels: {os.getenv('GMAIL_WATCH_LABELS')}")

    while True:
        response = input("\nDo you want to proceed with deployment? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            print("❌ Deployment cancelled by user.")
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def find_gcloud_executable():
    """Find the gcloud executable on the system."""
    global GCLOUD_PATH
    if GCLOUD_PATH:
        return GCLOUD_PATH

    # Common gcloud installation paths on Windows
    common_paths = [
        "gcloud",  # If it's in PATH
        r"C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        r"C:\Users\{}\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd".format(os.environ.get('USERNAME', '')),
        r"C:\google-cloud-sdk\bin\gcloud.cmd",
    ]

    for path in common_paths:
        try:
            # Test if the executable exists and works
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✓ Found gcloud at: {path}")
                GCLOUD_PATH = path
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue

    print("❌ Could not find gcloud executable. Please ensure Google Cloud SDK is installed.")
    print("Download from: https://cloud.google.com/sdk/docs/install")
    return None


def check_gcloud_auth():
    """Check if user is authenticated with gcloud."""
    # Use a simpler command format that works better on Windows
    result = run_command("gcloud auth list --filter=status:ACTIVE --format=value(account)", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        print("❌ You are not authenticated with gcloud. Please run 'gcloud auth login' first.")
        sys.exit(1)
    print(f"✓ Authenticated as: {result.stdout.strip()}")


def step6_deploy_cloud_run():
    """Step 6: Deploy Cloud Run service"""
    print("\n=== Step 6: Deploy Cloud Run Service ===")
    
    project_id = config.get_project_id()
    region = config.get_region()
    service_name = config.get_service_name()
    topic_name = config.get_topic_name()
    subscription_name = config.get_subscription_name()
    sa_email = config.get_service_account_email()

    # Update .env file with any new configuration values
    from .utils import update_env_file
    update_env_file('GOOGLE_CLOUD_PROJECT', project_id)
    update_env_file('GOOGLE_CLOUD_REGION', region)
    update_env_file('CLOUD_RUN_SERVICE_NAME', service_name)
    update_env_file('PUBSUB_TOPIC_NAME', topic_name)
    update_env_file('PUBSUB_SUBSCRIPTION_NAME', subscription_name)
    
    # Build the deployment command
    deploy_cmd = f"gcloud run deploy {service_name} --source . --region {region} --project {project_id}"
    deploy_cmd += f" --service-account {sa_email}"
    deploy_cmd += " --allow-unauthenticated"
    deploy_cmd += " --platform managed"
    deploy_cmd += " --memory 512Mi"
    deploy_cmd += " --cpu 1"
    deploy_cmd += " --max-instances 10"
    deploy_cmd += " --min-instances 0"
    deploy_cmd += " --timeout 300"
    deploy_cmd += " --quiet"
    
    # Add environment file if it exists
    env_file = Path(".env")
    if env_file.exists():
        deploy_cmd += " --env-vars-file .env"
        print("✓ Found .env file, including in deployment")
    
    # Deploy the service
    result = run_command(deploy_cmd)
    
    # Extract the service URL from the output
    service_url = None
    for line in result.stdout.split('\n'):
        if 'Service URL:' in line:
            service_url = line.split('Service URL:')[1].strip()
            break
    
    if not service_url:
        # Try alternative method to get URL using JSON format
        get_url_cmd = f"gcloud run services describe {service_name} --region {region} --format=json"
        url_result = run_command(get_url_cmd)
        if url_result.returncode == 0:
            import json
            try:
                service_data = json.loads(url_result.stdout)
                service_url = service_data.get('status', {}).get('url', '')
            except json.JSONDecodeError:
                pass
    
    if service_url:
        print(f"✓ Service deployed successfully: {service_url}")
        config.set_cloud_run_url(service_url)
        # Update .env file with the service URL
        update_env_file('CLOUD_RUN_URL', service_url)
        return service_url
    else:
        print("❌ Could not determine service URL")
        sys.exit(1)


def step7_configure_pubsub():
    """Step 7: Configure Pub/Sub subscription with Cloud Run endpoint"""
    print("\n=== Step 7: Configure Pub/Sub Subscription ===")
    
    service_url = config.get_cloud_run_url()
    if not service_url:
        print("❌ Cloud Run service URL not found. Please deploy the service first.")
        sys.exit(1)
    
    subscription_name = config.get_subscription_name()
    sa_email = config.get_service_account_email()
    
    # Configure push endpoint
    push_endpoint = f"{service_url}/email-notify"
    
    update_cmd = f"gcloud pubsub subscriptions update {subscription_name}"
    update_cmd += f" --push-endpoint={push_endpoint}"
    update_cmd += f" --push-auth-service-account={sa_email}"
    
    run_command(update_cmd)
    
    print(f"✓ Pub/Sub subscription configured with endpoint: {push_endpoint}")


def setup_cloud_scheduler():
    """Set up Cloud Scheduler job for watch renewal"""
    print("\n=== Setting up Cloud Scheduler ===")
    
    service_url = config.get_cloud_run_url()
    if not service_url:
        print("❌ Cloud Run service URL not found. Please deploy the service first.")
        sys.exit(1)
    
    sa_email = config.get_service_account_email()
    region = config.get_region()
    
    # Create scheduler job
    job_name = "renew-gmail-watch"
    renew_endpoint = f"{service_url}/renew-watch"
    
    # Check if job already exists
    check_cmd = f"gcloud scheduler jobs describe {job_name} --location={region}"
    check_result = run_command(check_cmd, check=False)
    
    if check_result.returncode == 0:
        print(f"Scheduler job {job_name} already exists, updating...")
        scheduler_cmd = f"gcloud scheduler jobs update http {job_name} --location={region}"
    else:
        print(f"Creating new scheduler job {job_name}...")
        scheduler_cmd = f"gcloud scheduler jobs create http {job_name} --location={region}"
    
    scheduler_cmd += " --schedule=\"0 0 */6 * *\""  # Every 6 days
    scheduler_cmd += f" --uri={renew_endpoint}"
    scheduler_cmd += f" --http-method=POST"
    scheduler_cmd += f" --oidc-service-account-email={sa_email}"
    scheduler_cmd += f" --time-zone=UTC"
    
    run_command(scheduler_cmd)
    
    print(f"✓ Cloud Scheduler configured to call: {renew_endpoint}")


def initialize_gmail_watch():
    """Initialize Gmail watch subscription"""
    print("\n=== Initializing Gmail Watch ===")
    
    service_url = config.get_cloud_run_url()
    if not service_url:
        print("❌ Cloud Run service URL not found. Please deploy the service first.")
        sys.exit(1)
    
    renew_endpoint = f"{service_url}/renew-watch"
    
    print(f"Calling {renew_endpoint} to initialize Gmail watch...")

    try:
        # Use requests to call the renew-watch endpoint
        response = requests.post(renew_endpoint, headers={'Content-Type': 'application/json'}, timeout=30)

        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    print("✓ Gmail watch initialized successfully")
                    print(f"  History ID: {response_data.get('historyId')}")
                    print(f"  Expiration: {response_data.get('expiration')}")
                else:
                    print(f"❌ Failed to initialize Gmail watch: {response_data}")
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON response from renew-watch endpoint: {response.text}")
        else:
            print(f"❌ Failed to call renew-watch endpoint: HTTP {response.status_code}")
            print(f"  Response: {response.text}")
    except requests.RequestException as e:
        print(f"❌ Failed to call renew-watch endpoint: {e}")


def main():
    """Main deployment function."""
    print("🚀 Deploying Gmail Pub/Sub Project")
    print("This script will execute steps 6-7 from the deployment sequence.")

    try:
        # Run validation checks
        if not run_validation():
            sys.exit(1)

        # Ask for user confirmation
        if not confirm_deployment():
            sys.exit(1)

        # Check authentication
        check_gcloud_auth()

        # Deploy Cloud Run service
        step6_deploy_cloud_run()
        
        # Configure Pub/Sub subscription
        step7_configure_pubsub()
        
        # Set up Cloud Scheduler
        setup_cloud_scheduler()
        
        # Initialize Gmail watch
        initialize_gmail_watch()
        
        print("\n🎉 Deployment completed successfully!")
        print("\nYour Gmail Pub/Sub API is now running at:")
        print(f"  {config.get_cloud_run_url()}")
        print("\nEndpoints:")
        print(f"  Health: {config.get_cloud_run_url()}/health")
        print(f"  Email notifications: {config.get_cloud_run_url()}/email-notify")
        print(f"  Renew watch: {config.get_cloud_run_url()}/renew-watch")
        print(f"  Watch status: {config.get_cloud_run_url()}/watch-status")
        
    except KeyboardInterrupt:
        print("\n❌ Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
