#!/usr/bin/env python3
"""
CodeSentry - Automated code analysis and test/documentation candidate detection.

CodeSentry scans repositories to identify:
1. New code that lacks tests
2. Code changes that need documentation updates
3. Test coverage gaps
4. Documentation synchronization opportunities
"""
import sys

from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from git import Repo, InvalidGitRepositoryError
import ast

from .banner import show_sentry_banner
from .runner_common import get_logger, TESTS_ALLOWLIST, DOCS_ALLOWLIST

logger = get_logger(__name__)


@dataclass
class CodeCandidate:
    """Represents a code candidate for testing or documentation."""
    file_path: str
    line_start: int
    line_end: int
    candidate_type: str  # 'test', 'doc', 'both'
    description: str
    complexity_score: float
    priority: str  # 'high', 'medium', 'low'


@dataclass
class AnalysisResult:
    """Result of code analysis."""
    untested_functions: List[CodeCandidate]
    undocumented_changes: List[CodeCandidate]
    test_coverage_gaps: List[CodeCandidate]
    documentation_needs: List[CodeCandidate]
    summary: Dict[str, int]


class CodeAnalyzer:
    """Analyzes code for testing and documentation opportunities."""

    def __init__(self, repo_path: str = "."):

        self.repo_path = Path(repo_path).resolve()
        self.repo = None
        self.test_files = set()
        self.source_files = set()

        try:
            self.repo = Repo(self.repo_path)
            logger.info(f"Analyzing repository: {self.repo_path}")
        except InvalidGitRepositoryError:
            logger.error(f"Not a git repository: {self.repo_path}")
            raise

    def analyze_repository(self) -> AnalysisResult:
        """Perform comprehensive code analysis."""
        logger.info("Starting code analysis...")

        # Discover files
        self._discover_files()

        # Analyze source code
        untested_functions = self._find_untested_functions()
        test_coverage_gaps = self._find_test_coverage_gaps()

        # Analyze recent changes
        undocumented_changes = self._find_undocumented_changes()
        documentation_needs = self._find_documentation_needs()

        # Create summary
        summary = {
            'untested_functions': len(untested_functions),
            'test_coverage_gaps': len(test_coverage_gaps),
            'undocumented_changes': len(undocumented_changes),
            'documentation_needs': len(documentation_needs),
            'total_candidates': len(untested_functions) + len(test_coverage_gaps)
            + len(undocumented_changes) + len(documentation_needs)
        }

        return AnalysisResult(
            untested_functions=untested_functions,
            undocumented_changes=undocumented_changes,
            test_coverage_gaps=test_coverage_gaps,
            documentation_needs=documentation_needs,
            summary=summary
        )

    def _discover_files(self):
        """Discover test and source files in the repository."""
        logger.info("Discovering files...")

        # Find test files
        for allowlist_path in TESTS_ALLOWLIST:
            test_pattern = self.repo_path / allowlist_path
            if test_pattern.exists():
                if test_pattern.is_file():
                    self.test_files.add(str(test_pattern))
                else:
                    for test_file in test_pattern.rglob("*.py"):
                        self.test_files.add(str(test_file))

        # Find source files (Python files not in tests)
        for py_file in self.repo_path.rglob("*.py"):
            file_path = str(py_file)
            if not any(test_pattern in file_path for test_pattern in self.test_files):
                self.source_files.add(file_path)

        logger.info(
            f"Found {len(self.test_files)} test files and {len(self.source_files)} source files")

    def _find_untested_functions(self) -> List[CodeCandidate]:
        """Find functions that don't have corresponding tests."""
        logger.info("Finding untested functions...")
        candidates = []

        for source_file in self.source_files:
            if not self._has_test_file(source_file):
                functions = self._extract_functions(source_file)
                for func in functions:
                    candidates.append(CodeCandidate(
                        file_path=source_file,
                        line_start=func['line_start'],
                        line_end=func['line_end'],
                        candidate_type='test',
                        description=f"Function '{func['name']}' lacks tests",
                        complexity_score=func['complexity'],
                        priority=self._calculate_priority(func['complexity'])
                    ))

        return candidates

    def _find_test_coverage_gaps(self) -> List[CodeCandidate]:
        """Find areas where test coverage could be improved."""
        logger.info("Finding test coverage gaps...")
        candidates = []

        # Look for complex functions with minimal tests
        for source_file in self.source_files:
            if self._has_test_file(source_file):
                functions = self._extract_functions(source_file)
                test_file = self._get_test_file(source_file)

                if test_file:
                    test_functions = self._extract_test_functions(test_file)
                    for func in functions:
                        if not self._has_comprehensive_tests(func, test_functions):
                            candidates.append(CodeCandidate(
                                file_path=source_file,
                                line_start=func['line_start'],
                                line_end=func['line_end'],
                                candidate_type='test',
                                description=f"Function '{func['name']}' needs more comprehensive tests",
                                complexity_score=func['complexity'],
                                priority=self._calculate_priority(func['complexity'])
                            ))

        return candidates

    def _find_undocumented_changes(self) -> List[CodeCandidate]:
        """Find recent code changes that need documentation updates."""
        logger.info("Finding undocumented changes...")
        candidates = []

        # Get recent commits
        recent_commits = list(self.repo.iter_commits('HEAD', max_count=10))

        for commit in recent_commits:
            for file_path in commit.stats.files:
                if self._is_source_file(file_path) and not self._is_test_file(file_path):
                    # Check if documentation exists for this change
                    if not self._has_documentation(file_path):
                        candidates.append(CodeCandidate(
                            file_path=file_path,
                            line_start=1,
                            line_end=1,
                            candidate_type='doc',
                            description=f"Recent changes in {file_path} need documentation",
                            complexity_score=1.0,
                            priority='medium'
                        ))

        return candidates

    def _find_documentation_needs(self) -> List[CodeCandidate]:
        """Find areas where documentation is missing or outdated."""
        logger.info("Finding documentation needs...")
        candidates = []

        for source_file in self.source_files:
            if not self._has_documentation(source_file):
                candidates.append(CodeCandidate(
                    file_path=source_file,
                    line_start=1,
                    line_end=1,
                    candidate_type='doc',
                    description=f"File {source_file} lacks documentation",
                    complexity_score=1.0,
                    priority='medium'
                ))

        return candidates

    def _has_test_file(self, source_file: str) -> bool:
        """Check if a source file has a corresponding test file."""
        source_path = Path(source_file)
        test_patterns = [
            source_path.parent / "tests" / f"test_{source_path.name}",
            source_path.parent / "tests" / f"{source_path.stem}_test.py",
            source_path.parent.parent / "tests" / f"test_{source_path.name}",
            source_path.parent.parent / "tests" / f"{source_path.stem}_test.py"
        ]

        return any(pattern.exists() for pattern in test_patterns)

    def _get_test_file(self, source_file: str) -> Optional[str]:
        """Get the path to the corresponding test file."""
        source_path = Path(source_file)
        test_patterns = [
            source_path.parent / "tests" / f"test_{source_path.name}",
            source_path.parent / "tests" / f"{source_path.stem}_test.py",
            source_path.parent.parent / "tests" / f"test_{source_path.name}",
            source_path.parent.parent / "tests" / f"{source_path.stem}_test.py"
        ]

        for pattern in test_patterns:
            if pattern.exists():
                return str(pattern)
        return None

    def _extract_functions(self, file_path: str) -> List[Dict]:
        """Extract function information from a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Calculate complexity (simplified)
                    complexity = 1
                    for child in ast.walk(node):
                        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                            complexity += 1

                    functions.append({
                        'name': node.name,
                        'line_start': node.lineno,
                        'line_end': node.end_lineno or node.lineno,
                        'complexity': complexity,
                        'docstring': ast.get_docstring(node)
                    })

            return functions
        except Exception as e:
            logger.warning(f"Error parsing {file_path}: {e}")
            return []

    def _extract_test_functions(self, test_file: str) -> List[Dict]:
        """Extract test function information from a test file."""
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            test_functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    test_functions.append({
                        'name': node.name,
                        'line_start': node.lineno,
                        'line_end': node.end_lineno or node.lineno
                    })

            return test_functions
        except Exception as e:
            logger.warning(f"Error parsing test file {test_file}: {e}")
            return []

    def _has_comprehensive_tests(self, func: Dict, test_functions: List[Dict]) -> bool:
        """Check if a function has comprehensive test coverage."""
        # Simple heuristic: if function has high complexity, it should have multiple tests
        if func['complexity'] > 3:
            return len([tf for tf in test_functions if tf['name'].endswith(func['name'])]) >= 2
        return len([tf for tf in test_functions if tf['name'].endswith(func['name'])]) >= 1

    def _is_source_file(self, file_path: str) -> bool:
        """Check if a file is a source file."""
        return file_path.endswith('.py') and 'test' not in file_path.lower()

    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file."""
        return 'test' in file_path.lower() or file_path.startswith('tests/')

    def _has_documentation(self, file_path: str) -> bool:
        """Check if a file has documentation."""
        # Check for docstrings in the file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            module_doc = ast.get_docstring(tree)

            if module_doc:
                return True

            # Check if any function has docstrings
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and ast.get_docstring(node):
                    return True

            return False
        except Exception:
            return False

    def _calculate_priority(self, complexity: float) -> str:
        """Calculate priority based on complexity."""
        if complexity > 5:
            return 'high'
        elif complexity > 2:
            return 'medium'
        else:
            return 'low'


