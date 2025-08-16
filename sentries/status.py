#!/usr/bin/env python3
"""
Sentries Status Utility

Shows the current status of all Sentries artifacts in the repository.
"""
import os
import sys
import json
import subprocess
from datetime import datetime
from typing import List, Dict

from .git_utils import get_sentries_branches, get_sentries_prs
from .runner_common import setup_logging, get_logger

logger = get_logger(__name__)

class SentriesStatusReporter:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
    
    def show_status(self):
        """Show comprehensive status of Sentries artifacts."""
        self.show_sentries_banner()
        print("=" * 60)
    
    def show_sentries_banner(self):
        """Display the Sentry ASCII art banner."""
        from sentries.banner import show_sentry_banner
        show_sentry_banner()
        print("📊 Starting Sentry Status Report...")
        print()
        print(f"Repository: {self.repo_path}")
        print(f"Generated: {datetime.now().isoformat()}")
        print()
        
        # Show branches
        self.show_branches_status()
        
        # Show PRs
        self.show_prs_status()
        
        # Show metadata files
        self.show_metadata_status()
        
        # Show summary
        self.show_summary()
    
    def show_branches_status(self):
        """Show status of Sentries branches."""
        print("🌿 Sentries Branches")
        print("-" * 30)
        
        try:
            # Change to repository directory
            original_cwd = os.getcwd()
            os.chdir(self.repo_path)
            
            branches = get_sentries_branches()
            
            if not branches:
                print("   No Sentries branches found")
            else:
                print(f"   Found {len(branches)} Sentries branches:")
                print()
                
                for branch in branches:
                    self.show_branch_details(branch)
            
            # Return to original directory
            os.chdir(original_cwd)
            
        except Exception as e:
            logger.error(f"Error getting branches status: {e}")
            print("   ❌ Error retrieving branches")
        
        print()
    
    def show_branch_details(self, branch_name: str):
        """Show detailed information about a branch."""
        try:
            # Get branch metadata
            result = subprocess.run(
                ['git', 'show', f'{branch_name}:.sentries-metadata.json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                metadata = json.loads(result.stdout)
                sentry_type = metadata.get('sentry_type', 'unknown')
                created_at = metadata.get('created_at', 'unknown')
                source_commit = metadata.get('source_commit', 'unknown')[:8]
                
                print(f"   📍 {branch_name}")
                print(f"      Type: {sentry_type}")
                print(f"      Created: {created_at}")
                print(f"      Source: {source_commit}")
                
                # Get last commit info
                commit_result = subprocess.run(
                    ['git', 'log', '--format=%h %s', branch_name, '-1'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if commit_result.returncode == 0:
                    last_commit = commit_result.stdout.strip()
                    print(f"      Last commit: {last_commit}")
                
                print()
            else:
                # No metadata, show basic info
                print(f"   📍 {branch_name} (no metadata)")
                
                # Get last commit info
                commit_result = subprocess.run(
                    ['git', 'log', '--format=%h %s', branch_name, '-1'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if commit_result.returncode == 0:
                    last_commit = commit_result.stdout.strip()
                    print(f"      Last commit: {last_commit}")
                
                print()
                
        except Exception as e:
            print(f"   📍 {branch_name} (error reading details: {e})")
            print()
    
    def show_prs_status(self):
        """Show status of Sentries PRs."""
        print("🔀 Sentries Pull Requests")
        print("-" * 30)
        
        try:
            prs = get_sentries_prs()
            
            if not prs:
                print("   No Sentries PRs found")
            else:
                print(f"   Found {len(prs)} Sentries PRs:")
                print()
                
                for pr in prs:
                    self.show_pr_details(pr)
            
        except Exception as e:
            logger.error(f"Error getting PRs status: {e}")
            print("   ❌ Error retrieving PRs")
        
        print()
    
    def show_pr_details(self, pr: Dict):
        """Show detailed information about a PR."""
        try:
            pr_number = pr.get('number', 'unknown')
            pr_title = pr.get('title', 'Unknown')
            pr_state = pr.get('state', 'unknown')
            pr_created = pr.get('created_at', 'unknown')
            pr_updated = pr.get('updated_at', 'unknown')
            pr_labels = [label.get('name', '') for label in pr.get('labels', [])]
            
            print(f"   🔀 PR #{pr_number}: {pr_title}")
            print(f"      State: {pr_state}")
            print(f"      Created: {pr_created}")
            print(f"      Updated: {pr_updated}")
            
            if pr_labels:
                print(f"      Labels: {', '.join(pr_labels)}")
            
            # Check if PR has Sentries metadata
            pr_body = pr.get('body', '')
            if '🤖 Sentries Metadata' in pr_body:
                print(f"      ✅ Has Sentries metadata")
            
            print()
            
        except Exception as e:
            print(f"   🔀 PR #{pr.get('number', 'unknown')} (error reading details: {e})")
            print()
    
    def show_metadata_status(self):
        """Show status of metadata files."""
        print("📁 Sentries Metadata Files")
        print("-" * 30)
        
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
                print(f"   Found {len(metadata_files)} metadata files:")
                print()
                
                for file_path in metadata_files:
                    if file_path.strip():
                        self.show_metadata_file_details(file_path)
            else:
                print("   No metadata files found")
                
        except Exception as e:
            logger.error(f"Error getting metadata status: {e}")
            print("   ❌ Error retrieving metadata files")
        
        print()
    
    def show_metadata_file_details(self, file_path: str):
        """Show details of a metadata file."""
        try:
            with open(file_path, 'r') as f:
                metadata = json.load(f)
            
            sentry_type = metadata.get('sentry_type', 'unknown')
            created_at = metadata.get('created_at', 'unknown')
            source_commit = metadata.get('source_commit', 'unknown')[:8]
            branch_name = metadata.get('branch_name', 'unknown')
            
            print(f"   📄 {file_path}")
            print(f"      Type: {sentry_type}")
            print(f"      Created: {created_at}")
            print(f"      Source: {source_commit}")
            print(f"      Branch: {branch_name}")
            print()
            
        except Exception as e:
            print(f"   📄 {file_path} (error reading: {e})")
            print()
    
    def show_summary(self):
        """Show summary statistics."""
        print("📊 Summary")
        print("-" * 30)
        
        try:
            # Count branches
            branches = get_sentries_branches()
            branch_count = len(branches)
            
            # Count PRs
            prs = get_sentries_prs()
            pr_count = len(prs)
            
            # Count metadata files
            result = subprocess.run(
                ['find', '.', '-name', '.sentries-metadata.json', '-type', 'f'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            metadata_count = 0
            if result.returncode == 0 and result.stdout.strip():
                metadata_count = len(result.stdout.strip().split('\n'))
            
            print(f"   Total Sentries branches: {branch_count}")
            print(f"   Total Sentries PRs: {pr_count}")
            print(f"   Total metadata files: {metadata_count}")
            
            # Show age distribution
            if branches:
                self.show_age_distribution(branches)
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            print("   ❌ Error generating summary")
        
        print()
        print("=" * 60)
    
    def show_age_distribution(self, branches: List[str]):
        """Show age distribution of branches."""
        try:
            ages = []
            for branch in branches:
                try:
                    result = subprocess.run(
                        ['git', 'log', '--format=%ci', branch, '-1'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        commit_date = datetime.fromisoformat(result.stdout.strip().replace(' ', 'T'))
                        age = datetime.now() - commit_date
                        ages.append(age.days)
                except Exception:
                    pass
            
            if ages:
                ages.sort()
                print(f"   Branch ages: {ages[0]} to {ages[-1]} days old")
                
                # Categorize by age
                recent = len([age for age in ages if age <= 1])
                week_old = len([age for age in ages if 1 < age <= 7])
                month_old = len([age for age in ages if 7 < age <= 30])
                old = len([age for age in ages if age > 30])
                
                print(f"     Recent (≤1 day): {recent}")
                print(f"     Week old (2-7 days): {week_old}")
                print(f"     Month old (8-30 days): {month_old}")
                print(f"     Old (>30 days): {old}")
        
        except Exception as e:
            logger.error(f"Error calculating age distribution: {e}")

def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Show Sentries status")
    parser.add_argument(
        '--repo-path', 
        default='.', 
        help='Path to git repository (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Initialize status reporter
    status_reporter = SentriesStatusReporter(repo_path=args.repo_path)
    
    # Show status
    status_reporter.show_status()

if __name__ == "__main__":
    main()
