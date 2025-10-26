#!/usr/bin/env python3
"""
Test suite for CAMEL GitOperationsTool - Phase 2 validation.

Tests the Git operations tool with proper mocking of git_utils functions
to verify branch management, commits, and PR creation functionality.
"""

from unittest.mock import patch

import pytest

from sentries.camel.tools import GitOperationsTool


class TestGitOperationsTool:
    """Test suite for GitOperationsTool Phase 2 functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.git_tool = GitOperationsTool()

    @patch("sentries.camel.tools.create_branch")
    @patch("sentries.camel.tools.tag_branch_with_sentries_metadata")
    def test_create_feature_branch_success(self, mock_tag, mock_create):
        """Test successful feature branch creation with metadata."""
        # Arrange
        mock_create.return_value = "camel-test-fix-123"
        mock_tag.return_value = None

        # Act
        result = self.git_tool.create_feature_branch("test-branch", "testsentry")

        # Assert
        assert result["success"] is True
        assert result["branch_name"] == "camel-test-fix-123"
        assert "Created and tagged branch" in result["message"]

        # Verify calls
        mock_create.assert_called_once_with("test-branch", "testsentry")
        # Verify tag was called with branch, sentry_type, and a SHA (any SHA is fine)
        assert mock_tag.call_count == 1
        call_args = mock_tag.call_args[0]
        assert call_args[0] == "camel-test-fix-123"
        assert call_args[1] == "testsentry"
        assert len(call_args[2]) > 0  # SHA should be non-empty

    @patch("sentries.camel.tools.create_branch")
    def test_create_feature_branch_failure(self, mock_create):
        """Test branch creation failure handling."""
        # Arrange
        mock_create.side_effect = Exception("Git operation failed")

        # Act
        result = self.git_tool.create_feature_branch("test-branch", "testsentry")

        # Assert
        assert result["success"] is False
        assert result["branch_name"] == "test-branch"
        assert "Git operation failed" in result["error"]
        assert "Failed to create branch" in result["message"]

    @patch("sentries.camel.tools.commit_all")
    def test_commit_changes_success(self, mock_commit):
        """Test successful commit operation."""
        # Arrange
        mock_commit.return_value = None
        commit_message = "feat: Add test improvements"

        # Act
        result = self.git_tool.commit_changes(commit_message)

        # Assert
        assert result["success"] is True
        assert result["commit_message"] == commit_message
        assert "Changes committed successfully" in result["message"]
        mock_commit.assert_called_once_with(commit_message)

    @patch("sentries.camel.tools.commit_all")
    def test_commit_changes_with_files(self, mock_commit):
        """Test commit operation with specific files."""
        # Arrange
        mock_commit.return_value = None
        commit_message = "fix: Update specific files"
        files = ["file1.py", "file2.py"]

        # Act
        result = self.git_tool.commit_changes(commit_message, files)

        # Assert
        assert result["success"] is False
        assert result.get("unsupported") is True
        assert "not supported" in result["error"].lower()
        assert "not supported" in result["message"].lower()
        mock_commit.assert_not_called()

    @patch("sentries.camel.tools.commit_all")
    def test_commit_changes_failure(self, mock_commit):
        """Test commit failure handling."""
        # Arrange
        mock_commit.side_effect = Exception("Commit failed")

        # Act
        result = self.git_tool.commit_changes("test message")

        # Assert
        assert result["success"] is False
        assert "Commit failed" in result["error"]
        assert "Failed to commit" in result["message"]

    @patch("sentries.camel.tools.open_pull_request")
    @patch("sentries.camel.tools.get_base_branch")
    def test_create_pull_request_success(self, mock_get_base, mock_pr):
        """Test successful PR creation."""
        # Arrange
        mock_get_base.return_value = "main"
        mock_pr.return_value = {"url": "https://github.com/test/repo/pull/123"}

        title = "Test PR"
        body = "Test description"
        head_branch = "feature-branch"

        # Act
        result = self.git_tool.create_pull_request(title, body, head_branch)

        # Assert
        assert result["success"] is True
        assert result["pr_url"] == "https://github.com/test/repo/pull/123"
        assert result["title"] == title
        assert result["base_branch"] == "main"
        assert result["head_branch"] == head_branch

        mock_pr.assert_called_once_with(title=title, body=body, base="main", head=head_branch)

    @patch("sentries.camel.tools.open_pull_request")
    @patch("sentries.camel.tools.get_base_branch")
    def test_create_pull_request_without_head_branch(self, mock_get_base, mock_pr):
        """Test PR creation without specifying head branch."""
        # Arrange
        mock_get_base.return_value = "main"
        mock_pr.return_value = {"url": "https://github.com/test/repo/pull/124"}

        # Act
        result = self.git_tool.create_pull_request("Test PR", "Test body")

        # Assert
        assert result["success"] is True
        assert result["head_branch"] == "current"
        mock_pr.assert_called_once_with(title="Test PR", body="Test body", base="main", head=None)

    @patch("sentries.camel.tools.open_pull_request")
    @patch("sentries.camel.tools.get_base_branch")
    def test_create_pull_request_failure(self, mock_get_base, mock_pr):
        """Test PR creation failure handling."""
        # Arrange
        mock_get_base.return_value = "main"
        mock_pr.side_effect = Exception("PR creation failed")

        # Act
        result = self.git_tool.create_pull_request("Test PR", "Test body")

        # Assert
        assert result["success"] is False
        assert "PR creation failed" in result["error"]
        assert "Failed to create PR" in result["message"]

    @patch("sentries.camel.tools.get_base_branch")
    def test_get_repository_info_success(self, mock_get_base):
        """Test successful repository info retrieval."""
        # Arrange
        mock_get_base.return_value = "main"

        # Act
        result = self.git_tool.get_repository_info()

        # Assert
        assert result["success"] is True
        assert result["base_branch"] == "main"
        assert "Repository info retrieved" in result["message"]

    @patch("sentries.camel.tools.get_base_branch")
    def test_get_repository_info_failure(self, mock_get_base):
        """Test repository info retrieval failure."""
        # Arrange
        mock_get_base.side_effect = Exception("Git info failed")

        # Act
        result = self.git_tool.get_repository_info()

        # Assert
        assert result["success"] is False
        assert "Git info failed" in result["error"]
        assert "Failed to get repo info" in result["message"]


class TestGitOperationsToolIntegration:
    """Integration tests for GitOperationsTool workflow."""

    @patch("sentries.camel.tools.create_branch")
    @patch("sentries.camel.tools.tag_branch_with_sentries_metadata")
    @patch("sentries.camel.tools.commit_all")
    @patch("sentries.camel.tools.open_pull_request")
    @patch("sentries.camel.tools.get_base_branch")
    def test_full_git_workflow(self, mock_get_base, mock_pr, mock_commit, mock_tag, mock_create):
        """Test complete Git workflow: branch → commit → PR."""
        # Arrange
        git_tool = GitOperationsTool()
        mock_create.return_value = "camel-workflow-test"
        mock_get_base.return_value = "main"
        mock_pr.return_value = {"url": "https://github.com/test/repo/pull/125"}

        # Act - Full workflow
        branch_result = git_tool.create_feature_branch("workflow-test", "testsentry")
        commit_result = git_tool.commit_changes("feat: Test workflow changes")
        pr_result = git_tool.create_pull_request(
            "Test Workflow PR", "Complete workflow test", "camel-workflow-test"
        )

        # Assert - All operations successful
        assert branch_result["success"] is True
        assert commit_result["success"] is True
        assert pr_result["success"] is True

        # Verify call sequence
        mock_create.assert_called_once_with("workflow-test", "testsentry")
        # Verify tag was called with correct parameters including SHA
        assert mock_tag.call_count == 1
        tag_args = mock_tag.call_args[0]
        assert tag_args[0] == "camel-workflow-test"
        assert tag_args[1] == "testsentry"
        assert len(tag_args[2]) > 0  # SHA present
        mock_commit.assert_called_once_with("feat: Test workflow changes")
        mock_pr.assert_called_once()

        # Verify PR details
        assert pr_result["pr_url"] == "https://github.com/test/repo/pull/125"
        assert pr_result["base_branch"] == "main"
        assert pr_result["head_branch"] == "camel-workflow-test"

    def test_git_tool_error_propagation(self):
        """Test that GitOperationsTool properly propagates errors."""
        git_tool = GitOperationsTool()

        with patch("sentries.camel.tools.create_branch") as mock_create:
            mock_create.side_effect = RuntimeError("Critical Git error")

            result = git_tool.create_feature_branch("test", "testsentry")

            assert result["success"] is False
            assert "Critical Git error" in result["error"]
            assert isinstance(result["error"], str)  # Error converted to string


# Test data for GitOperationsTool validation
GIT_TOOL_TEST_SCENARIOS = [
    {
        "name": "standard_branch_creation",
        "branch_name": "feature-123",
        "sentry_type": "testsentry",
        "expected_calls": 1,
    },
    {
        "name": "special_characters_branch",
        "branch_name": "fix/issue-456",
        "sentry_type": "docsentry",
        "expected_calls": 1,
    },
    {
        "name": "long_branch_name",
        "branch_name": "very-long-branch-name-for-comprehensive-testing",
        "sentry_type": "testsentry",
        "expected_calls": 1,
    },
]


@pytest.mark.parametrize("scenario", GIT_TOOL_TEST_SCENARIOS)
def test_git_tool_branch_creation_scenarios(scenario):
    """Parameterized test for various branch creation scenarios."""
    with (
        patch("sentries.camel.tools.create_branch") as mock_create,
        patch("sentries.camel.tools.tag_branch_with_sentries_metadata") as mock_tag,
    ):

        mock_create.return_value = f"actual-{scenario['branch_name']}"

        git_tool = GitOperationsTool()
        result = git_tool.create_feature_branch(scenario["branch_name"], scenario["sentry_type"])

        assert result["success"] is True
        assert mock_create.call_count == scenario["expected_calls"]
        assert mock_tag.call_count == scenario["expected_calls"]
