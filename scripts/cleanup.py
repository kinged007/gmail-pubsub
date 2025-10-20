#!/usr/bin/env python3
"""
Cleanup script for Gmail Pub/Sub project.

This script provides various cleanup operations to remove unused resources
and optimize Google Cloud resource usage:

1. Clean Cloud Run Revisions: Remove old, unused Cloud Run service revisions
2. Clean Container Images: Remove old container images from Artifact Registry/Container Registry
3. Clean Cloud Build History: Remove old build artifacts and logs
4. Clean Pub/Sub Dead Letter Messages: Clean up dead letter queues
5. Clean Cloud Scheduler Jobs: Remove orphaned scheduler jobs
6. Full Cleanup: Execute all cleanup operations

The script is designed to be safe and will ask for confirmation before
performing destructive operations.
"""

import os
import sys
import json
import subprocess
import shlex
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import config

# Handle imports for both direct execution and module import
try:
    from .utils import run_command, find_gcloud_executable
except ImportError:
    from utils import run_command, find_gcloud_executable

def check_gcloud_auth():
    """Check if user is authenticated with gcloud."""
    print("🔐 Checking gcloud authentication...")

    gcloud_path = find_gcloud_executable()
    if not gcloud_path:
        sys.exit(1)

    result = run_command(f"{gcloud_path} auth list --filter=status:ACTIVE --format=value(account)")

    if not result.stdout.strip():
        print("❌ Not authenticated with gcloud")
        print("Please run: gcloud auth login")
        sys.exit(1)

    print(f"✓ Authenticated as: {result.stdout.strip()}")


def get_project_info():
    """Get project information from config."""
    try:
        project_id = config.get_project_id(yaml_only=True)
        region = config.get_region(yaml_only=True)
        service_name = config.get_service_name(yaml_only=True)
        
        if not all([project_id, region, service_name]):
            print("❌ Missing required configuration. Please run 'uv run init' first.")
            sys.exit(1)
            
        return {
            'project_id': project_id,
            'region': region,
            'service_name': service_name
        }
    except Exception as e:
        print(f"❌ Error reading configuration: {e}")
        sys.exit(1)


def clean_cloud_run_revisions(project_info: Dict[str, str], keep_count: int = 3, dry_run: bool = False):
    """
    Clean old Cloud Run service revisions, keeping only the most recent ones.
    
    Args:
        project_info: Project configuration
        keep_count: Number of recent revisions to keep
        dry_run: If True, only show what would be deleted
    """
    print(f"\n🧹 Cleaning Cloud Run revisions (keeping {keep_count} most recent)...")
    
    gcloud_path = find_gcloud_executable()
    project_id = project_info['project_id']
    region = project_info['region']
    service_name = project_info['service_name']
    
    # List all revisions for the service
    cmd = f"{gcloud_path} run revisions list --service={service_name} --region={region} --project={project_id} --format=json"
    result = run_command(cmd)
    
    if result.returncode != 0:
        print(f"❌ Failed to list revisions: {result.stderr}")
        return False
    
    try:
        revisions = json.loads(result.stdout)
        if not revisions:
            print("✓ No revisions found")
            return True
            
        # Sort by creation time (newest first)
        revisions.sort(key=lambda x: x.get('metadata', {}).get('creationTimestamp', ''), reverse=True)
        
        # Find revisions to delete (keep the most recent ones)
        revisions_to_delete = revisions[keep_count:]
        
        if not revisions_to_delete:
            print(f"✓ Only {len(revisions)} revision(s) found, nothing to clean")
            return True
        
        print(f"📋 Found {len(revisions)} total revisions")
        print(f"🗑️  Will delete {len(revisions_to_delete)} old revision(s):")
        
        for revision in revisions_to_delete:
            name = revision.get('metadata', {}).get('name', 'unknown')
            created = revision.get('metadata', {}).get('creationTimestamp', 'unknown')
            traffic = revision.get('status', {}).get('traffic', [])
            has_traffic = any(t.get('percent', 0) > 0 for t in traffic)
            
            status = "🚦 HAS TRAFFIC" if has_traffic else "✓ No traffic"
            print(f"  - {name} (created: {created}) {status}")
        
        if dry_run:
            print("🔍 DRY RUN: No revisions were actually deleted")
            return True
        
        # Ask for confirmation
        response = input(f"\nDelete {len(revisions_to_delete)} old revision(s)? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Cleanup cancelled")
            return False
        
        # Delete revisions
        deleted_count = 0
        for revision in revisions_to_delete:
            name = revision.get('metadata', {}).get('name')
            if not name:
                continue
                
            print(f"🗑️  Deleting revision: {name}")
            delete_cmd = f"{gcloud_path} run revisions delete {name} --region={region} --project={project_id} --quiet"
            delete_result = run_command(delete_cmd)
            
            if delete_result.returncode == 0:
                deleted_count += 1
                print(f"✓ Deleted: {name}")
            else:
                print(f"❌ Failed to delete {name}: {delete_result.stderr}")
        
        print(f"✅ Successfully deleted {deleted_count}/{len(revisions_to_delete)} revisions")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse revisions JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error cleaning revisions: {e}")
        return False


