"""jskim diff - Summarize only files/methods changed in a git diff.

Usage:
    jskim --diff <ref>              Compare working tree to ref
    jskim <dir> --diff <ref>        Same, scoped to directory
    git diff main | jskim --diff -  Read diff from stdin
"""

import re
import subprocess
import sys
from pathlib import Path

from .util import (
    parse_java_source, classify_method, instance_fields,
    format_method_annotations, format_calls, walk_types,
)


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
            hunk_match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
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
                new_line_num += 1  # context line

    if current is not None:
        files.append(current)

    return files


def _changes_overlap(changed_lines, start, end):
    """Check if any changed lines fall within [start, end]."""
    return any(start <= ln <= end for ln in changed_lines)


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
    if ".." in ref:
        return ref.split("..", 1)[0]
    return ref


def _method_keys(parsed):
    """Map ``Type.identity`` to the method dict for every method in a file, nested types included."""
    return {
        f"{label}.{m['identity']}": m
        for label, t in walk_types(parsed["types"]) for m in t["methods"]
    }


def _field_keys(parsed):
    """Return ``{key: label}`` for every instance field in a file, nested types included.

    The label is prefixed with the type name for every type except the
    file's primary type.
    """
    primary = parsed["types"][0]["name"] if parsed["types"] else None
    result = {}
    for type_label, t in walk_types(parsed["types"]):
        for f in instance_fields(t):
            label = f"{f['type']} {f['name']}" if f["name"] else f["type"]
            if type_label != primary:
                label = f"{type_label}.{label}"
            result[f"{type_label}:{label}"] = label
    return result


def _get_old_structure(base_ref, path, cwd=None):
    """Parse the old version of a file, or None if it cannot be retrieved."""
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{path}"],
        capture_output=True, text=True, cwd=cwd, check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return parse_java_source(result.stdout, source_name=path)
    except Exception:
        return None


