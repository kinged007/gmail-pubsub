#!/usr/bin/env python3
"""
Initialization script for Gmail Pub/Sub project.
Executes steps 1-3: Authentication, project setup, Pub/Sub creation, and service account setup.
"""

import os
import subprocess
import sys
import json
import base64
import secrets
import string
import time
from pathlib import Path

LOGIN_ATTEMPT = 0

from src.config import config
from .utils import run_command, create_env_file, update_env_file, clear_mapped_env_variables

# Load run_command method from utils
config.load_run_command(run_command)


def setup_oauth_credentials():
    """
    Run OAuth 2.0 flow to get Gmail access token for personal Gmail accounts.
    Automatically finds and uses client_secret.json files from the project root.

    Returns:
        bool: True if OAuth setup was successful, False otherwise
    """
    print("\n🔐 Setting up OAuth for Personal Gmail")
    print("This will open a browser window for Gmail authentication...")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        # Define Gmail scopes
        SCOPES = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify"
        ]

        # Look for JSON files in current directory
        json_files = [f for f in os.listdir('.') if f.endswith('.json')]

        if not json_files:
            print("❌ No .json files found in the current directory.")
            print("Please download your OAuth 2.0 client secret file from Google Cloud Console")
            print("and place it in the project root as a .json file.")
            print(f"Current directory: {os.getcwd()}")
            return False

        # Show all JSON files and let user select
        print("Found the following JSON files in your project root:")
        for i, file in enumerate(json_files, 1):
            if file.startswith('client_secret'):
                print(f"{i}. {file} ← Client secret file (recommended)")
            else:
                print(f"{i}. {file}")

        try:
            choice = int(input(f"\nSelect the client secret file (1-{len(json_files)}): ")) - 1
            if choice < 0 or choice >= len(json_files):
                raise ValueError("Out of range")
            client_secret_path = json_files[choice]
        except (ValueError, IndexError):
            print("❌ Invalid selection.")
            return False

        # Check if selected file is a client secret file
        if client_secret_path.startswith('client_secret'):
            print(f"✓ Selected client secret file: {client_secret_path}")
        else:
            print(f"⚠️  Selected file: {client_secret_path}")
            print("Make sure this is your OAuth 2.0 client secret file from Google Cloud Console.")

        try:
            # Load and parse client secret file
            with open(client_secret_path, 'r') as f:
                client_secret_data = json.load(f)

            # Base64 encode the client secret for environment storage
            client_secret_json = json.dumps(client_secret_data)
            client_secret_base64 = base64.b64encode(client_secret_json.encode('utf-8')).decode('utf-8')

            print("✓ Client secret loaded and encoded")

            # Run OAuth flow using the client secret
            print("\n🌐 Starting OAuth flow...")
            print("A browser window will open for Gmail authentication.")
            print("Please sign in and grant permissions for Gmail access.")

            # Create a temporary client secret file for the OAuth flow
            with open("temp_client_secret.json", "w") as f:
                json.dump(client_secret_data, f)

            flow = InstalledAppFlow.from_client_secrets_file("temp_client_secret.json", SCOPES)
            credentials = flow.run_local_server(port=0)

            # Clean up temporary file
            os.remove("temp_client_secret.json")

            print("✓ OAuth flow completed successfully!")

            # Convert credentials to JSON and base64 encode
            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes
            }

            # Convert to JSON string and base64 encode for environment variable
            token_json = json.dumps(token_data)
            token_base64 = base64.b64encode(token_json.encode('utf-8')).decode('utf-8')

            print("✓ Token generated and encoded")

            # Update environment file with both client secret and token
            update_env_file('GMAIL_CLIENT_SECRET_JSON', client_secret_base64)
            update_env_file('GMAIL_OAUTH_TOKEN_JSON', token_base64)
            update_env_file('GMAIL_ACCOUNT_TYPE', 'oauth')

            # Also save to config.yaml
            config.set('gmail.account_type', 'oauth')

            print("✓ OAuth credentials saved to environment variables")
            print("✓ Client secret also saved (base64-encoded) for future use")
            print("Your application is now configured for personal Gmail access!")

            return True

        except Exception as e:
            print(f"❌ OAuth flow failed: {e}")
            print("Please check your client secret file format and internet connection.")
            return False

    except ImportError:
        print("❌ google-auth-oauthlib not installed.")
        print("Please install it with: pip install google-auth-oauthlib")
        return False


