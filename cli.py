"""cli.py — entry point for the CI Pipeline Documentation Tool."""

import argparse
import sys

from tool1.single_pipeline import check_pipeline, document_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="What is my CI pipeline doing? — automated CI pipeline documentation.",
    )
    subparsers = parser.add_subparsers(dest="command")

    tool1 = subparsers.add_parser("tool1", help="Document a single pipeline file.")
    tool1.add_argument("path", help="Path to a workflow file, e.g. .github/workflows/ci.yml")
    tool1.add_argument(
        "--check",
        action="store_true",
        help="Check the committed doc for drift instead of writing it.",
    )

    tool2 = subparsers.add_parser("tool2", help="Document a whole repository's pipelines.")
    tool2.add_argument("path", help="Path to a repository (or its workflows folder)")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "tool1":
        try:
            if args.check:
                return 0 if check_pipeline(args.path) else 1
            written = document_pipeline(args.path)
            print(f"Wrote {written}")
            return 0
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    elif args.command == "tool2":
        print(f"tool2 is not implemented yet (Phase 6). Requested: {args.path}")
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
