#!/usr/bin/env python3
"""
Sentries Cleanup Utility

Cleans up all Sentries-created artifacts including branches, PRs, and metadata.
"""
import os
import sys
import json


import argparse
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from .git_utils import (
    get_sentries_branches,
    get_sentries_prs,
    is_sentries_branch
)
from .runner_common import setup_logging, get_logger

logger = get_logger(__name__)

class SentriesCleanupManager:
    def __init__(self, repo_path: str = ".", dry_run: bool = False):


        self.repo_path = repo_path
        self.dry_run = dry_run
        self.cleanup_stats = {
            'branches_deleted': 0,
            'prs_closed': 0,
            'metadata_removed': 0,
            'errors': 0
        }

    def cleanup_all_sentries_artifacts(self, max_age_days: Optional[int] = None):
        """Clean up all Sentries artifacts."""
        self.show_sentries_banner()
        print("=" * 50)

    def show_sentries_banner(self):
        """Display the Sentry ASCII art banner."""
        from sentries.banner import show_sentry_banner
        show_sentry_banner()
        print("🧹 Starting Sentry Cleanup Process...")
        print()

    def cleanup_sentries_branches(self, max_age_days: Optional[int] = None):
        """Clean up Sentries-created branches."""
        print("🌿 Cleaning up Sentries branches...")

        try:
            # Change to repository directory
            original_cwd = os.getcwd()
            os.chdir(self.repo_path)

            # Get all Sentries branches
            branches = get_sentries_branches()

            if not branches:
                print("   No Sentries branches found")
                return

            print(f"   Found {len(branches)} Sentries branches")

            for branch in branches:
                if self.should_cleanup_branch(branch, max_age_days):
                    self.delete_branch(branch)

            # Return to original directory
            os.chdir(original_cwd)

        except Exception as e:
            logger.error(f"Error cleaning up branches: {e}")
            self.cleanup_stats['errors'] += 1

    def should_cleanup_branch(self, branch_name: str, max_age_days: Optional[int] = None) -> bool:
        """Check if a branch should be cleaned up based on age."""
        if not max_age_days:
            return True

        try:
            # Get branch creation time from metadata
            result = subprocess.run(
                ['git', 'show', f'{branch_name}:.sentries-metadata.json'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                import json
                metadata = json.loads(result.stdout)
                created_at = datetime.fromisoformat(metadata.get('created_at', ''))

                if datetime.now() - created_at > timedelta(days=max_age_days):
                    return True

            # If no metadata, check branch age using git log
            result = subprocess.run(
                ['git', 'log', '--format=%ci', branch_name, '-1'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                commit_date = datetime.fromisoformat(result.stdout.strip().replace(' ', 'T'))
                if datetime.now() - commit_date > timedelta(days=max_age_days):
                    return True

            return False

        except Exception:
            # If we can't determine age, clean it up
            return True

    def delete_branch(self, branch_name: str):
        """Delete a Sentries branch."""
        try:
            print(f"   🗑️  Deleting branch: {branch_name}")

            if not self.dry_run:
                # Switch to main branch if we're on the branch to delete
                current_branch = subprocess.run(
                    ['git', 'branch', '--show-current'],
                    capture_output=True, text=True, timeout=10
                ).stdout.strip()

                if current_branch == branch_name:
                    subprocess.run(['git', 'checkout', 'main'], check=True, timeout=10)

                # Delete local branch
                subprocess.run(['git', 'branch', '-D', branch_name], check=True, timeout=10)

                # Try to delete remote branch
                try:
                    subprocess.run(
                        ['git', 'push', 'origin', '--delete', branch_name],
                        check=True,
                        timeout=10
                    )
                    print(f"      ✅ Deleted remote branch: {branch_name}")
                except subprocess.CalledProcessError:
                    print(f"      ⚠️  Remote branch {branch_name} not found or already deleted")

                self.cleanup_stats['branches_deleted'] += 1
            else:
                print(f"      🔍 Would delete: {branch_name}")

        except Exception as e:
            logger.error(f"Error deleting branch {branch_name}: {e}")
            self.cleanup_stats['errors'] += 1

    def cleanup_sentries_prs(self, max_age_days: Optional[int] = None):
        """Clean up Sentries-created PRs."""
        print("🔀 Cleaning up Sentries PRs...")

        try:
            prs = get_sentries_prs()

            if not prs:
                print("   No Sentries PRs found")
                return

            print(f"   Found {len(prs)} Sentries PRs")

            for pr in prs:
                if self.should_cleanup_pr(pr, max_age_days):
                    self.close_pr(pr)

        except Exception as e:
            logger.error(f"Error cleaning up PRs: {e}")
            self.cleanup_stats['errors'] += 1

    def should_cleanup_pr(self, pr: Dict, max_age_days: Optional[int] = None) -> bool:
        """Check if a PR should be cleaned up based on age."""
        if not max_age_days:
            return True

        try:
            created_at = datetime.fromisoformat(pr.get('created_at', ''))
            if datetime.now() - created_at > timedelta(days=max_age_days):
                return True
        except Exception:
            # If we can't determine age, clean it up
            return True

        return False

    def close_pr(self, pr: Dict):
        """Close a Sentries PR."""
        try:
            pr_number = pr.get('number')
            pr_title = pr.get('title', 'Unknown')

            print(f"   🔒 Closing PR #{pr_number}: {pr_title}")

            if not self.dry_run:
                # Close the PR via GitHub API
                from .runner_common import GITHUB_TOKEN, GITHUB_REPOSITORY

                if GITHUB_TOKEN and GITHUB_REPOSITORY:
                    import requests

                    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls/{pr_number}"
                    headers = {
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json"
                    }

                    response = requests.patch(
                        url,
                        json={"state": "closed"},
                        headers=headers,
                        timeout=30
                    )

                    if response.status_code == 200:
                        print(f"      ✅ Closed PR #{pr_number}")
                        self.cleanup_stats['prs_closed'] += 1
                    else:
                        print(f"      ❌ Failed to close PR #{pr_number}")
                        self.cleanup_stats['errors'] += 1
                else:
                    print("      ⚠️  GitHub token not configured, cannot close PR")
            else:
                print(f"      🔍 Would close PR #{pr_number}")

        except Exception as e:
            logger.error(f"Error closing PR #{pr.get('number')}: {e}")
            self.cleanup_stats['errors'] += 1

    def cleanup_metadata_files(self):
        """Clean up any remaining Sentries metadata files."""
        print("📁 Cleaning up metadata files...")

        try:
            # Look for .sentries-metadata.json files
            result = subprocess.run(
                ['find', '.', '-name', '.sentries-metadata.json', '-type', 'f'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0 and result.stdout.strip():
                metadata_files = result.stdout.strip().split('\n')
                print(f"   Found {len(metadata_files)} metadata files")

                for file_path in metadata_files:
                    if file_path.strip():
                        print(f"   🗑️  Removing: {file_path}")

                        if not self.dry_run:
                            try:
                                os.remove(file_path)
                                self.cleanup_stats['metadata_removed'] += 1
                            except Exception as e:
                                logger.error(f"Error removing {file_path}: {e}")
                                self.cleanup_stats['errors'] += 1
                        else:
                            print(f"      🔍 Would remove: {file_path}")
            else:
                print("   No metadata files found")

        except Exception as e:
            logger.error(f"Error cleaning up metadata files: {e}")
            self.cleanup_stats['errors'] += 1

    def print_cleanup_summary(self):
        """Print summary of cleanup operations."""
        print("\n" + "=" * 50)
        print("🧹 Cleanup Summary")
        print("=" * 50)

        if self.dry_run:
            print("🔍 DRY RUN - No actual changes were made")
            print()

        print(f"Branches deleted: {self.cleanup_stats['branches_deleted']}")
        print(f"PRs closed: {self.cleanup_stats['prs_closed']}")
        print(f"Metadata files removed: {self.cleanup_stats['metadata_removed']}")
        print(f"Errors encountered: {self.cleanup_stats['errors']}")

        if self.cleanup_stats['errors'] > 0:
            print(f"\n⚠️  {self.cleanup_stats['errors']} errors occurred during cleanup")
            sys.exit(1)
        else:
            print("\n✅ Cleanup completed successfully")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Clean up Sentries artifacts")
    parser.add_argument(
        '--repo-path',
        default='.',
        help='Path to git repository (default: current directory)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be cleaned up without making changes'
    )
    parser.add_argument(
        '--max-age-days',
        type=int,
        help='Only clean up artifacts older than specified days'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force cleanup without confirmation'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Confirm cleanup unless --force is used
    if not args.force and not args.dry_run:
        print("⚠️  This will permanently delete Sentries branches and close PRs!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cleanup cancelled")
            sys.exit(0)

    # Initialize cleanup manager
    cleanup_manager = SentriesCleanupManager(
        repo_path=args.repo_path,
        dry_run=args.dry_run
    )

    # Run cleanup
    cleanup_manager.cleanup_all_sentries_artifacts(max_age_days=args.max_age_days)

if __name__ == "__main__":
    main()