def clean_container_images(project_info: Dict[str, str], keep_count: int = 5, dry_run: bool = False):
    """
    Clean old container images from Artifact Registry and Container Registry.
    
    Args:
        project_info: Project configuration
        keep_count: Number of recent images to keep per repository
        dry_run: If True, only show what would be deleted
    """
    print(f"\n🧹 Cleaning container images (keeping {keep_count} most recent per repository)...")
    
    gcloud_path = find_gcloud_executable()
    project_id = project_info['project_id']
    region = project_info['region']
    service_name = project_info['service_name']

    # Try Artifact Registry first (newer)
    success = clean_artifact_registry_images(gcloud_path, project_id, region, service_name, keep_count, dry_run)
    
    # Also try Container Registry (legacy)
    success = clean_container_registry_images(gcloud_path, project_id, service_name, keep_count, dry_run) or success
    
    return success


def clean_artifact_registry_images(gcloud_path: str, project_id: str, region: str, service_name: str, keep_count: int, dry_run: bool):
    """Clean images from Artifact Registry."""
    print("🔍 Checking Artifact Registry...")
    
    # List repositories
    cmd = f"{gcloud_path} artifacts repositories list --project={project_id} --format=json"
    result = run_command(cmd)
    
    if result.returncode != 0:
        print("ℹ️  No Artifact Registry repositories found or access denied")
        return False
    
    try:
        repositories = json.loads(result.stdout)
        if not repositories:
            print("ℹ️  No Artifact Registry repositories found")
            return False
        
        cleaned_any = False
        for repo in repositories:
            repo_name = repo.get('name', '')
            if not repo_name:
                continue
                
            # Extract repository details
            repo_parts = repo_name.split('/')
            if len(repo_parts) < 6:
                continue
                
            location = repo_parts[3]
            repo_id = repo_parts[5]
            
            print(f"📦 Checking repository: {repo_id} in {location}")
            
            # List images in repository
            list_cmd = f"{gcloud_path} artifacts docker images list {location}-docker.pkg.dev/{project_id}/{repo_id} --format=json --project={project_id}"
            list_result = run_command(list_cmd)
            
            if list_result.returncode != 0:
                print(f"⚠️  Could not list images in {repo_id}")
                continue
            
            images = json.loads(list_result.stdout)
            if not images:
                print(f"✓ No images found in {repo_id}")
                continue
            
            # Group images by package and clean each package
            packages = {}
            for image in images:
                package = image.get('package', '')
                if package not in packages:
                    packages[package] = []
                packages[package].append(image)
            
            for package, package_images in packages.items():
                if clean_package_images(gcloud_path, project_id, package, package_images, keep_count, dry_run):
                    cleaned_any = True
        
        return cleaned_any
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse repositories JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error cleaning Artifact Registry: {e}")
        return False


