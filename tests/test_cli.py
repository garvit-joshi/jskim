"""Tests for jskim.cli — CLI routing and argument parsing."""

import subprocess
import sys
import pytest
from pathlib import Path
from tests.conftest import FIXTURES_DIR, fixture_path


def run_jskim(*args, expect_error=False):
    """Run jskim as a subprocess and return (stdout, stderr, returncode)."""
    result = subprocess.run(
        [sys.executable, "-m", "jskim.cli", *args],
        capture_output=True,
        text=True,
    )
    if not expect_error:
        assert result.returncode == 0, f"jskim failed: {result.stderr}"
    return result.stdout, result.stderr, result.returncode


class TestCliRouting:
    def test_no_args_shows_usage(self):
        _, stderr, code = run_jskim(expect_error=True)
        assert code != 0
        assert "Usage" in stderr

    def test_help_flag(self):
        stdout, stderr, code = run_jskim("--help")
        assert code == 0
        assert "Usage" in stderr or "Usage" in stdout

    def test_version_flag(self):
        stdout, _, code = run_jskim("--version")
        assert code == 0
        assert "jskim" in stdout

    def test_non_java_file(self):
        _, stderr, code = run_jskim("foo.txt", expect_error=True)
        assert code != 0
        assert "not a .java file" in stderr

    def test_nonexistent_file(self):
        _, stderr, code = run_jskim("nonexistent.java", expect_error=True)
        assert code != 0
        assert "not found" in stderr


class TestSkimMode:
    def test_single_file(self):
        path = str(fixture_path("SimpleDirection.java"))
        stdout, _, _ = run_jskim(path)
        assert "SimpleDirection" in stdout
        assert "total:" in stdout

    def test_multiple_files(self):
        path1 = str(fixture_path("SimpleDirection.java"))
        path2 = str(fixture_path("StatusEnum.java"))
        stdout, _, _ = run_jskim(path1, path2)
        assert "SimpleDirection" in stdout
        assert "Status" in stdout

    def test_grep_filter(self):
        path = str(fixture_path("ScheduleServiceProxy.java"))
        stdout, _, _ = run_jskim(path, "--grep", "fetch")
        assert "fetch" in stdout.lower()

    def test_annotation_filter(self):
        path = str(fixture_path("AppConfiguration.java"))
        stdout, _, _ = run_jskim(path, "--annotation", "@Bean")
        assert "@Bean" in stdout


class TestMethodMode:
    def test_list_methods(self):
        path = str(fixture_path("ScheduleServiceProxy.java"))
        stdout, _, _ = run_jskim(path, "--list")
        assert "fetchOfficesForBusinessUnitId" in stdout
        assert "fetchShiftsForBusinessUnitId" in stdout

    def test_extract_method(self):
        path = str(fixture_path("BillingCalculator.java"))
        stdout, _, _ = run_jskim(path, "isSingleEscortTrip")
        assert "isSingleEscortTrip" in stdout
        assert "|" in stdout  # line numbers

    def test_extract_multiple_methods(self):
        path = str(fixture_path("ScheduleServiceProxy.java"))
        stdout, _, _ = run_jskim(
            path, "fetchOfficesForBusinessUnitId", "fetchShiftsForBusinessUnitId"
        )
        assert "fetchOfficesForBusinessUnitId" in stdout
        assert "fetchShiftsForBusinessUnitId" in stdout


class TestProjectMode:
    def test_directory_scan(self):
        stdout, _, _ = run_jskim(str(FIXTURES_DIR))
        assert "Project Map:" in stdout

    def test_deps_flag(self):
        stdout, _, _ = run_jskim(str(FIXTURES_DIR), "--deps")
        assert "Project Map:" in stdout

    def test_beans_flag(self):
        stdout, _, _ = run_jskim(str(FIXTURES_DIR), "--beans")
        assert "Project Map:" in stdout


class TestOutputFormat:
    def test_all_lines_comment_prefixed_skim(self):
        path = str(fixture_path("SimpleDirection.java"))
        stdout, _, _ = run_jskim(path)
        for line in stdout.strip().split("\n"):
            assert line.startswith("//"), f"Non-comment line: {line!r}"

    def test_all_lines_comment_prefixed_project(self):
        stdout, _, _ = run_jskim(str(FIXTURES_DIR))
        for line in stdout.strip().split("\n"):
            assert line.startswith("//"), f"Non-comment line: {line!r}"

    def test_all_lines_comment_prefixed_list(self):
        path = str(fixture_path("SimpleDirection.java"))
        stdout, _, _ = run_jskim(path, "--list")
        for line in stdout.strip().split("\n"):
            assert line.startswith("//"), f"Non-comment line: {line!r}"