class CodeSentry:
    """Main CodeSentry class for analyzing and reporting code candidates."""

    def __init__(self, repo_path: str = "."):

        self.analyzer = CodeAnalyzer(repo_path)
        self.results = None

    def analyze(self) -> AnalysisResult:
        """Analyze the repository for code candidates."""
        self.results = self.analyzer.analyze_repository()
        return self.results

    def generate_report(self) -> str:
        """Generate a human-readable report of findings."""
        if not self.results:
            self.analyze()

        report = []
        report.append("🔍 CodeSentry Analysis Report")
        report.append("=" * 50)
        report.append("")

        # Summary
        summary = self.results.summary
        report.append("📊 Summary")
        report.append(f"  • Untested functions: {summary['untested_functions']}")
        report.append(f"  • Test coverage gaps: {summary['test_coverage_gaps']}")
        report.append(f"  • Undocumented changes: {summary['undocumented_changes']}")
        report.append(f"  • Documentation needs: {summary['documentation_needs']}")
        report.append(f"  • Total candidates: {summary['total_candidates']}")
        report.append("")

        # High priority items
        high_priority = []
        for candidate_list in [self.results.untested_functions, self.results.test_coverage_gaps,
                               self.results.undocumented_changes, self.results.documentation_needs]:
            high_priority.extend([c for c in candidate_list if c.priority == 'high'])

        if high_priority:
            report.append("🚨 High Priority Items")
            for candidate in high_priority[:5]:  # Show top 5
                report.append(f"  • {candidate.description}")
                report.append(f"    File: {candidate.file_path}:{candidate.line_start}")
                report.append(f"    Type: {candidate.candidate_type}")
                report.append("")

        # Recommendations
        report.append("💡 Recommendations")
        if summary['untested_functions'] > 0:
            report.append("  • Run TestSentry to generate tests for untested functions")
        if summary['documentation_needs'] > 0:
            report.append("  • Run DocSentry to update documentation")
        if summary['test_coverage_gaps'] > 0:
            report.append("  • Improve test coverage for complex functions")

        return "\n".join(report)

    def get_test_candidates(self) -> List[CodeCandidate]:
        """Get candidates suitable for TestSentry."""
        if not self.results:
            self.analyze()

        return (self.results.untested_functions
                + self.results.test_coverage_gaps)

    def get_doc_candidates(self) -> List[CodeCandidate]:
        """Get candidates suitable for DocSentry."""
        if not self.results:
            self.analyze()

        return (self.results.undocumented_changes
                + self.results.documentation_needs)


def main():
    """Main entry point for CodeSentry CLI."""
    show_sentry_banner()
    print("🔍 CodeSentry - Code Analysis & Candidate Detection")
    print("=" * 60)

    try:
        # Initialize CodeSentry
        codesentry = CodeSentry()

        # Analyze repository
        print("🔍 Analyzing repository...")
        results = codesentry.analyze()

        # Generate and display report
        report = codesentry.generate_report()
        print(report)

        # Exit with appropriate code
        if results.summary['total_candidates'] > 0:
            print(f"\n⚠️  Found {results.summary['total_candidates']} candidates for improvement")
            sys.exit(1)
        else:
            print("\n✅ No improvement candidates found - repository is in good shape!")
            sys.exit(0)

    except Exception as e:
        logger.error(f"CodeSentry failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