def clean_package_images(gcloud_path: str, project_id: str, package: str, images: List[Dict], keep_count: int, dry_run: bool):
    """Clean images from a specific package."""
    if len(images) <= keep_count:
        print(f"✓ Package {package}: Only {len(images)} image(s), nothing to clean")
        return False
    
    # Sort by creation time (newest first)
    images.sort(key=lambda x: x.get('createTime', ''), reverse=True)
    
    images_to_delete = images[keep_count:]
    print(f"🗑️  Package {package}: Will delete {len(images_to_delete)} old image(s)")
    
    for image in images_to_delete:
        image_name = image.get('package', 'unknown')
        create_time = image.get('createTime', 'unknown')
        print(f"  - {image_name} (created: {create_time})")
    
    if dry_run:
        print("🔍 DRY RUN: No images were actually deleted")
        return True
    
    # Ask for confirmation
    response = input(f"\nDelete {len(images_to_delete)} old image(s) from {package}? (y/N): ").strip().lower()
    if response != 'y':
        print("❌ Cleanup cancelled")
        return False
    
    # Delete images
    deleted_count = 0
    for image in images_to_delete:
        image_uri = image.get('package')
        if not image_uri:
            continue
            
        print(f"🗑️  Deleting image: {image_uri}")
        delete_cmd = f"{gcloud_path} artifacts docker images delete {image_uri} --project={project_id} --quiet"
        delete_result = run_command(delete_cmd)
        
        if delete_result.returncode == 0:
            deleted_count += 1
            print(f"✓ Deleted: {image_uri}")
        else:
            print(f"❌ Failed to delete {image_uri}: {delete_result.stderr}")
    
    print(f"✅ Successfully deleted {deleted_count}/{len(images_to_delete)} images from {package}")
    return True


def clean_container_registry_images(gcloud_path: str, project_id: str, service_name: str, keep_count: int, dry_run: bool):
    """Clean images from Container Registry (legacy)."""
    print("🔍 Checking Container Registry...")
    
    # List images in Container Registry
    registry_hosts = ['gcr.io', 'us.gcr.io', 'eu.gcr.io', 'asia.gcr.io']
    
    cleaned_any = False
    for host in registry_hosts:
        image_name = f"{host}/{project_id}/{service_name}"
        
        cmd = f"{gcloud_path} container images list-tags {image_name} --format=json --project={project_id}"
        result = run_command(cmd, check=False)

        if result.returncode != 0:
            # Check if it's a "not found" error (expected for projects using only Artifact Registry)
            if "NAME_UNKNOWN" in result.stderr or "not found" in result.stderr.lower():
                if host == 'gcr.io':  # Only print this message once
                    print("✓ Container Registry not in use (using Artifact Registry instead)")
                break  # No need to check other registry hosts
            continue  # No images in this registry
        
        try:
            images = json.loads(result.stdout)
            if not images:
                continue
            
            if len(images) <= keep_count:
                print(f"✓ {host}: Only {len(images)} image(s), nothing to clean")
                continue
            
            # Sort by timestamp (newest first)
            images.sort(key=lambda x: x.get('timestamp', {}).get('datetime', ''), reverse=True)
            
            images_to_delete = images[keep_count:]
            print(f"🗑️  {host}: Will delete {len(images_to_delete)} old image(s)")
            
            for image in images_to_delete:
                digest = image.get('digest', 'unknown')
                timestamp = image.get('timestamp', {}).get('datetime', 'unknown')
                print(f"  - {digest[:12]}... (created: {timestamp})")
            
            if dry_run:
                print("🔍 DRY RUN: No images were actually deleted")
                cleaned_any = True
                continue
            
            # Ask for confirmation
            response = input(f"\nDelete {len(images_to_delete)} old image(s) from {host}? (y/N): ").strip().lower()
            if response != 'y':
                print("❌ Cleanup cancelled")
                continue
            
            # Delete images
            deleted_count = 0
            for image in images_to_delete:
                digest = image.get('digest')
                if not digest:
                    continue
                    
                image_uri = f"{image_name}@{digest}"
                print(f"🗑️  Deleting image: {digest[:12]}...")
                delete_cmd = f"{gcloud_path} container images delete {image_uri} --project={project_id} --quiet"
                delete_result = run_command(delete_cmd)
                
                if delete_result.returncode == 0:
                    deleted_count += 1
                    print(f"✓ Deleted: {digest[:12]}...")
                else:
                    print(f"❌ Failed to delete {digest[:12]}...: {delete_result.stderr}")
            
            print(f"✅ Successfully deleted {deleted_count}/{len(images_to_delete)} images from {host}")
            cleaned_any = True
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse images JSON for {host}: {e}")
            continue
        except Exception as e:
            print(f"❌ Error cleaning {host}: {e}")
            continue
    
    return cleaned_any


