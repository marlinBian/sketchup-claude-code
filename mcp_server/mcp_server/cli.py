"""Command line entry point for SketchUp Agent Harness."""

import argparse
import json
import sys

from mcp_server.project_init import init_project


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="sketchup-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a design project")
    init_parser.add_argument("project_path", help="Directory to create or initialize")
    init_parser.add_argument("--name", dest="project_name", help="Project name")
    init_parser.add_argument(
        "--template",
        choices=["empty", "bathroom"],
        default="empty",
        help="Initial project template",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing generated project files",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            result = init_project(
                args.project_path,
                project_name=args.project_name,
                template=args.template,
                overwrite=args.force,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
