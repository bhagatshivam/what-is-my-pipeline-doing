"""cli.py — entry point for the CI Pipeline Documentation Tool."""

import argparse
import sys

from tool1.single_pipeline import check_pipeline, document_pipeline
from tool2.multi_pipeline import check_repository, document_repository
from ir.validate import IRValidationError


EXIT_SUCCESS = 0
EXIT_CHECK_FAILED = 1
EXIT_OPERATIONAL_ERROR = 2
EXIT_INVALID_IR = 3


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
    tool1.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Layer 4 LLM beautification; write deterministic output only (no API key needed).",
    )

    tool2 = subparsers.add_parser("tool2", help="Document a whole repository's pipelines.")
    tool2.add_argument("path", help="Path to a repository (or its .github/workflows folder)")
    tool2.add_argument(
        "--check",
        action="store_true",
        help="Check the committed doc for drift instead of writing it.",
    )
    tool2.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Layer 4 LLM beautification; write deterministic output only (no API key needed).",
    )
    tool2.add_argument(
        "--inject",
        metavar="FILE",
        help="Inject the unified doc between <!-- ci-docs:start/end --> markers in FILE, "
             "instead of writing a standalone docs/<repo>.md file.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "tool1":
        try:
            if args.check:
                return EXIT_SUCCESS if check_pipeline(args.path) else EXIT_CHECK_FAILED
            written = document_pipeline(args.path, use_llm=not args.no_llm)
            print(f"Wrote {written}")
            return EXIT_SUCCESS
        except IRValidationError:
            return EXIT_INVALID_IR
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_OPERATIONAL_ERROR
    elif args.command == "tool2":
        try:
            if args.check:
                return EXIT_SUCCESS if check_repository(args.path, inject_into=args.inject) else EXIT_CHECK_FAILED
            written = document_repository(args.path, use_llm=not args.no_llm, inject_into=args.inject)
            print(f"Wrote {written}")
            return EXIT_SUCCESS
        except IRValidationError:
            return EXIT_INVALID_IR
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_OPERATIONAL_ERROR
    else:
        parser.print_help()

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