def clean_cloud_build_history(project_info: Dict[str, str], days_to_keep: int = 30, dry_run: bool = False):
    """
    Clean old Cloud Build history and artifacts.

    Args:
        project_info: Project configuration
        days_to_keep: Number of days of build history to keep
        dry_run: If True, only show what would be deleted
    """
    print(f"\n🧹 Cleaning Cloud Build history (keeping {days_to_keep} days)...")

    gcloud_path = find_gcloud_executable()
    project_id = project_info['project_id']

    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    cutoff_str = cutoff_date.strftime('%Y-%m-%dT%H:%M:%S')

    # List old builds
    cmd = f"{gcloud_path} builds list --project={project_id} --filter=\"createTime<'{cutoff_str}'\" --format=json"
    result = run_command(cmd)

    if result.returncode != 0:
        print("ℹ️  No Cloud Build history found or access denied")
        return False

    try:
        builds = json.loads(result.stdout)
        if not builds:
            print("✓ No old builds found to clean")
            return True

        print(f"🗑️  Found {len(builds)} old build(s) to delete:")

        for build in builds:
            build_id = build.get('id', 'unknown')
            create_time = build.get('createTime', 'unknown')
            status = build.get('status', 'unknown')
            print(f"  - {build_id} (created: {create_time}, status: {status})")

        if dry_run:
            print("🔍 DRY RUN: No builds were actually deleted")
            return True

        # Ask for confirmation
        response = input(f"\nDelete {len(builds)} old build(s)? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Cleanup cancelled")
            return False

        # Note: Cloud Build doesn't support bulk deletion, so we inform the user
        print("ℹ️  Note: Cloud Build history cleanup requires manual deletion through the console")
        print("   or individual gcloud commands. Build artifacts are automatically cleaned by Google.")
        print("   Visit: https://console.cloud.google.com/cloud-build/builds")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse builds JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error cleaning build history: {e}")
        return False


