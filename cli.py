"""cli.py — entry point for the CI Pipeline Documentation Tool."""

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="What is my CI pipeline doing? — automated CI pipeline documentation.",
    )
    subparsers = parser.add_subparsers(dest="command")

    tool1 = subparsers.add_parser("tool1", help="Document a single pipeline file.")
    tool1.add_argument("path", help="Path to a workflow file, e.g. .github/workflows/ci.yml")

    tool2 = subparsers.add_parser("tool2", help="Document a whole repository's pipelines.")
    tool2.add_argument("path", help="Path to a repository (or its workflows folder)")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "tool1":
        print(f"tool1 is not implemented yet (Phase 4/5). Requested: {args.path}")
    elif args.command == "tool2":
        print(f"tool2 is not implemented yet (Phase 6). Requested: {args.path}")
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