def generate_access_token():
    """
    Generate a cryptographically secure access token for API authentication.

    Returns:
        str: Secure random token for API access
    """
    # Generate a 64-character secure token using letters, digits, and special characters
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    token = ''.join(secrets.choice(alphabet) for _ in range(64))

    print("✓ Generated secure access token for API authentication")
    print(f"Token length: {len(token)} characters")

    return token


def check_gcloud_auth():
    """Check if user is authenticated with gcloud."""
    global LOGIN_ATTEMPT
    
    # Reset authentication?
    print("If you want to reset gcloud authentication, or destroy all services, run 'uv run reset'")
    time.sleep(2)
    
    # if LOGIN_ATTEMPT == 0 and os.path.exists("config.yaml") and input("Reset authentication? (y/N) ") == "y":
    #     print("\n🔄 Invoking reset script...")

    #     # Import and call the reset script
    #     from .reset import main as reset_main
    #     reset_main()

    #     print("✓ Reset completed - restarting initialization...")
    #     # Exit to allow user to restart the init process
    #     sys.exit(0)
    
    # Use a simpler command format that works better on Windows
    result = run_command("gcloud auth list --filter=status:ACTIVE --format=value(account)", check=False)

    if result.returncode != 0 or not result.stdout.strip():
        if LOGIN_ATTEMPT == 0:
            print("Not authenticated with gcloud. Attempting to log in...")
            login_result = run_command("gcloud auth login", check=False)
            LOGIN_ATTEMPT = 1
            if login_result.returncode == 0:
                # Retry authentication check after successful login
                return check_gcloud_auth()

        print("❌ Authentication failed. Please run 'gcloud auth login' manually and try again.")
        print("Make sure gcloud CLI is properly installed and in your PATH.")
        sys.exit(1)

    print(f"✓ Authenticated as: {result.stdout.strip()}")
    run_command(f"gcloud config set account {result.stdout.strip()}")


def step1_authenticate_and_setup():
    """Step 1: Authenticate & Select Project"""
    print("\n=== Step 1: Authenticate & Select Project ===")
    
    # Check authentication
    check_gcloud_auth()
    
    # Get project configuration
    project_id = config.get_project_id(yaml_only=True)
    # Set gcloud configuration
    run_command(f"gcloud config set project {project_id}")
    
    # Get project region
    region = config.get_region(yaml_only=True)
    # Set gcloud config
    run_command(f"gcloud config set run/region {region}")
    
    # Enable required APIs
    print("Enabling required APIs...")
    apis = [
        "gmail.googleapis.com",
        "pubsub.googleapis.com", 
        "run.googleapis.com",
        "cloudscheduler.googleapis.com",
        "secretmanager.googleapis.com"
    ]
    
    for api in apis:
        run_command(f"gcloud services enable {api}")
    
    print("✓ Step 1 completed successfully")


def step2_create_pubsub():
    """Step 2: Create Pub/Sub Topic and Subscription"""
    print("\n=== Step 2: Create Pub/Sub Topic and Subscription ===")
    
    topic_name = config.get_topic_name(yaml_only=True)
    subscription_name = config.get_subscription_name(yaml_only=True)
    
    # Create topic (ignore if already exists)
    result = run_command(f"gcloud pubsub topics create {topic_name}", check=False)
    if result.returncode == 0:
        print(f"✓ Created topic: {topic_name}")
    else:
        print(f"Topic {topic_name} already exists or error occurred")
    
    # Create subscription (ignore if already exists)
    result = run_command(f"gcloud pubsub subscriptions create {subscription_name} --topic {topic_name}", check=False)
    if result.returncode == 0:
        print(f"✓ Created subscription: {subscription_name}")
    else:
        print(f"Subscription {subscription_name} already exists or error occurred")
    
    print("✓ Step 2 completed successfully")