def clean_orphaned_scheduler_jobs(project_info: Dict[str, str], dry_run: bool = False):
    """
    Clean orphaned Cloud Scheduler jobs that are no longer needed.

    Args:
        project_info: Project configuration
        dry_run: If True, only show what would be deleted
    """
    print("\n🧹 Cleaning orphaned Cloud Scheduler jobs...")

    gcloud_path = find_gcloud_executable()
    project_id = project_info['project_id']
    region = project_info['region']
    service_name = project_info['service_name']

    # List all scheduler jobs
    cmd = f"{gcloud_path} scheduler jobs list --project={project_id} --location={region} --format=json"
    result = run_command(cmd, check=False)

    if result.returncode != 0:
        print("ℹ️  No Cloud Scheduler jobs found or access denied")
        return False

    try:
        jobs = json.loads(result.stdout)
        if not jobs:
            print("✓ No scheduler jobs found")
            return True

        # Find jobs related to this project that might be orphaned
        project_jobs = []
        expected_job_name = f"renew-gmail-watch"  # Expected job name pattern

        for job in jobs:
            job_name = job.get('name', '')
            if service_name in job_name or 'gmail-watch' in job_name:
                project_jobs.append(job)

        if not project_jobs:
            print("✓ No project-related scheduler jobs found")
            return True

        print(f"📋 Found {len(project_jobs)} project-related scheduler job(s):")

        for job in project_jobs:
            job_name = job.get('name', 'unknown')
            schedule = job.get('schedule', 'unknown')
            state = job.get('state', 'unknown')
            print(f"  - {job_name} (schedule: {schedule}, state: {state})")

        if dry_run:
            print("🔍 DRY RUN: No jobs were actually deleted")
            return True

        print("\nℹ️  Manual review recommended for scheduler jobs.")
        print("   Active jobs are typically needed for watch renewal.")
        print("   Only delete jobs if you're sure they're orphaned.")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse jobs JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error cleaning scheduler jobs: {e}")
        return False


def show_cleanup_menu():
    """Show the cleanup options menu."""
    print("\n🧹 Gmail Pub/Sub Cleanup Options")
    print("=" * 50)
    print("1. Clean Cloud Run Revisions (keep 3 most recent)")
    print("2. Clean Container Images (keep 5 most recent per repository)")
    print("3. Clean Cloud Build History (keep 30 days)")
    print("4. Clean Orphaned Scheduler Jobs")
    print("5. Full Cleanup (all of the above)")
    print("6. Dry Run (show what would be cleaned without deleting)")
    print("0. Exit")
    print()


def main():
    """Main cleanup function."""
    print("🧹 Gmail Pub/Sub Project Cleanup")
    print("This script helps clean up unused Google Cloud resources to optimize costs.")
    print()

    try:
        # Check authentication
        check_gcloud_auth()

        # Get project information
        project_info = get_project_info()

        print(f"\n📍 Project: {project_info['project_id']}")
        print(f"📍 Region: {project_info['region']}")
        print(f"📍 Service: {project_info['service_name']}")

        while True:
            show_cleanup_menu()

            try:
                choice = input("Select an option (0-6): ").strip()

                if choice == '0':
                    print("👋 Cleanup cancelled")
                    break
                elif choice == '1':
                    clean_cloud_run_revisions(project_info)
                elif choice == '2':
                    clean_container_images(project_info)
                elif choice == '3':
                    clean_cloud_build_history(project_info)
                elif choice == '4':
                    clean_orphaned_scheduler_jobs(project_info)
                elif choice == '5':
                    print("\n🚀 Running full cleanup...")
                    clean_cloud_run_revisions(project_info)
                    clean_container_images(project_info)
                    clean_cloud_build_history(project_info)
                    clean_orphaned_scheduler_jobs(project_info)
                    print("\n✅ Full cleanup completed!")
                elif choice == '6':
                    print("\n🔍 Running dry run (no actual deletions)...")
                    clean_cloud_run_revisions(project_info, dry_run=True)
                    clean_container_images(project_info, dry_run=True)
                    clean_cloud_build_history(project_info, dry_run=True)
                    clean_orphaned_scheduler_jobs(project_info, dry_run=True)
                    print("\n✅ Dry run completed!")
                else:
                    print("❌ Invalid option. Please select 0-6.")
                    continue

                # Ask if user wants to continue
                if choice != '0':
                    continue_choice = input("\nPerform another cleanup operation? (y/N): ").strip().lower()
                    if continue_choice != 'y':
                        break

            except KeyboardInterrupt:
                print("\n\n👋 Cleanup interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Error during cleanup: {e}")
                continue

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
