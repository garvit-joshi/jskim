"""Tests for jskim.diff — git diff summarization."""

import pytest
from jskim.diff import parse_diff_output, _changes_overlap, _resolve_base_ref, format_diff_output
from pathlib import Path
from tests.conftest import FIXTURES_DIR, fixture_path


# ---------------------------------------------------------------------------
# parse_diff_output
# ---------------------------------------------------------------------------

class TestParseDiffOutput:
    def test_empty_diff(self):
        assert parse_diff_output("") == []

    def test_added_file(self):
        diff = (
            "diff --git a/Foo.java b/Foo.java\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/Foo.java\n"
            "@@ -0,0 +1,3 @@\n"
            "+package com.example;\n"
            "+public class Foo {}\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["status"] == "added"
        assert files[0]["path"] == "Foo.java"
        assert 1 in files[0]["changed_lines"]
        assert 2 in files[0]["changed_lines"]

    def test_deleted_file(self):
        diff = (
            "diff --git a/Bar.java b/Bar.java\n"
            "deleted file mode 100644\n"
            "--- a/Bar.java\n"
            "+++ /dev/null\n"
            "@@ -1,3 +0,0 @@\n"
            "-package com.example;\n"
            "-public class Bar {}\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["status"] == "deleted"

    def test_modified_file(self):
        diff = (
            "diff --git a/Foo.java b/Foo.java\n"
            "--- a/Foo.java\n"
            "+++ b/Foo.java\n"
            "@@ -1,3 +1,4 @@\n"
            " package com.example;\n"
            "-public class Foo {}\n"
            "+public class Foo {\n"
            "+    int x;\n"
            "+}\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["status"] == "modified"
        # Line 2 was modified (old line removed, new lines added starting at line 2)
        assert 2 in files[0]["changed_lines"]

    def test_multiple_files(self):
        diff = (
            "diff --git a/A.java b/A.java\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/A.java\n"
            "@@ -0,0 +1,1 @@\n"
            "+class A {}\n"
            "diff --git a/B.java b/B.java\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/B.java\n"
            "@@ -0,0 +1,1 @@\n"
            "+class B {}\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 2
        paths = {f["path"] for f in files}
        assert "A.java" in paths
        assert "B.java" in paths

    def test_multiple_hunks(self):
        diff = (
            "diff --git a/Foo.java b/Foo.java\n"
            "--- a/Foo.java\n"
            "+++ b/Foo.java\n"
            "@@ -1,3 +1,3 @@\n"
            " line1\n"
            "-old\n"
            "+new\n"
            " line3\n"
            "@@ -10,3 +10,4 @@\n"
            " line10\n"
            "+added\n"
            " line11\n"
            " line12\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        changed = files[0]["changed_lines"]
        assert 2 in changed  # first hunk
        assert 11 in changed  # second hunk

    def test_renamed_file(self):
        diff = (
            "diff --git a/OldName.java b/NewName.java\n"
            "rename from OldName.java\n"
            "rename to NewName.java\n"
            "--- a/OldName.java\n"
            "+++ b/NewName.java\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["old_path"] == "OldName.java"
        assert files[0]["path"] == "NewName.java"

    def test_context_lines_track_position(self):
        diff = (
            "diff --git a/Foo.java b/Foo.java\n"
            "--- a/Foo.java\n"
            "+++ b/Foo.java\n"
            "@@ -1,5 +1,6 @@\n"
            " line1\n"
            " line2\n"
            " line3\n"
            "+inserted\n"
            " line4\n"
            " line5\n"
        )
        files = parse_diff_output(diff)
        changed = files[0]["changed_lines"]
        assert 4 in changed  # inserted line at position 4

    def test_deletion_marks_position(self):
        diff = (
            "diff --git a/Foo.java b/Foo.java\n"
            "--- a/Foo.java\n"
            "+++ b/Foo.java\n"
            "@@ -1,4 +1,3 @@\n"
            " line1\n"
            "-removed\n"
            " line3\n"
            " line4\n"
        )
        files = parse_diff_output(diff)
        changed = files[0]["changed_lines"]
        # Deletion at new-file position 2 (where the removed line was)
        assert 2 in changed

    def test_no_newline_at_end(self):
        diff = (
            "diff --git a/Foo.java b/Foo.java\n"
            "--- a/Foo.java\n"
            "+++ b/Foo.java\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "\\ No newline at end of file\n"
            "+new\n"
            "\\ No newline at end of file\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        assert 1 in files[0]["changed_lines"]

    def test_non_java_files_included(self):
        """parse_diff_output doesn't filter by extension — that's done later."""
        diff = (
            "diff --git a/readme.md b/readme.md\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/readme.md\n"
            "@@ -0,0 +1,1 @@\n"
            "+# readme\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["path"] == "readme.md"


# ---------------------------------------------------------------------------
# _changes_overlap
# ---------------------------------------------------------------------------

class TestChangesOverlap:
    def test_overlap_start(self):
        assert _changes_overlap({5, 6, 7}, 5, 10) is True

    def test_overlap_end(self):
        assert _changes_overlap({10}, 5, 10) is True

    def test_overlap_middle(self):
        assert _changes_overlap({7}, 5, 10) is True

    def test_no_overlap_before(self):
        assert _changes_overlap({3, 4}, 5, 10) is False

    def test_no_overlap_after(self):
        assert _changes_overlap({11, 12}, 5, 10) is False

    def test_empty_changes(self):
        assert _changes_overlap(set(), 5, 10) is False

    def test_single_line_range(self):
        assert _changes_overlap({5}, 5, 5) is True

    def test_single_line_no_match(self):
        assert _changes_overlap({6}, 5, 5) is False


# ---------------------------------------------------------------------------
# _resolve_base_ref
# ---------------------------------------------------------------------------

class TestResolveBaseRef:
    def test_simple_ref(self):
        assert _resolve_base_ref("HEAD~1") == "HEAD~1"

    def test_branch_name(self):
        assert _resolve_base_ref("main") == "main"

    def test_commit_hash(self):
        assert _resolve_base_ref("abc123") == "abc123"

    def test_double_dot_range(self):
        assert _resolve_base_ref("main..feature") == "main"

    def test_triple_dot_fallback(self):
        """If git merge-base fails, falls back to left side."""
        result = _resolve_base_ref("nonexistent1...nonexistent2", cwd="/tmp")
        assert result == "nonexistent1"


# ---------------------------------------------------------------------------
# format_diff_output
# ---------------------------------------------------------------------------

class TestFormatDiffOutput:
    def test_no_java_files(self):
        changed = [{"path": "readme.md", "status": "added", "changed_lines": set()}]
        output = format_diff_output(changed, Path("/tmp"), None)
        assert "No Java files changed" in output

    def test_added_java_file(self):
        """Test with a real fixture file marked as added."""
        changed = [{
            "path": str(fixture_path("SimpleDirection.java").relative_to(FIXTURES_DIR.parent.parent)),
            "old_path": str(fixture_path("SimpleDirection.java").relative_to(FIXTURES_DIR.parent.parent)),
            "status": "added",
            "changed_lines": set(range(1, 20)),
        }]
        output = format_diff_output(changed, FIXTURES_DIR.parent.parent, None)
        assert "[NEW]" in output
        assert "SimpleDirection" in output

    def test_deleted_java_file(self):
        changed = [{
            "path": "src/Deleted.java",
            "old_path": "src/Deleted.java",
            "status": "deleted",
            "changed_lines": set(),
        }]
        output = format_diff_output(changed, Path("/tmp"), None)
        assert "[DELETED]" in output
        assert "Deleted.java" in output

    def test_scope_filter(self):
        changed = [
            {
                "path": "src/main/Foo.java",
                "old_path": "src/main/Foo.java",
                "status": "added",
                "changed_lines": set(),
            },
            {
                "path": "src/test/Bar.java",
                "old_path": "src/test/Bar.java",
                "status": "added",
                "changed_lines": set(),
            },
        ]
        output = format_diff_output(changed, Path("/tmp"), None, scope="src/main")
        assert "Foo.java" in output
        # Bar.java should be filtered out
        assert "Bar.java" not in output

    def test_file_scope_filter(self):
        changed = [
            {
                "path": "Foo.java",
                "old_path": "Foo.java",
                "status": "modified",
                "changed_lines": set(),
            },
            {
                "path": "Bar.java",
                "old_path": "Bar.java",
                "status": "modified",
                "changed_lines": set(),
            },
        ]
        output = format_diff_output(changed, Path("/tmp"), None, scope="Foo.java")
        assert "Foo.java" in output

    def test_summary_header(self):
        changed = [
            {
                "path": "A.java",
                "old_path": "A.java",
                "status": "added",
                "changed_lines": set(),
            },
            {
                "path": "B.java",
                "old_path": "B.java",
                "status": "modified",
                "changed_lines": set(),
            },
            {
                "path": "C.java",
                "old_path": "C.java",
                "status": "deleted",
                "changed_lines": set(),
            },
        ]
        output = format_diff_output(changed, Path("/tmp"), None)
        assert "3 files" in output
        assert "modified" in output
        assert "added" in output
        assert "deleted" in output

    def test_modified_file_with_real_fixture(self):
        """Test modified file output using a real fixture."""
        rel_path = str(
            fixture_path("StaticFieldService.java").relative_to(FIXTURES_DIR.parent.parent)
        )
        changed = [{
            "path": rel_path,
            "old_path": rel_path,
            "status": "modified",
            "changed_lines": {33, 34, 35, 36},  # processOrder method lines
        }]
        output = format_diff_output(changed, FIXTURES_DIR.parent.parent, None)
        assert "StaticFieldService" in output


# ---------------------------------------------------------------------------
# Integration: parse then format
# ---------------------------------------------------------------------------

class TestDiffIntegration:
    def test_parse_and_format_added(self):
        """End-to-end: parse a diff for a new file and format it."""
        diff = (
            "diff --git a/tests/fixtures/SimpleDirection.java b/tests/fixtures/SimpleDirection.java\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/tests/fixtures/SimpleDirection.java\n"
            "@@ -0,0 +1,17 @@\n"
            "+package com.example;\n"
            "+\n"
            "+public enum SimpleDirection {\n"
            "+    NORTH,\n"
            "+    SOUTH,\n"
            "+    EAST,\n"
            "+    WEST;\n"
            "+\n"
            "+    public boolean isVertical() {\n"
            "+        return this == NORTH || this == SOUTH;\n"
            "+    }\n"
            "+\n"
            "+    public boolean isHorizontal() {\n"
            "+        return this == EAST || this == WEST;\n"
            "+    }\n"
            "+}\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 1
        assert files[0]["status"] == "added"
        output = format_diff_output(files, FIXTURES_DIR.parent.parent, None)
        assert "[NEW]" in output
        assert "SimpleDirection" in output

    def test_parse_and_format_mixed(self):
        """Parse a diff with multiple file statuses."""
        diff = (
            "diff --git a/Added.java b/Added.java\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            "+++ b/Added.java\n"
            "@@ -0,0 +1,1 @@\n"
            "+class Added {}\n"
            "diff --git a/Deleted.java b/Deleted.java\n"
            "deleted file mode 100644\n"
            "--- a/Deleted.java\n"
            "+++ /dev/null\n"
            "@@ -1,1 +0,0 @@\n"
            "-class Deleted {}\n"
        )
        files = parse_diff_output(diff)
        assert len(files) == 2
        statuses = {f["status"] for f in files}
        assert "added" in statuses
        assert "deleted" in statuses
