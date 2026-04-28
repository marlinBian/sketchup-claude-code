"""Command line entry point for SketchUp Agent Harness."""

import argparse
import json
import sys

from mcp_server.bridge_install import install_bridge
from mcp_server.doctor import run_doctor
from mcp_server.project_state import read_project_state
from mcp_server.project_init import init_project
from mcp_server.runtime_skills import install_runtime_skills
from mcp_server.smoke import DEFAULT_SMOKE_PROJECT, run_smoke, validate_project


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

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a design project workspace",
    )
    validate_parser.add_argument("project_path", help="Project directory to validate")

    state_parser = subparsers.add_parser(
        "state",
        help="Inspect design_model.json and supporting project summaries",
    )
    state_parser.add_argument("project_path", help="Project directory to inspect")
    state_parser.add_argument(
        "--no-assets",
        action="store_true",
        help="Omit assets.lock.json summary",
    )
    state_parser.add_argument(
        "--no-visual-feedback",
        action="store_true",
        help="Omit snapshots/manifest.json visual feedback summary",
    )

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Run a local headless smoke check",
    )
    smoke_parser.add_argument(
        "project_path",
        nargs="?",
        default=DEFAULT_SMOKE_PROJECT,
        help=f"Smoke project directory (default: {DEFAULT_SMOKE_PROJECT})",
    )
    smoke_parser.add_argument(
        "--template",
        choices=["bathroom"],
        default="bathroom",
        help="Smoke template to generate",
    )
    smoke_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing generated smoke project files",
    )
    smoke_parser.add_argument(
        "--with-bridge",
        action="store_true",
        help="Also execute the bathroom trace against a live SketchUp bridge",
    )

    bridge_parser = subparsers.add_parser(
        "install-bridge",
        help="Install the SketchUp Ruby bridge into a SketchUp Plugins directory",
    )
    bridge_parser.add_argument(
        "--plugins-dir",
        help="SketchUp Plugins directory. Defaults to the newest detected macOS SketchUp install.",
    )
    bridge_parser.add_argument(
        "--source-dir",
        help="Bridge source directory. Defaults to the repository su_bridge directory.",
    )
    bridge_parser.add_argument(
        "--sketchup-version",
        help="SketchUp version for the default macOS Plugins path, for example 2024.",
    )
    bridge_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing su_bridge plugin directory.",
    )
    bridge_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the target paths without copying files.",
    )

    skills_parser = subparsers.add_parser(
        "install-skills",
        help="Install runtime skills into a design project",
    )
    skills_parser.add_argument("project_path", help="Design project directory")
    skills_parser.add_argument(
        "--target",
        choices=["all", "codex", "claude"],
        default="all",
        help="Runtime skill target to install",
    )
    skills_parser.add_argument(
        "--source-dir",
        help="Runtime skills source directory. Defaults to packaged runtime skills.",
    )
    skills_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace locally modified runtime skill files.",
    )
    skills_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show runtime skill files that would be installed.",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check harness install, project files, and SketchUp bridge state",
    )
    doctor_parser.add_argument(
        "project_path",
        nargs="?",
        help="Optional design project directory to validate",
    )
    doctor_parser.add_argument(
        "--plugins-dir",
        help="SketchUp Plugins directory to check.",
    )
    doctor_parser.add_argument(
        "--sketchup-version",
        help="SketchUp version for the default macOS Plugins path, for example 2024.",
    )
    doctor_parser.add_argument(
        "--socket-path",
        default="/tmp/su_bridge.sock",
        help="SketchUp bridge socket path.",
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
        if args.command == "validate":
            result = validate_project(args.project_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 1
        if args.command == "state":
            result = read_project_state(
                args.project_path,
                include_assets=not args.no_assets,
                include_visual_feedback=not args.no_visual_feedback,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "smoke":
            result = run_smoke(
                args.project_path,
                template=args.template,
                overwrite=args.force,
                with_bridge=args.with_bridge,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 1
        if args.command == "install-bridge":
            result = install_bridge(
                plugins_dir=args.plugins_dir,
                source_dir=args.source_dir,
                sketchup_version=args.sketchup_version,
                force=args.force,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "install-skills":
            result = install_runtime_skills(
                project_path=args.project_path,
                target=args.target,
                source_dir=args.source_dir,
                force=args.force,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "doctor":
            result = run_doctor(
                project_path=args.project_path,
                plugins_dir=args.plugins_dir,
                sketchup_version=args.sketchup_version,
                socket_path=args.socket_path,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 1
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
