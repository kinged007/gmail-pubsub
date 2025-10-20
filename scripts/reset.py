#!/usr/bin/env python3
"""
Comprehensive reset script for Gmail Pub/Sub project.

This script provides two reset options:
1. Complete Wipe: Destroys all Google Cloud resources (Pub/Sub, Cloud Run, Service Accounts, etc.)
2. Local Reset: Clears local authentication and configuration only

Combines functionality from destroy.py and local cleanup operations.
"""

import os
import sys
import json
import requests
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import config

# Handle imports for both direct execution and module import
try:
    from .utils import run_command, clear_mapped_env_variables
except ImportError:
    from utils import run_command, clear_mapped_env_variables


def confirm_complete_wipe():
    """Ask user to confirm complete destruction of all Google Cloud resources."""
    print("\n⚠️  COMPLETE WIPE WARNING")
    print("=" * 80)
    print("This will PERMANENTLY DESTROY ALL Google Cloud resources created by this project:")
    print()

    try:
        project_id = config.get_project_id(True)
        region = config.get_region(True)
        service_name = config.get_service_name(True)
        topic_name = config.get_topic_name(True)
        subscription_name = config.get_subscription_name(True)
        sa_email = config.get_service_account_email(True)
        scheduler_job_name = config.get_topic_name(yaml_only=True) + "-gmail-watch"

        print(f"📍 Project: {project_id}")
        print(f"📍 Region: {region}")
        print()
        print("🗑️  Resources to be DESTROYED:")
        print(f"   • Cloud Run service: {service_name}")
        print(f"   • Pub/Sub topic: {topic_name}")
        print(f"   • Pub/Sub subscription: {subscription_name}")
        print(f"   • Cloud Scheduler job: {scheduler_job_name}")
        print(f"   • Container images for service: {service_name}")
        print(f"   • Service account: {sa_email}")
        print(f"   • All IAM permissions for service account")
        print(f"   • Gmail watch subscription (if active)")
        print()
        print("🔧 Local cleanup:")
        print(f"   • gcloud authentication tokens")
        print(f"   • gcloud project/region configuration")
        print(f"   • config.yaml file")
        print(f"   • All mapped environment variables from .env")

    except Exception as e:
        print("⚠️  Could not load project configuration.")
        print("This may indicate the project is not properly configured.")
        print(f"Error: {e}")
        print()
        print("🗑️  Will attempt to destroy any existing resources and clear local config.")

    print("=" * 80)
    print("⚠️  THIS ACTION CANNOT BE UNDONE!")
    print("⚠️  Make sure you have backups of any important data!")
    print("=" * 80)

    while True:
        response = input("\nType 'DESTROY EVERYTHING' to confirm complete wipe (or 'no' to cancel): ").strip()
        if response == "DESTROY EVERYTHING":
            return True
        elif response.lower() in ['no', 'n', 'cancel']:
            print("Complete wipe cancelled.")
            return False
        else:
            print("Please type 'DESTROY EVERYTHING' exactly or 'no' to cancel.")


