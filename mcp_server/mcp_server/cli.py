"""Command line entry point for SketchUp Agent Harness."""

import argparse
import json
import sys

from mcp_server.bridge_install import install_bridge, launch_bridge
from mcp_server.doctor import run_doctor
from mcp_server.project_assets import refresh_project_asset_lock
from mcp_server.project_state import read_project_state
from mcp_server.project_versions import (
    list_project_versions,
    restore_project_version,
    save_project_version,
)
from mcp_server.project_init import init_project
from mcp_server.release_check import run_release_check
from mcp_server.runtime_skills import install_runtime_skills
from mcp_server.smoke import DEFAULT_SMOKE_PROJECT, run_smoke, validate_project
from mcp_server.tools.report_tools import generate_project_report
from mcp_server.tools.project_executor import (
    build_project_execution_plan,
    execute_project_execution_plan,
)


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

    refresh_assets_parser = subparsers.add_parser(
        "refresh-assets",
        help="Regenerate assets.lock.json from current project truth",
    )
    refresh_assets_parser.add_argument(
        "project_path",
        help="Project directory whose asset lock should be refreshed",
    )

    plan_execution_parser = subparsers.add_parser(
        "plan-execution",
        help="Build a bridge operation trace from current project truth",
    )
    plan_execution_parser.add_argument(
        "project_path",
        help="Project directory whose design_model.json should be planned",
    )
    plan_execution_parser.add_argument(
        "--no-spaces",
        action="store_true",
        help="Omit space wall operations",
    )
    plan_execution_parser.add_argument(
        "--no-components",
        action="store_true",
        help="Omit component placement operations",
    )
    plan_execution_parser.add_argument(
        "--no-lighting",
        action="store_true",
        help="Omit lighting operations",
    )
    plan_execution_parser.add_argument(
        "--no-scene-info",
        action="store_true",
        help="Omit final scene info operation",
    )

    execute_project_parser = subparsers.add_parser(
        "execute-project",
        help="Execute current project truth against a live SketchUp bridge",
    )
    execute_project_parser.add_argument(
        "project_path",
        help="Project directory whose design_model.json should be executed",
    )
    execute_project_parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Execute planned operations even when some instances are skipped",
    )
    execute_project_parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue bridge execution after a failed operation",
    )
    execute_project_parser.add_argument(
        "--no-spaces",
        action="store_true",
        help="Omit space wall operations",
    )
    execute_project_parser.add_argument(
        "--no-components",
        action="store_true",
        help="Omit component placement operations",
    )
    execute_project_parser.add_argument(
        "--no-lighting",
        action="store_true",
        help="Omit lighting operations",
    )
    execute_project_parser.add_argument(
        "--no-scene-info",
        action="store_true",
        help="Omit final scene info operation",
    )

    save_version_parser = subparsers.add_parser(
        "save-version",
        help="Save structured project truth into versions/<tag>",
    )
    save_version_parser.add_argument("project_path", help="Project directory")
    save_version_parser.add_argument("version_tag", help="Version tag to create")
    save_version_parser.add_argument(
        "--description",
        default="",
        help="Optional version description",
    )
    save_version_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing version tag",
    )

    list_versions_parser = subparsers.add_parser(
        "list-versions",
        help="List structured project truth versions",
    )
    list_versions_parser.add_argument("project_path", help="Project directory")

    restore_version_parser = subparsers.add_parser(
        "restore-version",
        help="Restore structured project truth from versions/<tag>",
    )
    restore_version_parser.add_argument("project_path", help="Project directory")
    restore_version_parser.add_argument("version_tag", help="Version tag to restore")
    restore_version_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite current project truth files",
    )

    state_parser = subparsers.add_parser(
        "state",
        help="Inspect design_model.json and supporting project summaries",
    )
    state_parser.add_argument("project_path", help="Project directory to inspect")
    state_parser.add_argument(
        "--no-rules",
        action="store_true",
        help="Omit design_rules.json and effective rules summary",
    )
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
    state_parser.add_argument(
        "--no-versions",
        action="store_true",
        help="Omit versions/ summary",
    )
    state_parser.add_argument(
        "--no-execution",
        action="store_true",
        help="Omit bridge execution feedback summary",
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Generate an English-first Markdown project report",
    )
    report_parser.add_argument("project_path", help="Project directory to report")
    report_parser.add_argument(
        "--output-path",
        help="Report output path. Defaults to reports/design_report.md.",
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

    launch_bridge_parser = subparsers.add_parser(
        "launch-bridge",
        help="Open SketchUp with a model window and wait for the Ruby bridge socket",
    )
    launch_bridge_parser.add_argument(
        "--sketchup-version",
        help="SketchUp version to launch, for example 2024.",
    )
    launch_bridge_parser.add_argument(
        "--app-path",
        help="Explicit SketchUp.app path. Defaults to the newest detected app.",
    )
    launch_bridge_parser.add_argument(
        "--model-path",
        help="Optional .skp model to open. Defaults to a copied bundled template.",
    )
    launch_bridge_parser.add_argument(
        "--socket-path",
        default="/tmp/su_bridge.sock",
        help="SketchUp bridge socket path.",
    )
    launch_bridge_parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Seconds to wait for the bridge socket.",
    )
    launch_bridge_parser.add_argument(
        "--clear-quarantine",
        action="store_true",
        help="Remove macOS quarantine xattrs from the SketchUp app before launch.",
    )
    launch_bridge_parser.add_argument(
        "--suppress-update-check",
        action="store_true",
        help=(
            "Disable SketchUp update prompts before launch so modal dialogs do "
            "not block bridge startup."
        ),
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

    release_parser = subparsers.add_parser(
        "release-check",
        help="Run source-checkout release smoke checks without SketchUp UI",
    )
    release_parser.add_argument(
        "--project-path",
        default="/tmp/sah-release-check",
        help="Temporary project directory for product smoke.",
    )
    release_parser.add_argument(
        "--plugins-dir",
        default="/tmp/sah-release-plugins",
        help="Temporary Plugins directory for bridge install dry run.",
    )
    release_parser.add_argument(
        "--with-wheel",
        action="store_true",
        help="Also build and verify an installed wheel in a temporary venv.",
    )
    release_parser.add_argument(
        "--wheel-dist-dir",
        default="/tmp/sah-release-dist",
        help="Temporary wheel output directory used with --with-wheel.",
    )
    release_parser.add_argument(
        "--wheel-venv-dir",
        default="/tmp/sah-release-wheel-venv",
        help="Temporary venv directory used with --with-wheel.",
    )
    release_parser.add_argument(
        "--wheel-project-path",
        default="/tmp/sah-release-wheel-project",
        help="Temporary installed-package project path used with --with-wheel.",
    )
    release_parser.add_argument(
        "--wheel-plugins-dir",
        default="/tmp/sah-release-wheel-plugins",
        help="Temporary installed-package Plugins directory used with --with-wheel.",
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
        if args.command == "refresh-assets":
            result = refresh_project_asset_lock(args.project_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "plan-execution":
            result = build_project_execution_plan(
                args.project_path,
                include_spaces=not args.no_spaces,
                include_components=not args.no_components,
                include_lighting=not args.no_lighting,
                include_scene_info=not args.no_scene_info,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["skipped_count"] == 0 else 1
        if args.command == "execute-project":
            result = execute_project_execution_plan(
                args.project_path,
                stop_on_error=not args.continue_on_error,
                allow_partial=args.allow_partial,
                include_spaces=not args.no_spaces,
                include_components=not args.no_components,
                include_lighting=not args.no_lighting,
                include_scene_info=not args.no_scene_info,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result.get("status") == "success" else 1
        if args.command == "save-version":
            result = save_project_version(
                args.project_path,
                version_tag=args.version_tag,
                description=args.description,
                overwrite=args.force,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "list-versions":
            result = list_project_versions(args.project_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "restore-version":
            result = restore_project_version(
                args.project_path,
                version_tag=args.version_tag,
                overwrite_current=args.force,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "state":
            result = read_project_state(
                args.project_path,
                include_rules=not args.no_rules,
                include_assets=not args.no_assets,
                include_visual_feedback=not args.no_visual_feedback,
                include_versions=not args.no_versions,
                include_execution=not args.no_execution,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "report":
            result = generate_project_report(
                args.project_path,
                output_path=args.output_path,
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
        if args.command == "launch-bridge":
            result = launch_bridge(
                sketchup_version=args.sketchup_version,
                app_path=args.app_path,
                model_path=args.model_path,
                socket_path=args.socket_path,
                timeout=args.timeout,
                clear_app_quarantine=args.clear_quarantine,
                suppress_app_update_check=args.suppress_update_check,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["socket_ready"] else 1
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
        if args.command == "release-check":
            result = run_release_check(
                project_path=args.project_path,
                plugins_dir=args.plugins_dir,
                include_wheel=args.with_wheel,
                wheel_dist_dir=args.wheel_dist_dir,
                wheel_venv_dir=args.wheel_venv_dir,
                wheel_project_path=args.wheel_project_path,
                wheel_plugins_dir=args.wheel_plugins_dir,
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