def generate_service_account_key():
    """Generate service account key and return JSON credentials."""
    project_id = config.get_project_id(yaml_only=True)
    sa_name = config.get_service_account_name(yaml_only=True)
    key_file = f"{sa_name}-key.json"

    print("Generating service account key...")
    # Create a temporary key file
    run_command(f"gcloud iam service-accounts keys create {key_file} --iam-account={sa_name}@{project_id}.iam.gserviceaccount.com")

    # Read the key file content
    try:
        with open(key_file, 'r') as f:
            key_content = f.read()

        # Delete the temporary key file
        Path(key_file).unlink()

        print("✓ Generated and processed service account key")
        return key_content.strip()
    except Exception as e:
        print(f"❌ Error processing service account key: {e}")
        return None


def step3_create_service_account():
    """Step 3: Create Service Account and Assign Roles"""
    print("\n=== Step 3: Create Service Account and Assign Roles ===")

    project_id = config.get_project_id(yaml_only=True)
    sa_name = config.get_service_account_name(yaml_only=True)
    sa_email = config.get_service_account_email(yaml_only=True)
    topic_name = config.get_topic_name(yaml_only=True)

    # Create service account (ignore if already exists)
    result = run_command(f"gcloud iam service-accounts create {sa_name} --display-name='Gmail Processor Service Account'", check=False)
    if result.returncode == 0:
        print(f"✓ Created service account: {sa_name}")
        print("⏳ Waiting for service account propagation...")
        time.sleep(3)  # Wait for Google Cloud propagation to avoid IAM binding errors
    else:
        print(f"Service account {sa_name} already exists or error occurred")

    # Assign roles to service account
    roles = [
        "roles/pubsub.subscriber",
        "roles/pubsub.publisher",
        "roles/run.invoker",
        "roles/secretmanager.secretAccessor"
    ]

    for role in roles:
        run_command(f"gcloud projects add-iam-policy-binding {project_id} --member=serviceAccount:{sa_email} --role={role}")
        print(f"✓ Assigned role: {role}")

    # Allow Gmail to publish to Pub/Sub
    topic_resource = f"projects/{project_id}/topics/{topic_name}"
    run_command(f"gcloud pubsub topics add-iam-policy-binding {topic_resource} --member=serviceAccount:gmail-api-push@system.gserviceaccount.com --role=roles/pubsub.publisher")
    print("✓ Granted Gmail API permission to publish to Pub/Sub")

    # Check Gmail account type and configure accordingly
    print("\n--- Gmail Account Configuration ---")

    account_types = [
        "personal",  # Personal Gmail with OAuth
        "workspace", # Google Workspace with service account delegation
        "skip"       # Skip configuration (will need manual setup later)
    ]

    update_env_file("### AUTO GENERATED VARIABLES ###", "")  # Separator for auto-generated vars

    print("Select your Gmail account type:")
    print("1. Personal Gmail (@gmail.com) - requires OAuth setup")
    print("2. Google Workspace (company account) - uses service account delegation")
    print("3. Skip for now (configure manually later)")

    choice = input("Enter choice (1-3): ").strip()

    if choice == "1":
        # Personal Gmail OAuth setup - run automated OAuth flow
        print("\n🔐 Setting up Personal Gmail Access")
        print("We'll run the OAuth flow automatically to get Gmail access...")

        success = setup_oauth_credentials()

        if success:
            print("✅ OAuth setup completed successfully!")
            print("Your application is now configured for personal Gmail access.")
        else:
            print("❌ OAuth setup failed.")
            print("Please ensure you have:")
            print("1. A valid client_secret.json file in your project root")
            print("2. Internet connection for the OAuth flow")
            print("3. Permission to open a browser for authentication")

    elif choice == "2":
        # Google Workspace delegation setup
        print("\n📋 Workspace Delegation Setup Instructions:")
        print("1. In Google Cloud Console → IAM & Admin → Service Accounts")
        print(f"   Click '{sa_name}' → Show Domain-Wide Delegation → Enable")
        print("2. Copy the Client ID from the service account")
        print("3. In Google Workspace Admin Console → Security → API Controls → Domain-wide delegation")
        print("   Add a new client with the copied Client ID and these scopes:")
        print("   - https://www.googleapis.com/auth/gmail.readonly")
        print("   - https://www.googleapis.com/auth/gmail.modify")

        input("\nPress Enter after completing the above steps in the consoles...")

        # Get workspace configuration
        workspace_domain = input("Enter your Google Workspace domain (e.g., yourcompany.com): ").strip()
        delegated_user_email = input("Enter the Gmail address to delegate access to (e.g., user@yourcompany.com): ").strip()

        if workspace_domain and delegated_user_email:
            # Update both .env file and config.yaml with workspace configuration
            update_env_file('WORKSPACE_DOMAIN', workspace_domain)
            update_env_file('DELEGATED_USER_EMAIL', delegated_user_email)
            update_env_file('GMAIL_ACCOUNT_TYPE', 'workspace')

            # Also save to config.yaml
            config.set('workspace.domain', workspace_domain)
            config.set('workspace.delegated_user_email', delegated_user_email)
            config.set('gmail.account_type', 'workspace')

            print(f"✓ Configured workspace delegation for {delegated_user_email} at {workspace_domain}")
        else:
            print("❌ Invalid workspace configuration. Skipping delegation setup.")
    else:
        print("✓ Skipping Gmail configuration (will use service account)")
        update_env_file('GMAIL_ACCOUNT_TYPE', 'service_account')
        # Also save to config.yaml
        config.set('gmail.account_type', 'service_account')
    # Generate a secure random access token
    print("\n=== Generating Secure API Access Token ===")
    access_token = generate_access_token()
    update_env_file('API_ACCESS_TOKEN', access_token)
    print("✓ Access token saved to environment variables")
    print("🔐 IMPORTANT: Keep this token secure and don't share it publicly!")
    print("   You'll need it to authenticate API requests.")
    

    print("✓ Step 3 completed successfully")