def run_git_diff(ref, cwd=None):
    """Run git diff and return the output text."""
    try:
        result = subprocess.run(
            ["git", "diff", ref], capture_output=True, text=True, cwd=cwd, check=False,
        )
    except FileNotFoundError:
        print("Error: git not found", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        print(f"Error: git diff failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def _is_trivial(method):
    return classify_method(method) in ("getter", "setter", "boilerplate", "wiring")


def _append_method(out, tag, m):
    """Append a ``[TAG] L..-L.. (n lines): @Ann sig`` line plus its calls."""
    lines = m["end"] - m["start"] + 1
    ann_str = format_method_annotations(m)
    ann_str = f" {ann_str}" if ann_str else ""
    out.append(f"//   {tag:<10} L{m['start']}-L{m['end']} ({lines} lines):{ann_str} {m['sig']}")
    if m["calls"]:
        out.append(f"//     → {format_calls(m['calls'])}")


def _append_header(out, parsed):
    """Append the primary type's annotations and declaration."""
    if not parsed["types"]:
        return
    primary = parsed["types"][0]
    if primary["annotations"]:
        out.append(f"//   {' '.join(a['full'] for a in primary['annotations'])}")
    out.append(f"//   {primary['declaration']}")


def _load_parsed(git_root, path):
    """Parse the working-tree file at ``path``; returns (parsed, reason) on failure."""
    filepath = git_root / path
    if not filepath.exists():
        return None, "file not on disk"
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        return parse_java_source(content, source_name=path), None
    except Exception:
        return None, "parse error"


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
            java_files = [f for f in java_files if f["path"].startswith(prefix) or f["path"] == scope]

    if not java_files:
        return "// No Java files changed"

    added = [f for f in java_files if f["status"] == "added"]
    deleted = [f for f in java_files if f["status"] == "deleted"]
    modified = [f for f in java_files if f["status"] == "modified"]

    parts = []
    if modified:
        parts.append(f"{len(modified)} modified")
    if added:
        parts.append(f"{len(added)} added")
    if deleted:
        parts.append(f"{len(deleted)} deleted")
    out = [f"// === Changed Java Files ({len(java_files)} files: {', '.join(parts)}) ===", "//"]

    for f in deleted:
        out.append(f"// [DELETED] {f['path']}")
    if deleted and (added or modified):
        out.append("//")

    for f in added:
        parsed, reason = _load_parsed(git_root, f["path"])
        if parsed is None:
            out.append(f"// [NEW] {f['path']} ({reason})")
            out.append("//")
            continue
        out.append(f"// [NEW] {f['path']}")
        _append_header(out, parsed)
        fields = sum(len(instance_fields(t)) for _, t in walk_types(parsed["types"]))
        methods = [m for _, t in walk_types(parsed["types"]) for m in t["methods"]]
        out.append(f"//   {fields} fields, {len(methods)} methods, {parsed['total_lines']} lines")
        for m in methods:
            if not _is_trivial(m):
                _append_method(out, "[NEW]", m)
        out.append("//")

    for f in modified:
        parsed, reason = _load_parsed(git_root, f["path"])
        if parsed is None:
            out.append(f"// [MODIFIED] {f['path']} ({reason})")
            out.append("//")
            continue

        old = None
        if base_ref:
            old = _get_old_structure(base_ref, f.get("old_path", f["path"]), cwd=git_root)

        out.append(f"// {f['path']}")
        _append_header(out, parsed)

        changed_lines = f["changed_lines"]
        current_methods = _method_keys(parsed)
        old_methods = _method_keys(old) if old is not None else None

        new_methods, modified_methods = [], []
        unchanged_count = 0
        for key, m in current_methods.items():
            trivial = _is_trivial(m)
            if old_methods is not None and key not in old_methods:
                if trivial:
                    unchanged_count += 1
                else:
                    new_methods.append(m)
            elif _changes_overlap(changed_lines, m["decl_start"], m["end"]):
                if trivial:
                    unchanged_count += 1
                else:
                    modified_methods.append(m)
            else:
                unchanged_count += 1

        deleted_methods = []
        if old_methods is not None:
            deleted_methods = [old_methods[k] for k in sorted(set(old_methods) - set(current_methods))]

        field_changes = []
        if old is not None:
            old_fields = _field_keys(old)
            new_fields = _field_keys(parsed)
            field_changes = (
                [f"+{new_fields[k]}" for k in new_fields if k not in old_fields]
                + [f"-{old_fields[k]}" for k in old_fields if k not in new_fields]
            )
        if field_changes:
            out.append(f"//   {'[FIELDS]':<10} {', '.join(field_changes)}")

        for m in new_methods:
            _append_method(out, "[NEW]", m)
        for m in modified_methods:
            _append_method(out, "[MODIFIED]", m)
        for m in deleted_methods:
            out.append(f"//   {'[DELETED]':<10} {m['sig']}")

        if not (new_methods or modified_methods or deleted_methods or field_changes):
            out.append("//   (no field or method changes)")
        if unchanged_count:
            out.append(f"//   ({unchanged_count} other methods unchanged)")
        out.append("//")

    return "\n".join(out)


def main(args):
    """Run diff mode for ``args.diff`` scoped to ``args.paths[0]`` if given."""
    ref = args.diff
    scope_str = args.paths[0] if args.paths else None

    git_root = _find_git_root()
    if git_root is None:
        print("Error: not in a git repository", file=sys.stderr)
        sys.exit(1)

    if ref == "-":
        diff_text = sys.stdin.read()
        base_ref = None
    else:
        diff_text = run_git_diff(ref, cwd=git_root)
        base_ref = _resolve_base_ref(ref, cwd=git_root)

    changed_files = parse_diff_output(diff_text)

    scope = None
    if scope_str:
        scope_path = Path(scope_str).resolve()
        try:
            scope = str(scope_path.relative_to(git_root))
        except ValueError:
            print(f"Error: {scope_str} is not under git root {git_root}", file=sys.stderr)
            sys.exit(1)

    print(format_diff_output(changed_files, git_root, base_ref, scope))
