"""Measure jskim output quality on a real Java source tree.

Usage: python scripts/audit_real.py <src_dir | File.java>

Prints the numbers that decide whether an output change helped the consumer:
parse errors, how many `→` calls cannot be followed, how many lines method
extraction skips, how many constructors collapse, what nested types hide,
and the size of the project map. Run it before and after an output change
and compare.
"""

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jskim.project import find_java_files, format_output, scan_java_file  # noqa: E402
from jskim.util import classify_method, parse_java_bytes, parse_java_source, walk_types  # noqa: E402


def _error_nodes(node, acc):
    if node.type == "ERROR" or node.is_missing:
        acc.append(node.start_point[0] + 1)
    for child in node.children:
        _error_nodes(child, acc)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="source directory, or one .java file")
    args = parser.parse_args()
    files = [args.path] if args.path.is_file() else find_java_files(args.path)
    if not files:
        sys.exit(f"No .java files under {args.path}")

    parse_errors = {}
    calls = collections.Counter()
    static_owner_missing = collections.Counter()
    methods = wiring = annotated = skipped_lines = 0
    nested_types = nested_methods = nested_fields = 0
    longest_static = 0
    project_types = {f.stem for f in files}

    for f in files:
        src = f.read_bytes()
        errors = []
        _error_nodes(parse_java_bytes(src), errors)
        if errors:
            parse_errors[f] = errors
        parsed = parse_java_source(src, f)
        project_types.update(t["name"] for _, t in walk_types(parsed["types"]))
        for label, t in walk_types(parsed["types"]):
            fields = {x["name"] for x in t["fields"]}
            if "." in label:
                nested_types += 1
                nested_methods += len(t["methods"])
                nested_fields += len(t["fields"])
            statics = [x for x in t["fields"] if x["static"]]
            longest_static = max(longest_static, len(", ".join(x["name"] for x in statics)))
            for m in t["methods"]:
                methods += 1
                if classify_method(m) == "wiring":
                    wiring += 1
                if m["noise_spans"]:
                    annotated += 1
                    skipped_lines += sum(s["end"] - s["start"] + 1 for s in m["noise_spans"])
                for call in m["calls"]:
                    if "." not in call:
                        calls["same-class"] += 1
                    else:
                        owner = call.rsplit(".", 1)[0]
                        if owner in fields or owner == "super":
                            calls["field"] += 1
                        else:
                            calls["static"] += 1
                            if owner not in project_types:
                                static_owner_missing[owner] += 1

    total_calls = sum(calls.values())
    file_infos = [scan_java_file(f) for f in files]
    project_map = format_output(file_infos)

    print(f"files: {len(files)}, parse errors in {len(parse_errors)} files")
    for path, lines in list(parse_errors.items())[:10]:
        print(f"  {path}: lines {lines[:5]}")
    print(f"methods: {methods}; wiring constructors collapsed: {wiring}; "
          f"methods with documentation annotations: {annotated}, lines extraction skips: {skipped_lines}")
    print(f"→ calls: {total_calls} ({dict(calls)})")
    unresolved = sum(static_owner_missing.values())
    print(f"static call owners outside the scanned tree (sibling modules are fine; JDK/library names are leaks): {unresolved}"
          + (f" e.g. {static_owner_missing.most_common(8)}" if unresolved else ""))
    print(f"nested types: {nested_types}; nested methods {nested_methods}, nested fields {nested_fields}")
    print(f"longest static-field line: {longest_static} chars")
    print(f"project map: {project_map.count(chr(10)) + 1} lines, {len(project_map.encode())} bytes")


if __name__ == "__main__":
    main()