def main():
    """Main initialization function."""
    print("🚀 Initializing Gmail Pub/Sub Project")
    print("This script will execute steps 1-3 from the deployment sequence.")

    try:
        print("\n=== Creating .env file ===")
        create_env_file()

        step1_authenticate_and_setup()
        step2_create_pubsub()
        step3_create_service_account()

        # Create and populate .env file with necessary variables
        print("\n=== Setting up Environment Variables ===")

        # Update .env with all configuration values
        project_id = config.get_project_id(yaml_only=True)
        region = config.get_region(yaml_only=True)
        service_name = config.get_service_name(yaml_only=True)
        topic_name = config.get_topic_name(yaml_only=True)
        subscription_name = config.get_subscription_name(yaml_only=True)
        sa_name = config.get_service_account_name(yaml_only=True)

        # Update .env file with all config values
        update_env_file('GOOGLE_CLOUD_PROJECT', project_id)
        update_env_file('GOOGLE_CLOUD_REGION', region)
        update_env_file('CLOUD_RUN_SERVICE_NAME', service_name)
        update_env_file('PUBSUB_TOPIC_NAME', topic_name)
        update_env_file('PUBSUB_SUBSCRIPTION_NAME', subscription_name)
        update_env_file('SERVICE_ACCOUNT_NAME', sa_name)

        # Generate service account key and update .env
        credentials_json = generate_service_account_key()
        if credentials_json:
            # Base64 encode the client secret for environment storage
            credentials_json = json.dumps(credentials_json)
            credentials_json_base64 = base64.b64encode(credentials_json.encode('utf-8')).decode('utf-8')            
            update_env_file('GOOGLE_SERVICE_ACCOUNT_JSON', credentials_json_base64)
            print("✓ Service account credentials saved to environment variables")

        # Mark initialization as complete
        config.set('init.complete', 'true')
        print("✓ Marked initialization as complete in config.yaml")

        print("\n🎉 Initialization completed successfully!")
        print("\nNext steps:")
        print("1. Implement your custom logic in app/process_email.py")
        print("2. Update the .env file with any additional configuration as needed.")
        print("3. Run 'uv run deploy' to deploy the application")

    except KeyboardInterrupt:
        print("\n❌ Initialization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