def confirm_local_reset():
    """Ask user to confirm local authentication and configuration reset."""
    print("\n🔄 LOCAL RESET CONFIRMATION")
    print("=" * 50)
    print("This will clear local authentication and configuration:")
    print()
    print("🧹 Local cleanup:")
    print("   • Revoke gcloud authentication tokens")
    print("   • Clear gcloud project/region/account configuration")
    print("   • Remove config.yaml file")
    print("   • Clear mapped environment variables from .env file")
    print("   • Preserve custom variables (LOG_LEVEL, GMAIL_WATCH_LABELS, TELEGRAM_*)")
    print()
    print("✅ Google Cloud resources will remain untouched")
    print("=" * 50)

    while True:
        response = input("\nProceed with local reset? (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            print("Local reset cancelled.")
            return False
        else:
            print("Please answer 'yes' or 'no'.")


def stop_gmail_watch():
    """Attempt to stop Gmail watch subscription before destroying resources."""
    print("\n=== Stopping Gmail Watch Subscription ===")

    try:
        service_url = config.get_cloud_run_url()
        if not service_url:
            print("⚠️  No Cloud Run URL found, skipping Gmail watch stop")
            return

        stop_endpoint = f"{service_url}/stop-watch"
        print(f"Calling stop-watch endpoint: {stop_endpoint}")

        response = requests.post(stop_endpoint, timeout=30)
        if response.status_code == 200:
            print("✅ Gmail watch subscription stopped successfully")
        else:
            print(f"⚠️  Stop watch returned status {response.status_code}: {response.text}")

    except requests.RequestException as e:
        print(f"⚠️  Could not stop Gmail watch (service may be down): {e}")
    except Exception as e:
        print(f"⚠️  Error stopping Gmail watch: {e}")


def destroy_cloud_run_service():
    """Destroy Cloud Run service and clean up container images."""
    print("\n=== Destroying Cloud Run Service ===")

    try:
        service_name = config.get_service_name()
        region = config.get_region()
        project_id = config.get_project_id()

        print(f"Deleting Cloud Run service: {service_name}")
        run_command(f"gcloud run services delete {service_name} --region {region} --project {project_id} --quiet", check=False)

        # Clean up container images
        print("Cleaning up container images...")
        image_repo = f"gcr.io/{project_id}/{service_name}"
        run_command(f"gcloud container images delete {image_repo} --force-delete-tags --quiet", check=False)

        print("✅ Cloud Run service destroyed")

    except Exception as e:
        print(f"⚠️  Error destroying Cloud Run service: {e}")


def destroy_pubsub_resources():
    """Destroy Pub/Sub subscription and topic."""
    print("\n=== Destroying Pub/Sub Resources ===")

    try:
        project_id = config.get_project_id()
        topic_name = config.get_topic_name()
        subscription_name = config.get_subscription_name()

        # Delete subscription first (depends on topic)
        print(f"Deleting Pub/Sub subscription: {subscription_name}")
        run_command(f"gcloud pubsub subscriptions delete {subscription_name} --project {project_id} --quiet", check=False)

        # Delete topic
        print(f"Deleting Pub/Sub topic: {topic_name}")
        run_command(f"gcloud pubsub topics delete {topic_name} --project {project_id} --quiet", check=False)

        print("✅ Pub/Sub resources destroyed")

    except Exception as e:
        print(f"⚠️  Error destroying Pub/Sub resources: {e}")


def destroy_cloud_scheduler():
    """Destroy Cloud Scheduler job."""
    print("\n=== Destroying Cloud Scheduler ===")

    try:
        project_id = config.get_project_id()
        region = config.get_region()
        job_name = config.get_topic_name(yaml_only=True) + "-gmail-watch"

        print(f"Deleting Cloud Scheduler job: {job_name}")
        cmd = f"gcloud scheduler jobs delete {job_name} --location {region} --project {project_id} --quiet"
        run_command(cmd, check=False)

        print("✅ Cloud Scheduler destroyed")

    except Exception as e:
        print(f"⚠️  Error destroying Cloud Scheduler: {e}")


def destroy_service_account():
    """Destroy service account and remove all IAM permissions."""
    print("\n=== Destroying Service Account and Permissions ===")

    try:
        project_id = config.get_project_id()
        sa_email = config.get_service_account_email()
        topic_name = config.get_topic_name()

        # Remove IAM policy bindings
        roles = [
            "roles/pubsub.subscriber",
            "roles/run.invoker",
            "roles/secretmanager.secretAccessor"
        ]

        print("Removing IAM permissions...")
        for role in roles:
            cmd = f"gcloud projects remove-iam-policy-binding {project_id} " \
                  f"--member=serviceAccount:{sa_email} --role={role} --quiet"
            run_command(cmd, check=False)

        # Remove Gmail API permission from Pub/Sub topic
        topic_resource = f"projects/{project_id}/topics/{topic_name}"
        gmail_cmd = f"gcloud pubsub topics remove-iam-policy-binding {topic_resource} " \
                   f"--member=serviceAccount:gmail-api-push@system.gserviceaccount.com " \
                   f"--role=roles/pubsub.publisher --quiet"
        run_command(gmail_cmd, check=False)

        # Delete service account
        print(f"Deleting service account: {sa_email}")
        sa_cmd = f"gcloud iam service-accounts delete {sa_email} --project {project_id} --quiet"
        run_command(sa_cmd, check=False)

        print("✅ Service account and permissions destroyed")

    except Exception as e:
        print(f"⚠️  Error destroying service account: {e}")


def clear_local_config():
    """Clear local authentication and configuration."""
    print("\n=== Clearing Local Configuration ===")

    # Clear gcloud authentication and configuration
    print("Revoking gcloud authentication...")
    run_command("gcloud auth revoke", check=False)
    run_command("gcloud config unset project", check=False)
    run_command("gcloud config unset run/region", check=False)
    run_command("gcloud config unset account", check=False)

    # Remove config.yaml
    if os.path.exists("config.yaml"):
        os.remove("config.yaml")
        print("✅ Removed config.yaml file")

    # Clear mapped environment variables from .env file
    clear_mapped_env_variables()

    print("✅ Local configuration cleared")


def complete_wipe():
    """Perform complete wipe of all resources."""
    print("\n🗑️  STARTING COMPLETE WIPE")
    print("=" * 50)

    # Stop Gmail watch first
    stop_gmail_watch()

    # Destroy resources in reverse order of creation
    destroy_cloud_run_service()
    destroy_cloud_scheduler()
    destroy_pubsub_resources()
    destroy_service_account()

    # Clear local configuration
    if confirm_local_reset():
        local_reset()

    print("\n🎉 COMPLETE WIPE FINISHED!")
    print("All Google Cloud resources have been destroyed and local config cleared.")
    print("\nTo verify destruction, you can run the following. They should not work!")
    print("  gcloud run services list")
    print("  gcloud pubsub topics list")
    print("  gcloud pubsub subscriptions list")
    print("  gcloud scheduler jobs list")
    print("  gcloud iam service-accounts list")


def local_reset():
    """Perform local reset only."""
    print("\n🔄 STARTING LOCAL RESET")
    print("=" * 30)

    clear_local_config()

    print("\n✅ LOCAL RESET COMPLETE!")
    print("Local authentication and configuration cleared.")
    print("Google Cloud resources remain untouched.")


def main():
    """Main reset function with user choice."""
    print("🔄 Gmail Pub/Sub Project Reset Tool")
    print("=" * 50)
    print()
    print("Choose reset option:")
    print("1. Complete Wipe - Destroy ALL Google Cloud resources + clear local config")
    print("2. Local Reset - Clear local authentication and configuration only")
    print("3. Cancel")
    print()

    while True:
        choice = input("Enter your choice (1/2/3): ").strip()

        if choice == "1":
            if confirm_complete_wipe():
                try:
                    complete_wipe()
                except KeyboardInterrupt:
                    print("\n❌ Complete wipe cancelled by user")
                    sys.exit(1)
                except Exception as e:
                    print(f"\n❌ Complete wipe failed: {e}")
                    sys.exit(1)
            break

        elif choice == "2":
            if confirm_local_reset():
                try:
                    local_reset()
                except KeyboardInterrupt:
                    print("\n❌ Local reset cancelled by user")
                    sys.exit(1)
                except Exception as e:
                    print(f"\n❌ Local reset failed: {e}")
                    sys.exit(1)
            break

        elif choice == "3":
            print("Reset cancelled.")
            break

        else:
            print("Please enter 1, 2, or 3.")


if __name__ == "__main__":
    main()
