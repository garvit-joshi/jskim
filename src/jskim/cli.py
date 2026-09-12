"""jskim CLI - unified entry point for Java file skimming.

All flags are declared here once. The mode is chosen from the positional
arguments (file, directory, method names) and ``--diff``/``--list``; each
mode module receives the parsed namespace and never re-parses argv.
"""

import argparse
import sys
from pathlib import Path

USAGE = (
    "Usage:\n"
    "  jskim <file.java> [file2.java ...]              Summarize Java file(s)\n"
    "  jskim <file.java> --grep <pattern>               Filter methods by name\n"
    "  jskim <file.java> --annotation <@Ann>            Filter methods by annotation\n"
    "  jskim <file.java> <method> [method2 ...]         Extract method source code\n"
    "  jskim <file.java> --list                         List all methods\n"
    "  jskim <directory> [--deps] [--endpoints] [--beans]  Project structure map\n"
    "  jskim <directory> --package <prefix> | --annotation <@Ann> | --extends <C> | --implements <I>\n"
    "  jskim <directory> --callers Class.method [--depth N]  Show upstream callers\n"
    "  jskim <directory> --impact Class.method [--depth N]   Show callers + callees\n"
    "  jskim --diff <ref> [directory]                   Summarize changed files/methods\n"
    "  jskim --version                                  Show version"
)


def build_parser():
    """Build the single argparse parser shared by every mode."""
    parser = argparse.ArgumentParser(prog="jskim", usage=USAGE, add_help=False)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--grep")
    parser.add_argument("--annotation")
    parser.add_argument("--package")
    parser.add_argument("--extends")
    parser.add_argument("--implements")
    parser.add_argument("--callers")
    parser.add_argument("--impact")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--diff")
    parser.add_argument("--deps", action="store_true")
    parser.add_argument("--endpoints", action="store_true")
    parser.add_argument("--beans", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--version", "-V", action="store_true")
    parser.add_argument("--help", "-h", action="store_true")
    return parser


# Flags that only mean something in one mode. Anything else passed is reported
# rather than silently ignored.
MODE_FLAGS = {
    "project": {"deps", "endpoints", "beans", "package", "annotation", "extends",
                "implements", "callers", "impact", "depth"},
    "skim": {"grep", "annotation"},
    "method": {"list"},
    "diff": set(),
}
_ALL_MODE_FLAGS = set().union(*MODE_FLAGS.values())


def _warn_unused_flags(args, mode):
    """Print a warning for flags that the selected mode does not use."""
    defaults = vars(build_parser().parse_args([]))
    unused = sorted(
        flag for flag in _ALL_MODE_FLAGS - MODE_FLAGS[mode]
        if getattr(args, flag) != defaults[flag]
    )
    if unused:
        flags = ", ".join(f"--{f}" for f in unused)
        print(f"Warning: {flags} not used in {mode} mode, ignored", file=sys.stderr)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    args = build_parser().parse_intermixed_args(argv)

    if args.version:
        from . import __version__
        print(f"jskim {__version__}")
        return
    if args.help:
        print(USAGE, file=sys.stderr)
        return

    if args.diff:
        from .diff import main as diff_main
        _warn_unused_flags(args, "diff")
        diff_main(args)
        return

    if not args.paths:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    first = args.paths[0]
    if Path(first).is_dir():
        from .project import main as project_main
        _warn_unused_flags(args, "project")
        project_main(args)
        return

    if not first.endswith(".java"):
        print(f"Error: {first} is not a .java file or directory", file=sys.stderr)
        sys.exit(1)

    method_names = [p for p in args.paths[1:] if not p.endswith(".java")]
    if args.list or method_names:
        from .method import main as method_main
        _warn_unused_flags(args, "method")
        method_main(args)
        return

    from .skim import main as skim_main
    _warn_unused_flags(args, "skim")
    skim_main(args)


if __name__ == "__main__":
    main()
