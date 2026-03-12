"""jskim diff - Summarize only files/methods changed in a git diff.

Usage:
    jskim --diff <ref>              Compare working tree to ref
    jskim <dir> --diff <ref>        Same, scoped to directory
    git diff main | jskim --diff -  Read diff from stdin
"""

import sys
import re
import subprocess
from pathlib import Path
from .skim import parse_java, classify_method


def parse_diff_output(diff_text):
    """Parse unified diff into structured file change info.

    Returns list of dicts:
      {
        "old_path": str,          # file path (a-side)
        "path": str,              # file path (b-side / new)
        "status": str,            # "added", "deleted", or "modified"
        "changed_lines": set,     # new-file line numbers that were added/touched
      }
    """
    files = []
    current = None
    new_line_num = 0
    in_hunk = False

    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            if current is not None:
                files.append(current)
            match = re.match(r"diff --git a/(.*) b/(.*)", line)
            if match:
                current = {
                    "old_path": match.group(1),
                    "path": match.group(2),
                    "status": "modified",
                    "changed_lines": set(),
                }
            else:
                current = None
            in_hunk = False
            continue

        if current is None:
            continue

        if line.startswith("new file"):
            current["status"] = "added"
        elif line.startswith("deleted file"):
            current["status"] = "deleted"
        elif line.startswith("rename from "):
            current["old_path"] = line[len("rename from "):]
        elif line.startswith("@@ "):
            hunk_match = re.match(
                r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line
            )
            if hunk_match:
                new_line_num = int(hunk_match.group(1))
                in_hunk = True
        elif in_hunk:
            if line.startswith("+") and not line.startswith("+++"):
                current["changed_lines"].add(new_line_num)
                new_line_num += 1
            elif line.startswith("-") and not line.startswith("---"):
                # Deletion: mark this position as a change point
                current["changed_lines"].add(new_line_num)
            elif line.startswith("\\"):
                pass  # "\ No newline at end of file"
            else:
                # Context line
                new_line_num += 1

    if current is not None:
        files.append(current)

    return files


def _changes_overlap(changed_lines, start, end):
    """Check if any changed lines fall within [start, end]."""
    for ln in changed_lines:
        if start <= ln <= end:
            return True
    return False


