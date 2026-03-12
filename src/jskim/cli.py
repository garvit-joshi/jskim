"""jskim CLI - unified entry point for Java file skimming."""

import sys
from pathlib import Path


def _print_usage():
    print(
        "Usage:\n"
        "  jskim <file.java> [file2.java ...]              Summarize Java file(s)\n"
        "  jskim <file.java> --grep <pattern>               Filter methods by name\n"
        "  jskim <file.java> --annotation <@Ann>            Filter methods by annotation\n"
        "  jskim <file.java> <method> [method2 ...]         Extract method source code\n"
        "  jskim <file.java> --list                         List all methods\n"
        "  jskim <directory> [--deps] [--endpoints] [--beans]  Project structure map\n"
        "  jskim --version                                  Show version",
        file=sys.stderr,
    )


# Flags that consume the next argument as a value
_FLAGS_WITH_VALUE = {"--grep", "--annotation", "--package", "--extends", "--implements"}


def main():
    if len(sys.argv) < 2:
        _print_usage()
        sys.exit(1)

    if sys.argv[1] in ("--version", "-V"):
        from . import __version__
        print(f"jskim {__version__}")
        return

    if sys.argv[1] in ("--help", "-h"):
        _print_usage()
        return

    first_arg = sys.argv[1]
    first_path = Path(first_arg)

    # Directory -> project mode
    if first_path.is_dir():
        from .project import main as project_main
        project_main()
        return

    # Must be a .java file from here
    if not first_arg.endswith(".java"):
        print(f"Error: {first_arg} is not a .java file or directory", file=sys.stderr)
        sys.exit(1)

    # --list flag -> method mode
    if "--list" in sys.argv:
        from .method import main as method_main
        method_main()
        return

    # Check remaining args for method names (non-flag, non-.java positional args)
    has_method_args = False
    skip_next = False
    for arg in sys.argv[2:]:
        if skip_next:
            skip_next = False
            continue
        if arg in _FLAGS_WITH_VALUE:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        if arg.endswith(".java"):
            continue
        # Non-flag, non-.java positional arg -> method name
        has_method_args = True
        break

    if has_method_args:
        from .method import main as method_main
        method_main()
    else:
        from .skim import main as skim_main
        skim_main()


if __name__ == "__main__":
    main()
