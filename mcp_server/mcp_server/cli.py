"""Command line entry point for SketchUp Agent Harness."""

import argparse
import json
import sys

from mcp_server.bridge_install import install_bridge, launch_bridge
from mcp_server.doctor import run_doctor
from mcp_server.resources.design_rules_schema import (
    create_designer_profile,
    designer_profile_status,
)
from mcp_server.project_assets import refresh_project_asset_lock
from mcp_server.project_state import read_project_state
from mcp_server.project_versions import (
    compare_project_versions,
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
from mcp_server.tools.import_pipeline import (
    get_import_summary,
    import_floorplan_to_model,
    list_import_sessions,
    normalize_imported_wall_alignment,
    repair_imported_boundary_coverage,
    repair_imported_shell_overreach,
    register_import_source,
    repair_imported_corner_notch,
    repair_imported_region,
    rescale_imported_model,
    review_imported_boundary_coverage,
    review_imported_wall_space_consistency,
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

    profile_init_parser = subparsers.add_parser(
        "profile-init",
        help="Create a reusable designer design-rules profile",
    )
    profile_init_parser.add_argument(
        "--path",
        help="Profile output path. Defaults to ~/.sketchup-agent-harness/design_rules.json.",
    )
    profile_init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing profile file.",
    )

    profile_status_parser = subparsers.add_parser(
        "profile-status",
        help="Check a reusable designer design-rules profile",
    )
    profile_status_parser.add_argument(
        "--path",
        help=(
            "Profile path to check. Defaults to SKETCHUP_AGENT_DESIGN_RULES "
            "or ~/.sketchup-agent-harness/design_rules.json."
        ),
    )

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
        "--no-walls",
        action="store_true",
        help="Omit explicit wall operations",
    )
    plan_execution_parser.add_argument(
        "--no-openings",
        action="store_true",
        help="Omit imported opening placeholder operations",
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
        "--clean-before-execute",
        action="store_true",
        help="Clean managed SketchUp layers before replaying current project truth",
    )
    execute_project_parser.add_argument(
        "--clean-scope",
        choices=["managed", "all"],
        default="managed",
        help="Cleanup scope used with --clean-before-execute",
    )
    execute_project_parser.add_argument(
        "--no-spaces",
        action="store_true",
        help="Omit space wall operations",
    )
    execute_project_parser.add_argument(
        "--no-walls",
        action="store_true",
        help="Omit explicit wall operations",
    )
    execute_project_parser.add_argument(
        "--no-openings",
        action="store_true",
        help="Omit imported opening placeholder operations",
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

    compare_versions_parser = subparsers.add_parser(
        "compare-versions",
        help="Compare structured project truth versions",
    )
    compare_versions_parser.add_argument("project_path", help="Project directory")
    compare_versions_parser.add_argument("base_version", help="Base version tag")
    compare_versions_parser.add_argument(
        "head_version",
        nargs="?",
        default="current",
        help="Head version tag. Defaults to current project truth.",
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
        "--no-imports",
        action="store_true",
        help="Omit imports/ summaries",
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

    register_import_parser = subparsers.add_parser(
        "register-import",
        help="Register a DWG, DXF, PDF, image, or other source file",
    )
    register_import_parser.add_argument("project_path", help="Design project directory")
    register_import_parser.add_argument("source_path", help="Source file to register")
    register_import_parser.add_argument("--import-id", help="Optional import session ID")
    register_import_parser.add_argument("--label", help="Optional human label")
    register_import_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing import manifest with the same ID",
    )

    import_floorplan_parser = subparsers.add_parser(
        "import-floorplan",
        help="Import source material directly into editable design_model.json truth",
    )
    import_floorplan_parser.add_argument("project_path", help="Design project directory")
    import_floorplan_parser.add_argument(
        "source_path",
        nargs="?",
        help="Source file to register and import. Omit when --import-id already exists.",
    )
    import_floorplan_parser.add_argument("--import-id", help="Optional import session ID")
    import_floorplan_parser.add_argument("--label", help="Optional human label")
    import_floorplan_parser.add_argument("--width", type=float, help="Known plan width in mm")
    import_floorplan_parser.add_argument("--depth", type=float, help="Known plan depth in mm")
    import_floorplan_parser.add_argument(
        "--source-interpretation",
        dest="source_interpretation_path",
        help=(
            "Optional extracted source interpretation JSON with dimension chains, "
            "space candidates, room-label areas, and negative regions"
        ),
    )
    import_floorplan_parser.add_argument(
        "--area-tolerance-ratio",
        type=float,
        default=0.35,
        help="Maximum room label area delta ratio before rejecting a space candidate",
    )
    import_floorplan_parser.add_argument(
        "--negative-space-overlap-tolerance",
        type=float,
        default=0.05,
        help="Maximum candidate overlap with outside/void regions in square meters",
    )
    import_floorplan_parser.add_argument(
        "--wall-height",
        type=float,
        default=2800,
        help="Assumed wall height in mm",
    )
    import_floorplan_parser.add_argument(
        "--wall-thickness",
        type=float,
        default=120,
        help="Assumed wall thickness in mm",
    )
    import_floorplan_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the import session and regenerated entities",
    )

    import_summary_parser = subparsers.add_parser(
        "import-summary",
        help="Inspect import manifests and model import sessions",
    )
    import_summary_parser.add_argument("project_path", help="Design project directory")
    import_summary_parser.add_argument("--import-id", help="Optional import session ID")

    list_imports_parser = subparsers.add_parser(
        "list-imports",
        help="List import sessions registered in a design project",
    )
    list_imports_parser.add_argument("project_path", help="Design project directory")

    rescale_import_parser = subparsers.add_parser(
        "rescale-import",
        help="Rescale imported model geometry after a better dimension is known",
    )
    rescale_import_parser.add_argument("project_path", help="Design project directory")
    rescale_import_parser.add_argument("import_id", help="Import session ID")
    rescale_import_parser.add_argument("--scale-factor", type=float)
    rescale_import_parser.add_argument("--target-width", type=float)
    rescale_import_parser.add_argument("--target-depth", type=float)

    normalize_import_parser = subparsers.add_parser(
        "normalize-import-alignment",
        help="Snap near-boundary imported wall segments onto shared exterior lines",
    )
    normalize_import_parser.add_argument("project_path", help="Design project directory")
    normalize_import_parser.add_argument("import_id", help="Import session ID")
    normalize_import_parser.add_argument(
        "--tolerance",
        type=float,
        default=250,
        help="Maximum boundary offset in mm to normalize",
    )
    normalize_import_parser.add_argument(
        "--coordinate-match-tolerance",
        type=float,
        default=1,
        help="Point-coordinate equality tolerance in mm",
    )
    normalize_import_parser.add_argument(
        "--min-wall-length",
        type=float,
        default=20,
        help="Delete snapped connector walls at or below this plan length in mm",
    )
    normalize_import_parser.add_argument("--notes", help="Repair notes")

    corner_notch_parser = subparsers.add_parser(
        "repair-import-corner-notch",
        help="Restore a missing exterior corner notch in imported working truth",
    )
    corner_notch_parser.add_argument("project_path", help="Design project directory")
    corner_notch_parser.add_argument("import_id", help="Import session ID")
    corner_notch_parser.add_argument(
        "--corner",
        required=True,
        choices=["top_left", "top_right", "bottom_left", "bottom_right"],
        help="Imported exterior corner to notch",
    )
    corner_notch_parser.add_argument(
        "--horizontal-offset",
        type=float,
        required=True,
        help="Horizontal notch offset in mm",
    )
    corner_notch_parser.add_argument(
        "--vertical-offset",
        type=float,
        required=True,
        help="Vertical notch offset in mm",
    )
    corner_notch_parser.add_argument(
        "--target-space-id",
        help="Imported space whose footprint should receive the notch",
    )
    corner_notch_parser.add_argument(
        "--coordinate-match-tolerance",
        type=float,
        default=1,
        help="Point-coordinate equality tolerance in mm",
    )
    corner_notch_parser.add_argument(
        "--min-wall-length",
        type=float,
        default=20,
        help="Delete edited boundary walls at or below this plan length in mm",
    )
    corner_notch_parser.add_argument("--notes", help="Repair notes")

    boundary_review_parser = subparsers.add_parser(
        "review-import-boundary-coverage",
        help="Review imported space footprint edges for missing wall coverage",
    )
    boundary_review_parser.add_argument("project_path", help="Design project directory")
    boundary_review_parser.add_argument("import_id", help="Import session ID")
    boundary_review_parser.add_argument(
        "--min-gap-length",
        type=float,
        default=50,
        help="Ignore uncovered footprint gaps at or below this length in mm",
    )
    boundary_review_parser.add_argument(
        "--max-opening-gap-length",
        type=float,
        default=1200,
        help="Classify uncovered gaps at or below this length as possible openings",
    )
    boundary_review_parser.add_argument(
        "--no-infer-semantic-short-gaps",
        action="store_true",
        help="Disable automatic semantic repair recommendations for short false openings",
    )
    boundary_review_parser.add_argument(
        "--max-semantic-gap-length",
        type=float,
        default=900,
        help="Maximum short gap length in mm for semantic false-opening inference",
    )
    boundary_review_parser.add_argument(
        "--coordinate-match-tolerance",
        type=float,
        default=1,
        help="Point-coordinate equality tolerance in mm",
    )
    boundary_review_parser.add_argument(
        "--allow-unsupported-endpoints",
        action="store_true",
        help="Do not require nearby wall endpoints for repair recommendations",
    )

    boundary_repair_parser = subparsers.add_parser(
        "repair-import-boundary-coverage",
        help="Add walls for high-confidence imported footprint boundary gaps",
    )
    boundary_repair_parser.add_argument("project_path", help="Design project directory")
    boundary_repair_parser.add_argument("import_id", help="Import session ID")
    boundary_repair_parser.add_argument(
        "--min-gap-length",
        type=float,
        default=50,
        help="Ignore uncovered footprint gaps at or below this length in mm",
    )
    boundary_repair_parser.add_argument(
        "--max-opening-gap-length",
        type=float,
        default=1200,
        help="Treat larger uncovered gaps as missing-wall candidates",
    )
    boundary_repair_parser.add_argument(
        "--no-infer-semantic-short-gaps",
        action="store_true",
        help="Disable automatic repair of semantically unlikely short opening gaps",
    )
    boundary_repair_parser.add_argument(
        "--max-semantic-gap-length",
        type=float,
        default=900,
        help="Maximum short gap length in mm for semantic false-opening repair",
    )
    boundary_repair_parser.add_argument(
        "--coordinate-match-tolerance",
        type=float,
        default=1,
        help="Point-coordinate equality tolerance in mm",
    )
    boundary_repair_parser.add_argument(
        "--allow-unsupported-endpoints",
        action="store_true",
        help="Do not require nearby wall endpoints for automatic repair",
    )
    boundary_repair_parser.add_argument(
        "--max-repairs",
        type=int,
        default=20,
        help="Maximum wall segments to add in one repair pass",
    )
    boundary_repair_parser.add_argument("--notes", help="Repair notes")

    wall_space_review_parser = subparsers.add_parser(
        "review-import-wall-space",
        help="Review imported walls for shell overreach outside space footprints",
    )
    wall_space_review_parser.add_argument("project_path", help="Design project directory")
    wall_space_review_parser.add_argument("import_id", help="Import session ID")
    wall_space_review_parser.add_argument(
        "--min-segment-length",
        type=float,
        default=250,
        help="Ignore unexplained wall segments at or below this length in mm",
    )
    wall_space_review_parser.add_argument(
        "--coordinate-match-tolerance",
        type=float,
        default=1,
        help="Point-coordinate equality tolerance in mm",
    )

    shell_overreach_parser = subparsers.add_parser(
        "repair-import-shell-overreach",
        help="Trim imported wall segments that enclose space outside imported footprints",
    )
    shell_overreach_parser.add_argument("project_path", help="Design project directory")
    shell_overreach_parser.add_argument("import_id", help="Import session ID")
    shell_overreach_parser.add_argument(
        "--min-segment-length",
        type=float,
        default=250,
        help="Ignore unexplained wall segments at or below this length in mm",
    )
    shell_overreach_parser.add_argument(
        "--coordinate-match-tolerance",
        type=float,
        default=1,
        help="Point-coordinate equality tolerance in mm",
    )
    shell_overreach_parser.add_argument(
        "--min-wall-length",
        type=float,
        default=20,
        help="Delete trimmed wall remainders at or below this plan length in mm",
    )
    shell_overreach_parser.add_argument(
        "--no-fill-boundary-gaps",
        action="store_true",
        help="Do not add missing footprint-boundary walls after trimming overreach",
    )
    shell_overreach_parser.add_argument(
        "--max-repairs",
        type=int,
        default=20,
        help="Maximum overreach segments to repair in one pass",
    )
    shell_overreach_parser.add_argument("--notes", help="Repair notes")

    repair_import_parser = subparsers.add_parser(
        "repair-import",
        help="Patch imported working truth using source-backed repair inputs",
    )
    repair_import_parser.add_argument("project_path", help="Design project directory")
    repair_import_parser.add_argument("import_id", help="Import session ID")
    repair_import_parser.add_argument("--target-width", type=float)
    repair_import_parser.add_argument("--target-depth", type=float)
    repair_import_parser.add_argument("--wall-thickness", type=float)
    repair_import_parser.add_argument("--notes", help="Repair notes")

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
        if args.command == "profile-init":
            result = create_designer_profile(
                profile_path=args.path,
                force=args.force,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "profile-status":
            result = designer_profile_status(profile_path=args.path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["valid"] or not result["exists"] else 1
        if args.command == "refresh-assets":
            result = refresh_project_asset_lock(args.project_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "plan-execution":
            result = build_project_execution_plan(
                args.project_path,
                include_spaces=not args.no_spaces,
                include_walls=not args.no_walls,
                include_openings=not args.no_openings,
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
                clean_before_execute=args.clean_before_execute,
                clean_scope=args.clean_scope,
                include_spaces=not args.no_spaces,
                include_walls=not args.no_walls,
                include_openings=not args.no_openings,
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
        if args.command == "compare-versions":
            result = compare_project_versions(
                args.project_path,
                base_version=args.base_version,
                head_version=args.head_version,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if not result["errors"] else 1
        if args.command == "state":
            result = read_project_state(
                args.project_path,
                include_rules=not args.no_rules,
                include_assets=not args.no_assets,
                include_imports=not args.no_imports,
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
        if args.command == "register-import":
            result = register_import_source(
                args.project_path,
                args.source_path,
                import_id=args.import_id,
                label=args.label,
                overwrite=args.force,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "import-floorplan":
            result = import_floorplan_to_model(
                args.project_path,
                source_path=args.source_path,
                import_id=args.import_id,
                label=args.label,
                width=args.width,
                depth=args.depth,
                source_interpretation_path=args.source_interpretation_path,
                area_tolerance_ratio=args.area_tolerance_ratio,
                negative_space_overlap_tolerance_m2=args.negative_space_overlap_tolerance,
                wall_height=args.wall_height,
                wall_thickness=args.wall_thickness,
                overwrite=args.force,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "import-summary":
            result = get_import_summary(
                args.project_path,
                import_id=args.import_id,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "list-imports":
            imports = list_import_sessions(args.project_path)
            print(
                json.dumps(
                    {
                        "project_path": args.project_path,
                        "count": len(imports),
                        "imports": imports,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.command == "rescale-import":
            result = rescale_imported_model(
                args.project_path,
                args.import_id,
                scale_factor=args.scale_factor,
                target_width=args.target_width,
                target_depth=args.target_depth,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "normalize-import-alignment":
            result = normalize_imported_wall_alignment(
                args.project_path,
                args.import_id,
                tolerance=args.tolerance,
                coordinate_match_tolerance=args.coordinate_match_tolerance,
                min_wall_length=args.min_wall_length,
                notes=args.notes,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "repair-import-corner-notch":
            result = repair_imported_corner_notch(
                args.project_path,
                args.import_id,
                corner=args.corner,
                horizontal_offset=args.horizontal_offset,
                vertical_offset=args.vertical_offset,
                target_space_id=args.target_space_id,
                coordinate_match_tolerance=args.coordinate_match_tolerance,
                min_wall_length=args.min_wall_length,
                notes=args.notes,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "review-import-boundary-coverage":
            result = review_imported_boundary_coverage(
                args.project_path,
                args.import_id,
                min_gap_length=args.min_gap_length,
                max_opening_gap_length=args.max_opening_gap_length,
                infer_semantic_short_gaps=not args.no_infer_semantic_short_gaps,
                max_semantic_gap_length=args.max_semantic_gap_length,
                coordinate_match_tolerance=args.coordinate_match_tolerance,
                require_structural_endpoints=not args.allow_unsupported_endpoints,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "repair-import-boundary-coverage":
            result = repair_imported_boundary_coverage(
                args.project_path,
                args.import_id,
                min_gap_length=args.min_gap_length,
                max_opening_gap_length=args.max_opening_gap_length,
                infer_semantic_short_gaps=not args.no_infer_semantic_short_gaps,
                max_semantic_gap_length=args.max_semantic_gap_length,
                coordinate_match_tolerance=args.coordinate_match_tolerance,
                require_structural_endpoints=not args.allow_unsupported_endpoints,
                max_repairs=args.max_repairs,
                notes=args.notes,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "review-import-wall-space":
            result = review_imported_wall_space_consistency(
                args.project_path,
                args.import_id,
                min_segment_length=args.min_segment_length,
                coordinate_match_tolerance=args.coordinate_match_tolerance,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "repair-import-shell-overreach":
            result = repair_imported_shell_overreach(
                args.project_path,
                args.import_id,
                min_segment_length=args.min_segment_length,
                coordinate_match_tolerance=args.coordinate_match_tolerance,
                min_wall_length=args.min_wall_length,
                fill_resulting_boundary_gaps=not args.no_fill_boundary_gaps,
                max_repairs=args.max_repairs,
                notes=args.notes,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "repair-import":
            result = repair_imported_region(
                args.project_path,
                args.import_id,
                target_width=args.target_width,
                target_depth=args.target_depth,
                wall_thickness=args.wall_thickness,
                notes=args.notes,
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