def _find_git_root(start_dir=None):
    """Find the git repository root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, cwd=start_dir, check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip())


def _resolve_base_ref(ref, cwd=None):
    """Resolve the base commit ref for git show.

    For 'A...B' (merge-base) syntax, resolves to the merge base commit.
    For 'A..B' syntax, returns A.
    For simple refs (HEAD~1, main, abc123), returns the ref unchanged.
    """
    if "..." in ref:
        parts = ref.split("...", 1)
        result = subprocess.run(
            ["git", "merge-base", parts[0], parts[1]],
            capture_output=True, text=True, cwd=cwd, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return parts[0]
    elif ".." in ref:
        return ref.split("..", 1)[0]
    return ref


def _get_old_method_names(base_ref, path, cwd=None):
    """Get method names from the old version of a file.

    Returns a set of method names, or None if the old file cannot be retrieved.
    """
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{path}"],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    if result.returncode != 0:
        return None
    try:
        parsed = parse_java(result.stdout)
        names = set()
        for m in parsed["methods"]:
            name_match = re.search(r"(\w+)\s*\(", m["sig"])
            if name_match:
                names.add(name_match.group(1))
        return names
    except Exception:
        return None


def run_git_diff(ref, cwd=None):
    """Run git diff and return the output text."""
    cmd = ["git", "diff", ref]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, check=False,
        )
    except FileNotFoundError:
        print("Error: git not found", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"Error: git diff failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    return result.stdout


def format_diff_output(changed_files, git_root, base_ref, scope=None):
    """Format diff analysis into compact output.

    Args:
        changed_files: list from parse_diff_output
        git_root: Path to git repository root
        base_ref: resolved base ref for git show (None for stdin mode)
        scope: optional path prefix to filter results (relative to git root)
    """
    java_files = [f for f in changed_files if f["path"].endswith(".java")]

    if scope:
        if scope.endswith(".java"):
            java_files = [f for f in java_files if f["path"] == scope]
        else:
            prefix = scope.rstrip("/") + "/"
            java_files = [
                f for f in java_files
                if f["path"].startswith(prefix) or f["path"] == scope
            ]

    if not java_files:
        return "// No Java files changed"

    added = [f for f in java_files if f["status"] == "added"]
    deleted = [f for f in java_files if f["status"] == "deleted"]
    modified = [f for f in java_files if f["status"] == "modified"]

    out = []
    parts = []
    if modified:
        parts.append(f"{len(modified)} modified")
    if added:
        parts.append(f"{len(added)} added")
    if deleted:
        parts.append(f"{len(deleted)} deleted")
    out.append(
        f"// === Changed Java Files ({len(java_files)} files: {', '.join(parts)}) ==="
    )
    out.append("//")

    # --- Deleted files ---
    for f in deleted:
        out.append(f"// [DELETED] {f['path']}")

    if deleted and (added or modified):
        out.append("//")

    # --- Added files ---
    for f in added:
        filepath = git_root / f["path"]
        if not filepath.exists():
            out.append(f"// [NEW] {f['path']} (file not on disk)")
            out.append("//")
            continue

        content = filepath.read_text(encoding="utf-8", errors="replace")
        try:
            parsed = parse_java(content)
        except Exception:
            out.append(f"// [NEW] {f['path']} (parse error)")
            out.append("//")
            continue

        out.append(f"// [NEW] {f['path']}")
        if parsed["class_annotations"]:
            out.append(f"//   {' '.join(parsed['class_annotations'])}")
        out.append(f"//   {parsed['class_declaration']}")
        fc = len(parsed["fields"])
        mc = len(parsed["methods"])
        out.append(f"//   {fc} fields, {mc} methods, {parsed['total_lines']} lines")

        for m in parsed["methods"]:
            kind = classify_method(m["sig"])
            if kind in ("getter", "setter", "boilerplate"):
                continue
            lines = m["end"] - m["start"] + 1
            ann_str = ""
            if m["annotations"]:
                ann_str = " " + " ".join(m["annotations"])
            out.append(
                f"//   [NEW] L{m['start']}-L{m['end']} ({lines} lines):{ann_str} {m['sig']}"
            )
        out.append("//")

    # --- Modified files ---
    for f in modified:
        filepath = git_root / f["path"]
        if not filepath.exists():
            out.append(f"// [MODIFIED] {f['path']} (file not on disk)")
            out.append("//")
            continue

        content = filepath.read_text(encoding="utf-8", errors="replace")
        try:
            parsed = parse_java(content)
        except Exception:
            out.append(f"// [MODIFIED] {f['path']} (parse error)")
            out.append("//")
            continue

        changed_lines = f["changed_lines"]

        # Get old method names for NEW/DELETED detection
        old_method_names = None
        if base_ref:
            old_path = f.get("old_path", f["path"])
            old_method_names = _get_old_method_names(base_ref, old_path, cwd=git_root)

        out.append(f"// {f['path']}")
        if parsed["class_annotations"]:
            out.append(f"//   {' '.join(parsed['class_annotations'])}")
        out.append(f"//   {parsed['class_declaration']}")

        new_methods = []
        modified_methods = []
        unchanged_count = 0

        current_method_names = set()
        for m in parsed["methods"]:
            name_match = re.search(r"(\w+)\s*\(", m["sig"])
            name = name_match.group(1) if name_match else m["sig"]
            current_method_names.add(name)

            kind = classify_method(m["sig"])
            is_trivial = kind in ("getter", "setter", "boilerplate")

            if old_method_names is not None and name not in old_method_names:
                # Method exists in current but not in old -> NEW
                if not is_trivial:
                    new_methods.append(m)
                else:
                    unchanged_count += 1
            elif _changes_overlap(changed_lines, m["start"], m["end"]):
                # Method exists in both (or can't determine), hunks overlap -> MODIFIED
                if not is_trivial:
                    modified_methods.append(m)
                else:
                    unchanged_count += 1
            else:
                unchanged_count += 1

        # Detect deleted methods
        deleted_method_names = []
        if old_method_names is not None:
            deleted_method_names = sorted(old_method_names - current_method_names)

        for m in new_methods:
            lines = m["end"] - m["start"] + 1
            ann_str = ""
            if m["annotations"]:
                ann_str = " " + " ".join(m["annotations"])
            out.append(
                f"//   [NEW]      L{m['start']}-L{m['end']} ({lines} lines):{ann_str} {m['sig']}"
            )

        for m in modified_methods:
            lines = m["end"] - m["start"] + 1
            ann_str = ""
            if m["annotations"]:
                ann_str = " " + " ".join(m["annotations"])
            out.append(
                f"//   [MODIFIED] L{m['start']}-L{m['end']} ({lines} lines):{ann_str} {m['sig']}"
            )

        for name in deleted_method_names:
            out.append(f"//   [DELETED]  {name}()")

        if not new_methods and not modified_methods and not deleted_method_names:
            out.append("//   (non-method changes only)")

        if unchanged_count:
            out.append(f"//   ({unchanged_count} other methods unchanged)")

        out.append("//")

    return "\n".join(out)


def _parse_args(argv):
    """Parse CLI arguments for diff mode.

    Returns (ref, scope_path_str) where scope_path_str may be None.
    """
    ref = None
    scope = None
    i = 0
    while i < len(argv):
        if argv[i] == "--diff" and i + 1 < len(argv):
            ref = argv[i + 1]
            i += 2
        elif not argv[i].startswith("--"):
            scope = argv[i]
            i += 1
        else:
            i += 1
    return ref, scope


def main():
    ref, scope_str = _parse_args(sys.argv[1:])

    if not ref:
        print(
            "Usage: jskim --diff <ref> [directory]\n"
            "       git diff main | jskim --diff -",
            file=sys.stderr,
        )
        sys.exit(1)

    git_root = _find_git_root()
    if git_root is None:
        print("Error: not in a git repository", file=sys.stderr)
        sys.exit(1)

    # Read diff from stdin or run git diff
    if ref == "-":
        diff_text = sys.stdin.read()
        base_ref = None
    else:
        diff_text = run_git_diff(ref, cwd=git_root)
        base_ref = _resolve_base_ref(ref, cwd=git_root)

    changed_files = parse_diff_output(diff_text)

    # Resolve scope path relative to git root
    scope = None
    if scope_str:
        scope_path = Path(scope_str).resolve()
        try:
            scope = str(scope_path.relative_to(git_root))
        except ValueError:
            print(
                f"Error: {scope_str} is not under git root {git_root}",
                file=sys.stderr,
            )
            sys.exit(1)

    print(format_diff_output(changed_files, git_root, base_ref, scope))
