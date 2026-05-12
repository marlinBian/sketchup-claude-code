"""Autonomous-first source import into editable project truth."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from mcp_server.resources.design_model_schema import load_design_model, save_design_model
from mcp_server.resources.import_manifest_schema import (
    create_import_manifest,
    load_import_manifest,
    save_import_manifest,
)
from mcp_server.resources.project_files import (
    DESIGN_MODEL_FILENAME,
    find_design_model_path,
    import_manifest_path,
    import_session_path,
    imports_path,
)

DEFAULT_IMPORTED_WIDTH = 6000.0
DEFAULT_IMPORTED_DEPTH = 4000.0
DEFAULT_WALL_HEIGHT = 2800.0
DEFAULT_WALL_THICKNESS = 120.0
DEFAULT_ALIGNMENT_TOLERANCE = 250.0
DEFAULT_COORDINATE_MATCH_TOLERANCE = 1.0
DEFAULT_MIN_WALL_LENGTH = 20.0
DEFAULT_MIN_BOUNDARY_GAP_LENGTH = 50.0
DEFAULT_MIN_SHELL_OVERREACH_LENGTH = 250.0
DEFAULT_MIN_HOSTED_OPENING_WIDTH = 300.0
DEFAULT_MAX_OPENING_GAP_LENGTH = 1200.0
DEFAULT_MAX_CIRCULATION_GAP_LENGTH = 1800.0
DEFAULT_MAX_SOURCE_EVIDENCE_SHORT_GAP_LENGTH = 900.0
DEFAULT_LABEL_AREA_TOLERANCE_RATIO = 0.35
DEFAULT_NEGATIVE_SPACE_OVERLAP_TOLERANCE_M2 = 0.05
DEFAULT_NEGATIVE_REGION_BOUNDARY_COVERAGE_RATIO = 0.5
DEFAULT_DIMENSION_CONSTRAINT_TOLERANCE = 120.0
DEFAULT_STRONG_LABEL_AREA_TOLERANCE_RATIO = 0.08
DEFAULT_STRONG_DIMENSION_TOLERANCE = 80.0
VALID_CORNER_NOTCHES = {"top_left", "top_right", "bottom_left", "bottom_right"}
EXTRACTED_EVIDENCE_ORIGINS = {
    "agent_extracted_from_source",
    "cad_extracted",
    "deterministic_extractor",
    "image_extracted",
    "ocr_extracted",
    "pdf_extracted",
    "source_extracted",
    "tool_extracted",
    "vision_extracted",
}
SOURCE_CONSTRAINT_LIST_KEYS = (
    "opening_constraints",
    "openings",
    "door_constraints",
    "window_constraints",
    "wall_constraints",
    "walls",
    "boundary_constraints",
    "exterior_outline_constraints",
    "outline_constraints",
    "wall_mass_outline_constraints",
    "source_outline_constraints",
    "boundary_closure_constraints",
    "space_boundary_constraints",
    "required_boundary_constraints",
    "negative_region_constraints",
    "negative_regions",
    "outside_regions",
    "space_constraints",
    "space_footprint_constraints",
    "spaces",
    "adjacency_constraints",
    "space_adjacency_constraints",
    "required_adjacencies",
    "alignment_constraints",
    "edge_alignment_constraints",
)
SOURCE_INTERPRETATION_DIRECT_CONSTRAINT_KEYS = (
    "opening_constraints",
    "door_constraints",
    "window_constraints",
    "wall_constraints",
    "boundary_constraints",
    "exterior_outline_constraints",
    "outline_constraints",
    "wall_mass_outline_constraints",
    "source_outline_constraints",
    "boundary_closure_constraints",
    "space_boundary_constraints",
    "required_boundary_constraints",
    "negative_region_constraints",
    "space_constraints",
    "space_footprint_constraints",
    "adjacency_constraints",
    "space_adjacency_constraints",
    "required_adjacencies",
    "alignment_constraints",
    "edge_alignment_constraints",
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}
CAD_EXTENSIONS = {".dwg", ".dxf"}
SOURCE_REFERENCE_TYPES = {"chat_image_attachment"}
INTERPRETATION_SOURCE_TYPES = {
    "image",
    "pdf",
    "dwg",
    "dxf",
    "sketchup",
    *SOURCE_REFERENCE_TYPES,
}
RASTER_INTERPRETATION_SOURCE_TYPES = {"image", "pdf", "chat_image_attachment"}
Y_DOWN_COORDINATE_TOKENS = ("y south", "y_down", "y-down", "y down", "image y")
Y_UP_COORDINATE_TOKENS = ("y north", "y_up", "y-up", "y up", "model y")
POINT_FIELD_KEYS = {
    "anchor",
    "center",
    "end",
    "label_anchor",
    "label_point",
    "max",
    "min",
    "position",
    "source_anchor",
    "source_label_anchor",
    "source_point",
    "start",
    "text_anchor",
}
POINT_SEQUENCE_KEYS = {
    "footprint",
    "outline",
    "path",
    "polygon",
    "polyline",
    "segment",
}
IMPORT_TIMING_PHASES: dict[str, dict[str, Any]] = {
    "project_state_read": {
        "label": "Project state read",
        "classification": "deterministic_cli",
        "budget_ms": 500.0,
    },
    "source_registration": {
        "label": "Source registration",
        "classification": "deterministic_cli",
        "budget_ms": 750.0,
    },
    "source_preprocessing_or_extraction": {
        "label": "Source preprocessing or extraction",
        "classification": "model_vision_or_external_extractor",
        "budget_ms": None,
    },
    "source_interpretation_loading_normalization": {
        "label": "Source interpretation loading and normalization",
        "classification": "deterministic_cli",
        "budget_ms": 1000.0,
    },
    "model_generation": {
        "label": "Model generation",
        "classification": "deterministic_cli",
        "budget_ms": 1500.0,
    },
    "source_constraint_validation": {
        "label": "Source constraint validation",
        "classification": "deterministic_cli",
        "budget_ms": 1000.0,
    },
    "plan_execution": {
        "label": "Plan execution",
        "classification": "deterministic_cli",
        "budget_ms": None,
    },
    "live_sketchup_execution": {
        "label": "Live SketchUp execution",
        "classification": "live_sketchup",
        "budget_ms": None,
    },
    "snapshot_report_generation": {
        "label": "Snapshot/report generation",
        "classification": "deterministic_cli",
        "budget_ms": None,
    },
    "manifest_report_persistence": {
        "label": "Manifest/report persistence",
        "classification": "deterministic_cli",
        "budget_ms": 750.0,
    },
}
IMPORT_TOTAL_BUDGET_MS = 5000.0


def utc_now() -> str:
    """Return an ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ImportTimingTrace:
    """Collect structured phase timings for one floor-plan import."""

    def __init__(self, *, trace_type: str = "import_floorplan") -> None:
        self.trace_type = trace_type
        self.started_at = utc_now()
        self._started_perf = time.perf_counter()
        self._phases: list[dict[str, Any]] = []

    @contextmanager
    def phase(self, name: str) -> Iterator[dict[str, Any]]:
        """Measure one import phase."""
        spec = IMPORT_TIMING_PHASES.get(name, {})
        phase: dict[str, Any] = {
            "name": name,
            "label": spec.get("label", name.replace("_", " ")),
            "classification": spec.get("classification", "deterministic_cli"),
            "status": "success",
            "started_at": utc_now(),
        }
        budget_ms = spec.get("budget_ms")
        if budget_ms is not None:
            phase["budget_ms"] = float(budget_ms)
        started_perf = time.perf_counter()
        try:
            yield phase
        except Exception as exc:
            phase["status"] = "failed"
            phase["error"] = exc.__class__.__name__
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_perf) * 1000, 3)
            phase["ended_at"] = utc_now()
            phase["duration_ms"] = duration_ms
            if "budget_ms" in phase:
                phase["within_budget"] = duration_ms <= float(phase["budget_ms"])
            self._phases.append(phase)

    def skip_phase(self, name: str, reason: str) -> None:
        """Record a phase that is intentionally outside this command."""
        spec = IMPORT_TIMING_PHASES.get(name, {})
        phase: dict[str, Any] = {
            "name": name,
            "label": spec.get("label", name.replace("_", " ")),
            "classification": spec.get("classification", "deterministic_cli"),
            "status": "skipped",
            "skip_reason": reason,
            "started_at": utc_now(),
            "ended_at": utc_now(),
            "duration_ms": 0.0,
        }
        budget_ms = spec.get("budget_ms")
        if budget_ms is not None:
            phase["budget_ms"] = float(budget_ms)
            phase["within_budget"] = True
        self._phases.append(phase)

    def finish(self) -> dict[str, Any]:
        """Return a JSON-serializable timing trace."""
        ended_at = utc_now()
        total_ms = round((time.perf_counter() - self._started_perf) * 1000, 3)
        over_budget_phases = [
            phase["name"]
            for phase in self._phases
            if phase.get("within_budget") is False
        ]
        measured_phases = [
            phase for phase in self._phases if phase.get("status") != "skipped"
        ]
        slowest_phase = (
            max(measured_phases, key=lambda phase: float(phase.get("duration_ms", 0.0)))
            if measured_phases
            else None
        )
        classification_totals_ms: dict[str, float] = {}
        for phase in measured_phases:
            classification = str(phase.get("classification", "unknown"))
            classification_totals_ms[classification] = round(
                classification_totals_ms.get(classification, 0.0)
                + float(phase.get("duration_ms", 0.0)),
                3,
            )

        within_total_budget = total_ms <= IMPORT_TOTAL_BUDGET_MS
        trace = {
            "schema_version": "1.0",
            "trace_type": self.trace_type,
            "scope": "deterministic_product_pipeline",
            "started_at": self.started_at,
            "ended_at": ended_at,
            "total_ms": total_ms,
            "classification_totals_ms": classification_totals_ms,
            "phases": self._phases,
            "slowest_phase": (
                {
                    "name": slowest_phase["name"],
                    "duration_ms": slowest_phase["duration_ms"],
                    "classification": slowest_phase.get("classification"),
                }
                if slowest_phase is not None
                else None
            ),
            "budget": {
                "total_budget_ms": IMPORT_TOTAL_BUDGET_MS,
                "within_budget": within_total_budget and not over_budget_phases,
                "total_within_budget": within_total_budget,
                "over_budget_phases": over_budget_phases,
            },
        }
        trace["diagnostics"] = import_timing_diagnostics(trace)
        return trace


def import_timing_diagnostics(timing: dict[str, Any]) -> dict[str, Any]:
    """Build concise diagnostic hints from a timing trace."""
    phases = timing.get("phases", [])
    extraction_phase = next(
        (
            phase
            for phase in phases
            if phase.get("name") == "source_preprocessing_or_extraction"
        ),
        None,
    )
    over_budget = timing.get("budget", {}).get("over_budget_phases", [])
    if over_budget:
        slow_stage_hint = "Inspect over-budget deterministic product phases first."
    elif extraction_phase and extraction_phase.get("status") == "skipped":
        slow_stage_hint = (
            "If the user experienced a slow import, latency likely happened before "
            "this command in agent-side vision/OCR/CAD extraction."
        )
    else:
        slow_stage_hint = "Deterministic import phases stayed inside the baseline budget."

    return {
        "mcp_tool_overhead_timed": False,
        "model_vision_extraction_timed": (
            extraction_phase is not None and extraction_phase.get("status") != "skipped"
        ),
        "live_sketchup_execution_timed": any(
            phase.get("name") == "live_sketchup_execution"
            and phase.get("status") != "skipped"
            for phase in phases
        ),
        "slow_stage_hint": slow_stage_hint,
    }


def compact_import_timing(timing: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a compact timing summary safe for list responses."""
    if not isinstance(timing, dict):
        return None
    return {
        "total_ms": timing.get("total_ms"),
        "within_budget": timing.get("budget", {}).get("within_budget"),
        "slowest_phase": timing.get("slowest_phase"),
        "diagnostics": timing.get("diagnostics", {}),
    }


def format_import_timing_summary(timing: dict[str, Any]) -> str:
    """Return a concise human-readable timing summary."""
    lines = [
        (
            f"Import timing: {timing.get('total_ms', 0)} ms "
            f"(budget {timing.get('budget', {}).get('total_budget_ms', 0)} ms, "
            f"within_budget={timing.get('budget', {}).get('within_budget')})"
        )
    ]
    for phase in timing.get("phases", []):
        budget = (
            f", budget={phase['budget_ms']} ms, within_budget={phase.get('within_budget')}"
            if "budget_ms" in phase
            else ""
        )
        reason = (
            f", skipped={phase.get('skip_reason')}"
            if phase.get("status") == "skipped"
            else ""
        )
        lines.append(
            "- "
            f"{phase.get('name')}: {phase.get('duration_ms')} ms "
            f"[{phase.get('classification')}, {phase.get('status')}{budget}{reason}]"
        )
    diagnostics = timing.get("diagnostics", {})
    if diagnostics.get("slow_stage_hint"):
        lines.append(f"Hint: {diagnostics['slow_stage_hint']}")
    return "\n".join(lines)


def import_safe_id(value: str) -> str:
    """Return a safe import/session identifier."""
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_")
    if not normalized:
        raise ValueError("import_id must contain at least one letter or number.")
    if not normalized.replace("_", "").isalnum():
        raise ValueError("import_id must contain only letters, numbers, and underscores.")
    return normalized


def next_import_id(project_path: str | Path) -> str:
    """Return the next deterministic import ID for a project."""
    root = imports_path(project_path)
    existing = {
        child.name
        for child in root.iterdir()
        if child.is_dir() and child.name.startswith("import_")
    } if root.exists() else set()
    index = 1
    while True:
        import_id = f"import_{index:03d}"
        if import_id not in existing:
            return import_id
        index += 1


def detect_source_type(path: Path) -> str:
    """Return a normalized source type from a file extension."""
    extension = path.suffix.lower()
    if extension == ".pdf":
        return "pdf"
    if extension in CAD_EXTENSIONS:
        return extension.lstrip(".")
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension == ".skp":
        return "sketchup"
    return "unknown"


def sha256_file(path: Path) -> str:
    """Return the SHA256 hash for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_relative_path(project_path: str | Path, path: str | Path) -> str:
    """Return a project-relative path when possible."""
    root = Path(project_path).expanduser().resolve()
    target = Path(path).expanduser().resolve()
    try:
        return str(target.relative_to(root))
    except ValueError:
        return str(target)


def append_processing_step(
    manifest: dict[str, Any],
    step: str,
    *,
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    """Append one manifest processing step."""
    record: dict[str, Any] = {
        "step": step,
        "status": status,
        "created_at": utc_now(),
    }
    if details:
        record["details"] = details
    manifest.setdefault("processing_steps", []).append(record)


def dedupe_quality_flags(flags: list[str]) -> list[str]:
    """Return quality flags in stable unique order."""
    seen: set[str] = set()
    result: list[str] = []
    for flag in flags:
        if flag not in seen:
            result.append(flag)
            seen.add(flag)
    return result


def register_import_source(
    project_path: str | Path,
    source_path: str | Path,
    *,
    import_id: str | None = None,
    label: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Register one source file under imports/<import_id>/."""
    root = Path(project_path).expanduser().resolve()
    source = Path(source_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"source file not found: {source}")

    chosen_id = import_safe_id(import_id) if import_id else next_import_id(root)
    session_dir = import_session_path(root, chosen_id)
    manifest_path = import_manifest_path(root, chosen_id)
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(
            f"Import manifest already exists: {manifest_path}. Use overwrite=True."
        )

    source_dir = session_dir / "source"
    preview_dir = session_dir / "previews"
    evidence_dir = session_dir / "evidence"
    extracted_dir = session_dir / "extracted"
    for directory in (source_dir, preview_dir, evidence_dir, extracted_dir):
        directory.mkdir(parents=True, exist_ok=True)

    destination = source_dir / source.name
    if source != destination:
        shutil.copyfile(source, destination)

    source_info = {
        "original_path": str(source),
        "stored_path": project_relative_path(root, destination),
        "filename": destination.name,
        "extension": destination.suffix.lower(),
        "source_type": detect_source_type(destination),
        "file_backed": True,
        "sha256": sha256_file(destination),
        "size_bytes": destination.stat().st_size,
    }
    manifest = create_import_manifest(
        import_id=chosen_id,
        source=source_info,
        label=label,
    )
    saved, errors = save_import_manifest(manifest_path, manifest)
    if not saved:
        raise ValueError("; ".join(errors))

    return {
        "project_path": str(root),
        "import_id": chosen_id,
        "manifest_path": str(manifest_path),
        "source": source_info,
        "status": "registered",
    }


def register_import_source_reference(
    project_path: str | Path,
    source_reference: str,
    *,
    import_id: str | None = None,
    label: str | None = None,
    source_reference_type: str = "chat_image_attachment",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Register an unfiled runtime source reference under imports/<import_id>/.

    This is used when an agent can see a chat/CLI-attached floor-plan image but
    the attachment has no local file path available to the MCP server. It is
    intentionally marked as not file-backed so source fidelity can stay honest.
    """
    root = Path(project_path).expanduser().resolve()
    source_reference_type = source_reference_type.strip().lower()
    if source_reference_type not in SOURCE_REFERENCE_TYPES:
        supported = ", ".join(sorted(SOURCE_REFERENCE_TYPES))
        raise ValueError(
            f"Unsupported source_reference_type {source_reference_type!r}. "
            f"Use one of: {supported}."
        )
    if not source_reference.strip():
        raise ValueError("source_reference must not be empty.")

    chosen_id = import_safe_id(import_id) if import_id else next_import_id(root)
    session_dir = import_session_path(root, chosen_id)
    manifest_path = import_manifest_path(root, chosen_id)
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(
            f"Import manifest already exists: {manifest_path}. Use overwrite=True."
        )

    for directory in (
        session_dir / "source",
        session_dir / "previews",
        session_dir / "evidence",
        session_dir / "extracted",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    evidence_file = session_dir / "evidence" / "source_reference.md"
    evidence_file.write_text(
        "\n".join(
            [
                "# Runtime Source Reference",
                "",
                f"- import_id: {chosen_id}",
                f"- source_reference_type: {source_reference_type}",
                f"- source_reference: {source_reference.strip()}",
                "- file_backed: false",
                "",
                "The original attachment was visible to the runtime agent but was not",
                "available to the MCP server as a local source file path. Treat this",
                "import as a source-reference draft until it is rerun with an actual",
                "image, PDF, DWG, DXF, or SketchUp source file path.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    source_info = {
        "original_path": source_reference.strip(),
        "stored_path": project_relative_path(root, evidence_file),
        "filename": evidence_file.name,
        "extension": evidence_file.suffix.lower(),
        "source_type": source_reference_type,
        "file_backed": False,
        "note": (
            "Runtime source reference only; the original raster/document file was "
            "not available as a local path."
        ),
        "sha256": sha256_file(evidence_file),
        "size_bytes": evidence_file.stat().st_size,
    }
    manifest = create_import_manifest(
        import_id=chosen_id,
        source=source_info,
        label=label,
    )
    manifest["quality_flags"] = dedupe_quality_flags(
        [
            flag
            for flag in manifest.get("quality_flags", [])
            if flag != "scale_missing"
        ]
        + [
            "chat_attachment_no_local_source_file",
            "source_file_backed_import_pending",
        ]
    )
    append_processing_step(
        manifest,
        "register_source_reference",
        details={
            "source_reference_type": source_reference_type,
            "file_backed": False,
        },
    )
    saved, errors = save_import_manifest(manifest_path, manifest)
    if not saved:
        raise ValueError("; ".join(errors))

    return {
        "project_path": str(root),
        "import_id": chosen_id,
        "manifest_path": str(manifest_path),
        "source": source_info,
        "status": "registered",
    }


def source_is_file_backed(manifest: dict[str, Any]) -> bool:
    """Return whether an import manifest source points to a real source file."""
    source = manifest.get("source", {}) if isinstance(manifest, dict) else {}
    if "file_backed" in source:
        return bool(source["file_backed"])
    return str(source.get("source_type", "unknown")) not in SOURCE_REFERENCE_TYPES


def dynamic_import_skill_name(import_id: str) -> str:
    """Return a Codex/Claude-loadable project dynamic skill name."""
    slug = re.sub(r"[^a-z0-9]+", "-", import_id.lower()).strip("-")
    if not slug:
        slug = "source"
    return f"import-source-{slug}"


def skill_markdown_value(value: Any) -> str:
    """Return a one-line markdown-safe metadata value."""
    if value is None:
        return "none"
    return str(value).replace("\n", " ").strip() or "none"


def write_import_dynamic_runtime_skill(
    project_path: str | Path,
    *,
    import_id: str,
    manifest: dict[str, Any],
    interpretation_path: str | None,
    source_interpretation_path: str | None,
    source_constraints_path: str | None,
    lifecycle: str = "persistent-project-memory",
) -> dict[str, Any]:
    """Create or update project-local dynamic runtime skills for one import."""
    root = Path(project_path).expanduser().resolve()
    source = manifest.get("source", {})
    source_type = str(source.get("source_type", "unknown"))
    file_backed = source_is_file_backed(manifest)
    skill_name = dynamic_import_skill_name(import_id)
    source_reference_note = (
        "This import is backed by a local source file."
        if file_backed
        else (
            "This import was created from an unfiled runtime source reference. "
            "Do not claim source-file-backed automatic recognition until it is "
            "rerun with a local source file path."
        )
    )
    constraints_note = (
        "Use the linked constraints file for machine-checkable source fidelity."
        if source_constraints_path
        else (
            "No source constraints file is linked yet; source fidelity is not "
            "constraint-checked."
        )
    )
    content = f"""---
name: {skill_name}
description: Project-local memory for import source {import_id}.
---

# Import Source {import_id}

## Scope

This dynamic runtime skill applies only to this design project and import
source. `design_model.json` remains canonical truth.

## Classification

- origin: product_import_tool
- lifecycle: {lifecycle}
- source_file_backed: {str(file_backed).lower()}

## Provenance

- import_id: {import_id}
- source_type: {source_type}
- source_path_or_reference: {skill_markdown_value(source.get("original_path"))}
- stored_source_record: {skill_markdown_value(source.get("stored_path"))}
- source_hash: {skill_markdown_value(source.get("sha256"))}
- manifest_path: {project_relative_path(root, import_manifest_path(root, import_id))}
- generated_interpretation_path: {skill_markdown_value(interpretation_path)}
- source_interpretation_path: {skill_markdown_value(source_interpretation_path)}
- source_constraints_path: {skill_markdown_value(source_constraints_path)}

## Recognition Status

{source_reference_note}

{constraints_note}

## Runtime Guidance

- Read the linked import evidence before repairing this import.
- Store source-specific geometry, openings, boundaries, negative regions, and
  corrections as structured evidence under `imports/{import_id}/`.
- Do not promote this source-specific guidance into shipped runtime skills or
  maintainer development skills.
- Do not treat this dynamic skill as proof of automatic recognition. Automatic
  recognition requires source-extracted evidence with provenance such as
  `vision_extracted`, `ocr_extracted`, `cad_extracted`, or `tool_extracted`.
"""
    relative_paths: list[str] = []
    for base in (Path(".agents") / "skills", Path(".claude") / "skills"):
        skill_file = root / base / skill_name / "SKILL.md"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(content, encoding="utf-8")
        relative_paths.append(project_relative_path(root, skill_file))
    return {
        "skill_name": skill_name,
        "paths": relative_paths,
        "lifecycle": lifecycle,
        "source_file_backed": file_backed,
    }


def load_project_import_manifest(
    project_path: str | Path,
    import_id: str,
) -> tuple[dict[str, Any], Path]:
    """Load one project import manifest or raise a ValueError."""
    manifest_path = import_manifest_path(project_path, import_safe_id(import_id))
    manifest, errors = load_import_manifest(manifest_path)
    if errors or manifest is None:
        raise ValueError("; ".join(errors))
    return manifest, manifest_path


def source_confidence(source_type: str, has_explicit_dimensions: bool) -> float:
    """Return a conservative import confidence for deterministic interpretation."""
    if has_explicit_dimensions:
        return {
            "dwg": 0.74,
            "dxf": 0.74,
            "pdf": 0.66,
            "image": 0.58,
            "sketchup": 0.55,
            "chat_image_attachment": 0.48,
            "unknown": 0.42,
        }.get(source_type, 0.42)
    return {
        "dwg": 0.52,
        "dxf": 0.52,
        "pdf": 0.45,
        "image": 0.38,
        "sketchup": 0.4,
        "chat_image_attachment": 0.32,
        "unknown": 0.3,
    }.get(source_type, 0.3)


def imported_quality_flags(
    source_type: str,
    *,
    has_explicit_dimensions: bool,
) -> list[str]:
    """Return non-blocking quality flags for the first working model."""
    flags = ["source_interpreted_as_rectangular_shell"]
    if not has_explicit_dimensions:
        flags.append("scale_estimated")
    if source_type in RASTER_INTERPRETATION_SOURCE_TYPES:
        flags.append("raster_or_document_interpretation")
    if source_type in {"dwg", "dxf"}:
        flags.append("cad_layers_not_semantically_verified")
    if source_type == "chat_image_attachment":
        flags.extend(
            [
                "chat_attachment_no_local_source_file",
                "source_file_backed_import_pending",
            ]
        )
    if source_type == "unknown":
        flags.append("unknown_source_type")
    return flags


def imported_entity_ids(import_id: str) -> dict[str, Any]:
    """Return deterministic model IDs for one import."""
    return {
        "space_id": f"{import_id}_space_001",
        "wall_ids": [
            f"{import_id}_wall_south",
            f"{import_id}_wall_east",
            f"{import_id}_wall_north",
            f"{import_id}_wall_west",
        ],
        "opening_ids": [
            f"{import_id}_door_001",
            f"{import_id}_window_001",
        ],
    }


def wall_payloads(
    import_id: str,
    *,
    width: float,
    depth: float,
    wall_height: float,
    wall_thickness: float,
    confidence: float,
    assumptions: list[str],
) -> dict[str, dict[str, Any]]:
    """Return deterministic wall payloads for a rectangular imported shell."""
    ids = imported_entity_ids(import_id)["wall_ids"]
    paths = {
        ids[0]: [[0, 0, 0], [width, 0, 0]],
        ids[1]: [[width, 0, 0], [width, depth, 0]],
        ids[2]: [[width, depth, 0], [0, depth, 0]],
        ids[3]: [[0, depth, 0], [0, 0, 0]],
    }
    return {
        wall_id: {
            "path": path,
            "height": float(wall_height),
            "thickness": float(wall_thickness),
            "alignment": "inner",
            "layer": "Walls",
            "source": {
                "kind": "import_floorplan",
                "import_id": import_id,
                "confidence": confidence,
                "assumptions": assumptions,
            },
        }
        for wall_id, path in paths.items()
    }


def opening_payloads(
    import_id: str,
    *,
    width: float,
    depth: float,
    confidence: float,
    assumptions: list[str],
) -> dict[str, dict[str, Any]]:
    """Return deterministic opening payloads for the first working model."""
    ids = imported_entity_ids(import_id)
    door_width = min(900.0, max(700.0, width * 0.18))
    window_width = min(1500.0, max(900.0, width * 0.25))
    return {
        ids["opening_ids"][0]: {
            "type": "door",
            "host_wall": ids["wall_ids"][0],
            "offset": max(0.0, width * 0.5 - door_width / 2),
            "width": door_width,
            "height": 2100.0,
            "swing_direction": "left",
            "representation": "hosted",
            "layer": "Doors",
            "source": {
                "kind": "import_floorplan",
                "import_id": import_id,
                "confidence": max(confidence - 0.08, 0),
                "assumptions": [*assumptions, "Door inferred on the south wall."],
            },
        },
        ids["opening_ids"][1]: {
            "type": "window",
            "host_wall": ids["wall_ids"][2],
            "offset": max(0.0, width * 0.5 - window_width / 2),
            "width": window_width,
            "height": 1200.0,
            "sill_height": 900.0,
            "representation": "hosted",
            "layer": "Windows",
            "source": {
                "kind": "import_floorplan",
                "import_id": import_id,
                "confidence": max(confidence - 0.12, 0),
                "assumptions": [*assumptions, "Window inferred on the north wall."],
            },
        },
    }


def space_payload(
    import_id: str,
    *,
    width: float,
    depth: float,
    wall_height: float,
    confidence: float,
    assumptions: list[str],
) -> dict[str, Any]:
    """Return one imported space payload."""
    bounds = {
        "min": [0, 0, 0],
        "max": [float(width), float(depth), float(wall_height)],
    }
    return {
        "type": "other",
        "bounds": bounds,
        "center": [float(width) / 2, float(depth) / 2, float(wall_height) / 2],
        "footprint": [
            [0, 0, 0],
            [float(width), 0, 0],
            [float(width), float(depth), 0],
            [0, float(depth), 0],
        ],
        "source": {
            "kind": "import_floorplan",
            "import_id": import_id,
            "confidence": confidence,
            "assumptions": assumptions,
        },
    }


def polygon_area_mm2(points: list[list[float]]) -> float:
    """Return the absolute XY area for one footprint polygon."""
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        area += start[0] * end[1] - end[0] * start[1]
    return abs(area) / 2.0


def polygon_bounds(points: list[list[float]]) -> tuple[float, float, float, float]:
    """Return footprint bounds as min_x, max_x, min_y, max_y."""
    if not points:
        raise ValueError("footprint must contain at least one point.")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def bounds_overlap_area_mm2(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    """Return axis-aligned bounds overlap area in square millimeters."""
    min_x = max(first[0], second[0])
    max_x = min(first[1], second[1])
    min_y = max(first[2], second[2])
    max_y = min(first[3], second[3])
    if max_x <= min_x or max_y <= min_y:
        return 0.0
    return (max_x - min_x) * (max_y - min_y)


def clip_polygon_to_half_plane(
    points: list[list[float]],
    *,
    boundary: str,
    value: float,
) -> list[list[float]]:
    """Clip an XY polygon to one axis-aligned half-plane."""
    if not points:
        return []

    def inside(point: list[float]) -> bool:
        if boundary == "left":
            return point[0] >= value
        if boundary == "right":
            return point[0] <= value
        if boundary == "bottom":
            return point[1] >= value
        if boundary == "top":
            return point[1] <= value
        raise ValueError(f"unknown clip boundary: {boundary}")

    def intersection(start: list[float], end: list[float]) -> list[float]:
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if boundary in {"left", "right"}:
            ratio = 0.0 if dx == 0 else (value - start[0]) / dx
            return [value, start[1] + ratio * dy, 0.0]
        ratio = 0.0 if dy == 0 else (value - start[1]) / dy
        return [start[0] + ratio * dx, value, 0.0]

    clipped: list[list[float]] = []
    previous = points[-1]
    previous_inside = inside(previous)
    for current in points:
        current_inside = inside(current)
        if current_inside:
            if not previous_inside:
                clipped.append(intersection(previous, current))
            clipped.append([float(current[0]), float(current[1]), 0.0])
        elif previous_inside:
            clipped.append(intersection(previous, current))
        previous = current
        previous_inside = current_inside
    return clipped


def polygon_overlap_with_bounds_area_mm2(
    footprint: list[list[float]],
    bounds: tuple[float, float, float, float],
) -> float:
    """Return actual polygon overlap area with axis-aligned bounds."""
    min_x, max_x, min_y, max_y = bounds
    clipped = [[float(point[0]), float(point[1]), 0.0] for point in footprint]
    for boundary, value in (
        ("left", min_x),
        ("right", max_x),
        ("bottom", min_y),
        ("top", max_y),
    ):
        clipped = clip_polygon_to_half_plane(
            clipped,
            boundary=boundary,
            value=value,
        )
        if not clipped:
            return 0.0
    return polygon_area_mm2(clipped)


def point_on_segment_2d(
    point: list[float],
    start: list[float],
    end: list[float],
    *,
    tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> bool:
    """Return whether a point lies on an XY segment within tolerance."""
    px, py = float(point[0]), float(point[1])
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    cross = (px - sx) * (ey - sy) - (py - sy) * (ex - sx)
    if abs(cross) > tolerance * max(abs(ex - sx), abs(ey - sy), 1.0):
        return False
    return (
        min(sx, ex) - tolerance <= px <= max(sx, ex) + tolerance
        and min(sy, ey) - tolerance <= py <= max(sy, ey) + tolerance
    )


def point_in_polygon_2d(
    point: list[float],
    polygon: list[list[float]],
    *,
    tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> bool:
    """Return whether an XY point is inside or on a polygon boundary."""
    if len(polygon) < 3:
        return False
    px, py = float(point[0]), float(point[1])
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if point_on_segment_2d(
            point,
            previous,
            current,
            tolerance=tolerance,
        ):
            return True
        y1 = float(previous[1])
        y2 = float(current[1])
        x1 = float(previous[0])
        x2 = float(current[0])
        if (y1 > py) != (y2 > py):
            intersection_x = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if intersection_x >= px - tolerance:
                inside = not inside
        previous = current
    return inside


def normalize_label_anchor(value: Any) -> list[float] | None:
    """Return a source label anchor point from a candidate or constraint."""
    raw = (
        value.get("label_anchor")
        or value.get("label_point")
        or value.get("text_anchor")
        or value.get("source_label_anchor")
        if isinstance(value, dict)
        else None
    )
    if isinstance(raw, dict):
        raw = raw.get("point") or raw.get("position")
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    if len(raw) == 2:
        raw = [raw[0], raw[1], 0]
    return normalize_3d_point(raw, label="source label anchor")


def footprint_from_payload(value: Any, *, label: str) -> list[list[float]]:
    """Return a normalized 3D footprint from a source interpretation payload."""
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError(f"{label} must contain at least three points.")
    return [
        normalize_3d_point(point, label=f"{label}[{index}]")
        for index, point in enumerate(value)
    ]


def source_interpretation_quality_flags(source_type: str) -> list[str]:
    """Return base quality flags for interpretation-driven import."""
    flags = ["source_interpretation_used"]
    if source_type in RASTER_INTERPRETATION_SOURCE_TYPES:
        flags.append("raster_or_document_interpretation")
    if source_type in {"dwg", "dxf"}:
        flags.append("cad_layers_not_semantically_verified")
    if source_type == "chat_image_attachment":
        flags.extend(
            [
                "chat_attachment_no_local_source_file",
                "source_file_backed_import_pending",
            ]
        )
    if source_type == "unknown":
        flags.append("unknown_source_type")
    return flags


def load_source_interpretation(path: str | Path) -> dict[str, Any]:
    """Load the optional structured extraction used before truth generation."""
    source_path = Path(path).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"source interpretation not found: {source_path}")
    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"source interpretation is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("source interpretation must be a JSON object.")
    return data


def require_known_source_for_interpretation(
    source_type: str,
    manifest: dict[str, Any],
) -> None:
    """Reject source interpretations without a recognized source provenance."""
    if source_type in INTERPRETATION_SOURCE_TYPES:
        return
    source = manifest.get("source", {}) if isinstance(manifest, dict) else {}
    filename = source.get("filename") or source.get("stored_path") or "unknown source"
    raise ValueError(
        "source_interpretation_path requires a registered source file or an "
        f"official source_reference with a recognized source type, got {source_type!r} "
        f"for {filename!r}. Do not use text notes or ad hoc placeholders as "
        "image import sources; use source_path for a local file or source_reference "
        "for a chat/CLI attachment that has no local path."
    )


def coordinate_system_text(interpretation: dict[str, Any]) -> str:
    """Return the source interpretation coordinate-system description."""
    scale = interpretation.get("scale", {})
    value = None
    if isinstance(scale, dict):
        value = (
            scale.get("coordinate_system")
            or scale.get("source_coordinate_system")
            or scale.get("orientation")
        )
    value = value or interpretation.get("coordinate_system")
    return str(value or "").strip().lower()


def coordinate_system_is_y_down(interpretation: dict[str, Any]) -> bool:
    """Return whether the interpretation uses image/PDF-style Y-down space."""
    text = coordinate_system_text(interpretation)
    if not text:
        return False
    if any(token in text for token in Y_UP_COORDINATE_TOKENS):
        return False
    return any(token in text for token in Y_DOWN_COORDINATE_TOKENS)


def numeric_point(value: Any) -> list[float] | None:
    """Return a numeric 3D point from a source value when possible."""
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        x = float(value[0])
        y = float(value[1])
        z = float(value[2]) if len(value) >= 3 else 0.0
    except (TypeError, ValueError):
        return None
    return [x, y, z]


def collect_plan_points(value: Any, *, key: str | None = None) -> list[list[float]]:
    """Collect source plan points from known geometry fields."""
    points: list[list[float]] = []
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            points.extend(collect_plan_points(child_value, key=str(child_key)))
        return points
    if not isinstance(value, list):
        return points

    if key in POINT_FIELD_KEYS:
        point = numeric_point(value)
        if point is not None:
            return [point]
    if key in POINT_SEQUENCE_KEYS:
        for item in value:
            point = numeric_point(item)
            if point is not None:
                points.append(point)
            elif isinstance(item, (dict, list)):
                points.extend(collect_plan_points(item))
        return points
    for item in value:
        if isinstance(item, dict):
            points.extend(collect_plan_points(item))
    return points


def interpretation_plan_depth(interpretation: dict[str, Any]) -> tuple[float, str]:
    """Return the plan depth used for Y-down to Y-up conversion."""
    scale = interpretation.get("scale", {})
    if isinstance(scale, dict):
        for key in ("depth", "height", "source_depth", "plan_depth"):
            value = scale.get(key)
            if value is not None:
                depth = float(value)
                if depth > 0:
                    return depth, f"scale.{key}"
    points = collect_plan_points(interpretation)
    if points:
        max_y = max(point[1] for point in points)
        if max_y > 0:
            return max_y, "inferred_from_source_geometry"
    raise ValueError(
        "Cannot transform image/PDF Y-down source coordinates without a positive "
        "plan depth in source_interpretation.scale.depth or source geometry."
    )


def transform_y_down_point(point: list[Any], depth: float) -> list[float]:
    """Transform one image-space Y-down point into model-space Y-up coordinates."""
    normalized = numeric_point(point)
    if normalized is None:
        raise ValueError(f"invalid source point for coordinate transform: {point!r}")
    return [normalized[0], depth - normalized[1], normalized[2]]


def transform_y_down_bounds(bounds: Any, depth: float) -> Any:
    """Transform a source bounds payload from Y-down to Y-up coordinates."""
    if isinstance(bounds, dict):
        min_point = bounds.get("min")
        max_point = bounds.get("max")
        if min_point is None or max_point is None:
            return {
                key: transform_y_down_value(key, value, depth)
                for key, value in bounds.items()
            }
        transformed = [
            transform_y_down_point(min_point, depth),
            transform_y_down_point(max_point, depth),
        ]
        min_x = min(point[0] for point in transformed)
        max_x = max(point[0] for point in transformed)
        min_y = min(point[1] for point in transformed)
        max_y = max(point[1] for point in transformed)
        min_z = min(point[2] for point in transformed)
        max_z = max(point[2] for point in transformed)
        result = dict(bounds)
        result["min"] = [min_x, min_y, min_z]
        result["max"] = [max_x, max_y, max_z]
        return result
    if isinstance(bounds, list) and len(bounds) == 4:
        try:
            min_x = min(float(bounds[0]), float(bounds[2]))
            max_x = max(float(bounds[0]), float(bounds[2]))
            first_y = depth - float(bounds[1])
            second_y = depth - float(bounds[3])
            return [min_x, min(first_y, second_y), max_x, max(first_y, second_y)]
        except (TypeError, ValueError):
            return bounds
    return bounds


def transform_y_down_point_sequence(values: Any, depth: float) -> Any:
    """Transform a sequence containing source points or segment objects."""
    if not isinstance(values, list):
        return values
    transformed: list[Any] = []
    for item in values:
        point = numeric_point(item)
        if point is not None:
            transformed.append(transform_y_down_point(item, depth))
        elif isinstance(item, dict):
            transformed.append(
                {
                    key: transform_y_down_value(key, value, depth)
                    for key, value in item.items()
                }
            )
        elif isinstance(item, list):
            transformed.append(transform_y_down_point_sequence(item, depth))
        else:
            transformed.append(item)
    return transformed


def transform_y_down_value(key: str, value: Any, depth: float) -> Any:
    """Transform known coordinate-bearing fields from Y-down to Y-up."""
    if key == "bounds":
        return transform_y_down_bounds(value, depth)
    if key in POINT_FIELD_KEYS:
        if isinstance(value, dict):
            return {
                child_key: transform_y_down_value(child_key, child_value, depth)
                for child_key, child_value in value.items()
            }
        point = numeric_point(value)
        return transform_y_down_point(value, depth) if point is not None else value
    if key in POINT_SEQUENCE_KEYS or key == "segments":
        return transform_y_down_point_sequence(value, depth)
    if isinstance(value, dict):
        return {
            child_key: transform_y_down_value(child_key, child_value, depth)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            transform_y_down_value("", item, depth) if isinstance(item, dict) else item
            for item in value
        ]
    return value


def source_interval_mode(value: dict[str, Any]) -> str:
    """Return the declared interval semantics for source opening evidence."""
    for key in ("interval_mode", "source_interval_mode", "host_interval_mode"):
        if value.get(key):
            return str(value[key]).strip().lower()
    return "wall_coordinate"


def interval_is_offset_mode(value: dict[str, Any]) -> bool:
    """Return whether an opening interval already represents wall offset."""
    return source_interval_mode(value) in {
        "offset",
        "wall_offset",
        "distance_from_start",
        "distance",
    }


def normalize_interval_values(interval: Any) -> list[float] | None:
    """Return a sorted numeric two-value interval."""
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        return None
    try:
        first = float(interval[0])
        second = float(interval[1])
    except (TypeError, ValueError):
        return None
    if first == second:
        return None
    return [min(first, second), max(first, second)]


def transform_y_down_opening_intervals(
    interpretation: dict[str, Any],
    *,
    depth: float,
) -> None:
    """Transform vertical-wall source intervals after Y-down point conversion."""
    walls_by_id = {
        str(wall.get("wall_id") or wall.get("id")): wall
        for wall in interpretation.get("walls", interpretation.get("wall_candidates", []))
        if isinstance(wall, dict) and (wall.get("wall_id") or wall.get("id"))
    }
    for opening in interpretation.get("openings", []):
        if not isinstance(opening, dict) or interval_is_offset_mode(opening):
            continue
        host_wall = walls_by_id.get(str(opening.get("host_wall", "")))
        if not isinstance(host_wall, dict):
            continue
        host_axis = wall_axis(host_wall.get("path", []))
        if host_axis is None or wall_variable_axis(host_axis) != "y":
            continue
        for key in ("source_interval", "interval", "host_interval"):
            interval = normalize_interval_values(opening.get(key))
            if interval is None:
                continue
            transformed = [depth - interval[1], depth - interval[0]]
            opening[key] = [min(transformed), max(transformed)]
        opening["source_interval_mode"] = "wall_coordinate"
        opening["source_interval_coordinate_system"] = "model_y_up"


def normalize_source_interpretation_coordinates(
    interpretation: dict[str, Any],
    *,
    source_type: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    """Normalize source interpretation coordinates before truth generation."""
    if not coordinate_system_is_y_down(interpretation):
        return interpretation, None, []
    if source_type not in RASTER_INTERPRETATION_SOURCE_TYPES:
        return interpretation, None, []

    depth, depth_source = interpretation_plan_depth(interpretation)
    transformed = copy.deepcopy(interpretation)
    for key, value in list(transformed.items()):
        transformed[key] = transform_y_down_value(key, value, depth)
    transform_y_down_opening_intervals(transformed, depth=depth)

    scale = transformed.setdefault("scale", {})
    if isinstance(scale, dict):
        original_coordinate_system = coordinate_system_text(interpretation)
        scale["source_coordinate_system"] = original_coordinate_system
        scale["coordinate_system"] = "x east, y north, origin at transformed source south edge"
        scale["coordinate_transform"] = {
            "type": "image_y_down_to_model_y_up",
            "source_depth": depth,
            "source_depth_from": depth_source,
        }
    assumptions = transformed.setdefault("assumptions", [])
    if isinstance(assumptions, list):
        assumptions.append(
            "Image/PDF Y-down source coordinates were transformed into model Y-up coordinates before truth generation."
        )
    transform_info = {
        "type": "image_y_down_to_model_y_up",
        "source_depth": depth,
        "source_depth_from": depth_source,
    }
    return transformed, transform_info, ["source_y_down_coordinates_transformed"]


def import_constraints_path(project_path: str | Path, import_id: str) -> Path:
    """Return the project-local source constraints path for one import."""
    return import_session_path(project_path, import_safe_id(import_id)) / "constraints.json"


def load_import_constraints(
    project_path: str | Path,
    import_id: str,
    *,
    constraints_path: str | Path | None = None,
) -> tuple[dict[str, Any] | None, Path]:
    """Load optional source-fidelity constraints for one import."""
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    path = (
        Path(constraints_path).expanduser().resolve()
        if constraints_path is not None
        else import_constraints_path(root, chosen_id)
    )
    if not path.exists():
        return None, path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"import constraints are not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("import constraints must be a JSON object.")
    data_import_id = data.get("import_id")
    if data_import_id and import_safe_id(str(data_import_id)) != chosen_id:
        raise ValueError(
            f"constraints import_id {data_import_id!r} does not match {chosen_id!r}."
        )
    return data, path


def source_interpretation_default_origin(interpretation: dict[str, Any]) -> str | None:
    """Return the default extracted-evidence origin for source interpretation."""
    for value in (
        interpretation.get("provenance"),
        interpretation.get("source", {}).get("provenance")
        if isinstance(interpretation.get("source"), dict)
        else None,
    ):
        origin = evidence_origin_from_value(value)
        if origin:
            return origin
    return None


def constraint_provenance_from_source(
    value: dict[str, Any],
    *,
    default_origin: str | None,
) -> dict[str, Any] | None:
    """Return provenance for a derived source constraint."""
    for key in ("provenance", "evidence", "source_provenance"):
        provenance = value.get(key)
        if isinstance(provenance, dict):
            result = dict(provenance)
            if default_origin and not evidence_origin_from_value(result):
                result["origin"] = default_origin
            return result
        origin = evidence_origin_from_value(provenance)
        if origin:
            return {"origin": origin}
    if default_origin:
        return {"origin": default_origin}
    return None


def source_wall_axis_for_path(path: Any) -> str | None:
    """Return source wall orientation token for one path."""
    if not isinstance(path, list) or len(path) < 2:
        return None
    axis = wall_axis(path)
    if axis == "x":
        return "vertical"
    if axis == "y":
        return "horizontal"
    return None


def copy_direct_constraints_from_interpretation(
    interpretation: dict[str, Any],
    *,
    default_origin: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """Copy already-structured top-level source constraints from extraction."""
    copied_by_key: dict[str, list[dict[str, Any]]] = {}
    for key in SOURCE_INTERPRETATION_DIRECT_CONSTRAINT_KEYS:
        value = interpretation.get(key)
        if not isinstance(value, list):
            continue
        copied: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            provenance = constraint_provenance_from_source(
                item,
                default_origin=default_origin,
            )
            if provenance is None:
                continue
            constraint = dict(item)
            if not any(
                constraint.get(provenance_key) is not None
                for provenance_key in (
                    "provenance",
                    "evidence",
                    "source_provenance",
                    "origin",
                    "evidence_origin",
                    "extraction_origin",
                )
            ):
                constraint["provenance"] = provenance
            copied.append(constraint)
        if copied:
            copied_by_key[key] = copied
    return copied_by_key


def derive_source_constraints_from_interpretation(
    interpretation: dict[str, Any],
) -> dict[str, Any] | None:
    """Derive machine-checkable source constraints from extracted interpretation.

    This does not invent missing evidence. It only converts explicit extracted
    negative regions, walls, and openings into validator-readable constraints.
    """
    default_origin = source_interpretation_default_origin(interpretation)
    constraints: dict[str, Any] = {
        "version": "1.0",
        "provenance": {"origin": default_origin} if default_origin else {},
        "derived_from_source_interpretation": True,
    }
    direct_constraints = copy_direct_constraints_from_interpretation(
        interpretation,
        default_origin=default_origin,
    )
    constraints.update(direct_constraints)

    wall_constraints: list[dict[str, Any]] = []
    for wall in interpretation.get("walls", interpretation.get("wall_candidates", [])):
        if not isinstance(wall, dict):
            continue
        provenance = constraint_provenance_from_source(
            wall,
            default_origin=default_origin,
        )
        if provenance is None:
            continue
        path = wall.get("path")
        if not isinstance(path, list) or len(path) < 2:
            continue
        constraint: dict[str, Any] = {
            "id": str(
                wall.get("wall_id")
                or wall.get("target_id")
                or wall.get("id")
                or f"wall_constraint_{len(wall_constraints) + 1}"
            ),
            "path": path,
            "path_tolerance": float(wall.get("path_tolerance", 80)),
        }
        if isinstance(wall.get("space_refs"), list):
            constraint["space_refs"] = wall["space_refs"]
        constraint["provenance"] = provenance
        wall_constraints.append(constraint)

    opening_constraints: list[dict[str, Any]] = []
    walls_by_id = {
        str(wall.get("wall_id") or wall.get("id")): wall
        for wall in interpretation.get("walls", interpretation.get("wall_candidates", []))
        if isinstance(wall, dict) and (wall.get("wall_id") or wall.get("id"))
    }
    for opening in interpretation.get("openings", []):
        if not isinstance(opening, dict):
            continue
        opening_id = opening.get("opening_id") or opening.get("id")
        if not opening_id:
            continue
        provenance = constraint_provenance_from_source(
            opening,
            default_origin=default_origin,
        )
        if provenance is None:
            continue
        constraint = {
            "id": str(opening_id),
            "type": str(opening.get("type", "opening")),
        }
        for key in (
            "host_wall",
            "open_to_space",
            "access_from_space",
            "open_side",
            "swing_direction",
            "source_anchor",
            "source_interval",
            "source_interval_mode",
            "source_interval_coordinate_system",
            "interval",
            "interval_mode",
        ):
            if opening.get(key) is not None:
                constraint[key] = opening[key]
        host_wall = str(opening.get("host_wall", ""))
        host_axis = source_wall_axis_for_path(walls_by_id.get(host_wall, {}).get("path"))
        if host_axis:
            constraint["host_wall_axis"] = host_axis
        if (
            (constraint.get("source_interval") is not None or constraint.get("interval") is not None)
            and "interval_mode" not in constraint
            and "source_interval_mode" not in constraint
        ):
            constraint["interval_mode"] = "wall_coordinate"
        if opening.get("open_to_space") and opening.get("access_from_space"):
            constraint["require_host_space_refs"] = True
        constraint["provenance"] = provenance
        opening_constraints.append(constraint)

    negative_region_constraints: list[dict[str, Any]] = []
    for region in interpretation.get("negative_regions", []):
        if not isinstance(region, dict):
            continue
        provenance = constraint_provenance_from_source(
            region,
            default_origin=default_origin,
        )
        if provenance is None:
            continue
        raw_footprint = region.get("footprint") or region.get("polygon")
        bounds = region.get("bounds")
        if raw_footprint is None and not isinstance(bounds, dict):
            continue
        constraint = {
            "id": str(
                region.get("id")
                or region.get("constraint_id")
                or f"negative_region_{len(negative_region_constraints) + 1}"
            ),
            "forbid_spaces": True,
            "forbid_boundary_enclosure": True,
            "coordinate_tolerance": float(region.get("coordinate_tolerance", 80)),
        }
        if raw_footprint is not None:
            constraint["footprint"] = raw_footprint
        if isinstance(bounds, dict):
            constraint["bounds"] = bounds
        constraint["provenance"] = provenance
        negative_region_constraints.append(constraint)

    if wall_constraints:
        constraints.setdefault("wall_constraints", []).extend(wall_constraints)
    if opening_constraints:
        constraints.setdefault("opening_constraints", []).extend(opening_constraints)
    if negative_region_constraints:
        constraints.setdefault("negative_region_constraints", []).extend(
            negative_region_constraints
        )

    has_constraints = any(
        isinstance(constraints.get(key), list) and constraints[key]
        for key in SOURCE_CONSTRAINT_LIST_KEYS
    )
    return constraints if has_constraints else None


def write_interpretation_constraints_if_present(
    project_path: str | Path,
    import_id: str,
    interpretation: dict[str, Any],
) -> str | None:
    """Persist source interpretation constraints into the import session."""
    constraints = interpretation.get("constraints")
    derived_constraints = False
    if not isinstance(constraints, dict):
        constraints = derive_source_constraints_from_interpretation(interpretation)
        derived_constraints = constraints is not None
    if not isinstance(constraints, dict):
        return None
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    payload = {
        "version": str(constraints.get("version", "1.0")),
        "import_id": str(constraints.get("import_id", chosen_id)),
        **{
            key: value
        for key, value in constraints.items()
        if key not in {"version", "import_id"}
        },
    }
    if derived_constraints:
        payload["derived_from_source_interpretation"] = True
    path = import_constraints_path(root, chosen_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return project_relative_path(root, path)


def interpretation_negative_regions(
    interpretation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return normalized negative regions from a source interpretation."""
    regions: list[dict[str, Any]] = []
    for index, region in enumerate(interpretation.get("negative_regions", [])):
        if not isinstance(region, dict):
            continue
        raw_footprint = region.get("footprint") or region.get("polygon")
        if raw_footprint is None and isinstance(region.get("bounds"), dict):
            bounds = region["bounds"]
            min_point = bounds.get("min")
            max_point = bounds.get("max")
            if isinstance(min_point, list) and isinstance(max_point, list):
                raw_footprint = [
                    [min_point[0], min_point[1], 0],
                    [max_point[0], min_point[1], 0],
                    [max_point[0], max_point[1], 0],
                    [min_point[0], max_point[1], 0],
                ]
        if raw_footprint is None:
            continue
        footprint = footprint_from_payload(
            raw_footprint,
            label=f"negative_regions[{index}].footprint",
        )
        regions.append(
            {
                "id": str(region.get("id") or f"negative_region_{index + 1}"),
                "kind": str(region.get("kind") or "outside_plan"),
                "enforcement": str(region.get("enforcement") or "auto"),
                "footprint": footprint,
                "bounds": polygon_bounds(footprint),
                "area_m2": polygon_area_mm2(footprint) / 1_000_000,
            }
        )
    return regions


def dimension_constraints_for_candidate(
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return normalized dimension constraints for one space candidate."""
    constraints: list[dict[str, Any]] = []
    raw_constraints = candidate.get("dimension_constraints", [])
    if isinstance(raw_constraints, list):
        for raw in raw_constraints:
            if not isinstance(raw, dict):
                continue
            axis = raw.get("axis")
            length = raw.get("length")
            if axis not in {"x", "y"} or length is None:
                continue
            constraints.append(
                {
                    "axis": axis,
                    "length": float(length),
                    "tolerance": float(
                        raw.get("tolerance", DEFAULT_DIMENSION_CONSTRAINT_TOLERANCE)
                    ),
                    "source": raw.get("source"),
                }
            )
    if candidate.get("expected_width") is not None:
        constraints.append(
            {
                "axis": "x",
                "length": float(candidate["expected_width"]),
                "tolerance": float(
                    candidate.get("expected_width_tolerance", DEFAULT_DIMENSION_CONSTRAINT_TOLERANCE)
                ),
                "source": "expected_width",
            }
        )
    if candidate.get("expected_depth") is not None:
        constraints.append(
            {
                "axis": "y",
                "length": float(candidate["expected_depth"]),
                "tolerance": float(
                    candidate.get("expected_depth_tolerance", DEFAULT_DIMENSION_CONSTRAINT_TOLERANCE)
                ),
                "source": "expected_depth",
            }
            )
    return constraints


def candidate_selection_score(
    *,
    area_delta_ratio: float | None,
    dimension_deltas: list[dict[str, Any]],
    confidence: float,
) -> float:
    """Return a lower-is-better score for competing candidates of one space."""
    area_score = area_delta_ratio if area_delta_ratio is not None else 0.25
    if dimension_deltas:
        dimension_score = max(
            float(item["delta"]) / max(float(item["tolerance"]), 1.0)
            for item in dimension_deltas
        )
    else:
        dimension_score = 0.25
    confidence_bonus = max(0.0, min(1.0, confidence)) * 0.05
    return round(area_score + dimension_score - confidence_bonus, 6)


def review_space_candidate(
    candidate: dict[str, Any],
    *,
    candidate_index: int,
    negative_regions: list[dict[str, Any]],
    area_tolerance_ratio: float,
    negative_space_overlap_tolerance_m2: float,
) -> dict[str, Any]:
    """Score one interpreted space candidate before it can become truth."""
    if not isinstance(candidate, dict):
        raise ValueError(f"space_candidates[{candidate_index}] must be an object.")
    raw_footprint = candidate.get("footprint")
    if raw_footprint is None:
        raise ValueError(f"space_candidates[{candidate_index}].footprint is required.")
    footprint = footprint_from_payload(
        raw_footprint,
        label=f"space_candidates[{candidate_index}].footprint",
    )
    area_m2 = polygon_area_mm2(footprint) / 1_000_000
    bounds = polygon_bounds(footprint)
    issues: list[dict[str, Any]] = []
    area_delta_ratio: float | None = None
    dimension_deltas: list[dict[str, Any]] = []
    label_anchor = normalize_label_anchor(candidate)
    if label_anchor is not None and not point_in_polygon_2d(label_anchor, footprint):
        issues.append(
            {
                "code": "label_anchor_outside_footprint",
                "severity": "reject",
                "label_anchor": label_anchor,
            }
        )

    label_area_m2 = (
        candidate.get("label_area_m2")
        if candidate.get("label_area_m2") is not None
        else candidate.get("expected_area_m2")
    )
    if label_area_m2 is not None:
        expected_area = float(label_area_m2)
        if expected_area <= 0:
            raise ValueError(
                f"space_candidates[{candidate_index}].label_area_m2 must be positive."
            )
        area_delta_ratio = abs(area_m2 - expected_area) / expected_area
        if area_delta_ratio > area_tolerance_ratio:
            issues.append(
                {
                    "code": "room_label_area_mismatch",
                    "severity": "reject",
                    "expected_area_m2": expected_area,
                    "actual_area_m2": area_m2,
                    "delta_ratio": area_delta_ratio,
                    "tolerance_ratio": area_tolerance_ratio,
                }
            )

    for constraint in dimension_constraints_for_candidate(candidate):
        actual = bounds[1] - bounds[0] if constraint["axis"] == "x" else bounds[3] - bounds[2]
        delta = abs(actual - constraint["length"])
        dimension_deltas.append(
            {
                "axis": constraint["axis"],
                "expected_length": constraint["length"],
                "actual_length": actual,
                "delta": delta,
                "tolerance": constraint["tolerance"],
                "source": constraint.get("source"),
            }
        )
        if delta > constraint["tolerance"]:
            issues.append(
                {
                    "code": "dimension_constraint_mismatch",
                    "severity": "reject",
                    "axis": constraint["axis"],
                    "expected_length": constraint["length"],
                    "actual_length": actual,
                    "delta": delta,
                    "tolerance": constraint["tolerance"],
                    "source": constraint.get("source"),
                }
            )

    strong_positive_evidence = (
        area_delta_ratio is not None
        and area_delta_ratio <= DEFAULT_STRONG_LABEL_AREA_TOLERANCE_RATIO
        and bool(dimension_deltas)
        and all(
            float(item["delta"]) <= min(float(item["tolerance"]), DEFAULT_STRONG_DIMENSION_TOLERANCE)
            for item in dimension_deltas
        )
    )
    for region in negative_regions:
        overlap_m2 = (
            polygon_overlap_with_bounds_area_mm2(footprint, region["bounds"])
            / 1_000_000
        )
        if overlap_m2 > negative_space_overlap_tolerance_m2:
            if strong_positive_evidence and region.get("enforcement") != "hard":
                issues.append(
                    {
                        "code": "negative_space_conflict_overridden",
                        "severity": "warning",
                        "negative_region_id": region["id"],
                        "negative_region_kind": region["kind"],
                        "overlap_area_m2": overlap_m2,
                        "reason": "room label area and dimension constraints are stronger",
                    }
                )
                continue
            issues.append(
                {
                    "code": "negative_space_overlap",
                    "severity": "reject",
                    "negative_region_id": region["id"],
                    "negative_region_kind": region["kind"],
                    "overlap_area_m2": overlap_m2,
                    "tolerance_m2": negative_space_overlap_tolerance_m2,
                }
            )

    status = "rejected" if any(issue["severity"] == "reject" for issue in issues) else "accepted"
    return {
        "candidate_id": str(candidate.get("id") or f"space_candidate_{candidate_index + 1}"),
        "space_id": str(candidate.get("space_id") or candidate.get("id") or f"space_{candidate_index + 1}"),
        "status": status,
        "type": candidate.get("type", "other"),
        "name": candidate.get("name"),
        "confidence": float(candidate.get("confidence", 0.5)),
        "computed_area_m2": area_m2,
        "label_area_m2": label_area_m2,
        "label_anchor": label_anchor,
        "area_delta_ratio": area_delta_ratio,
        "dimension_deltas": dimension_deltas,
        "selection_score": candidate_selection_score(
            area_delta_ratio=area_delta_ratio,
            dimension_deltas=dimension_deltas,
            confidence=float(candidate.get("confidence", 0.5)),
        ),
        "footprint": footprint,
        "bounds": bounds,
        "issues": issues,
        "candidate": candidate,
    }


def space_payload_from_candidate(
    import_id: str,
    review: dict[str, Any],
    *,
    wall_height: float,
    assumptions: list[str],
) -> dict[str, Any]:
    """Return one design_model space payload from an accepted candidate."""
    min_x, max_x, min_y, max_y = review["bounds"]
    candidate = review["candidate"]
    payload = {
        "type": str(candidate.get("type", review.get("type", "other"))),
        "bounds": {
            "min": [min_x, min_y, 0],
            "max": [max_x, max_y, float(wall_height)],
        },
        "center": [
            (min_x + max_x) / 2,
            (min_y + max_y) / 2,
            float(wall_height) / 2,
        ],
        "footprint": review["footprint"],
        "source": {
            "kind": "import_floorplan",
            "import_id": import_id,
            "confidence": review["confidence"],
            "assumptions": assumptions,
            "candidate_id": review["candidate_id"],
            "computed_area_m2": review["computed_area_m2"],
        },
    }
    if candidate.get("name"):
        payload["name"] = str(candidate["name"])
    if candidate.get("label"):
        payload["label"] = str(candidate["label"])
    if candidate.get("label_area_m2") is not None:
        payload["source"]["label_area_m2"] = float(candidate["label_area_m2"])
    return payload


def wall_payload_from_interpretation(
    import_id: str,
    wall: dict[str, Any],
    *,
    wall_height: float,
    wall_thickness: float,
    assumptions: list[str],
    index: int,
) -> tuple[str, dict[str, Any]]:
    """Return one explicit wall payload from source interpretation."""
    wall_id = str(wall.get("wall_id") or wall.get("id") or f"{import_id}_wall_{index + 1:03d}")
    path = wall.get("path")
    if not isinstance(path, list) or len(path) < 2:
        raise ValueError(f"walls[{index}].path must contain at least two points.")
    normalized_path = [
        normalize_3d_point(point, label=f"walls[{index}].path[{point_index}]")
        for point_index, point in enumerate(path)
    ]
    payload = {
        "path": normalized_path,
        "height": float(wall.get("height", wall_height)),
        "thickness": float(wall.get("thickness", wall_thickness)),
        "alignment": wall.get("alignment", "center"),
        "layer": wall.get("layer", "Walls"),
        "source": {
            "kind": "import_floorplan",
            "import_id": import_id,
            "confidence": float(wall.get("confidence", 0.58)),
            "assumptions": assumptions,
        },
    }
    if wall.get("space_refs"):
        payload["source"]["space_refs"] = wall["space_refs"]
    return wall_id, payload


def opening_source_interval(opening: dict[str, Any]) -> tuple[float, float] | None:
    """Return a source-backed hosted opening interval when the extractor provides one."""
    interval = opening.get("source_interval") or opening.get("interval")
    normalized = normalize_interval_values(interval)
    if normalized is None:
        return None
    return normalized[0], normalized[1]


def opening_payload_from_interpretation(
    import_id: str,
    opening: dict[str, Any],
    *,
    walls: dict[str, dict[str, Any]],
    assumptions: list[str],
    index: int,
) -> tuple[str, dict[str, Any]]:
    """Return one hosted opening payload from source interpretation."""
    opening_id = str(
        opening.get("opening_id") or opening.get("id") or f"{import_id}_opening_{index + 1:03d}"
    )
    source_interval = opening_source_interval(opening)
    offset = float(opening.get("offset", 0))
    if source_interval is not None:
        host_wall = walls.get(str(opening.get("host_wall", "")))
        host_axis = (
            wall_axis(host_wall.get("path", [])) if isinstance(host_wall, dict) else None
        )
        if (
            host_axis is not None
            and not interval_is_offset_mode(opening)
            and isinstance(host_wall, dict)
        ):
            offset = interval_offset_from_wall_start(
                host_wall.get("path", []),
                host_axis,
                source_interval,
            )
        else:
            offset = source_interval[0]
        width = source_interval[1] - source_interval[0]
    else:
        width = float(opening["width"])
    payload: dict[str, Any] = {
        "type": opening.get("type", "opening"),
        "host_wall": opening["host_wall"],
        "offset": offset,
        "width": width,
        "height": float(opening["height"]),
        "sill_height": float(opening.get("sill_height", 0)),
        "representation": "hosted",
        "layer": opening.get("layer") or ("Windows" if opening.get("type") == "window" else "Doors"),
        "source": {
            "kind": "import_floorplan",
            "import_id": import_id,
            "confidence": float(opening.get("confidence", 0.5)),
            "assumptions": assumptions,
        },
    }
    if opening.get("swing_direction"):
        payload["swing_direction"] = opening["swing_direction"]
    if opening.get("open_to_space"):
        payload["open_to_space"] = opening["open_to_space"]
    if opening.get("access_from_space"):
        payload["access_from_space"] = opening["access_from_space"]
    if opening.get("open_side"):
        payload["open_side"] = opening["open_side"]
    source_evidence = {}
    for key in (
        "source_anchor",
        "source_interval",
        "source_interval_mode",
        "source_interval_coordinate_system",
        "is_entry",
        "is_exterior",
    ):
        if key in opening:
            source_evidence[key] = opening[key]
    if source_evidence:
        payload["source"]["opening_evidence"] = source_evidence
    return opening_id, payload


def generation_opening_priority(opening: dict[str, Any]) -> int:
    """Return semantic priority for resolving hosted opening interval conflicts."""
    opening_type = str(opening.get("type", "opening"))
    if opening_type == "door":
        return 3
    if opening_type == "opening":
        return 2
    if opening_type == "window":
        return 1
    return 0


def generation_opening_confidence(opening: dict[str, Any]) -> float:
    """Return source confidence for ordering generation-time opening repairs."""
    source = opening.get("source", {})
    if not isinstance(source, dict):
        return 0.0
    return float(source.get("confidence", 0.0))


def normalize_generation_opening_conflicts(
    design_model: dict[str, Any],
    import_id: str,
    *,
    min_opening_width: float = DEFAULT_MIN_HOSTED_OPENING_WIDTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> dict[str, Any]:
    """Clip or remove overlapping hosted openings before bridge execution."""
    openings = design_model.get("openings", {})
    walls = design_model.get("walls", {})
    adjusted_openings: list[dict[str, Any]] = []
    removed_openings: list[dict[str, Any]] = []
    inspected_hosts: list[str] = []

    openings_by_host: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for opening_id, opening in openings.items():
        if not isinstance(opening, dict):
            continue
        source = opening.get("source", {})
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        host_wall = str(opening.get("host_wall", ""))
        if host_wall:
            openings_by_host.setdefault(host_wall, []).append((opening_id, opening))

    for host_wall, hosted_openings in sorted(openings_by_host.items()):
        if len(hosted_openings) < 2:
            continue
        wall = walls.get(host_wall)
        if not isinstance(wall, dict):
            continue
        length = wall_length(wall.get("path", []))
        if length <= coordinate_match_tolerance:
            continue

        inspected_hosts.append(host_wall)
        accepted_intervals: list[tuple[float, float, str]] = []
        for opening_id, opening in sorted(
            hosted_openings,
            key=lambda item: (
                -generation_opening_priority(item[1]),
                -generation_opening_confidence(item[1]),
                float(item[1].get("offset", 0.0)),
                item[0],
            ),
        ):
            original_offset = float(opening.get("offset", 0.0))
            original_width = float(opening.get("width", 0.0))
            raw_start = max(0.0, original_offset)
            raw_end = min(length, original_offset + original_width)
            if raw_end - raw_start < min_opening_width:
                openings.pop(opening_id, None)
                removed_openings.append(
                    {
                        "opening_id": opening_id,
                        "host_wall": host_wall,
                        "reason": "opening interval is too small or outside host wall",
                    }
                )
                continue

            available_spans = subtract_intervals(
                (raw_start, raw_end),
                [(start, end) for start, end, _ in accepted_intervals],
                tolerance=coordinate_match_tolerance,
            )
            available_spans = [
                span
                for span in available_spans
                if span[1] - span[0] >= min_opening_width
            ]
            if not available_spans:
                openings.pop(opening_id, None)
                removed_openings.append(
                    {
                        "opening_id": opening_id,
                        "host_wall": host_wall,
                        "reason": "opening fully overlapped higher-priority host openings",
                    }
                )
                continue

            chosen_start, chosen_end = max(
                available_spans,
                key=lambda span: (span[1] - span[0], -abs(span[0] - raw_start)),
            )
            chosen_width = chosen_end - chosen_start
            if (
                abs(chosen_start - original_offset) > coordinate_match_tolerance
                or abs(chosen_width - original_width) > coordinate_match_tolerance
            ):
                opening["offset"] = round(chosen_start, 3)
                opening["width"] = round(chosen_width, 3)
                adjusted_openings.append(
                    {
                        "opening_id": opening_id,
                        "host_wall": host_wall,
                        "from": {
                            "offset": original_offset,
                            "width": original_width,
                        },
                        "to": {
                            "offset": opening["offset"],
                            "width": opening["width"],
                        },
                        "reason": "opening clipped to avoid overlap with higher-priority host openings",
                    }
                )
            accepted_intervals.append((chosen_start, chosen_end, opening_id))
            accepted_intervals.sort(key=lambda interval: (interval[0], interval[1]))

    return {
        "status": "normalized" if adjusted_openings or removed_openings else "unchanged",
        "inspected_hosts": inspected_hosts,
        "adjusted_openings": adjusted_openings,
        "removed_openings": removed_openings,
        "min_opening_width": min_opening_width,
    }


def wall_variable_axis(axis: str) -> str:
    """Return the changing coordinate axis for an axis-aligned wall."""
    return "y" if axis == "x" else "x"


def interval_offset_from_wall_start(
    path: list[Any],
    axis: str,
    interval: tuple[float, float],
) -> float:
    """Return a sorted interval's offset measured from the wall path start."""
    variable_axis = wall_variable_axis(axis)
    start_value = point_axis_value(path[0], variable_axis)
    end_value = point_axis_value(path[-1], variable_axis)
    interval_start, interval_end = interval
    if end_value >= start_value:
        return max(0.0, interval_start - start_value)
    return max(0.0, start_value - interval_end)


def opening_interval_on_wall(
    opening: dict[str, Any],
    wall: dict[str, Any],
    axis: str,
) -> tuple[float, float]:
    """Return an opening interval in the wall's sorted variable coordinate."""
    path = wall.get("path", [])
    variable_axis = wall_variable_axis(axis)
    start_value = point_axis_value(path[0], variable_axis)
    end_value = point_axis_value(path[-1], variable_axis)
    direction = 1.0 if end_value >= start_value else -1.0
    offset = float(opening.get("offset", 0))
    width = float(opening.get("width", 0))
    first = start_value + direction * offset
    second = start_value + direction * (offset + width)
    return (min(first, second), max(first, second))


def space_edge_intervals_for_wall(
    design_model: dict[str, Any],
    import_id: str,
    *,
    axis: str,
    line_coordinate: float,
    wall_interval: tuple[float, float],
    coordinate_match_tolerance: float,
) -> list[dict[str, Any]]:
    """Return imported space footprint edges overlapping one wall interval."""
    edges: list[dict[str, Any]] = []
    wall_start, wall_end = wall_interval
    for space_id, space in design_model.get("spaces", {}).items():
        source = space.get("source", {}) if isinstance(space, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        footprint = space.get("footprint")
        if not isinstance(footprint, list) or len(footprint) < 3:
            continue
        center = space.get("center")
        if isinstance(center, list) and len(center) >= 2:
            center_value = float(center[0] if axis == "x" else center[1])
        else:
            bounds = space.get("bounds", {})
            min_point = bounds.get("min", [0, 0, 0])
            max_point = bounds.get("max", [0, 0, 0])
            center_value = (
                float(min_point[0] + max_point[0]) / 2
                if axis == "x"
                else float(min_point[1] + max_point[1]) / 2
            )
        side = center_value - line_coordinate
        if abs(side) <= coordinate_match_tolerance:
            continue

        for index, raw_start in enumerate(footprint):
            raw_end = footprint[(index + 1) % len(footprint)]
            edge_path = [
                normalize_3d_point(raw_start, label=f"{space_id} footprint[{index}]"),
                normalize_3d_point(
                    raw_end,
                    label=f"{space_id} footprint[{(index + 1) % len(footprint)}]",
                ),
            ]
            if wall_axis(edge_path, tolerance=coordinate_match_tolerance) != axis:
                continue
            if (
                abs(segment_line_coordinate(edge_path, axis) - line_coordinate)
                > coordinate_match_tolerance
            ):
                continue
            edge_start, edge_end = segment_interval(edge_path, axis)
            overlap_start = max(wall_start, edge_start)
            overlap_end = min(wall_end, edge_end)
            if overlap_end <= overlap_start + coordinate_match_tolerance:
                continue
            edges.append(
                {
                    "space_id": space_id,
                    "type": space.get("type", "other"),
                    "label": space.get("label"),
                    "interval": (overlap_start, overlap_end),
                    "side": 1 if side > 0 else -1,
                    "edge_index": index,
                }
            )
    return edges


def should_infer_circulation_opening(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Return whether adjacent space semantics imply a doorless passage opening."""
    first_type = str(first.get("type", "other"))
    second_type = str(second.get("type", "other"))
    types = {first_type, second_type}
    if "hallway" not in types:
        return False
    return bool(types & {"living_room", "dining_room", "kitchen", "office", "other"})


def is_circulation_gap(
    adjacent_spaces: list[dict[str, Any]],
    *,
    length: float,
    max_length: float = DEFAULT_MAX_CIRCULATION_GAP_LENGTH,
) -> bool:
    """Return whether a boundary gap can remain open for normal circulation."""
    if length > max_length:
        return False
    for first_index, first in enumerate(adjacent_spaces):
        for second in adjacent_spaces[first_index + 1 :]:
            if should_infer_circulation_opening(first, second):
                return True
    return False


def infer_generation_circulation_openings(
    design_model: dict[str, Any],
    import_id: str,
    *,
    assumptions: list[str],
    min_opening_width: float = 650.0,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> dict[str, Any]:
    """Add hosted passage openings where a generated wall blocks circulation."""
    openings = design_model.setdefault("openings", {})
    added_openings: list[str] = []
    inspected_pairs: list[dict[str, Any]] = []

    for wall_id, wall in list(design_model.get("walls", {}).items()):
        source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        path = wall.get("path", [])
        axis = wall_axis(path, tolerance=coordinate_match_tolerance)
        if axis is None:
            continue

        line_coordinate = segment_line_coordinate(path, axis)
        wall_interval = segment_interval(path, axis)
        wall_height = float(wall.get("height", DEFAULT_WALL_HEIGHT))
        existing_intervals = [
            opening_interval_on_wall(opening, wall, axis)
            for opening in openings.values()
            if isinstance(opening, dict) and opening.get("host_wall") == wall_id
        ]
        edges = space_edge_intervals_for_wall(
            design_model,
            import_id,
            axis=axis,
            line_coordinate=line_coordinate,
            wall_interval=wall_interval,
            coordinate_match_tolerance=coordinate_match_tolerance,
        )

        candidate_intervals: list[tuple[float, float]] = []
        for first_index, first in enumerate(edges):
            for second in edges[first_index + 1 :]:
                if int(first["side"]) == int(second["side"]):
                    continue
                if not should_infer_circulation_opening(first, second):
                    continue
                overlap = (
                    max(float(first["interval"][0]), float(second["interval"][0])),
                    min(float(first["interval"][1]), float(second["interval"][1])),
                )
                if overlap[1] - overlap[0] < min_opening_width:
                    continue
                candidate_intervals.append(overlap)
                inspected_pairs.append(
                    {
                        "wall_id": wall_id,
                        "spaces": [first["space_id"], second["space_id"]],
                        "space_types": sorted([str(first["type"]), str(second["type"])]),
                        "interval": [overlap[0], overlap[1]],
                    }
                )

        for interval_index, interval in enumerate(
            merge_intervals(candidate_intervals, tolerance=coordinate_match_tolerance),
            start=1,
        ):
            for start, end in subtract_intervals(
                interval,
                existing_intervals,
                tolerance=coordinate_match_tolerance,
            ):
                width = end - start
                if width < min_opening_width:
                    continue
                opening_id = f"{wall_id}_circulation_opening_{interval_index:02d}"
                suffix = 2
                while opening_id in openings:
                    opening_id = f"{wall_id}_circulation_opening_{interval_index:02d}_{suffix}"
                    suffix += 1
                openings[opening_id] = {
                    "type": "opening",
                    "host_wall": wall_id,
                    "offset": interval_offset_from_wall_start(path, axis, (start, end)),
                    "width": width,
                    "height": wall_height,
                    "sill_height": 0,
                    "representation": "hosted",
                    "layer": "Other",
                    "source": {
                        "kind": "import_floorplan",
                        "import_id": import_id,
                        "confidence": 0.62,
                        "assumptions": [
                            *assumptions,
                            (
                                "A doorless circulation opening was inferred where "
                                "a wall crossed a shared hallway-to-public-space edge."
                            ),
                        ],
                    },
                }
                added_openings.append(opening_id)

    return {
        "status": "inferred" if added_openings else "unchanged",
        "added_openings": added_openings,
        "inspected_pairs": inspected_pairs,
    }


def normalized_label_token(value: Any) -> str:
    """Return a coarse lowercase token for matching opening names to spaces."""
    return "".join(character for character in str(value).lower() if character.isalnum())


def space_match_tokens(space_id: str, space: dict[str, Any]) -> set[str]:
    """Return normalized tokens that may identify one imported space."""
    tokens = {normalized_label_token(space_id)}
    if "_" in space_id:
        tokens.add(normalized_label_token(space_id.rsplit("_", 1)[0]))
    for key in ("type", "label", "name"):
        if space.get(key):
            tokens.add(normalized_label_token(space[key]))
    return {token for token in tokens if token}


def infer_opening_target_space_id(
    opening_id: str,
    opening: dict[str, Any],
    spaces: dict[str, dict[str, Any]],
) -> str | None:
    """Infer the room a door belongs to from explicit fields or stable IDs."""
    explicit = opening.get("open_to_space") or opening.get("target_space")
    if explicit and explicit in spaces:
        return str(explicit)

    opening_token = normalized_label_token(opening_id)
    if opening.get("name"):
        opening_token += normalized_label_token(opening["name"])
    matches: list[tuple[int, str]] = []
    for space_id, space in spaces.items():
        for token in space_match_tokens(space_id, space):
            if token and token in opening_token:
                matches.append((len(token), space_id))
                break
    if not matches:
        return None
    matches.sort(reverse=True)
    return matches[0][1]


def wall_space_refs(wall: dict[str, Any]) -> list[str]:
    """Return semantic space references attached to an imported wall."""
    source = wall.get("source", {}) if isinstance(wall, dict) else {}
    refs = source.get("space_refs") if isinstance(source, dict) else None
    if not isinstance(refs, list):
        return []
    return [str(ref) for ref in refs]


def opening_access_from_space(opening: dict[str, Any]) -> str | None:
    """Return the source-side space used to access an opening when known."""
    for key in ("access_from_space", "from_space", "source_space"):
        value = opening.get(key)
        if value:
            return str(value)
    source = opening.get("source", {})
    if isinstance(source, dict):
        evidence = source.get("opening_evidence", {})
        if isinstance(evidence, dict) and evidence.get("access_from_space"):
            return str(evidence["access_from_space"])
    return None


def opening_is_exterior_access(opening_id: str, opening: dict[str, Any]) -> bool:
    """Return whether a door is explicitly source-backed exterior access."""
    access_from = normalized_label_token(opening_access_from_space(opening) or "")
    if access_from in {"exterior", "outside", "outdoor", "entry"}:
        return True
    source = opening.get("source", {})
    evidence = source.get("opening_evidence", {}) if isinstance(source, dict) else {}
    explicit_flags = (
        opening.get("is_entry"),
        opening.get("is_exterior"),
        opening.get("entry"),
        opening.get("exterior"),
    )
    if isinstance(evidence, dict):
        explicit_flags += (
            evidence.get("is_entry"),
            evidence.get("is_exterior"),
        )
    if any(bool(flag) for flag in explicit_flags):
        return True
    opening_token = normalized_label_token(opening_id)
    if opening.get("name"):
        opening_token += normalized_label_token(opening["name"])
    return any(
        token in opening_token
        for token in ("entrydoor", "frontdoor", "exteriordoor")
    )


def door_host_wall_score(
    wall: dict[str, Any],
    *,
    opening_id: str,
    wall_id: str,
    current_host_wall: str,
    target_space_id: str,
    spaces: dict[str, dict[str, Any]],
    opening: dict[str, Any],
) -> float:
    """Return a semantic score for hosting a target-space door on one wall."""
    refs = wall_space_refs(wall)
    if target_space_id not in refs:
        return -1.0

    target_type = str(spaces.get(target_space_id, {}).get("type", "other"))
    access_from_space = opening_access_from_space(opening)
    exterior_access = opening_is_exterior_access(opening_id, opening)
    known_other_refs = [ref for ref in refs if ref != target_space_id and ref in spaces]
    other_types = {
        str(spaces.get(ref, {}).get("type", "other"))
        for ref in refs
        if ref != target_space_id
    }
    score = 1000.0
    if access_from_space:
        if access_from_space in spaces:
            if access_from_space in refs:
                score += 260.0
            else:
                score -= 140.0
        elif normalized_label_token(access_from_space) in {"exterior", "outside", "outdoor"}:
            score += 180.0 if not known_other_refs else -80.0
    if "hallway" in other_types:
        score += 150.0 if target_type in {"bedroom", "bathroom", "storage"} else 90.0
    if other_types & {"living_room", "dining_room", "kitchen", "office"}:
        score += 45.0
    if other_types & {"bedroom", "bathroom", "storage"}:
        score += 10.0
    if target_type == "balcony":
        if other_types & {"living_room", "dining_room", "kitchen", "bedroom", "office"}:
            score += 190.0
        elif not known_other_refs and not exterior_access:
            score -= 120.0
    if exterior_access and not known_other_refs:
        score += 220.0
    if wall_id == current_host_wall:
        score += 5.0
    return score


def is_single_space_boundary_host(
    wall: dict[str, Any] | None,
    *,
    target_space_id: str,
    spaces: dict[str, dict[str, Any]],
) -> bool:
    """Return whether a door is already hosted on a target-space boundary wall."""
    if not isinstance(wall, dict):
        return False
    refs = wall_space_refs(wall)
    if target_space_id not in refs:
        return False
    known_other_refs = [ref for ref in refs if ref != target_space_id and ref in spaces]
    return not known_other_refs


def point_on_wall_at_distance(path: list[Any], distance: float) -> list[float]:
    """Return a point along a wall path at a distance from the path start."""
    start = normalize_3d_point(path[0], label="wall path start")
    end = normalize_3d_point(path[-1], label="wall path end")
    length = wall_length([start, end])
    if length <= 0:
        return start
    ratio = max(0.0, min(1.0, distance / length))
    return [
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
        start[2] + (end[2] - start[2]) * ratio,
    ]


def walls_share_endpoint(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    tolerance: float,
) -> bool:
    """Return whether two walls meet at an endpoint."""
    first_path = first.get("path", [])
    second_path = second.get("path", [])
    if not isinstance(first_path, list) or not isinstance(second_path, list):
        return False
    if len(first_path) < 2 or len(second_path) < 2:
        return False
    return any(
        point_matches(first_point, second_point, tolerance=tolerance)
        for first_point in (first_path[0], first_path[-1])
        for second_point in (second_path[0], second_path[-1])
    )


def relocated_opening_offset(
    opening: dict[str, Any],
    current_wall: dict[str, Any] | None,
    target_wall: dict[str, Any],
    *,
    coordinate_match_tolerance: float,
) -> float:
    """Return an opening offset after moving it to a better host wall."""
    width = float(opening.get("width", 0))
    old_offset = float(opening.get("offset", 0))
    target_path = target_wall.get("path", [])
    target_axis = wall_axis(target_path, tolerance=coordinate_match_tolerance)
    if target_axis is None:
        return max(0.0, old_offset)

    target_length = wall_length(target_path)
    if target_length <= width:
        return 0.0

    if current_wall is None:
        return min(max(0.0, old_offset), target_length - width)

    current_path = current_wall.get("path", [])
    if not isinstance(current_path, list) or len(current_path) < 2:
        return min(max(0.0, old_offset), target_length - width)

    reference_center = point_on_wall_at_distance(current_path, old_offset + width / 2)
    variable_axis = wall_variable_axis(target_axis)
    center_value = point_axis_value(reference_center, variable_axis)
    interval_start, interval_end = segment_interval(target_path, target_axis)
    min_center = interval_start + width / 2
    max_center = interval_end - width / 2
    clamped_center = min(max(center_value, min_center), max_center)

    if (
        abs(center_value - clamped_center) > coordinate_match_tolerance
        and old_offset > 0
        and walls_share_endpoint(
            current_wall,
            target_wall,
            tolerance=coordinate_match_tolerance,
        )
    ):
        return min(max(0.0, old_offset), target_length - width)

    interval = (clamped_center - width / 2, clamped_center + width / 2)
    return min(
        max(0.0, interval_offset_from_wall_start(target_path, target_axis, interval)),
        target_length - width,
    )


def door_open_side_for_space(
    wall: dict[str, Any],
    space: dict[str, Any],
    *,
    coordinate_match_tolerance: float,
) -> str | None:
    """Return normal/opposite for the side of a wall containing a space center."""
    path = wall.get("path", [])
    if wall_axis(path, tolerance=coordinate_match_tolerance) is None:
        return None
    if not isinstance(path, list) or len(path) < 2:
        return None
    center = space.get("center")
    if not isinstance(center, list) or len(center) < 2:
        return None
    start = normalize_3d_point(path[0], label="wall path start")
    end = normalize_3d_point(path[-1], label="wall path end")
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length <= 0:
        return None
    normal = (-dy / length, dx / length)
    vector = (float(center[0]) - start[0], float(center[1]) - start[1])
    return "normal" if normal[0] * vector[0] + normal[1] * vector[1] >= 0 else "opposite"


def normalize_generation_door_hosts(
    design_model: dict[str, Any],
    import_id: str,
    *,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    min_score_delta: float = 25.0,
) -> dict[str, Any]:
    """Repair semantically wrong door host walls before truth is written."""
    spaces = design_model.get("spaces", {})
    walls = design_model.get("walls", {})
    openings = design_model.get("openings", {})
    repaired_openings: list[dict[str, Any]] = []

    for opening_id, opening in openings.items():
        if not isinstance(opening, dict) or opening.get("type") != "door":
            continue
        source = opening.get("source", {}) if isinstance(opening, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        target_space_id = infer_opening_target_space_id(opening_id, opening, spaces)
        if target_space_id is None:
            continue

        current_host_wall = str(opening.get("host_wall", ""))
        current_wall = walls.get(current_host_wall)
        current_score = (
            door_host_wall_score(
                current_wall,
                opening_id=opening_id,
                wall_id=current_host_wall,
                current_host_wall=current_host_wall,
                target_space_id=target_space_id,
                spaces=spaces,
                opening=opening,
            )
            if isinstance(current_wall, dict)
            else -1.0
        )
        scored_candidates = [
            (
                door_host_wall_score(
                    wall,
                    opening_id=opening_id,
                    wall_id=wall_id,
                    current_host_wall=current_host_wall,
                    target_space_id=target_space_id,
                    spaces=spaces,
                    opening=opening,
                ),
                wall_id,
                wall,
            )
            for wall_id, wall in walls.items()
            if isinstance(wall, dict)
        ]
        scored_candidates = [
            candidate for candidate in scored_candidates if candidate[0] >= 0
        ]
        if not scored_candidates:
            continue
        scored_candidates.sort(reverse=True, key=lambda item: item[0])
        best_score, best_wall_id, best_wall = scored_candidates[0]
        if (
            best_wall_id == current_host_wall
            or best_score < current_score + min_score_delta
            or (
                opening_is_exterior_access(opening_id, opening)
                and is_single_space_boundary_host(
                    current_wall if isinstance(current_wall, dict) else None,
                    target_space_id=target_space_id,
                    spaces=spaces,
                )
            )
        ):
            opening["open_to_space"] = target_space_id
            side_wall = current_wall if isinstance(current_wall, dict) else best_wall
            open_side = door_open_side_for_space(
                side_wall,
                spaces[target_space_id],
                coordinate_match_tolerance=coordinate_match_tolerance,
            )
            if open_side:
                opening["open_side"] = open_side
            continue

        previous_host = current_host_wall
        opening["host_wall"] = best_wall_id
        opening["offset"] = relocated_opening_offset(
            opening,
            current_wall if isinstance(current_wall, dict) else None,
            best_wall,
            coordinate_match_tolerance=coordinate_match_tolerance,
        )
        opening["open_to_space"] = target_space_id
        open_side = door_open_side_for_space(
            best_wall,
            spaces[target_space_id],
            coordinate_match_tolerance=coordinate_match_tolerance,
        )
        if open_side:
            opening["open_side"] = open_side
        opening.setdefault("source", {}).setdefault("repairs", []).append(
            {
                "code": "door_host_wall_repaired",
                "from_host_wall": previous_host,
                "to_host_wall": best_wall_id,
                "target_space_id": target_space_id,
                "reason": "door host wall matched target room and circulation adjacency",
            }
        )
        repaired_openings.append(
            {
                "opening_id": opening_id,
                "from_host_wall": previous_host,
                "to_host_wall": best_wall_id,
                "target_space_id": target_space_id,
                "offset": opening["offset"],
                "open_side": opening.get("open_side"),
                "score_delta": best_score - current_score,
            }
        )

    return {
        "status": "repaired" if repaired_openings else "unchanged",
        "repaired_openings": repaired_openings,
    }


def path_start_shift_after_trim(original_path: list[Any], new_path: list[Any], axis: str) -> float:
    """Return the offset shift caused by moving a wall start point during trim."""
    original_start = point_axis_value(original_path[0], axis)
    original_end = point_axis_value(original_path[-1], axis)
    new_start = point_axis_value(new_path[0], axis)
    if original_end >= original_start:
        return max(0.0, new_start - original_start)
    return max(0.0, original_start - new_start)


def wall_path_from_interval_preserving_direction(
    original_path: list[Any],
    axis: str,
    line_coordinate: float,
    interval: tuple[float, float],
    z: float,
) -> list[list[float]]:
    """Return a trimmed wall path while preserving the original path direction."""
    original_start = point_axis_value(original_path[0], axis)
    original_end = point_axis_value(original_path[-1], axis)
    ordered = interval if original_end >= original_start else (interval[1], interval[0])
    return [
        point_from_axis_interval(axis, line_coordinate, ordered[0], z),
        point_from_axis_interval(axis, line_coordinate, ordered[1], z),
    ]


def trim_generation_shell_overreach(
    design_model: dict[str, Any],
    import_id: str,
    *,
    source_constraints: dict[str, Any] | None = None,
    min_segment_length: float = DEFAULT_MIN_SHELL_OVERREACH_LENGTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    min_wall_length: float = DEFAULT_MIN_WALL_LENGTH,
) -> dict[str, Any]:
    """Trim imported walls that extend beyond accepted interpreted spaces."""
    overreach_segments = imported_wall_space_overreach_segments(
        design_model,
        import_id,
        min_segment_length=min_segment_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
    )
    if not overreach_segments:
        return {
            "status": "unchanged",
            "overreach_count": 0,
            "trimmed_walls": [],
            "removed_walls": [],
            "split_walls": [],
            "removed_openings": [],
            "adjusted_openings": [],
            "preserved_source_constrained_segments": [],
            "segments": [],
        }

    remove_intervals_by_wall: dict[str, list[tuple[float, float]]] = {}
    source_protected_wall_ids = source_constraint_wall_ids(source_constraints or {})
    source_protected_segments = source_constraint_protected_segments(
        source_constraints or {}
    )
    preserved_source_constrained_segments: list[dict[str, Any]] = []
    for segment in overreach_segments:
        wall = design_model.get("walls", {}).get(segment["wall_id"])
        if not isinstance(wall, dict):
            continue
        overreach_interval = (
            float(segment["interval"][0]),
            float(segment["interval"][1]),
        )
        protected_coverage = source_constraint_coverage_for_overreach_segment(
            segment,
            wall,
            protected_wall_ids=source_protected_wall_ids,
            protected_segments=source_protected_segments,
            tolerance=coordinate_match_tolerance,
        )
        removable_intervals = subtract_intervals(
            overreach_interval,
            protected_coverage,
            tolerance=coordinate_match_tolerance,
        )
        if not removable_intervals:
            preserved_source_constrained_segments.append(segment)
            continue
        for removable_interval in removable_intervals:
            if removable_interval[1] - removable_interval[0] <= min_segment_length:
                preserved_segment = dict(segment)
                preserved_segment["interval"] = [
                    removable_interval[0],
                    removable_interval[1],
                ]
                preserved_segment["length"] = removable_interval[1] - removable_interval[0]
                preserved_source_constrained_segments.append(preserved_segment)
                continue
            remove_intervals_by_wall.setdefault(segment["wall_id"], []).append(
                removable_interval
            )

    trimmed_walls: list[str] = []
    removed_walls: list[str] = []
    split_walls: list[str] = []
    removed_openings: list[str] = []
    adjusted_openings: list[str] = []

    for wall_id, remove_intervals in remove_intervals_by_wall.items():
        wall = design_model.get("walls", {}).get(wall_id)
        if not isinstance(wall, dict):
            continue
        original_path = wall.get("path", [])
        axis = wall_axis(original_path, tolerance=coordinate_match_tolerance)
        if axis is None:
            continue
        base_interval = segment_interval(original_path, axis)
        kept_intervals = subtract_intervals(
            base_interval,
            remove_intervals,
            tolerance=coordinate_match_tolerance,
        )
        line_coordinate = segment_line_coordinate(original_path, axis)
        z = float(original_path[0][2])
        kept_paths = [
            wall_path_from_interval_preserving_direction(
                original_path,
                axis,
                line_coordinate,
                interval,
                z,
            )
            for interval in kept_intervals
            if interval[1] - interval[0] > min_wall_length
        ]

        if not kept_paths:
            design_model["walls"].pop(wall_id, None)
            removed_walls.append(wall_id)
            continue

        new_path = kept_paths[0]
        wall["path"] = new_path
        wall.pop("execution", None)
        trimmed_walls.append(wall_id)
        start_shift = path_start_shift_after_trim(original_path, new_path, axis)

        new_length = wall_length(new_path)
        for opening_id, opening in list(design_model.get("openings", {}).items()):
            if not isinstance(opening, dict) or opening.get("host_wall") != wall_id:
                continue
            opening["offset"] = float(opening.get("offset", 0)) - start_shift
            if opening["offset"] < -coordinate_match_tolerance or (
                opening["offset"] + float(opening.get("width", 0))
                > new_length + coordinate_match_tolerance
            ):
                design_model["openings"].pop(opening_id, None)
                removed_openings.append(opening_id)
                continue
            opening["offset"] = max(0.0, opening["offset"])
            opening.pop("execution", None)
            adjusted_openings.append(opening_id)

        for index, kept_path in enumerate(kept_paths[1:], start=1):
            split_wall_id = f"{wall_id}_kept_{index}"
            design_model["walls"][split_wall_id] = wall_payload_from_reference(
                split_wall_id,
                kept_path,
                wall,
            )
            split_walls.append(split_wall_id)

    return {
        "status": "trimmed" if (trimmed_walls or removed_walls or split_walls) else "unchanged",
        "overreach_count": len(overreach_segments),
        "trimmed_walls": trimmed_walls,
        "removed_walls": removed_walls,
        "split_walls": split_walls,
        "removed_openings": removed_openings,
        "adjusted_openings": sorted(set(adjusted_openings)),
        "preserved_source_constrained_segments": preserved_source_constrained_segments,
        "segments": overreach_segments,
    }


def remove_generation_redundant_wall_overlaps(
    design_model: dict[str, Any],
    import_id: str,
    *,
    source_constraints: dict[str, Any] | None = None,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> dict[str, Any]:
    """Remove imported walls fully covered by other imported wall segments."""
    protected_wall_ids = source_constraint_wall_ids(source_constraints or {})
    hosted_wall_ids = {
        str(opening.get("host_wall"))
        for opening in design_model.get("openings", {}).values()
        if isinstance(opening, dict) and opening.get("host_wall")
    }
    removed_walls: list[dict[str, Any]] = []
    for wall_id, wall in list(design_model.get("walls", {}).items()):
        wall_id = str(wall_id)
        if wall_id in protected_wall_ids or wall_id in hosted_wall_ids:
            continue
        if not isinstance(wall, dict):
            continue
        source = wall.get("source", {})
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        path = wall.get("path", [])
        if wall_axis(path, tolerance=coordinate_match_tolerance) is None:
            continue
        coverage = imported_wall_coverage_for_segment(
            design_model,
            import_id,
            path,
            tolerance=coordinate_match_tolerance,
            exclude_wall_ids={wall_id},
        )
        if not coverage["covered"]:
            continue
        candidate_length = wall_length(path)
        covering_lengths = [
            wall_length(design_model["walls"][covering_id].get("path", []))
            for covering_id in coverage["matched_wall_ids"]
            if isinstance(design_model["walls"].get(covering_id), dict)
        ]
        if (
            len(coverage["matched_wall_ids"]) == 1
            and covering_lengths
            and covering_lengths[0] > candidate_length + coordinate_match_tolerance
        ):
            continue
        design_model["walls"].pop(wall_id, None)
        removed_walls.append(
            {
                "wall_id": wall_id,
                "covered_by": coverage["matched_wall_ids"],
            }
        )

    return {
        "status": "removed" if removed_walls else "unchanged",
        "removed_walls": removed_walls,
    }


def build_interpreted_import_payloads(
    import_id: str,
    interpretation: dict[str, Any],
    *,
    source_type: str,
    wall_height: float,
    wall_thickness: float,
    area_tolerance_ratio: float,
    negative_space_overlap_tolerance_m2: float,
) -> dict[str, Any]:
    """Build import truth from source candidates after generation-time checks."""
    negative_regions = interpretation_negative_regions(interpretation)
    assumptions = [
        "Generated from source interpretation candidates, not a verified survey.",
        "Room labels, dimension constraints, and negative regions were used as generation gates.",
    ]
    assumptions.extend(str(item) for item in interpretation.get("assumptions", []))
    flags = source_interpretation_quality_flags(source_type)

    candidate_reviews = [
        review_space_candidate(
            candidate,
            candidate_index=index,
            negative_regions=negative_regions,
            area_tolerance_ratio=area_tolerance_ratio,
            negative_space_overlap_tolerance_m2=negative_space_overlap_tolerance_m2,
        )
        for index, candidate in enumerate(interpretation.get("space_candidates", []))
    ]
    if not candidate_reviews:
        raise ValueError("source interpretation must include at least one space candidate.")

    selected_by_space: dict[str, dict[str, Any]] = {}
    rejected_candidates: list[dict[str, Any]] = []
    for review in sorted(
        candidate_reviews,
        key=lambda item: (
            str(item["space_id"]),
            float(item["selection_score"]),
            -float(item["confidence"]),
        ),
    ):
        if review["status"] != "accepted":
            rejected_candidates.append(review)
            continue
        selected_by_space.setdefault(review["space_id"], review)

    if not selected_by_space:
        raise ValueError("source interpretation produced no accepted space candidates.")

    if rejected_candidates:
        flags.append("source_space_candidate_rejected")
    if any(
        issue["code"] == "negative_space_conflict_overridden"
        for review in candidate_reviews
        for issue in review["issues"]
    ):
        flags.append("source_negative_region_conflict_overridden")

    spaces = {
        space_id: space_payload_from_candidate(
            import_id,
            review,
            wall_height=wall_height,
            assumptions=assumptions,
        )
        for space_id, review in sorted(selected_by_space.items())
    }
    walls: dict[str, dict[str, Any]] = {}
    accepted_space_ids = set(spaces)
    for index, wall in enumerate(interpretation.get("walls", interpretation.get("wall_candidates", []))):
        if not isinstance(wall, dict):
            continue
        space_refs = wall.get("space_refs")
        if isinstance(space_refs, list) and space_refs and not (
            set(str(space_id) for space_id in space_refs) & accepted_space_ids
        ):
            continue
        wall_id, payload = wall_payload_from_interpretation(
            import_id,
            wall,
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            assumptions=assumptions,
            index=index,
        )
        walls[wall_id] = payload
    openings: dict[str, dict[str, Any]] = {}
    for index, opening in enumerate(interpretation.get("openings", [])):
        if not isinstance(opening, dict):
            continue
        if opening.get("host_wall") not in walls:
            continue
        opening_id, payload = opening_payload_from_interpretation(
            import_id,
            opening,
            walls=walls,
            assumptions=assumptions,
            index=index,
        )
        openings[opening_id] = payload

    scratch_model = {
        "spaces": spaces,
        "walls": walls,
        "openings": openings,
        "import_sessions": {import_id: {"quality_flags": flags}},
        "quality_flags": [],
    }
    door_host_repair = normalize_generation_door_hosts(scratch_model, import_id)
    if door_host_repair["status"] == "repaired":
        flags.append("source_door_host_repaired_during_generation")
        openings = scratch_model["openings"]
    circulation_openings = infer_generation_circulation_openings(
        scratch_model,
        import_id,
        assumptions=assumptions,
    )
    if circulation_openings["status"] == "inferred":
        flags.append("source_circulation_openings_inferred_during_generation")
        openings = scratch_model["openings"]
    shell_trim = trim_generation_shell_overreach(
        scratch_model,
        import_id,
        source_constraints=interpretation.get("constraints")
        if isinstance(interpretation.get("constraints"), dict)
        else None,
    )
    if shell_trim["status"] == "trimmed":
        flags.append("source_shell_overreach_trimmed_during_generation")
        walls = scratch_model["walls"]
        openings = scratch_model["openings"]
    opening_conflicts = normalize_generation_opening_conflicts(scratch_model, import_id)
    if opening_conflicts["status"] == "normalized":
        flags.append("source_opening_conflicts_normalized_during_generation")
        openings = scratch_model["openings"]
    redundant_walls = remove_generation_redundant_wall_overlaps(
        scratch_model,
        import_id,
        source_constraints=interpretation.get("constraints")
        if isinstance(interpretation.get("constraints"), dict)
        else None,
    )
    if redundant_walls["status"] == "removed":
        flags.append("source_redundant_walls_removed_during_generation")
        walls = scratch_model["walls"]

    generated_model = {
        "design_model": DESIGN_MODEL_FILENAME,
        "space_ids": sorted(spaces),
        "wall_ids": sorted(walls),
        "opening_ids": sorted(openings),
        "changed_model_ids": sorted([*spaces, *walls, *openings]),
    }
    scale = interpretation.get("scale", {})
    return {
        "spaces": spaces,
        "walls": walls,
        "openings": openings,
        "generated_model": generated_model,
        "assumptions": assumptions,
        "quality_flags": dedupe_quality_flags(flags),
        "summary": {
            "space_count": len(spaces),
            "wall_count": len(walls),
            "opening_count": len(openings),
            "confidence": min(
                [float(review["confidence"]) for review in selected_by_space.values()]
                or [0.0]
            ),
            "accepted_candidate_count": len(selected_by_space),
            "rejected_candidate_count": len(rejected_candidates),
        },
        "interpretation": {
            "version": "1.0",
            "import_id": import_id,
            "created_at": utc_now(),
            "autonomous_first": True,
            "source_interpretation_used": True,
            "scale": scale,
            "negative_regions": negative_regions,
            "candidate_reviews": [
                {
                    key: value
                    for key, value in review.items()
                    if key not in {"candidate", "footprint", "bounds"}
                }
                for review in candidate_reviews
            ],
            "selected_space_ids": sorted(spaces),
            "rejected_candidate_count": len(rejected_candidates),
            "door_host_repair": door_host_repair,
            "circulation_openings": circulation_openings,
            "shell_trim": shell_trim,
            "opening_conflicts": opening_conflicts,
            "redundant_walls": redundant_walls,
            "assumptions": assumptions,
            "quality_flags": dedupe_quality_flags(flags),
            "generated_model": generated_model,
        },
    }


def remove_previous_import_entities(
    design_model: dict[str, Any],
    import_id: str,
) -> dict[str, list[str]]:
    """Remove model entities previously generated by one import session."""
    removed: dict[str, list[str]] = {"spaces": [], "walls": [], "openings": []}
    for collection_name in ("spaces", "walls", "openings"):
        collection = design_model.setdefault(collection_name, {})
        for entity_id, entity in list(collection.items()):
            source = entity.get("source", {}) if isinstance(entity, dict) else {}
            if isinstance(source, dict) and source.get("import_id") == import_id:
                removed[collection_name].append(entity_id)
                del collection[entity_id]
    return removed


def mark_execution_dirty(
    design_model: dict[str, Any],
    *,
    reason: str,
    source: str,
    details: dict[str, Any],
) -> None:
    """Mark live SketchUp execution feedback stale after import mutation."""
    stale_feedback = clear_execution_feedback(design_model)
    design_model.setdefault("metadata", {})
    design_model["metadata"]["execution_sync"] = {
        "status": "dirty",
        "reason": reason,
        "source": source,
        "updated_at": utc_now(),
        "details": {
            **details,
            "stale_execution_feedback": stale_feedback,
        },
    }


def clear_execution_feedback(design_model: dict[str, Any]) -> dict[str, Any]:
    """Remove stale live SketchUp execution feedback after truth changes."""
    removed_operations: list[str] = []
    execution = design_model.get("execution")
    if not isinstance(execution, dict):
        execution = {}
        design_model["execution"] = execution
    bridge_operations = execution.get("bridge_operations")
    if isinstance(bridge_operations, dict):
        removed_operations = sorted(str(key) for key in bridge_operations)
    execution["bridge_operations"] = {}

    cleared_entities: dict[str, list[str]] = {
        "spaces": [],
        "walls": [],
        "openings": [],
        "components": [],
        "lighting": [],
    }
    for collection_name in ("spaces", "walls", "openings"):
        collection = design_model.get(collection_name, {})
        if not isinstance(collection, dict):
            continue
        for entity_id, entity in collection.items():
            if not isinstance(entity, dict) or "execution" not in entity:
                continue
            entity.pop("execution", None)
            cleared_entities[collection_name].append(str(entity_id))

    for collection_name in ("components", "lighting"):
        collection = design_model.get(collection_name, {})
        if not isinstance(collection, dict):
            continue
        for entity_id, entity in collection.items():
            if not isinstance(entity, dict):
                continue
            cleared = False
            if "execution" in entity:
                entity.pop("execution", None)
                cleared = True
            if "entity_id" in entity:
                entity.pop("entity_id", None)
                cleared = True
            if cleared:
                cleared_entities[collection_name].append(str(entity_id))

    return {
        "removed_bridge_operations": removed_operations,
        "cleared_entities": {
            key: sorted(value)
            for key, value in cleared_entities.items()
            if value
        },
    }


def import_floorplan_to_model(
    project_path: str | Path,
    *,
    source_path: str | Path | None = None,
    source_reference: str | None = None,
    source_reference_type: str = "chat_image_attachment",
    import_id: str | None = None,
    label: str | None = None,
    width: float | None = None,
    depth: float | None = None,
    source_interpretation_path: str | Path | None = None,
    area_tolerance_ratio: float = DEFAULT_LABEL_AREA_TOLERANCE_RATIO,
    negative_space_overlap_tolerance_m2: float = DEFAULT_NEGATIVE_SPACE_OVERLAP_TOLERANCE_M2,
    wall_height: float = DEFAULT_WALL_HEIGHT,
    wall_thickness: float = DEFAULT_WALL_THICKNESS,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate editable working truth from an imported source file."""
    timing = ImportTimingTrace()
    root = Path(project_path).expanduser().resolve()
    if source_path is not None and source_reference is not None:
        raise ValueError("Use either source_path or source_reference, not both.")
    with timing.phase("source_registration") as phase:
        if source_path is not None:
            registered = register_import_source(
                root,
                source_path,
                import_id=import_id,
                label=label,
                overwrite=overwrite,
            )
            chosen_id = registered["import_id"]
            manifest, manifest_file = load_project_import_manifest(root, chosen_id)
            phase["details"] = {"mode": "source_path", "import_id": chosen_id}
        elif source_reference is not None:
            registered = register_import_source_reference(
                root,
                source_reference,
                import_id=import_id,
                label=label,
                source_reference_type=source_reference_type,
                overwrite=overwrite,
            )
            chosen_id = registered["import_id"]
            manifest, manifest_file = load_project_import_manifest(root, chosen_id)
            phase["details"] = {"mode": "source_reference", "import_id": chosen_id}
        elif import_id is not None:
            chosen_id = import_safe_id(import_id)
            manifest, manifest_file = load_project_import_manifest(root, chosen_id)
            phase["details"] = {"mode": "existing_manifest", "import_id": chosen_id}
        else:
            raise ValueError("source_path, source_reference, or import_id is required.")

    if width is not None and width <= 0:
        raise ValueError("width must be positive when provided.")
    if depth is not None and depth <= 0:
        raise ValueError("depth must be positive when provided.")
    if wall_height <= 0 or wall_thickness <= 0:
        raise ValueError("wall_height and wall_thickness must be positive.")
    if area_tolerance_ratio < 0:
        raise ValueError("area_tolerance_ratio must be non-negative.")
    if negative_space_overlap_tolerance_m2 < 0:
        raise ValueError("negative_space_overlap_tolerance_m2 must be non-negative.")

    with timing.phase("project_state_read") as phase:
        source_type = str(manifest["source"].get("source_type", "unknown"))
        file_backed_source = source_is_file_backed(manifest)
        has_explicit_dimensions = width is not None and depth is not None
        model_width = float(width if width is not None else DEFAULT_IMPORTED_WIDTH)
        model_depth = float(depth if depth is not None else DEFAULT_IMPORTED_DEPTH)

        design_model_path = find_design_model_path(root)
        design_model, model_errors = load_design_model(str(design_model_path))
        if model_errors or design_model is None:
            raise ValueError("; ".join(model_errors))

        removed = remove_previous_import_entities(design_model, chosen_id)
        phase["details"] = {
            "source_type": source_type,
            "file_backed_source": file_backed_source,
            "removed_previous_entities": removed,
        }

    timing.skip_phase(
        "source_preprocessing_or_extraction",
        (
            "import-floorplan consumes a registered source and optional "
            "source_interpretation_path; agent vision/OCR/CAD extraction happens "
            "before this command unless a future extractor is wired in."
        ),
    )

    source_interpretation = None
    coordinate_transform = None
    coordinate_quality_flags: list[str] = []
    if source_interpretation_path is not None:
        with timing.phase("source_interpretation_loading_normalization") as phase:
            source_interpretation = load_source_interpretation(source_interpretation_path)
            require_known_source_for_interpretation(source_type, manifest)
            (
                source_interpretation,
                coordinate_transform,
                coordinate_quality_flags,
            ) = normalize_source_interpretation_coordinates(
                source_interpretation,
                source_type=source_type,
            )
            phase["details"] = {
                "source_interpretation_path": str(source_interpretation_path),
                "coordinate_transform_applied": coordinate_transform is not None,
            }
    else:
        timing.skip_phase(
            "source_interpretation_loading_normalization",
            "No source_interpretation_path was provided.",
        )

    with timing.phase("model_generation") as phase:
        if source_interpretation is not None:
            payloads = build_interpreted_import_payloads(
                chosen_id,
                source_interpretation,
                source_type=source_type,
                wall_height=wall_height,
                wall_thickness=wall_thickness,
                area_tolerance_ratio=area_tolerance_ratio,
                negative_space_overlap_tolerance_m2=negative_space_overlap_tolerance_m2,
            )
            spaces = payloads["spaces"]
            walls = payloads["walls"]
            openings = payloads["openings"]
            generated_model = payloads["generated_model"]
            assumptions = payloads["assumptions"]
            flags = dedupe_quality_flags(
                [*payloads["quality_flags"], *coordinate_quality_flags]
            )
            summary = {
                **payloads["summary"],
                "scale_source": "source_interpretation",
            }
            interpretation = payloads["interpretation"]
            if coordinate_transform is not None:
                interpretation["coordinate_transform"] = coordinate_transform
                summary["coordinate_transform"] = coordinate_transform
            scale_payload = {
                "units": "mm",
                "source": "source_interpretation",
                "confidence": float(
                    source_interpretation.get("scale", {}).get("confidence", 0.65)
                ),
                **{
                    key: value
                    for key, value in source_interpretation.get("scale", {}).items()
                    if key not in {"units", "source", "confidence"}
                },
            }
            if coordinate_transform is not None:
                scale_payload["coordinate_transform"] = coordinate_transform
            if width is not None:
                scale_payload["width"] = model_width
            if depth is not None:
                scale_payload["depth"] = model_depth
        else:
            confidence = source_confidence(source_type, has_explicit_dimensions)
            assumptions = [
                "Generated as an editable working model, not a verified survey.",
                "Outer shell interpreted as a rectangular floor plan.",
            ]
            if not has_explicit_dimensions:
                assumptions.append(
                    f"Scale estimated as {model_width:g} mm by {model_depth:g} mm."
                )
            ids = imported_entity_ids(chosen_id)
            generated_model = {
                "design_model": DESIGN_MODEL_FILENAME,
                "space_ids": [ids["space_id"]],
                "wall_ids": ids["wall_ids"],
                "opening_ids": ids["opening_ids"],
                "changed_model_ids": [
                    ids["space_id"],
                    *ids["wall_ids"],
                    *ids["opening_ids"],
                ],
            }
            flags = imported_quality_flags(
                source_type,
                has_explicit_dimensions=has_explicit_dimensions,
            )
            spaces = {
                ids["space_id"]: space_payload(
                    chosen_id,
                    width=model_width,
                    depth=model_depth,
                    wall_height=wall_height,
                    confidence=confidence,
                    assumptions=assumptions,
                )
            }
            walls = wall_payloads(
                chosen_id,
                width=model_width,
                depth=model_depth,
                wall_height=wall_height,
                wall_thickness=wall_thickness,
                confidence=confidence,
                assumptions=assumptions,
            )
            openings = opening_payloads(
                chosen_id,
                width=model_width,
                depth=model_depth,
                confidence=confidence,
                assumptions=assumptions,
            )
            interpretation = {
                "version": "1.0",
                "import_id": chosen_id,
                "created_at": utc_now(),
                "autonomous_first": True,
                "source_interpretation_used": False,
                "assumptions": assumptions,
                "quality_flags": flags,
                "generated_model": generated_model,
            }
            scale_payload = {
                "units": "mm",
                "source": "user_dimensions" if has_explicit_dimensions else "estimated",
                "confidence": 1.0 if has_explicit_dimensions else 0.35,
                "width": model_width,
                "depth": model_depth,
            }
            summary = {
                "space_count": 1,
                "wall_count": len(ids["wall_ids"]),
                "opening_count": len(ids["opening_ids"]),
                "scale_source": scale_payload["source"],
                "confidence": confidence,
            }
        phase["details"] = {
            "source_interpretation_used": source_interpretation is not None,
            "space_count": len(spaces),
            "wall_count": len(walls),
            "opening_count": len(openings),
        }

    raw_interpretation_path = None
    extracted_path = import_session_path(root, chosen_id) / "extracted" / "interpretation.json"
    extracted_relative_path = project_relative_path(root, extracted_path)
    constraints_path_from_interpretation = None
    constraints_derived_from_interpretation = False
    if source_interpretation_path is not None:
        constraints_path_from_interpretation = write_interpretation_constraints_if_present(
            root,
            chosen_id,
            source_interpretation or {},
        )
        constraints_derived_from_interpretation = (
            constraints_path_from_interpretation is not None
            and source_interpretation is not None
            and not isinstance(source_interpretation.get("constraints"), dict)
        )
        if constraints_derived_from_interpretation:
            flags = dedupe_quality_flags(
                [*flags, "source_constraints_derived_from_interpretation"]
            )

    design_model.setdefault("spaces", {}).update(spaces)
    design_model.setdefault("walls", {}).update(walls)
    design_model.setdefault("openings", {}).update(openings)
    design_model.setdefault("import_sessions", {})[chosen_id] = {
        "source_file": manifest["source"]["stored_path"],
        "source_type": source_type,
        "source_file_backed": file_backed_source,
        "status": "imported",
        "manifest_path": project_relative_path(root, manifest_file),
        "scale": scale_payload,
        "quality_flags": flags,
        "generated_model": generated_model,
    }
    if constraints_path_from_interpretation:
        design_model["import_sessions"][chosen_id][
            "source_constraints_path"
        ] = constraints_path_from_interpretation
    dynamic_runtime_skill = None
    if source_interpretation_path is not None or not file_backed_source:
        anticipated_source_interpretation_path = (
            project_relative_path(
                root,
                import_session_path(root, chosen_id)
                / "extracted"
                / "source_interpretation.json",
            )
            if source_interpretation_path is not None
            else None
        )
        dynamic_runtime_skill = write_import_dynamic_runtime_skill(
            root,
            import_id=chosen_id,
            manifest=manifest,
            interpretation_path=extracted_relative_path,
            source_interpretation_path=anticipated_source_interpretation_path,
            source_constraints_path=constraints_path_from_interpretation,
        )
        design_model["import_sessions"][chosen_id][
            "dynamic_runtime_skill"
        ] = dynamic_runtime_skill
    quality_flags = [
        flag
        for flag in design_model.get("quality_flags", [])
        if not (
            isinstance(flag, dict)
            and isinstance(flag.get("source"), dict)
            and flag["source"].get("import_id") == chosen_id
        )
    ]
    quality_flags.extend(
        {
            "code": flag,
            "severity": "warning" if flag != "source_interpreted_as_rectangular_shell" else "info",
            "message": flag.replace("_", " "),
            "source": {"kind": "import_floorplan", "import_id": chosen_id},
        }
        for flag in flags
    )
    design_model["quality_flags"] = quality_flags
    design_model["updated_at"] = utc_now()
    mark_execution_dirty(
        design_model,
        reason="floorplan_imported",
        source="import_floorplan_to_model",
        details={
            "import_id": chosen_id,
            "changed_model_ids": generated_model["changed_model_ids"],
            "source_interpretation_used": source_interpretation is not None,
        },
    )

    with timing.phase("manifest_report_persistence") as phase:
        saved, save_errors = save_design_model(str(design_model_path), design_model)
        if not saved:
            raise ValueError("; ".join(save_errors))

        extracted_path.parent.mkdir(parents=True, exist_ok=True)
        if source_interpretation_path is not None:
            raw_interpretation_path = extracted_path.parent / "source_interpretation.json"
            source_file = Path(source_interpretation_path).expanduser().resolve()
            if source_file != raw_interpretation_path:
                shutil.copyfile(source_file, raw_interpretation_path)
            interpretation["source_interpretation_path"] = project_relative_path(
                root,
                raw_interpretation_path,
            )
            if constraints_path_from_interpretation:
                interpretation["source_constraints_path"] = constraints_path_from_interpretation
                if constraints_derived_from_interpretation:
                    interpretation["source_constraints_derived_from_interpretation"] = True
        extracted_path.write_text(
            json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        manifest["status"] = "imported"
        manifest["scale"] = design_model["import_sessions"][chosen_id]["scale"]
        manifest["generated_model"] = generated_model
        manifest["quality_flags"] = dedupe_quality_flags(flags)
        append_processing_step(
            manifest,
            "import_floorplan_to_model",
            details={
                "autonomous_first": True,
                "removed_previous_entities": removed,
                "interpretation_path": extracted_relative_path,
                "source_interpretation_path": (
                    project_relative_path(root, raw_interpretation_path)
                    if raw_interpretation_path is not None
                    else None
                ),
                "source_constraints_path": constraints_path_from_interpretation,
                "dynamic_runtime_skill": dynamic_runtime_skill,
            },
        )
        saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
        if not saved_manifest:
            raise ValueError("; ".join(manifest_errors))
        phase["details"] = {
            "design_model_path": str(design_model_path),
            "manifest_path": str(manifest_file),
            "interpretation_path": extracted_relative_path,
        }

    source_fidelity = None
    if import_constraints_path(root, chosen_id).exists():
        with timing.phase("source_constraint_validation") as phase:
            source_fidelity = validate_import_source_constraints(
                root,
                chosen_id,
                update_state=True,
            )
            phase["details"] = {
                "status": source_fidelity.get("status"),
                "violation_count": source_fidelity.get("violation_count"),
            }
    else:
        timing.skip_phase(
            "source_constraint_validation",
            "No source-scoped import constraints were present.",
        )

    timing.skip_phase(
        "plan_execution",
        "import-floorplan writes design_model.json; bridge plan execution is a separate command.",
    )
    timing.skip_phase(
        "live_sketchup_execution",
        "No live SketchUp bridge execution was requested by import-floorplan.",
    )
    timing.skip_phase(
        "snapshot_report_generation",
        "No snapshot or visual report generation was requested by import-floorplan.",
    )
    timing_trace = timing.finish()
    manifest_for_timing, manifest_errors = load_import_manifest(manifest_file)
    if manifest_for_timing is None:
        raise ValueError("; ".join(manifest_errors))
    manifest_for_timing["timing"] = timing_trace
    saved_manifest, manifest_errors = save_import_manifest(
        manifest_file,
        manifest_for_timing,
    )
    if not saved_manifest:
        raise ValueError("; ".join(manifest_errors))

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "manifest_path": str(manifest_file),
        "status": "imported",
        "autonomous_first": True,
        "generated_model": generated_model,
        "assumptions": assumptions,
        "quality_flags": flags,
        "removed_previous_entities": removed,
        "source_interpretation_used": source_interpretation is not None,
        "source_file_backed": file_backed_source,
        "dynamic_runtime_skill": dynamic_runtime_skill,
        "source_fidelity": source_fidelity,
        "summary": summary,
        "timing": timing_trace,
    }


def list_import_sessions(project_path: str | Path) -> list[dict[str, Any]]:
    """Return compact summaries for project import manifests."""
    root = Path(project_path).expanduser().resolve()
    result: list[dict[str, Any]] = []
    imports_root = imports_path(root)
    if not imports_root.exists():
        return result
    for manifest_file in sorted(imports_root.glob("*/manifest.json")):
        manifest, errors = load_import_manifest(manifest_file)
        if manifest is None:
            result.append(
                {
                    "import_id": manifest_file.parent.name,
                    "manifest_path": str(manifest_file),
                    "valid": False,
                    "errors": errors,
                }
            )
            continue
        result.append(
            {
                "import_id": manifest["import_id"],
                "manifest_path": str(manifest_file),
                "valid": True,
                "status": manifest.get("status"),
                "source": manifest.get("source", {}),
                "scale": manifest.get("scale", {}),
                "quality_flags": manifest.get("quality_flags", []),
                "generated_model": manifest.get("generated_model", {}),
                "timing": compact_import_timing(manifest.get("timing")),
            }
        )
    return result


def get_import_summary(
    project_path: str | Path,
    import_id: str | None = None,
) -> dict[str, Any]:
    """Return import summaries from manifests and design_model.json."""
    root = Path(project_path).expanduser().resolve()
    sessions = list_import_sessions(root)
    if import_id:
        chosen_id = import_safe_id(import_id)
        sessions = [session for session in sessions if session["import_id"] == chosen_id]

    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    model_sessions = design_model.get("import_sessions", {})
    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "count": len(sessions),
        "imports": sessions,
        "model_import_sessions": (
            {import_id: model_sessions.get(import_id)}
            if import_id
            else model_sessions
        ),
    }


def imported_ids_in_model(design_model: dict[str, Any], import_id: str) -> dict[str, list[str]]:
    """Return model entity IDs generated by one import."""
    result: dict[str, list[str]] = {"spaces": [], "walls": [], "openings": []}
    for collection_name in result:
        for entity_id, entity in design_model.get(collection_name, {}).items():
            source = entity.get("source", {}) if isinstance(entity, dict) else {}
            if isinstance(source, dict) and source.get("import_id") == import_id:
                result[collection_name].append(entity_id)
    return result


def scale_point_xy(point: list[Any], scale_x: float, scale_y: float) -> list[float]:
    """Scale a 3D point in plan while preserving height."""
    return [float(point[0]) * scale_x, float(point[1]) * scale_y, float(point[2])]


def point_axis_value(point: list[Any], axis: str) -> float:
    """Return a point coordinate for the requested plan axis."""
    return float(point[0] if axis == "x" else point[1])


def wall_axis(path: list[Any], tolerance: float = 1e-6) -> str | None:
    """Return x for vertical walls, y for horizontal walls, else None."""
    if not isinstance(path, list) or len(path) < 2:
        return None
    start = path[0]
    end = path[-1]
    dx = abs(float(start[0]) - float(end[0]))
    dy = abs(float(start[1]) - float(end[1]))
    if dx <= tolerance and dy > tolerance:
        return "x"
    if dy <= tolerance and dx > tolerance:
        return "y"
    return None


def wall_length(path: list[Any]) -> float:
    """Return the plan length of an axis-aligned wall path."""
    if not isinstance(path, list) or len(path) < 2:
        return 0.0
    start = path[0]
    end = path[-1]
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    return (dx * dx + dy * dy) ** 0.5


def normalize_3d_point(point: list[Any], *, label: str) -> list[float]:
    """Return one normalized 3D point or raise a ValueError."""
    if not isinstance(point, list) or len(point) != 3:
        raise ValueError(f"{label} must be a 3D point.")
    return [float(point[0]), float(point[1]), float(point[2])]


def segment_line_coordinate(path: list[Any], axis: str) -> float:
    """Return the constant coordinate for one axis-aligned plan segment."""
    point = path[0]
    return float(point[0] if axis == "x" else point[1])


def segment_interval(path: list[Any], axis: str) -> tuple[float, float]:
    """Return the sorted variable-coordinate interval for a plan segment."""
    start = path[0]
    end = path[-1]
    if axis == "x":
        first = float(start[1])
        second = float(end[1])
    else:
        first = float(start[0])
        second = float(end[0])
    return (min(first, second), max(first, second))


def point_from_axis_interval(
    axis: str,
    line_coordinate: float,
    interval_coordinate: float,
    z: float,
) -> list[float]:
    """Return a plan point from an axis line and variable coordinate."""
    if axis == "x":
        return [float(line_coordinate), float(interval_coordinate), float(z)]
    return [float(interval_coordinate), float(line_coordinate), float(z)]


def source_constraint_items(
    constraints: dict[str, Any],
    *keys: str,
) -> list[dict[str, Any]]:
    """Return source constraint objects from the first matching list key."""
    for key in keys:
        value = constraints.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def evidence_origin_from_value(value: Any) -> str | None:
    """Return a normalized evidence-origin label from a constraint payload."""
    if isinstance(value, str) and value.strip():
        return value.strip().lower().replace("-", "_")
    if isinstance(value, dict):
        for key in (
            "origin",
            "evidence_origin",
            "extraction_origin",
            "source_origin",
            "method",
        ):
            origin = evidence_origin_from_value(value.get(key))
            if origin:
                return origin
    return None


def source_constraint_evidence_origin(
    constraint: dict[str, Any],
    *,
    default_origin: str | None,
) -> str | None:
    """Return the best evidence-origin label for one source constraint."""
    for key in (
        "evidence_origin",
        "origin",
        "extraction_origin",
        "provenance",
        "evidence",
        "source_provenance",
    ):
        origin = evidence_origin_from_value(constraint.get(key))
        if origin:
            return origin
    return default_origin


def validate_source_constraint_evidence_origins(
    constraints: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    """Validate that source constraints came from extraction, not a hand-fed answer."""
    failures: list[dict[str, Any]] = []
    checked = 0
    default_origin = source_constraint_evidence_origin(
        constraints,
        default_origin=evidence_origin_from_value(constraints.get("provenance")),
    )
    origin_counts: dict[str, int] = {}

    for key in SOURCE_CONSTRAINT_LIST_KEYS:
        value = constraints.get(key)
        if not isinstance(value, list):
            continue
        for index, constraint in enumerate(value):
            if not isinstance(constraint, dict):
                continue
            checked += 1
            origin = source_constraint_evidence_origin(
                constraint,
                default_origin=default_origin,
            )
            normalized_origin = origin or "missing"
            origin_counts[normalized_origin] = origin_counts.get(normalized_origin, 0) + 1
            if normalized_origin in EXTRACTED_EVIDENCE_ORIGINS:
                continue
            append_constraint_failure(
                failures,
                code="constraint_evidence_not_extracted",
                constraint={
                    "id": constraint.get("id")
                    or constraint.get("constraint_id")
                    or f"{key}[{index}]"
                },
                target_id=None,
                expected={"origin": sorted(EXTRACTED_EVIDENCE_ORIGINS)},
                actual={
                    "origin": normalized_origin,
                    "constraint_group": key,
                },
                message=(
                    "Source constraint is not marked as extracted from the source; "
                    "it may be a manual or temporary validation answer and cannot "
                    "prove automatic import recognition."
                ),
            )

    summary = {
        "status": "passed" if not failures else "failed",
        "checked_count": checked,
        "failure_count": len(failures),
        "origin_counts": origin_counts,
    }
    return failures, checked, summary


def constraint_tolerance(
    constraint: dict[str, Any],
    default_tolerance: float,
    *keys: str,
) -> float:
    """Return a numeric tolerance from one constraint."""
    for key in (*keys, "tolerance", "tolerance_mm"):
        value = constraint.get(key)
        if value is not None:
            return max(0.0, float(value))
    return default_tolerance


def append_constraint_failure(
    failures: list[dict[str, Any]],
    *,
    code: str,
    constraint: dict[str, Any],
    target_id: str | None,
    expected: Any,
    actual: Any,
    message: str,
) -> None:
    """Append one source-fidelity constraint failure."""
    failures.append(
        {
            "code": code,
            "constraint_id": constraint.get("constraint_id") or constraint.get("id"),
            "target_id": target_id,
            "expected": expected,
            "actual": actual,
            "message": message,
        }
    )


def source_constraint_status(failure_count: int, checked_count: int) -> str:
    """Return the source-fidelity status for a completed constraint check."""
    if checked_count == 0:
        return "no_checks"
    return "passed" if failure_count == 0 else "failed"


def opening_interval(opening: dict[str, Any]) -> tuple[float, float]:
    """Return the hosted opening interval on its wall."""
    offset = float(opening.get("offset", 0.0))
    width = float(opening.get("width", 0.0))
    return offset, offset + width


def opening_anchor_point(
    opening: dict[str, Any],
    wall: dict[str, Any],
    *,
    mode: str = "center",
    tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> list[float] | None:
    """Return an opening anchor point in plan coordinates for source checks."""
    path = wall.get("path", [])
    axis = wall_axis(path, tolerance=tolerance)
    if axis is None:
        return None
    interval = opening_interval_on_wall(opening, wall, axis)
    if mode == "start":
        coordinate = interval[0]
    elif mode == "end":
        coordinate = interval[1]
    else:
        coordinate = (interval[0] + interval[1]) / 2
    return point_from_axis_interval(
        axis,
        segment_line_coordinate(path, axis),
        coordinate,
        0.0,
    )


def normalize_anchor_constraint(
    constraint: dict[str, Any],
) -> tuple[list[float], str] | None:
    """Return source anchor point and mode from an opening constraint."""
    raw_anchor = (
        constraint.get("source_anchor")
        or constraint.get("anchor")
        or constraint.get("source_point")
    )
    mode = str(constraint.get("anchor_mode", "center"))
    if isinstance(raw_anchor, dict):
        point = raw_anchor.get("point") or raw_anchor.get("position")
        mode = str(raw_anchor.get("mode", mode))
    else:
        point = raw_anchor
    if not isinstance(point, list) or len(point) < 2:
        return None
    if len(point) == 2:
        point = [point[0], point[1], 0]
    return normalize_3d_point(point, label="opening source anchor"), mode


def points_within_plan_tolerance(
    actual: list[float],
    expected: list[float],
    *,
    tolerance: float,
) -> bool:
    """Return whether two plan points match within XY tolerance."""
    return (
        abs(float(actual[0]) - float(expected[0])) <= tolerance
        and abs(float(actual[1]) - float(expected[1])) <= tolerance
    )


def normalize_source_wall_axis(value: Any) -> str | None:
    """Return a wall-axis token from source-facing orientation wording."""
    if value is None:
        return None
    token = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if token in {"x", "constant_x", "north_south", "n_s", "vertical"}:
        return "x"
    if token in {"y", "constant_y", "east_west", "e_w", "horizontal"}:
        return "y"
    return None


def intervals_within_tolerance(
    actual: tuple[float, float],
    expected: tuple[float, float],
    *,
    tolerance: float,
) -> bool:
    """Return whether two intervals match within tolerance at both ends."""
    return (
        abs(actual[0] - expected[0]) <= tolerance
        and abs(actual[1] - expected[1]) <= tolerance
    )


def point_distance(first: list[Any], second: list[Any]) -> float:
    """Return 3D Euclidean distance between two points."""
    return sum(
        (float(first[index]) - float(second[index])) ** 2 for index in range(3)
    ) ** 0.5


def wall_paths_within_tolerance(
    actual_path: list[Any],
    expected_path: list[Any],
    *,
    tolerance: float,
) -> bool:
    """Return whether two wall paths share endpoints within tolerance."""
    if len(actual_path) < 2 or len(expected_path) < 2:
        return False
    actual = [actual_path[0], actual_path[-1]]
    expected = [expected_path[0], expected_path[-1]]
    return (
        point_distance(actual[0], expected[0]) <= tolerance
        and point_distance(actual[1], expected[1]) <= tolerance
    ) or (
        point_distance(actual[0], expected[1]) <= tolerance
        and point_distance(actual[1], expected[0]) <= tolerance
    )


def wall_path_covers_segment(
    actual_path: list[Any],
    expected_path: list[Any],
    *,
    tolerance: float,
) -> bool:
    """Return whether one wall path covers a source segment in plan."""
    actual_axis = wall_axis(actual_path, tolerance=tolerance)
    expected_axis = wall_axis(expected_path, tolerance=tolerance)
    if actual_axis is None or actual_axis != expected_axis:
        return False
    if (
        abs(
            segment_line_coordinate(actual_path, actual_axis)
            - segment_line_coordinate(expected_path, expected_axis)
        )
        > tolerance
    ):
        return False
    actual_interval = segment_interval(actual_path, actual_axis)
    expected_interval = segment_interval(expected_path, expected_axis)
    return (
        actual_interval[0] <= expected_interval[0] + tolerance
        and actual_interval[1] >= expected_interval[1] - tolerance
    )


def interval_overlap_length(
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    """Return the length of interval overlap."""
    return max(0.0, min(first[1], second[1]) - max(first[0], second[0]))


def wall_overlap_with_bounds(
    wall: dict[str, Any],
    bounds: tuple[float, float, float, float],
    *,
    tolerance: float,
) -> float:
    """Return the axis-aligned wall length inside one rectangular source region."""
    path = wall.get("path", [])
    axis = wall_axis(path, tolerance=tolerance)
    if axis is None:
        return 0.0
    line_coordinate = segment_line_coordinate(path, axis)
    interval = segment_interval(path, axis)
    if axis == "x":
        if line_coordinate < bounds[0] - tolerance or line_coordinate > bounds[1] + tolerance:
            return 0.0
        if (
            abs(line_coordinate - bounds[0]) <= tolerance
            or abs(line_coordinate - bounds[1]) <= tolerance
        ):
            return 0.0
        return interval_overlap_length(interval, (bounds[2], bounds[3]))
    if line_coordinate < bounds[2] - tolerance or line_coordinate > bounds[3] + tolerance:
        return 0.0
    if (
        abs(line_coordinate - bounds[2]) <= tolerance
        or abs(line_coordinate - bounds[3]) <= tolerance
    ):
        return 0.0
    return interval_overlap_length(interval, (bounds[0], bounds[1]))


def normalize_source_segment(value: Any, *, label: str) -> list[list[float]] | None:
    """Return one normalized two-point source segment from a constraint value."""
    raw_segment = value
    if isinstance(value, dict):
        raw_segment = (
            value.get("path")
            or value.get("segment")
            or (
                [value.get("start"), value.get("end")]
                if value.get("start") and value.get("end")
                else None
            )
        )
    if not isinstance(raw_segment, list) or len(raw_segment) < 2:
        return None
    return [
        normalize_3d_point(raw_segment[0], label=f"{label}.start"),
        normalize_3d_point(raw_segment[-1], label=f"{label}.end"),
    ]


def source_constraint_segments(
    constraint: dict[str, Any],
    *,
    label: str,
) -> list[list[list[float]]]:
    """Return normalized source segments from a path/segment/polyline constraint."""
    segments: list[list[list[float]]] = []
    raw_segments = constraint.get("segments")
    if isinstance(raw_segments, list):
        for index, item in enumerate(raw_segments):
            segment = normalize_source_segment(item, label=f"{label}.segments[{index}]")
            if segment is not None:
                segments.append(segment)

    raw_polyline = constraint.get("polyline") or constraint.get("outline")
    if isinstance(raw_polyline, list) and len(raw_polyline) >= 2:
        points = [
            normalize_3d_point(point, label=f"{label}.polyline[{index}]")
            for index, point in enumerate(raw_polyline)
        ]
        for index in range(len(points) - 1):
            segments.append([points[index], points[index + 1]])
        if bool(constraint.get("closed", constraint.get("is_closed", False))):
            segments.append([points[-1], points[0]])

    direct_segment = normalize_source_segment(
        constraint,
        label=label,
    )
    if direct_segment is not None:
        segments.append(direct_segment)

    return segments


def source_constraint_wall_ids(constraints: dict[str, Any]) -> set[str]:
    """Return wall ids that source constraints explicitly reference."""
    if not isinstance(constraints, dict):
        return set()
    wall_ids: set[str] = set()
    for constraint in source_constraint_items(
        constraints,
        "wall_constraints",
        "walls",
        "boundary_constraints",
    ):
        for key in ("wall_id", "target_id", "id"):
            value = constraint.get(key)
            if value:
                wall_ids.add(str(value))

    for constraint in source_constraint_items(
        constraints,
        "opening_constraints",
        "openings",
        "door_constraints",
        "window_constraints",
    ):
        host_wall = constraint.get("host_wall")
        if host_wall:
            wall_ids.add(str(host_wall))
        allowed_hosts = constraint.get("allowed_host_walls")
        if isinstance(allowed_hosts, list):
            wall_ids.update(str(host) for host in allowed_hosts if host)
    return wall_ids


def source_constraint_protected_segments(
    constraints: dict[str, Any],
) -> list[list[list[float]]]:
    """Return source-backed wall/outline segments that generation must not trim."""
    if not isinstance(constraints, dict):
        return []
    protected_segments: list[list[list[float]]] = []
    for label, items in (
        (
            "wall_constraints",
            source_constraint_items(
                constraints,
                "wall_constraints",
                "walls",
                "boundary_constraints",
            ),
        ),
        (
            "exterior_outline_constraints",
            source_constraint_items(
                constraints,
                "exterior_outline_constraints",
                "outline_constraints",
                "wall_mass_outline_constraints",
                "source_outline_constraints",
            ),
        ),
        (
            "boundary_closure_constraints",
            source_constraint_items(
                constraints,
                "boundary_closure_constraints",
                "space_boundary_constraints",
                "required_boundary_constraints",
            ),
        ),
    ):
        for index, constraint in enumerate(items):
            protected_segments.extend(
                source_constraint_segments(
                    constraint,
                    label=f"{label}[{index}]",
                )
            )
    return protected_segments


def source_constraint_coverage_for_overreach_segment(
    overreach_segment: dict[str, Any],
    wall: dict[str, Any],
    *,
    protected_wall_ids: set[str],
    protected_segments: list[list[list[float]]],
    tolerance: float,
) -> list[tuple[float, float]]:
    """Return portions of an overreach segment protected by source constraints."""
    wall_id = str(overreach_segment.get("wall_id", ""))
    overreach_interval = (
        float(overreach_segment["interval"][0]),
        float(overreach_segment["interval"][1]),
    )
    if wall_id in protected_wall_ids:
        return [overreach_interval]

    axis = str(overreach_segment.get("axis", ""))
    path = wall.get("path", [])
    if axis not in {"x", "y"} or wall_axis(path, tolerance=tolerance) != axis:
        return []
    line_coordinate = float(overreach_segment.get("line_coordinate", 0.0))
    coverage: list[tuple[float, float]] = []
    for expected_segment in protected_segments:
        expected_axis = wall_axis(expected_segment, tolerance=tolerance)
        if expected_axis != axis:
            continue
        if (
            abs(segment_line_coordinate(expected_segment, axis) - line_coordinate)
            > tolerance
        ):
            continue
        expected_interval = segment_interval(expected_segment, axis)
        overlap_start = max(overreach_interval[0], expected_interval[0])
        overlap_end = min(overreach_interval[1], expected_interval[1])
        if overlap_end > overlap_start + tolerance:
            coverage.append((overlap_start, overlap_end))
    return merge_intervals(coverage, tolerance=tolerance)


def imported_wall_matches_for_segment(
    design_model: dict[str, Any],
    import_id: str,
    expected_path: list[list[float]],
    *,
    tolerance: float,
) -> list[tuple[str, dict[str, Any]]]:
    """Return imported walls whose path covers a source segment."""
    matches: list[tuple[str, dict[str, Any]]] = []
    for wall_id, wall in design_model.get("walls", {}).items():
        if not isinstance(wall, dict):
            continue
        source = wall.get("source", {})
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        if wall_path_covers_segment(
            wall.get("path", []),
            expected_path,
            tolerance=tolerance,
        ):
            matches.append((str(wall_id), wall))
    return matches


def imported_wall_coverage_for_segment(
    design_model: dict[str, Any],
    import_id: str,
    expected_path: list[list[float]],
    *,
    tolerance: float,
    wall_filter: Callable[[str, dict[str, Any]], bool] | None = None,
    exclude_wall_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Return union wall coverage for a source segment."""
    expected_axis = wall_axis(expected_path, tolerance=tolerance)
    if expected_axis is None:
        return {
            "covered": False,
            "matched_wall_ids": [],
            "gaps": [],
        }
    expected_line = segment_line_coordinate(expected_path, expected_axis)
    expected_interval = segment_interval(expected_path, expected_axis)
    coverage: list[tuple[float, float]] = []
    matched_wall_ids: list[str] = []
    excluded = exclude_wall_ids or set()
    for wall_id, wall in design_model.get("walls", {}).items():
        if str(wall_id) in excluded:
            continue
        if not isinstance(wall, dict):
            continue
        source = wall.get("source", {})
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        if wall_filter is not None and not wall_filter(str(wall_id), wall):
            continue
        path = wall.get("path", [])
        axis = wall_axis(path, tolerance=tolerance)
        if axis is None or axis != expected_axis:
            continue
        if abs(segment_line_coordinate(path, axis) - expected_line) > tolerance:
            continue
        actual_interval = segment_interval(path, axis)
        overlap_start = max(expected_interval[0], actual_interval[0])
        overlap_end = min(expected_interval[1], actual_interval[1])
        if overlap_end <= overlap_start + tolerance:
            continue
        coverage.append((overlap_start, overlap_end))
        matched_wall_ids.append(str(wall_id))

    gaps = subtract_intervals(
        expected_interval,
        coverage,
        tolerance=tolerance,
    )
    return {
        "covered": not gaps,
        "matched_wall_ids": sorted(set(matched_wall_ids)),
        "gaps": [[start, end] for start, end in gaps],
    }


def footprint_edges(
    footprint: list[list[float]],
    *,
    tolerance: float,
) -> list[list[list[float]]]:
    """Return non-zero plan edges for one footprint polygon."""
    edges: list[list[list[float]]] = []
    if len(footprint) < 2:
        return edges
    for index, start in enumerate(footprint):
        end = footprint[(index + 1) % len(footprint)]
        if (
            abs(float(start[0]) - float(end[0])) <= tolerance
            and abs(float(start[1]) - float(end[1])) <= tolerance
        ):
            continue
        edges.append([start, end])
    return edges


def segment_plan_length(path: list[list[float]], *, tolerance: float) -> float:
    """Return the plan length for one supported source segment."""
    axis = wall_axis(path, tolerance=tolerance)
    if axis is not None:
        interval = segment_interval(path, axis)
        return abs(interval[1] - interval[0])
    if len(path) < 2:
        return 0.0
    start, end = path[0], path[-1]
    return ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5


def negative_region_boundary_wall_coverage(
    design_model: dict[str, Any],
    footprint: list[list[float]],
    *,
    import_id: str,
    tolerance: float,
) -> dict[str, Any]:
    """Return imported wall coverage along a negative/outside region boundary."""
    total_length = 0.0
    covered_length = 0.0
    matched_wall_ids: set[str] = set()
    edge_results: list[dict[str, Any]] = []
    skipped_edges = 0

    for edge in footprint_edges(footprint, tolerance=tolerance):
        axis = wall_axis(edge, tolerance=tolerance)
        edge_length = segment_plan_length(edge, tolerance=tolerance)
        if edge_length <= tolerance:
            continue
        if axis is None:
            skipped_edges += 1
            edge_results.append(
                {
                    "path": edge,
                    "axis": None,
                    "length": edge_length,
                    "covered_length": 0.0,
                    "matched_wall_ids": [],
                    "gaps": [],
                    "skipped": True,
                }
            )
            continue

        coverage = imported_wall_coverage_for_segment(
            design_model,
            import_id,
            edge,
            tolerance=tolerance,
        )
        gap_length = sum(
            max(0.0, float(gap[1]) - float(gap[0]))
            for gap in coverage["gaps"]
        )
        edge_covered_length = max(0.0, edge_length - gap_length)
        total_length += edge_length
        covered_length += edge_covered_length
        matched_wall_ids.update(str(wall_id) for wall_id in coverage["matched_wall_ids"])
        edge_results.append(
            {
                "path": edge,
                "axis": axis,
                "length": edge_length,
                "covered_length": edge_covered_length,
                "covered_ratio": edge_covered_length / edge_length,
                "matched_wall_ids": coverage["matched_wall_ids"],
                "gaps": coverage["gaps"],
            }
        )

    coverage_ratio = covered_length / total_length if total_length > 0 else 0.0
    return {
        "coverage_ratio": coverage_ratio,
        "covered_length": covered_length,
        "total_length": total_length,
        "matched_wall_ids": sorted(matched_wall_ids),
        "edges": edge_results,
        "skipped_edges": skipped_edges,
    }


def imported_space_overlap_with_bounds(
    space: dict[str, Any],
    bounds: tuple[float, float, float, float],
) -> float:
    """Return imported space footprint overlap area with a source region."""
    raw_footprint = space.get("footprint")
    if not isinstance(raw_footprint, list) or len(raw_footprint) < 3:
        space_bounds = space_plan_bounds(space)
        if space_bounds is None:
            return 0.0
        return bounds_overlap_area_mm2(space_bounds, bounds)
    try:
        footprint = footprint_from_payload(raw_footprint, label="space.footprint")
    except ValueError:
        return 0.0
    return polygon_overlap_with_bounds_area_mm2(footprint, bounds)


def validate_opening_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    default_tolerance: float,
    require_executed: bool,
    require_source_evidence_fields: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """Validate source constraints for doors, windows, and generic openings."""
    failures: list[dict[str, Any]] = []
    checked = 0
    openings = design_model.get("openings", {})
    walls = design_model.get("walls", {})
    spaces = design_model.get("spaces", {})

    for constraint in constraints:
        opening_id = str(
            constraint.get("opening_id")
            or constraint.get("target_id")
            or constraint.get("id")
            or ""
        )
        if not opening_id:
            continue
        checked += 1
        opening = openings.get(opening_id)
        must_exist = bool(constraint.get("must_exist", True))
        if not isinstance(opening, dict):
            if must_exist:
                append_constraint_failure(
                    failures,
                    code="opening_missing",
                    constraint=constraint,
                    target_id=opening_id,
                    expected="existing opening",
                    actual=None,
                    message="Expected source-backed opening is missing from design_model.json.",
                )
            continue

        opening_type = str(constraint.get("type") or opening.get("type") or "").lower()
        if require_source_evidence_fields and opening_type == "door":
            source_host_axis = normalize_source_wall_axis(
                constraint.get("host_wall_axis")
                or constraint.get("source_host_axis")
                or constraint.get("host_axis")
                or constraint.get("source_wall_orientation")
                or constraint.get("host_wall_orientation")
            )
            if not source_host_axis:
                append_constraint_failure(
                    failures,
                    code="opening_source_host_axis_missing",
                    constraint=constraint,
                    target_id=opening_id,
                    expected="source-derived host wall axis/orientation",
                    actual=None,
                    message=(
                        "Door source constraint lacks host wall orientation evidence; "
                        "a door can otherwise snap to the wrong adjacent wall."
                    ),
                )

            source_interval = (
                constraint.get("interval")
                or constraint.get("source_interval")
                or constraint.get("host_interval")
            )
            has_interval = isinstance(source_interval, list) and len(source_interval) == 2
            has_anchor = normalize_anchor_constraint(constraint) is not None
            has_source_bounds = any(
                key in constraint
                for key in (
                    "source_bbox",
                    "bbox",
                    "source_bounds",
                    "image_bbox",
                    "detected_bbox",
                )
            )
            if not has_interval and not has_anchor and not has_source_bounds:
                append_constraint_failure(
                    failures,
                    code="opening_source_anchor_or_interval_missing",
                    constraint=constraint,
                    target_id=opening_id,
                    expected="source-derived host interval, anchor, or detection bounds",
                    actual=None,
                    message=(
                        "Door source constraint lacks localization evidence on the host wall."
                    ),
                )

            constrained_open_to = constraint.get("open_to_space")
            constrained_access_from = constraint.get("access_from_space")
            if constrained_open_to is None and opening.get("open_to_space") is not None:
                append_constraint_failure(
                    failures,
                    code="opening_source_open_space_missing",
                    constraint=constraint,
                    target_id=opening_id,
                    expected="source-derived open_to_space",
                    actual=None,
                    message=(
                        "Door source constraint does not identify the room the door opens to."
                    ),
                )
            if constrained_access_from is None and opening.get("access_from_space") is not None:
                append_constraint_failure(
                    failures,
                    code="opening_source_access_space_missing",
                    constraint=constraint,
                    target_id=opening_id,
                    expected="source-derived access_from_space",
                    actual=None,
                    message=(
                        "Door source constraint does not identify the access side; "
                        "the generated host can silently choose the wrong adjacent space."
                    ),
                )

            expected_open_to = constrained_open_to or opening.get("open_to_space")
            expected_access_from = constrained_access_from or opening.get("access_from_space")
            expected_internal_refs = {
                str(space_id)
                for space_id in (expected_open_to, expected_access_from)
                if space_id
                and str(space_id) in spaces
                and normalized_label_token(str(space_id))
                not in {"exterior", "outside", "outdoor", "entry"}
            }
            if (
                len(expected_internal_refs) >= 2
                and not bool(constraint.get("require_host_space_refs"))
            ):
                append_constraint_failure(
                    failures,
                    code="opening_host_space_refs_not_required",
                    constraint=constraint,
                    target_id=opening_id,
                    expected={
                        "require_host_space_refs": True,
                        "space_refs": sorted(expected_internal_refs),
                    },
                    actual={"require_host_space_refs": constraint.get("require_host_space_refs")},
                    message=(
                        "Interior door source constraint must require the host wall to connect "
                        "the source-indicated room and access space."
                    ),
                )

        for field in (
            "type",
            "host_wall",
            "open_to_space",
            "access_from_space",
            "open_side",
            "swing_direction",
        ):
            expected = constraint.get(field)
            if expected is None:
                continue
            actual = opening.get(field)
            if actual != expected:
                append_constraint_failure(
                    failures,
                    code=f"opening_{field}_mismatch",
                    constraint=constraint,
                    target_id=opening_id,
                    expected=expected,
                    actual=actual,
                    message=f"Opening field {field!r} does not match source constraint.",
                )

        allowed_hosts = constraint.get("allowed_host_walls")
        if isinstance(allowed_hosts, list) and opening.get("host_wall") not in allowed_hosts:
            append_constraint_failure(
                failures,
                code="opening_host_wall_not_allowed",
                constraint=constraint,
                target_id=opening_id,
                expected=allowed_hosts,
                actual=opening.get("host_wall"),
                message="Opening host wall is not in the source-allowed host wall set.",
            )

        expected_host_axis = normalize_source_wall_axis(
            constraint.get("host_wall_axis")
            or constraint.get("source_host_axis")
            or constraint.get("host_axis")
            or constraint.get("source_wall_orientation")
            or constraint.get("host_wall_orientation")
        )
        if expected_host_axis:
            wall = walls.get(str(opening.get("host_wall", "")))
            actual_host_axis = (
                wall_axis(wall.get("path", [])) if isinstance(wall, dict) else None
            )
            if actual_host_axis != expected_host_axis:
                append_constraint_failure(
                    failures,
                    code="opening_host_axis_mismatch",
                    constraint=constraint,
                    target_id=opening_id,
                    expected=expected_host_axis,
                    actual=actual_host_axis,
                    message="Opening host wall orientation does not match source evidence.",
                )

        expected_interval = (
            constraint.get("interval")
            or constraint.get("source_interval")
            or constraint.get("host_interval")
        )
        if isinstance(expected_interval, list) and len(expected_interval) == 2:
            tolerance = constraint_tolerance(
                constraint,
                default_tolerance,
                "interval_tolerance",
                "interval_tolerance_mm",
            )
            expected = (
                min(float(expected_interval[0]), float(expected_interval[1])),
                max(float(expected_interval[0]), float(expected_interval[1])),
            )
            if not interval_is_offset_mode(constraint):
                wall = walls.get(str(opening.get("host_wall", "")))
                axis = wall_axis(wall.get("path", [])) if isinstance(wall, dict) else None
                actual = (
                    opening_interval_on_wall(opening, wall, axis)
                    if isinstance(wall, dict) and axis is not None
                    else opening_interval(opening)
                )
            else:
                actual = opening_interval(opening)
            if not intervals_within_tolerance(actual, expected, tolerance=tolerance):
                append_constraint_failure(
                    failures,
                    code="opening_interval_mismatch",
                    constraint=constraint,
                    target_id=opening_id,
                    expected=list(expected),
                    actual=list(actual),
                    message="Opening interval on host wall does not match source evidence.",
                )

        anchor_constraint = normalize_anchor_constraint(constraint)
        if anchor_constraint is not None:
            expected_anchor, anchor_mode = anchor_constraint
            tolerance = constraint_tolerance(
                constraint,
                default_tolerance,
                "anchor_tolerance",
                "anchor_tolerance_mm",
            )
            wall = walls.get(str(opening.get("host_wall", "")))
            actual_anchor = (
                opening_anchor_point(
                    opening,
                    wall,
                    mode=anchor_mode,
                    tolerance=tolerance,
                )
                if isinstance(wall, dict)
                else None
            )
            if actual_anchor is None or not points_within_plan_tolerance(
                actual_anchor,
                expected_anchor,
                tolerance=tolerance,
            ):
                append_constraint_failure(
                    failures,
                    code="opening_anchor_mismatch",
                    constraint=constraint,
                    target_id=opening_id,
                    expected={"point": expected_anchor, "mode": anchor_mode},
                    actual=actual_anchor,
                    message="Opening anchor point does not match source evidence.",
                )

        if bool(constraint.get("require_host_space_refs")):
            host_wall = walls.get(str(opening.get("host_wall", "")))
            host_refs = set(wall_space_refs(host_wall)) if isinstance(host_wall, dict) else set()
            expected_refs = {
                str(space_id)
                for space_id in (
                    constraint.get("open_to_space") or opening.get("open_to_space"),
                    constraint.get("access_from_space") or opening.get("access_from_space"),
                )
                if space_id and str(space_id) in spaces
            }
            if not expected_refs.issubset(host_refs):
                append_constraint_failure(
                    failures,
                    code="opening_host_space_refs_mismatch",
                    constraint=constraint,
                    target_id=opening_id,
                    expected=sorted(expected_refs),
                    actual=sorted(host_refs),
                    message="Opening host wall does not connect the source-indicated spaces.",
                )

        for field in ("offset", "width", "height", "sill_height"):
            expected = constraint.get(field)
            if expected is None:
                continue
            tolerance = constraint_tolerance(
                constraint,
                default_tolerance,
                f"{field}_tolerance",
                f"{field}_tolerance_mm",
            )
            actual = float(opening.get(field, 0.0))
            if abs(actual - float(expected)) > tolerance:
                append_constraint_failure(
                    failures,
                    code=f"opening_{field}_mismatch",
                    constraint=constraint,
                    target_id=opening_id,
                    expected=expected,
                    actual=actual,
                    message=f"Opening numeric field {field!r} is outside tolerance.",
                )

        if require_executed or constraint.get("require_execution"):
            execution = opening.get("execution", {})
            if not isinstance(execution, dict) or execution.get("status") != "success":
                append_constraint_failure(
                    failures,
                    code="opening_not_executed",
                    constraint=constraint,
                    target_id=opening_id,
                    expected="successful execution feedback",
                    actual=execution,
                    message="Opening has not been successfully replayed into SketchUp.",
                )

    return failures, checked


def validate_wall_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    import_id: str,
    default_tolerance: float,
) -> tuple[list[dict[str, Any]], int]:
    """Validate source constraints for wall existence and source path."""
    failures: list[dict[str, Any]] = []
    checked = 0
    walls = design_model.get("walls", {})

    for constraint in constraints:
        wall_id = str(
            constraint.get("wall_id")
            or constraint.get("target_id")
            or constraint.get("id")
            or ""
        )
        expected_path = constraint.get("path")
        if not wall_id and not expected_path:
            continue
        checked += 1

        if not wall_id and isinstance(expected_path, list) and len(expected_path) >= 2:
            tolerance = constraint_tolerance(
                constraint,
                default_tolerance,
                "path_tolerance",
                "path_tolerance_mm",
            )
            normalized_path = [
                normalize_3d_point(point, label=f"wall_constraint.path[{index}]")
                for index, point in enumerate(expected_path)
            ]
            matched_wall_ids = [
                candidate_id
                for candidate_id, candidate in walls.items()
                if isinstance(candidate, dict)
                and isinstance(candidate.get("source"), dict)
                and candidate["source"].get("import_id") == import_id
                and wall_paths_within_tolerance(
                    candidate.get("path", []),
                    normalized_path,
                    tolerance=tolerance,
                )
            ]
            if not matched_wall_ids:
                append_constraint_failure(
                    failures,
                    code="wall_path_missing",
                    constraint=constraint,
                    target_id=None,
                    expected=normalized_path,
                    actual=None,
                    message="No imported wall path satisfies the source constraint.",
                )
            continue

        wall = walls.get(wall_id)
        must_exist = bool(constraint.get("must_exist", True))
        if not isinstance(wall, dict):
            if must_exist:
                append_constraint_failure(
                    failures,
                    code="wall_missing",
                    constraint=constraint,
                    target_id=wall_id,
                    expected="existing wall",
                    actual=None,
                    message="Expected source-backed wall is missing from design_model.json.",
                )
            continue

        if constraint.get("space_refs"):
            expected_refs = set(str(ref) for ref in constraint["space_refs"])
            actual_refs = set(wall_space_refs(wall))
            if not expected_refs.issubset(actual_refs):
                append_constraint_failure(
                    failures,
                    code="wall_space_refs_mismatch",
                    constraint=constraint,
                    target_id=wall_id,
                    expected=sorted(expected_refs),
                    actual=sorted(actual_refs),
                    message="Wall semantic space references do not satisfy source constraint.",
                )

        if isinstance(expected_path, list) and len(expected_path) >= 2:
            tolerance = constraint_tolerance(
                constraint,
                default_tolerance,
                "path_tolerance",
                "path_tolerance_mm",
            )
            normalized_path = [
                normalize_3d_point(point, label=f"{wall_id}.path[{index}]")
                for index, point in enumerate(expected_path)
            ]
            if not wall_paths_within_tolerance(
                wall.get("path", []),
                normalized_path,
                tolerance=tolerance,
            ):
                append_constraint_failure(
                    failures,
                    code="wall_path_mismatch",
                    constraint=constraint,
                    target_id=wall_id,
                    expected=normalized_path,
                    actual=wall.get("path"),
                    message="Wall path does not match source constraint.",
                )

    return failures, checked


def validate_exterior_outline_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    import_id: str,
    default_tolerance: float,
) -> tuple[list[dict[str, Any]], int]:
    """Validate source exterior outline segments independent of room labels."""
    failures: list[dict[str, Any]] = []
    checked = 0
    for constraint_index, constraint in enumerate(constraints):
        tolerance = constraint_tolerance(
            constraint,
            default_tolerance,
            "path_tolerance",
            "path_tolerance_mm",
            "outline_tolerance",
            "outline_tolerance_mm",
        )
        segments = source_constraint_segments(
            constraint,
            label=f"exterior_outline_constraints[{constraint_index}]",
        )
        for segment in segments:
            checked += 1
            coverage = imported_wall_coverage_for_segment(
                design_model,
                import_id,
                segment,
                tolerance=tolerance,
            )
            if coverage["covered"]:
                continue
            append_constraint_failure(
                failures,
                code="exterior_outline_segment_missing",
                constraint=constraint,
                target_id=None,
                expected={"segment": segment, "tolerance": tolerance},
                actual={
                    "matched_wall_ids": coverage["matched_wall_ids"],
                    "gaps": coverage["gaps"],
                },
                message="Generated imported walls do not cover a source exterior outline segment.",
            )

    return failures, checked


def opening_matches_boundary_requirement(
    opening: dict[str, Any],
    wall: dict[str, Any],
    required_type: str | None,
    expected_path: list[list[float]],
    *,
    tolerance: float,
) -> bool:
    """Return whether an opening on a wall satisfies a boundary source segment."""
    if required_type and str(opening.get("type")) != required_type:
        return False
    axis = wall_axis(wall.get("path", []), tolerance=tolerance)
    expected_axis = wall_axis(expected_path, tolerance=tolerance)
    if axis is None or axis != expected_axis:
        return False
    opening_segment = opening_interval_on_wall(opening, wall, axis)
    expected_segment = segment_interval(expected_path, axis)
    return interval_overlap_length(opening_segment, expected_segment) > tolerance


def validate_boundary_closure_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    import_id: str,
    default_tolerance: float,
) -> tuple[list[dict[str, Any]], int]:
    """Validate required source boundary closure and boundary opening types."""
    failures: list[dict[str, Any]] = []
    checked = 0
    openings = design_model.get("openings", {})

    for constraint_index, constraint in enumerate(constraints):
        tolerance = constraint_tolerance(
            constraint,
            default_tolerance,
            "path_tolerance",
            "path_tolerance_mm",
            "boundary_tolerance",
            "boundary_tolerance_mm",
        )
        required_opening_type = constraint.get("required_opening_type")
        if required_opening_type is None:
            required_opening_type = constraint.get("opening_type")
        if required_opening_type is None:
            required_opening_type = constraint.get("required_type")
        required_opening_type = (
            str(required_opening_type) if required_opening_type is not None else None
        )
        expected_refs = {
            str(ref)
            for ref in constraint.get("space_refs", [])
            if ref is not None
        } if isinstance(constraint.get("space_refs"), list) else set()
        segments = source_constraint_segments(
            constraint,
            label=f"boundary_closure_constraints[{constraint_index}]",
        )
        for segment in segments:
            checked += 1
            def wall_satisfies_boundary_refs(
                wall_id: str,
                wall: dict[str, Any],
            ) -> bool:
                del wall_id
                return not expected_refs or expected_refs.issubset(set(wall_space_refs(wall)))

            coverage = imported_wall_coverage_for_segment(
                design_model,
                import_id,
                segment,
                tolerance=tolerance,
                wall_filter=wall_satisfies_boundary_refs,
            )
            matches = [
                (wall_id, design_model.get("walls", {}).get(wall_id))
                for wall_id in coverage["matched_wall_ids"]
                if isinstance(design_model.get("walls", {}).get(wall_id), dict)
            ]
            if not coverage["covered"]:
                append_constraint_failure(
                    failures,
                    code="boundary_closure_missing",
                    constraint=constraint,
                    target_id=None,
                    expected={
                        "segment": segment,
                        "space_refs": sorted(expected_refs),
                        "tolerance": tolerance,
                    },
                    actual={
                        "matched_wall_ids": coverage["matched_wall_ids"],
                        "gaps": coverage["gaps"],
                    },
                    message="Generated truth does not close a required source boundary segment.",
                )
                continue

            if required_opening_type is None:
                continue
            matching_openings = [
                opening_id
                for wall_id, wall in matches
                for opening_id, opening in openings.items()
                if isinstance(opening, dict)
                and opening.get("host_wall") == wall_id
                and opening_matches_boundary_requirement(
                    opening,
                    wall,
                    required_opening_type,
                    segment,
                    tolerance=tolerance,
                )
            ]
            if not matching_openings:
                append_constraint_failure(
                    failures,
                    code="boundary_opening_type_missing",
                    constraint=constraint,
                    target_id=None,
                    expected={
                        "segment": segment,
                        "required_opening_type": required_opening_type,
                        "matched_wall_ids": [wall_id for wall_id, _wall in matches],
                    },
                    actual={"matching_opening_ids": []},
                    message="Required source boundary opening type is missing on the matched wall segment.",
                )

    return failures, checked


def validate_negative_region_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    import_id: str,
    default_tolerance: float,
) -> tuple[list[dict[str, Any]], int]:
    """Validate regions that should not contain imported generated geometry."""
    failures: list[dict[str, Any]] = []
    checked = 0
    walls = design_model.get("walls", {})
    spaces = design_model.get("spaces", {})

    for constraint in constraints:
        raw_footprint = constraint.get("footprint") or constraint.get("polygon")
        if raw_footprint is None and isinstance(constraint.get("bounds"), dict):
            bounds = constraint["bounds"]
            min_point = bounds.get("min")
            max_point = bounds.get("max")
            if min_point and max_point:
                raw_footprint = [
                    [min_point[0], min_point[1], 0],
                    [max_point[0], min_point[1], 0],
                    [max_point[0], max_point[1], 0],
                    [min_point[0], max_point[1], 0],
                ]
        if raw_footprint is None:
            continue
        checked += 1
        footprint = footprint_from_payload(
            raw_footprint,
            label=f"negative_region_constraints[{checked - 1}].footprint",
        )
        bounds = polygon_bounds(footprint)
        tolerance = constraint_tolerance(
            constraint,
            default_tolerance,
            "coordinate_tolerance",
            "coordinate_tolerance_mm",
        )
        max_boundary_coverage_ratio: float | None = None
        if (
            constraint.get("forbid_boundary_enclosure")
            or constraint.get("forbid_enclosure")
            or constraint.get("forbid_wall_enclosure")
        ):
            max_boundary_coverage_ratio = DEFAULT_NEGATIVE_REGION_BOUNDARY_COVERAGE_RATIO
        for key in (
            "max_boundary_wall_coverage_ratio",
            "max_boundary_coverage_ratio",
            "max_enclosing_wall_coverage_ratio",
        ):
            if constraint.get(key) is not None:
                max_boundary_coverage_ratio = float(constraint[key])
                break

        if max_boundary_coverage_ratio is not None:
            boundary_coverage = negative_region_boundary_wall_coverage(
                design_model,
                footprint,
                import_id=import_id,
                tolerance=tolerance,
            )
            if (
                boundary_coverage["total_length"] > 0
                and boundary_coverage["coverage_ratio"]
                > max_boundary_coverage_ratio
            ):
                append_constraint_failure(
                    failures,
                    code="negative_region_boundary_enclosure",
                    constraint=constraint,
                    target_id=None,
                    expected={
                        "max_boundary_wall_coverage_ratio": max_boundary_coverage_ratio,
                    },
                    actual=boundary_coverage,
                    message=(
                        "Imported walls enclose too much of a source negative/outside "
                        "region boundary."
                    ),
                )

        max_overlap = float(constraint.get("max_wall_overlap_length", 0.0))
        max_space_overlap_area_mm2: float | None = None
        if constraint.get("forbid_spaces") or constraint.get("forbid_imported_spaces"):
            max_space_overlap_area_mm2 = 0.0
        if constraint.get("max_space_overlap_area") is not None:
            max_space_overlap_area_mm2 = float(constraint["max_space_overlap_area"])
        if constraint.get("max_space_overlap_area_m2") is not None:
            max_space_overlap_area_mm2 = (
                float(constraint["max_space_overlap_area_m2"]) * 1_000_000
            )
        max_space_overlap_ratio = constraint.get("max_space_overlap_ratio")
        area_tolerance_mm2 = (
            float(constraint.get("area_tolerance_m2", 0.0)) * 1_000_000
            if constraint.get("area_tolerance_m2") is not None
            else 0.0
        )
        for wall_id, wall in walls.items():
            if not isinstance(wall, dict):
                continue
            source = wall.get("source", {})
            if not isinstance(source, dict) or source.get("import_id") != import_id:
                continue
            overlap = wall_overlap_with_bounds(wall, bounds, tolerance=tolerance)
            if overlap > max_overlap + tolerance:
                append_constraint_failure(
                    failures,
                    code="negative_region_wall_overlap",
                    constraint=constraint,
                    target_id=wall_id,
                    expected={"max_wall_overlap_length": max_overlap},
                    actual={"overlap_length": overlap, "wall_path": wall.get("path")},
                    message="Imported wall overlaps a source negative/outside region.",
                )

        if max_space_overlap_area_mm2 is None and max_space_overlap_ratio is None:
            continue
        region_area = max(polygon_area_mm2(footprint), 1.0)
        for space_id, space in spaces.items():
            if not isinstance(space, dict):
                continue
            source = space.get("source", {})
            if not isinstance(source, dict) or source.get("import_id") != import_id:
                continue
            overlap_area = imported_space_overlap_with_bounds(space, bounds)
            ratio = overlap_area / region_area
            area_limit = (
                max_space_overlap_area_mm2
                if max_space_overlap_area_mm2 is not None
                else region_area + area_tolerance_mm2
            )
            ratio_limit = (
                float(max_space_overlap_ratio)
                if max_space_overlap_ratio is not None
                else 1.0
            )
            if (
                overlap_area > area_limit + area_tolerance_mm2
                or ratio > ratio_limit
            ):
                append_constraint_failure(
                    failures,
                    code="negative_region_space_overlap",
                    constraint=constraint,
                    target_id=str(space_id),
                    expected={
                        "max_space_overlap_area": area_limit,
                        "max_space_overlap_ratio": ratio_limit,
                    },
                    actual={
                        "overlap_area": overlap_area,
                        "overlap_area_m2": overlap_area / 1_000_000,
                        "overlap_ratio": ratio,
                    },
                    message="Imported space overlaps a source negative/outside region.",
                )

    return failures, checked


def space_plan_bounds(space: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return a space's plan bounds from footprint or rectangular bounds."""
    footprint = space.get("footprint")
    if isinstance(footprint, list) and len(footprint) >= 3:
        points = [
            normalize_3d_point(point, label="space.footprint point")
            for point in footprint
            if isinstance(point, list)
        ]
        if len(points) >= 3:
            return polygon_bounds(points)
    bounds = space.get("bounds", {})
    if isinstance(bounds, dict) and bounds.get("min") and bounds.get("max"):
        min_point = normalize_3d_point(bounds["min"], label="space.bounds.min")
        max_point = normalize_3d_point(bounds["max"], label="space.bounds.max")
        return (
            min(min_point[0], max_point[0]),
            max(min_point[0], max_point[0]),
            min(min_point[1], max_point[1]),
            max(min_point[1], max_point[1]),
        )
    return None


def constraint_bounds(constraint: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return expected plan bounds from one source constraint."""
    value = constraint.get("bounds")
    if isinstance(value, dict):
        min_point = value.get("min")
        max_point = value.get("max")
        if min_point and max_point:
            min_xyz = normalize_3d_point(min_point, label="constraint.bounds.min")
            max_xyz = normalize_3d_point(max_point, label="constraint.bounds.max")
            return (
                min(min_xyz[0], max_xyz[0]),
                max(min_xyz[0], max_xyz[0]),
                min(min_xyz[1], max_xyz[1]),
                max(min_xyz[1], max_xyz[1]),
            )
    if isinstance(value, list) and len(value) == 4:
        return (
            min(float(value[0]), float(value[2])),
            max(float(value[0]), float(value[2])),
            min(float(value[1]), float(value[3])),
            max(float(value[1]), float(value[3])),
        )
    footprint = constraint.get("footprint")
    if isinstance(footprint, list) and len(footprint) >= 3:
        return polygon_bounds(
            footprint_from_payload(footprint, label="space_constraint.footprint")
        )
    return None


def bounds_within_tolerance(
    actual: tuple[float, float, float, float],
    expected: tuple[float, float, float, float],
    *,
    tolerance: float,
) -> bool:
    """Return whether two plan bounds match within per-side tolerance."""
    return all(abs(actual[index] - expected[index]) <= tolerance for index in range(4))


def validate_space_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    default_tolerance: float,
) -> tuple[list[dict[str, Any]], int]:
    """Validate source constraints for imported space footprints and bounds."""
    failures: list[dict[str, Any]] = []
    checked = 0
    spaces = design_model.get("spaces", {})

    for constraint in constraints:
        space_id = str(
            constraint.get("space_id")
            or constraint.get("target_id")
            or constraint.get("id")
            or ""
        )
        if not space_id:
            continue
        checked += 1
        space = spaces.get(space_id)
        must_exist = bool(constraint.get("must_exist", True))
        if not isinstance(space, dict):
            if must_exist:
                append_constraint_failure(
                    failures,
                    code="space_missing",
                    constraint=constraint,
                    target_id=space_id,
                    expected="existing space",
                    actual=None,
                    message="Expected source-backed space is missing from design_model.json.",
                )
            continue

        expected_type = constraint.get("type")
        if expected_type is not None and space.get("type") != expected_type:
            append_constraint_failure(
                failures,
                code="space_type_mismatch",
                constraint=constraint,
                target_id=space_id,
                expected=expected_type,
                actual=space.get("type"),
                message="Space type does not match source constraint.",
            )

        expected_bounds = constraint_bounds(constraint)
        if expected_bounds is not None:
            tolerance = constraint_tolerance(
                constraint,
                default_tolerance,
                "bounds_tolerance",
                "bounds_tolerance_mm",
                "coordinate_tolerance",
                "coordinate_tolerance_mm",
            )
            actual_bounds = space_plan_bounds(space)
            if actual_bounds is None or not bounds_within_tolerance(
                actual_bounds,
                expected_bounds,
                tolerance=tolerance,
            ):
                append_constraint_failure(
                    failures,
                    code="space_bounds_mismatch",
                    constraint=constraint,
                    target_id=space_id,
                    expected=list(expected_bounds),
                    actual=list(actual_bounds) if actual_bounds else None,
                    message="Space footprint bounds do not match source evidence.",
                )

        label_anchor = normalize_label_anchor(constraint)
        if label_anchor is not None:
            tolerance = constraint_tolerance(
                constraint,
                default_tolerance,
                "label_anchor_tolerance",
                "label_anchor_tolerance_mm",
                "coordinate_tolerance",
                "coordinate_tolerance_mm",
            )
            footprint = space.get("footprint")
            normalized_footprint = (
                footprint_from_payload(footprint, label="space.footprint")
                if isinstance(footprint, list) and len(footprint) >= 3
                else []
            )
            if not normalized_footprint or not point_in_polygon_2d(
                label_anchor,
                normalized_footprint,
                tolerance=tolerance,
            ):
                append_constraint_failure(
                    failures,
                    code="space_label_anchor_outside_footprint",
                    constraint=constraint,
                    target_id=space_id,
                    expected={"label_anchor": label_anchor},
                    actual={"footprint": footprint},
                    message="Source room label anchor is not inside the generated space footprint.",
                )

        expected_area_m2 = constraint.get("area_m2") or constraint.get("label_area_m2")
        if expected_area_m2 is not None:
            footprint = space.get("footprint")
            if isinstance(footprint, list) and len(footprint) >= 3:
                area_m2 = polygon_area_mm2(
                    [
                        normalize_3d_point(point, label="space.footprint point")
                        for point in footprint
                    ]
                ) / 1_000_000
                ratio_tolerance = float(
                    constraint.get("area_tolerance_ratio", DEFAULT_LABEL_AREA_TOLERANCE_RATIO)
                )
                expected_area = float(expected_area_m2)
                if expected_area > 0 and abs(area_m2 - expected_area) / expected_area > ratio_tolerance:
                    append_constraint_failure(
                        failures,
                        code="space_area_mismatch",
                        constraint=constraint,
                        target_id=space_id,
                        expected=expected_area,
                        actual=area_m2,
                        message="Space area differs from source label beyond tolerance.",
                    )

    return failures, checked


def adjacency_constraint_space_ids(constraint: dict[str, Any]) -> tuple[str, str] | None:
    """Return the two space IDs from one adjacency source constraint."""
    value = constraint.get("space_ids") or constraint.get("spaces")
    if isinstance(value, list) and len(value) == 2:
        return str(value[0]), str(value[1])
    first = constraint.get("space_a") or constraint.get("from_space")
    second = constraint.get("space_b") or constraint.get("to_space")
    if first and second:
        return str(first), str(second)
    return None


def opening_connects_spaces(opening: dict[str, Any], first: str, second: str) -> bool:
    """Return whether an opening semantically connects the two spaces."""
    values = {
        str(value)
        for value in (
            opening.get("open_to_space"),
            opening.get("access_from_space"),
            opening.get("from_space"),
            opening.get("to_space"),
        )
        if value
    }
    return {first, second}.issubset(values)


def validate_space_adjacency_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    import_id: str,
) -> tuple[list[dict[str, Any]], int]:
    """Validate source-backed adjacency between spaces and their openings."""
    failures: list[dict[str, Any]] = []
    checked = 0
    spaces = design_model.get("spaces", {})
    walls = design_model.get("walls", {})
    openings = design_model.get("openings", {})

    for constraint in constraints:
        space_ids = adjacency_constraint_space_ids(constraint)
        if space_ids is None:
            continue
        checked += 1
        first, second = space_ids
        missing_spaces = [space_id for space_id in space_ids if space_id not in spaces]
        if missing_spaces:
            append_constraint_failure(
                failures,
                code="adjacency_space_missing",
                constraint=constraint,
                target_id=None,
                expected=list(space_ids),
                actual={"missing_spaces": missing_spaces},
                message="Source adjacency references a missing space.",
            )
            continue

        shared_wall_ids = [
            wall_id
            for wall_id, wall in walls.items()
            if isinstance(wall, dict)
            and isinstance(wall.get("source"), dict)
            and wall["source"].get("import_id") == import_id
            and {first, second}.issubset(set(wall_space_refs(wall)))
        ]
        if constraint.get("require_shared_wall", True) and not shared_wall_ids:
            append_constraint_failure(
                failures,
                code="adjacency_shared_wall_missing",
                constraint=constraint,
                target_id=None,
                expected={"space_ids": list(space_ids), "shared_wall": True},
                actual={"shared_wall_ids": []},
                message="No imported wall connects the source-adjacent spaces.",
            )

        opening_id = constraint.get("opening_id")
        require_opening = bool(opening_id or constraint.get("require_opening"))
        if not require_opening:
            continue
        candidate_openings = []
        if opening_id:
            opening = openings.get(str(opening_id))
            if isinstance(opening, dict):
                candidate_openings.append((str(opening_id), opening))
        else:
            candidate_openings = [
                (candidate_id, opening)
                for candidate_id, opening in openings.items()
                if isinstance(opening, dict)
            ]
        matching_opening_ids = [
            candidate_id
            for candidate_id, opening in candidate_openings
            if (
                str(opening.get("host_wall", "")) in shared_wall_ids
                or opening_connects_spaces(opening, first, second)
            )
        ]
        if not matching_opening_ids:
            append_constraint_failure(
                failures,
                code="adjacency_opening_missing",
                constraint=constraint,
                target_id=str(opening_id) if opening_id else None,
                expected={
                    "space_ids": list(space_ids),
                    "shared_wall_ids": shared_wall_ids,
                    "opening_id": opening_id,
                },
                actual={
                    "matching_opening_ids": [],
                    "candidate_opening_ids": [item[0] for item in candidate_openings],
                },
                message="No imported opening satisfies the source adjacency.",
            )

    return failures, checked


def entity_edge_coordinate(
    design_model: dict[str, Any],
    *,
    collection_name: str,
    entity_id: str,
    axis: str,
    edge: str,
) -> float | None:
    """Return a source-checkable entity edge coordinate."""
    collection = design_model.get(collection_name, {})
    entity = collection.get(entity_id) if isinstance(collection, dict) else None
    if not isinstance(entity, dict):
        return None
    if collection_name == "spaces":
        bounds = space_plan_bounds(entity)
        if bounds is None:
            return None
        index = {"x": {"min": 0, "max": 1}, "y": {"min": 2, "max": 3}}[axis][edge]
        return float(bounds[index])
    if collection_name == "walls":
        path = entity.get("path", [])
        wall_orientation = wall_axis(path)
        if wall_orientation is None:
            return None
        bounds = polygon_bounds(
            [
                normalize_3d_point(point, label="wall.path point")
                for point in (path[0], path[-1])
            ]
        )
        index = {"x": {"min": 0, "max": 1}, "y": {"min": 2, "max": 3}}[axis][edge]
        return float(bounds[index])
    return None


def validate_alignment_constraints(
    design_model: dict[str, Any],
    constraints: list[dict[str, Any]],
    *,
    default_tolerance: float,
) -> tuple[list[dict[str, Any]], int]:
    """Validate generic source-backed edge alignment constraints."""
    failures: list[dict[str, Any]] = []
    checked = 0

    for constraint in constraints:
        axis = str(constraint.get("axis", "x"))
        edge = str(constraint.get("edge", "min"))
        if axis not in {"x", "y"} or edge not in {"min", "max"}:
            continue
        collection_name = str(
            constraint.get("collection")
            or constraint.get("entity_collection")
            or "spaces"
        )
        if not collection_name.endswith("s"):
            collection_name = f"{collection_name}s"
        entity_ids = (
            constraint.get("entity_ids")
            or constraint.get("space_ids")
            or constraint.get("wall_ids")
        )
        if not isinstance(entity_ids, list) or len(entity_ids) < 2:
            continue
        checked += 1
        tolerance = constraint_tolerance(
            constraint,
            default_tolerance,
            "alignment_tolerance",
            "alignment_tolerance_mm",
        )
        actual: dict[str, float | None] = {
            str(entity_id): entity_edge_coordinate(
                design_model,
                collection_name=collection_name,
                entity_id=str(entity_id),
                axis=axis,
                edge=edge,
            )
            for entity_id in entity_ids
        }
        numeric_values = [
            value for value in actual.values() if isinstance(value, (int, float))
        ]
        missing = [entity_id for entity_id, value in actual.items() if value is None]
        expected_coordinate = constraint.get("coordinate")
        if expected_coordinate is not None:
            target = float(expected_coordinate)
        elif numeric_values:
            target = numeric_values[0]
        else:
            target = 0.0
        mismatches = {
            entity_id: value
            for entity_id, value in actual.items()
            if value is None or abs(float(value) - target) > tolerance
        }
        if missing or mismatches or (
            numeric_values and max(numeric_values) - min(numeric_values) > tolerance
        ):
            append_constraint_failure(
                failures,
                code="edge_alignment_mismatch",
                constraint=constraint,
                target_id=None,
                expected={
                    "collection": collection_name,
                    "entity_ids": [str(entity_id) for entity_id in entity_ids],
                    "axis": axis,
                    "edge": edge,
                    "coordinate": target,
                    "tolerance": tolerance,
                },
                actual=actual,
                message="Source-aligned entity edges are not aligned in generated truth.",
            )

    return failures, checked


def source_fidelity_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Return compact source-fidelity state safe for manifests and model sessions."""
    summary = {
        "status": result["status"],
        "checked_count": result["checked_count"],
        "failure_count": result["failure_count"],
        "constraints_path": result.get("constraints_path"),
        "updated_at": result["updated_at"],
    }
    if result.get("evidence_origin"):
        summary["evidence_origin"] = result["evidence_origin"]
    return summary


def validate_import_source_constraints(
    project_path: str | Path,
    import_id: str,
    *,
    constraints_path: str | Path | None = None,
    tolerance: float = 80.0,
    require_executed: bool = False,
    require_extracted_evidence: bool = False,
    update_state: bool = True,
) -> dict[str, Any]:
    """Validate generated import truth against source-scoped constraints."""
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    constraints, loaded_constraints_path = load_import_constraints(
        root,
        chosen_id,
        constraints_path=constraints_path,
    )

    timestamp = utc_now()
    design_model_path = find_design_model_path(root)
    design_model, model_errors = load_design_model(str(design_model_path))
    if model_errors or design_model is None:
        raise ValueError("; ".join(model_errors))

    if constraints is None:
        return {
            "project_path": str(root),
            "design_model_path": str(design_model_path),
            "import_id": chosen_id,
            "constraints_path": str(loaded_constraints_path),
            "status": "no_constraints",
            "checked_count": 0,
            "failure_count": 0,
            "failures": [],
            "warnings": ["No import source constraints file was found."],
            "updated_at": timestamp,
        }

    opening_constraints = source_constraint_items(
        constraints,
        "opening_constraints",
        "openings",
        "door_constraints",
        "window_constraints",
    )
    wall_constraints = source_constraint_items(
        constraints,
        "wall_constraints",
        "walls",
        "boundary_constraints",
    )
    exterior_outline_constraints = source_constraint_items(
        constraints,
        "exterior_outline_constraints",
        "outline_constraints",
        "wall_mass_outline_constraints",
        "source_outline_constraints",
    )
    boundary_closure_constraints = source_constraint_items(
        constraints,
        "boundary_closure_constraints",
        "space_boundary_constraints",
        "required_boundary_constraints",
    )
    negative_region_constraints = source_constraint_items(
        constraints,
        "negative_region_constraints",
        "negative_regions",
        "outside_regions",
    )
    space_constraints = source_constraint_items(
        constraints,
        "space_constraints",
        "space_footprint_constraints",
        "spaces",
    )
    adjacency_constraints = source_constraint_items(
        constraints,
        "adjacency_constraints",
        "space_adjacency_constraints",
        "required_adjacencies",
    )
    alignment_constraints = source_constraint_items(
        constraints,
        "alignment_constraints",
        "edge_alignment_constraints",
    )

    failures: list[dict[str, Any]] = []
    checked_count = 0
    evidence_origin = None
    if require_extracted_evidence:
        (
            evidence_failures,
            evidence_checked,
            evidence_origin,
        ) = validate_source_constraint_evidence_origins(constraints)
        failures.extend(evidence_failures)
        checked_count += evidence_checked
    for validator, items in (
        (
            lambda value: validate_opening_constraints(
                design_model,
                value,
                default_tolerance=tolerance,
                require_executed=require_executed,
                require_source_evidence_fields=require_extracted_evidence,
            ),
            opening_constraints,
        ),
        (
            lambda value: validate_wall_constraints(
                design_model,
                value,
                import_id=chosen_id,
                default_tolerance=tolerance,
            ),
            wall_constraints,
        ),
        (
            lambda value: validate_exterior_outline_constraints(
                design_model,
                value,
                import_id=chosen_id,
                default_tolerance=tolerance,
            ),
            exterior_outline_constraints,
        ),
        (
            lambda value: validate_boundary_closure_constraints(
                design_model,
                value,
                import_id=chosen_id,
                default_tolerance=tolerance,
            ),
            boundary_closure_constraints,
        ),
        (
            lambda value: validate_negative_region_constraints(
                design_model,
                value,
                import_id=chosen_id,
                default_tolerance=tolerance,
            ),
            negative_region_constraints,
        ),
        (
            lambda value: validate_space_constraints(
                design_model,
                value,
                default_tolerance=tolerance,
            ),
            space_constraints,
        ),
        (
            lambda value: validate_space_adjacency_constraints(
                design_model,
                value,
                import_id=chosen_id,
            ),
            adjacency_constraints,
        ),
        (
            lambda value: validate_alignment_constraints(
                design_model,
                value,
                default_tolerance=tolerance,
            ),
            alignment_constraints,
        ),
    ):
        validator_failures, validator_checked = validator(items)
        failures.extend(validator_failures)
        checked_count += validator_checked

    result = {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "constraints_path": project_relative_path(root, loaded_constraints_path),
        "status": source_constraint_status(len(failures), checked_count),
        "checked_count": checked_count,
        "failure_count": len(failures),
        "failures": failures,
        "warnings": [],
        "updated_at": timestamp,
    }
    if evidence_origin is not None:
        result["evidence_origin"] = evidence_origin

    if update_state:
        summary = source_fidelity_summary(result)
        design_model.setdefault("import_sessions", {}).setdefault(chosen_id, {})[
            "source_fidelity"
        ] = summary
        saved, save_errors = save_design_model(str(design_model_path), design_model)
        if not saved:
            raise ValueError("; ".join(save_errors))

        manifest, manifest_file = load_project_import_manifest(root, chosen_id)
        manifest["source_fidelity"] = summary
        append_processing_step(
            manifest,
            "validate_import_source_constraints",
            status="success" if result["status"] == "passed" else result["status"],
            details={
                "constraints_path": result["constraints_path"],
                "checked_count": result["checked_count"],
                "failure_count": result["failure_count"],
            },
        )
        saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
        if not saved_manifest:
            raise ValueError("; ".join(manifest_errors))

    return result


def merge_intervals(
    intervals: list[tuple[float, float]],
    *,
    tolerance: float,
) -> list[tuple[float, float]]:
    """Merge overlapping or touching intervals."""
    if not intervals:
        return []
    sorted_intervals = sorted(intervals)
    merged: list[tuple[float, float]] = [sorted_intervals[0]]
    for start, end in sorted_intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + tolerance:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def subtract_intervals(
    base: tuple[float, float],
    coverage: list[tuple[float, float]],
    *,
    tolerance: float,
) -> list[tuple[float, float]]:
    """Return portions of base not covered by coverage intervals."""
    gaps = [base]
    for cover_start, cover_end in merge_intervals(coverage, tolerance=tolerance):
        next_gaps: list[tuple[float, float]] = []
        for gap_start, gap_end in gaps:
            overlap_start = max(gap_start, cover_start)
            overlap_end = min(gap_end, cover_end)
            if overlap_end <= overlap_start + tolerance:
                next_gaps.append((gap_start, gap_end))
                continue
            if gap_start < overlap_start - tolerance:
                next_gaps.append((gap_start, overlap_start))
            if overlap_end < gap_end - tolerance:
                next_gaps.append((overlap_end, gap_end))
        gaps = next_gaps
    return gaps


def imported_axis_bounds(
    design_model: dict[str, Any],
    import_id: str,
    axis: str,
) -> tuple[float, float] | None:
    """Return min/max coordinate bounds for imported walls and spaces."""
    values: list[float] = []
    for collection_name in ("walls", "spaces"):
        for entity in design_model.get(collection_name, {}).values():
            source = entity.get("source", {}) if isinstance(entity, dict) else {}
            if not isinstance(source, dict) or source.get("import_id") != import_id:
                continue
            if collection_name == "walls":
                for point in entity.get("path", []):
                    values.append(point_axis_value(point, axis))
            else:
                footprint = entity.get("footprint")
                if isinstance(footprint, list):
                    values.extend(point_axis_value(point, axis) for point in footprint)
                bounds = entity.get("bounds", {})
                for key in ("min", "max"):
                    if key in bounds:
                        values.append(point_axis_value(bounds[key], axis))
    if not values:
        return None
    return min(values), max(values)


def boundary_snap_map_for_axis(
    design_model: dict[str, Any],
    import_id: str,
    axis: str,
    *,
    tolerance: float,
) -> dict[float, float]:
    """Return coordinate snaps for near-boundary imported wall segments."""
    bounds = imported_axis_bounds(design_model, import_id, axis)
    if bounds is None:
        return {}
    min_coord, max_coord = bounds
    coordinates: set[float] = set()
    for wall in design_model.get("walls", {}).values():
        source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        path = wall.get("path", [])
        if wall_axis(path) == axis:
            coordinates.add(point_axis_value(path[0], axis))

    snap_map: dict[float, float] = {}
    for coord in sorted(coordinates):
        if 0 < abs(coord - min_coord) <= tolerance:
            snap_map[coord] = min_coord
        elif 0 < abs(max_coord - coord) <= tolerance:
            snap_map[coord] = max_coord
    return snap_map


def snap_point(
    point: list[Any],
    snap_maps: dict[str, dict[float, float]],
    *,
    coordinate_match_tolerance: float,
) -> tuple[list[float], bool]:
    """Snap a point against axis coordinate maps."""
    result = [float(point[0]), float(point[1]), float(point[2])]
    changed = False
    for axis in ("x", "y"):
        index = 0 if axis == "x" else 1
        for source_coord, target_coord in snap_maps.get(axis, {}).items():
            if abs(result[index] - source_coord) <= coordinate_match_tolerance:
                result[index] = float(target_coord)
                changed = True
                break
    return result, changed


def add_import_quality_flag(
    design_model: dict[str, Any],
    import_id: str,
    code: str,
    *,
    severity: str = "info",
    message: str | None = None,
) -> None:
    """Add a deduped quality flag to model and import session summaries."""
    session = design_model.setdefault("import_sessions", {}).setdefault(import_id, {})
    session_flags = session.setdefault("quality_flags", [])
    if code not in session_flags:
        session_flags.append(code)

    quality_flags = design_model.setdefault("quality_flags", [])
    for flag in quality_flags:
        source = flag.get("source", {}) if isinstance(flag, dict) else {}
        if (
            isinstance(flag, dict)
            and flag.get("code") == code
            and isinstance(source, dict)
            and source.get("import_id") == import_id
        ):
            return
    quality_flags.append(
        {
            "code": code,
            "severity": severity,
            "message": message or code.replace("_", " "),
            "source": {"kind": "import_floorplan", "import_id": import_id},
        }
    )


def point_matches(
    point: list[Any],
    target: list[float],
    *,
    tolerance: float,
) -> bool:
    """Return whether two plan points are effectively equal."""
    return (
        abs(float(point[0]) - target[0]) <= tolerance
        and abs(float(point[1]) - target[1]) <= tolerance
    )


def replace_wall_endpoint(
    wall: dict[str, Any],
    old_point: list[float],
    new_point: list[float],
    *,
    tolerance: float,
) -> tuple[bool, float]:
    """Replace one matching wall endpoint and return start-offset adjustment."""
    path = wall.get("path", [])
    if not isinstance(path, list) or len(path) < 2:
        return False, 0.0
    for index in (0, len(path) - 1):
        if point_matches(path[index], old_point, tolerance=tolerance):
            offset_adjustment = wall_length([old_point, new_point]) if index == 0 else 0.0
            path[index] = [float(new_point[0]), float(new_point[1]), float(path[index][2])]
            wall["path"] = path
            wall.pop("execution", None)
            return True, offset_adjustment
    return False, 0.0


def find_boundary_wall_at_corner(
    design_model: dict[str, Any],
    import_id: str,
    corner_point: list[float],
    axis: str,
    *,
    coordinate_match_tolerance: float,
) -> tuple[str, dict[str, Any]] | None:
    """Find an imported boundary wall endpoint at one corner."""
    for wall_id, wall in design_model.get("walls", {}).items():
        source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        path = wall.get("path", [])
        if wall_axis(path) != axis:
            continue
        if any(
            point_matches(point, corner_point, tolerance=coordinate_match_tolerance)
            for point in (path[0], path[-1])
        ):
            return wall_id, wall
    return None


def imported_plan_bounds(
    design_model: dict[str, Any],
    import_id: str,
) -> tuple[float, float, float, float]:
    """Return imported model plan bounds as min_x, max_x, min_y, max_y."""
    x_bounds = imported_axis_bounds(design_model, import_id, "x")
    y_bounds = imported_axis_bounds(design_model, import_id, "y")
    if x_bounds is None or y_bounds is None:
        raise ValueError(f"no imported walls or spaces found for import_id: {import_id}")
    return x_bounds[0], x_bounds[1], y_bounds[0], y_bounds[1]


def imported_wall_endpoints(
    design_model: dict[str, Any],
    import_id: str,
) -> list[list[float]]:
    """Return start and end points from imported wall paths."""
    endpoints: list[list[float]] = []
    for wall in design_model.get("walls", {}).values():
        source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        path = wall.get("path", [])
        if isinstance(path, list) and len(path) >= 2:
            endpoints.append(normalize_3d_point(path[0], label="wall path start"))
            endpoints.append(normalize_3d_point(path[-1], label="wall path end"))
    return endpoints


def point_has_near_endpoint(
    point: list[float],
    endpoints: list[list[float]],
    *,
    tolerance: float,
) -> bool:
    """Return whether a point is supported by a nearby imported wall endpoint."""
    return any(point_matches(endpoint, point, tolerance=tolerance) for endpoint in endpoints)


def wall_coverage_for_edge(
    design_model: dict[str, Any],
    import_id: str,
    *,
    axis: str,
    line_coordinate: float,
    edge_interval: tuple[float, float],
    coordinate_match_tolerance: float,
) -> list[tuple[float, float]]:
    """Return wall intervals that cover one imported space footprint edge."""
    coverage: list[tuple[float, float]] = []
    edge_start, edge_end = edge_interval
    for wall in design_model.get("walls", {}).values():
        source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        path = wall.get("path", [])
        if wall_axis(path, tolerance=coordinate_match_tolerance) != axis:
            continue
        if (
            abs(segment_line_coordinate(path, axis) - line_coordinate)
            > coordinate_match_tolerance
        ):
            continue
        wall_start, wall_end = segment_interval(path, axis)
        overlap_start = max(edge_start, wall_start)
        overlap_end = min(edge_end, wall_end)
        if overlap_end > overlap_start + coordinate_match_tolerance:
            coverage.append((overlap_start, overlap_end))
    return coverage


def spaces_covering_edge_segment(
    design_model: dict[str, Any],
    import_id: str,
    *,
    axis: str,
    line_coordinate: float,
    segment_interval_value: tuple[float, float],
    coordinate_match_tolerance: float,
) -> list[dict[str, Any]]:
    """Return imported spaces whose footprint edge covers a plan segment."""
    segment_start, segment_end = segment_interval_value
    spaces: list[dict[str, Any]] = []
    seen: set[str] = set()
    for space_id, space in design_model.get("spaces", {}).items():
        source = space.get("source", {}) if isinstance(space, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        footprint = space.get("footprint")
        if not isinstance(footprint, list) or len(footprint) < 3:
            continue
        for index, raw_start in enumerate(footprint):
            raw_end = footprint[(index + 1) % len(footprint)]
            edge_path = [
                normalize_3d_point(raw_start, label=f"{space_id} footprint[{index}]"),
                normalize_3d_point(
                    raw_end,
                    label=f"{space_id} footprint[{(index + 1) % len(footprint)}]",
                ),
            ]
            if wall_axis(edge_path, tolerance=coordinate_match_tolerance) != axis:
                continue
            if (
                abs(segment_line_coordinate(edge_path, axis) - line_coordinate)
                > coordinate_match_tolerance
            ):
                continue
            edge_start, edge_end = segment_interval(edge_path, axis)
            if (
                segment_start < edge_start - coordinate_match_tolerance
                or segment_end > edge_end + coordinate_match_tolerance
            ):
                continue
            if space_id in seen:
                continue
            seen.add(space_id)
            spaces.append(
                {
                    "space_id": space_id,
                    "type": space.get("type", "other"),
                    "label": space.get("label"),
                    "edge_index": index,
                }
            )
    return spaces


def short_gap_source_evidence_signal(
    *,
    axis: str,
    length: float,
    adjacent_spaces: list[dict[str, Any]],
    max_source_evidence_gap_length: float,
) -> dict[str, Any]:
    """Return whether a short footprint gap has source evidence for auto-repair."""
    space_types = {str(space.get("type", "other")) for space in adjacent_spaces}
    if length > max_source_evidence_gap_length:
        return {
            "repair_recommended": False,
            "confidence": 0.0,
            "reasons": ["gap exceeds short-gap source-evidence length threshold"],
            "adjacent_space_types": sorted(space_types),
        }
    return {
        "repair_recommended": False,
        "confidence": 0.0,
        "reasons": [
            "space adjacency alone is insufficient for auto-filling a short gap",
            "source-backed wall-continuity evidence is required",
        ],
        "adjacent_space_types": sorted(space_types),
    }


def space_edge_coverage_for_wall(
    design_model: dict[str, Any],
    import_id: str,
    *,
    axis: str,
    line_coordinate: float,
    wall_interval: tuple[float, float],
    coordinate_match_tolerance: float,
) -> list[tuple[float, float]]:
    """Return imported space footprint intervals that explain one wall segment."""
    coverage: list[tuple[float, float]] = []
    wall_start, wall_end = wall_interval
    for space_id, space in design_model.get("spaces", {}).items():
        source = space.get("source", {}) if isinstance(space, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        footprint = space.get("footprint")
        if not isinstance(footprint, list) or len(footprint) < 3:
            continue
        for index, raw_start in enumerate(footprint):
            raw_end = footprint[(index + 1) % len(footprint)]
            edge_path = [
                normalize_3d_point(raw_start, label=f"{space_id} footprint[{index}]"),
                normalize_3d_point(
                    raw_end,
                    label=f"{space_id} footprint[{(index + 1) % len(footprint)}]",
                ),
            ]
            if wall_axis(edge_path, tolerance=coordinate_match_tolerance) != axis:
                continue
            if (
                abs(segment_line_coordinate(edge_path, axis) - line_coordinate)
                > coordinate_match_tolerance
            ):
                continue
            edge_start, edge_end = segment_interval(edge_path, axis)
            overlap_start = max(wall_start, edge_start)
            overlap_end = min(wall_end, edge_end)
            if overlap_end > overlap_start + coordinate_match_tolerance:
                coverage.append((overlap_start, overlap_end))
    return coverage


def imported_wall_space_overreach_segments(
    design_model: dict[str, Any],
    import_id: str,
    *,
    min_segment_length: float = DEFAULT_MIN_SHELL_OVERREACH_LENGTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> list[dict[str, Any]]:
    """Return imported wall segments not explained by any imported space edge."""
    if min_segment_length <= 0:
        raise ValueError("min_segment_length must be positive.")
    if coordinate_match_tolerance <= 0:
        raise ValueError("coordinate_match_tolerance must be positive.")

    segments: list[dict[str, Any]] = []
    for wall_id, wall in design_model.get("walls", {}).items():
        source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        path = wall.get("path", [])
        axis = wall_axis(path, tolerance=coordinate_match_tolerance)
        if axis is None:
            continue
        line_coordinate = segment_line_coordinate(path, axis)
        wall_interval = segment_interval(path, axis)
        coverage = space_edge_coverage_for_wall(
            design_model,
            import_id,
            axis=axis,
            line_coordinate=line_coordinate,
            wall_interval=wall_interval,
            coordinate_match_tolerance=coordinate_match_tolerance,
        )
        uncovered = subtract_intervals(
            wall_interval,
            coverage,
            tolerance=coordinate_match_tolerance,
        )
        z = float(path[0][2])
        for start, end in uncovered:
            length = end - start
            if length <= min_segment_length:
                continue
            segments.append(
                {
                    "wall_id": wall_id,
                    "axis": axis,
                    "line_coordinate": line_coordinate,
                    "wall_interval": [wall_interval[0], wall_interval[1]],
                    "interval": [start, end],
                    "start_point": point_from_axis_interval(axis, line_coordinate, start, z),
                    "end_point": point_from_axis_interval(axis, line_coordinate, end, z),
                    "length": length,
                    "classification": "candidate_shell_overreach",
                    "repair_recommended": True,
                }
            )
    return segments


def wall_path_from_interval(
    axis: str,
    line_coordinate: float,
    interval: tuple[float, float],
    z: float,
) -> list[list[float]]:
    """Return a wall path from an axis line and interval."""
    return [
        point_from_axis_interval(axis, line_coordinate, interval[0], z),
        point_from_axis_interval(axis, line_coordinate, interval[1], z),
    ]


def split_wall_path_by_removing_intervals(
    path: list[Any],
    remove_intervals: list[tuple[float, float]],
    *,
    coordinate_match_tolerance: float,
    min_wall_length: float,
) -> list[list[list[float]]]:
    """Return wall paths after removing overreach intervals."""
    axis = wall_axis(path, tolerance=coordinate_match_tolerance)
    if axis is None:
        return []
    base_interval = segment_interval(path, axis)
    kept_intervals = subtract_intervals(
        base_interval,
        remove_intervals,
        tolerance=coordinate_match_tolerance,
    )
    line_coordinate = segment_line_coordinate(path, axis)
    z = float(path[0][2])
    kept_paths: list[list[list[float]]] = []
    for interval in kept_intervals:
        if interval[1] - interval[0] <= min_wall_length:
            continue
        kept_paths.append(wall_path_from_interval(axis, line_coordinate, interval, z))
    return kept_paths


def sync_generated_wall_ids(
    session: dict[str, Any],
    *,
    added_walls: list[str],
    removed_walls: list[str],
    changed_model_ids: list[str],
) -> None:
    """Keep import-session generated model IDs aligned with wall repairs."""
    generated_model = session.setdefault("generated_model", {})
    if isinstance(generated_model.get("wall_ids"), list):
        generated_model["wall_ids"] = [
            wall_id
            for wall_id in generated_model["wall_ids"]
            if wall_id not in removed_walls
        ]
        for wall_id in added_walls:
            if wall_id not in generated_model["wall_ids"]:
                generated_model["wall_ids"].append(wall_id)
    if isinstance(generated_model.get("changed_model_ids"), list):
        generated_model["changed_model_ids"] = [
            entity_id
            for entity_id in generated_model["changed_model_ids"]
            if entity_id not in removed_walls
        ]
        for entity_id in changed_model_ids:
            if (
                entity_id not in removed_walls
                and entity_id not in generated_model["changed_model_ids"]
            ):
                generated_model["changed_model_ids"].append(entity_id)


def boundary_gap_id(
    import_id: str,
    start_point: list[float],
    end_point: list[float],
) -> str:
    """Return a stable wall ID for a repaired imported boundary gap."""
    payload = json.dumps([start_point, end_point], separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"{import_id}_boundary_gap_{digest}"


def imported_boundary_coverage_gaps(
    design_model: dict[str, Any],
    import_id: str,
    *,
    min_gap_length: float = DEFAULT_MIN_BOUNDARY_GAP_LENGTH,
    max_opening_gap_length: float = DEFAULT_MAX_OPENING_GAP_LENGTH,
    infer_source_evidence_short_gaps: bool = True,
    max_source_evidence_gap_length: float = DEFAULT_MAX_SOURCE_EVIDENCE_SHORT_GAP_LENGTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    require_structural_endpoints: bool = True,
) -> list[dict[str, Any]]:
    """Return uncovered imported space footprint segments."""
    if min_gap_length <= 0:
        raise ValueError("min_gap_length must be positive.")
    if max_opening_gap_length < 0:
        raise ValueError("max_opening_gap_length must be non-negative.")
    if max_source_evidence_gap_length < 0:
        raise ValueError("max_source_evidence_gap_length must be non-negative.")
    if coordinate_match_tolerance <= 0:
        raise ValueError("coordinate_match_tolerance must be positive.")

    endpoints = imported_wall_endpoints(design_model, import_id)
    gaps: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, int]] = set()

    for space_id, space in design_model.get("spaces", {}).items():
        source = space.get("source", {}) if isinstance(space, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        footprint = space.get("footprint")
        if not isinstance(footprint, list) or len(footprint) < 3:
            continue
        for index, raw_start in enumerate(footprint):
            raw_end = footprint[(index + 1) % len(footprint)]
            edge_path = [
                normalize_3d_point(raw_start, label=f"{space_id} footprint[{index}]"),
                normalize_3d_point(
                    raw_end,
                    label=f"{space_id} footprint[{(index + 1) % len(footprint)}]",
                ),
            ]
            axis = wall_axis(edge_path, tolerance=coordinate_match_tolerance)
            if axis is None:
                continue
            edge_interval = segment_interval(edge_path, axis)
            if edge_interval[1] - edge_interval[0] <= min_gap_length:
                continue
            line_coordinate = segment_line_coordinate(edge_path, axis)
            coverage = wall_coverage_for_edge(
                design_model,
                import_id,
                axis=axis,
                line_coordinate=line_coordinate,
                edge_interval=edge_interval,
                coordinate_match_tolerance=coordinate_match_tolerance,
            )
            uncovered = subtract_intervals(
                edge_interval,
                coverage,
                tolerance=coordinate_match_tolerance,
            )
            z = float(edge_path[0][2])
            for gap_start, gap_end in uncovered:
                length = gap_end - gap_start
                if length <= min_gap_length:
                    continue
                start_point = point_from_axis_interval(axis, line_coordinate, gap_start, z)
                end_point = point_from_axis_interval(axis, line_coordinate, gap_end, z)
                dedupe_key = (
                    axis,
                    round(line_coordinate / coordinate_match_tolerance),
                    round(gap_start / coordinate_match_tolerance),
                    round(gap_end / coordinate_match_tolerance),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                start_supported = point_has_near_endpoint(
                    start_point,
                    endpoints,
                    tolerance=coordinate_match_tolerance,
                )
                end_supported = point_has_near_endpoint(
                    end_point,
                    endpoints,
                    tolerance=coordinate_match_tolerance,
                )
                classification = (
                    "candidate_opening_or_intentional_gap"
                    if length <= max_opening_gap_length
                    else "candidate_missing_wall"
                )
                adjacent_spaces = spaces_covering_edge_segment(
                    design_model,
                    import_id,
                    axis=axis,
                    line_coordinate=line_coordinate,
                    segment_interval_value=(gap_start, gap_end),
                    coordinate_match_tolerance=coordinate_match_tolerance,
                )
                circulation_gap = is_circulation_gap(
                    adjacent_spaces,
                    length=length,
                )
                if classification == "candidate_missing_wall" and circulation_gap:
                    classification = "candidate_circulation_opening_or_intentional_gap"
                if infer_source_evidence_short_gaps:
                    source_evidence_repair = short_gap_source_evidence_signal(
                        axis=axis,
                        length=length,
                        adjacent_spaces=adjacent_spaces,
                        max_source_evidence_gap_length=max_source_evidence_gap_length,
                    )
                else:
                    source_evidence_repair = {
                        "repair_recommended": False,
                        "confidence": 0.0,
                        "reasons": ["short-gap source-evidence review disabled"],
                        "adjacent_space_types": sorted(
                            {
                                str(space.get("type", "other"))
                                for space in adjacent_spaces
                            }
                        ),
                    }
                repair_recommended = classification == "candidate_missing_wall" and (
                    not require_structural_endpoints
                    or (start_supported and end_supported)
                )
                gaps.append(
                    {
                        "space_id": space_id,
                        "edge_index": index,
                        "axis": axis,
                        "line_coordinate": line_coordinate,
                        "interval": [gap_start, gap_end],
                        "start_point": start_point,
                        "end_point": end_point,
                        "length": length,
                        "classification": classification,
                        "repair_recommended": repair_recommended,
                        "adjacent_spaces": adjacent_spaces,
                        "circulation_gap": circulation_gap,
                        "source_evidence_repair": source_evidence_repair,
                        "endpoint_support": {
                            "start": start_supported,
                            "end": end_supported,
                        },
                    }
                )
    return gaps


def reference_wall_for_boundary_segment(
    design_model: dict[str, Any],
    import_id: str,
    start_point: list[float],
    end_point: list[float],
    *,
    coordinate_match_tolerance: float,
) -> dict[str, Any]:
    """Return a nearby imported wall to inherit wall attributes from."""
    target_axis = wall_axis([start_point, end_point], tolerance=coordinate_match_tolerance)
    candidates: list[dict[str, Any]] = []
    for wall in design_model.get("walls", {}).values():
        source = wall.get("source", {}) if isinstance(wall, dict) else {}
        if not isinstance(source, dict) or source.get("import_id") != import_id:
            continue
        candidates.append(wall)
        path = wall.get("path", [])
        if target_axis is not None and wall_axis(path) == target_axis:
            if any(
                point_matches(point, start_point, tolerance=coordinate_match_tolerance)
                or point_matches(point, end_point, tolerance=coordinate_match_tolerance)
                for point in (path[0], path[-1])
            ):
                return wall
    if candidates:
        return candidates[0]
    return {
        "height": DEFAULT_WALL_HEIGHT,
        "thickness": DEFAULT_WALL_THICKNESS,
        "alignment": "inner",
        "layer": "Walls",
        "source": {
            "kind": "import_floorplan",
            "import_id": import_id,
            "confidence": 0.5,
            "assumptions": ["Boundary wall inferred from imported space footprint."],
        },
    }


def add_imported_boundary_wall(
    design_model: dict[str, Any],
    import_id: str,
    *,
    start_point: list[float],
    end_point: list[float],
    wall_id: str | None = None,
    coordinate_match_tolerance: float,
) -> tuple[str, bool]:
    """Add one source-backed imported boundary wall if it does not already exist."""
    path = [start_point, end_point]
    if wall_axis(path, tolerance=coordinate_match_tolerance) is None:
        raise ValueError("boundary gap repair only supports axis-aligned wall segments.")
    if wall_length(path) <= DEFAULT_MIN_WALL_LENGTH:
        raise ValueError("boundary gap repair wall segment is too short.")

    chosen_wall_id = wall_id or boundary_gap_id(import_id, start_point, end_point)
    existing = design_model.setdefault("walls", {}).get(chosen_wall_id)
    if isinstance(existing, dict):
        existing_path = existing.get("path", [])
        if (
            isinstance(existing_path, list)
            and len(existing_path) >= 2
            and point_matches(
                normalize_3d_point(existing_path[0], label=f"{chosen_wall_id} start"),
                start_point,
                tolerance=coordinate_match_tolerance,
            )
            and point_matches(
                normalize_3d_point(existing_path[-1], label=f"{chosen_wall_id} end"),
                end_point,
                tolerance=coordinate_match_tolerance,
            )
        ):
            return chosen_wall_id, False
        raise ValueError(f"wall_id already exists with different geometry: {chosen_wall_id}")

    reference_wall = reference_wall_for_boundary_segment(
        design_model,
        import_id,
        start_point,
        end_point,
        coordinate_match_tolerance=coordinate_match_tolerance,
    )
    design_model["walls"][chosen_wall_id] = wall_payload_from_reference(
        chosen_wall_id,
        path,
        reference_wall,
    )
    return chosen_wall_id, True


def corner_notch_geometry(
    bounds: tuple[float, float, float, float],
    corner: str,
    horizontal_offset: float,
    vertical_offset: float,
) -> dict[str, Any]:
    """Return wall edit geometry for an exterior corner notch."""
    min_x, max_x, min_y, max_y = bounds
    if corner == "top_left":
        corner_point = [min_x, max_y, 0.0]
        top_endpoint = [min_x + horizontal_offset, max_y, 0.0]
        side_endpoint = [min_x, max_y - vertical_offset, 0.0]
        return {
            "corner_point": corner_point,
            "top_endpoint": top_endpoint,
            "side_endpoint": side_endpoint,
            "vertical_return": [top_endpoint, [min_x + horizontal_offset, max_y - vertical_offset, 0.0]],
            "horizontal_return": [[min_x + horizontal_offset, max_y - vertical_offset, 0.0], side_endpoint],
            "top_axis": "y",
            "side_axis": "x",
        }
    if corner == "top_right":
        corner_point = [max_x, max_y, 0.0]
        top_endpoint = [max_x - horizontal_offset, max_y, 0.0]
        side_endpoint = [max_x, max_y - vertical_offset, 0.0]
        return {
            "corner_point": corner_point,
            "top_endpoint": top_endpoint,
            "side_endpoint": side_endpoint,
            "vertical_return": [top_endpoint, [max_x - horizontal_offset, max_y - vertical_offset, 0.0]],
            "horizontal_return": [[max_x - horizontal_offset, max_y - vertical_offset, 0.0], side_endpoint],
            "top_axis": "y",
            "side_axis": "x",
        }
    if corner == "bottom_left":
        corner_point = [min_x, min_y, 0.0]
        bottom_endpoint = [min_x + horizontal_offset, min_y, 0.0]
        side_endpoint = [min_x, min_y + vertical_offset, 0.0]
        return {
            "corner_point": corner_point,
            "top_endpoint": bottom_endpoint,
            "side_endpoint": side_endpoint,
            "vertical_return": [bottom_endpoint, [min_x + horizontal_offset, min_y + vertical_offset, 0.0]],
            "horizontal_return": [[min_x + horizontal_offset, min_y + vertical_offset, 0.0], side_endpoint],
            "top_axis": "y",
            "side_axis": "x",
        }
    if corner == "bottom_right":
        corner_point = [max_x, min_y, 0.0]
        bottom_endpoint = [max_x - horizontal_offset, min_y, 0.0]
        side_endpoint = [max_x, min_y + vertical_offset, 0.0]
        return {
            "corner_point": corner_point,
            "top_endpoint": bottom_endpoint,
            "side_endpoint": side_endpoint,
            "vertical_return": [bottom_endpoint, [max_x - horizontal_offset, min_y + vertical_offset, 0.0]],
            "horizontal_return": [[max_x - horizontal_offset, min_y + vertical_offset, 0.0], side_endpoint],
            "top_axis": "y",
            "side_axis": "x",
        }
    raise ValueError(f"unsupported corner: {corner}")


def wall_payload_from_reference(
    wall_id: str,
    path: list[list[float]],
    reference_wall: dict[str, Any],
) -> dict[str, Any]:
    """Create an imported wall payload from an existing imported wall."""
    return {
        "path": path,
        "height": float(reference_wall.get("height", DEFAULT_WALL_HEIGHT)),
        "thickness": float(reference_wall.get("thickness", DEFAULT_WALL_THICKNESS)),
        "alignment": reference_wall.get("alignment", "inner"),
        "layer": reference_wall.get("layer", "Walls"),
        "source": reference_wall.get("source", {}),
    }


def notched_space_footprint(
    space: dict[str, Any],
    corner: str,
    horizontal_offset: float,
    vertical_offset: float,
) -> list[list[float]]:
    """Return a rectangular space footprint with one exterior corner notched."""
    bounds = space.get("bounds", {})
    if not isinstance(bounds, dict) or "min" not in bounds or "max" not in bounds:
        raise ValueError("target space must have rectangular bounds.")
    min_x, min_y, min_z = [float(value) for value in bounds["min"]]
    max_x, max_y, _max_z = [float(value) for value in bounds["max"]]
    z = min_z
    if horizontal_offset >= max_x - min_x:
        raise ValueError("horizontal_offset must be smaller than target space width.")
    if vertical_offset >= max_y - min_y:
        raise ValueError("vertical_offset must be smaller than target space depth.")

    if corner == "top_left":
        return [
            [min_x + horizontal_offset, max_y, z],
            [max_x, max_y, z],
            [max_x, min_y, z],
            [min_x, min_y, z],
            [min_x, max_y - vertical_offset, z],
            [min_x + horizontal_offset, max_y - vertical_offset, z],
        ]
    if corner == "top_right":
        return [
            [min_x, max_y, z],
            [max_x - horizontal_offset, max_y, z],
            [max_x - horizontal_offset, max_y - vertical_offset, z],
            [max_x, max_y - vertical_offset, z],
            [max_x, min_y, z],
            [min_x, min_y, z],
        ]
    if corner == "bottom_left":
        return [
            [min_x, max_y, z],
            [max_x, max_y, z],
            [max_x, min_y, z],
            [min_x + horizontal_offset, min_y, z],
            [min_x + horizontal_offset, min_y + vertical_offset, z],
            [min_x, min_y + vertical_offset, z],
        ]
    if corner == "bottom_right":
        return [
            [min_x, max_y, z],
            [max_x, max_y, z],
            [max_x, min_y + vertical_offset, z],
            [max_x - horizontal_offset, min_y + vertical_offset, z],
            [max_x - horizontal_offset, min_y, z],
            [min_x, min_y, z],
        ]
    raise ValueError(f"unsupported corner: {corner}")


def normalize_imported_wall_alignment(
    project_path: str | Path,
    import_id: str,
    *,
    tolerance: float = DEFAULT_ALIGNMENT_TOLERANCE,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    min_wall_length: float = DEFAULT_MIN_WALL_LENGTH,
    notes: str | None = None,
) -> dict[str, Any]:
    """Snap near-boundary imported wall segments onto shared exterior lines."""
    if tolerance <= 0:
        raise ValueError("tolerance must be positive.")
    if coordinate_match_tolerance <= 0:
        raise ValueError("coordinate_match_tolerance must be positive.")
    if min_wall_length < 0:
        raise ValueError("min_wall_length must be non-negative.")

    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    session = design_model.get("import_sessions", {}).get(chosen_id)
    if not isinstance(session, dict):
        raise ValueError(f"import session not found in design_model.json: {chosen_id}")

    snap_maps = {
        axis: boundary_snap_map_for_axis(
            design_model,
            chosen_id,
            axis,
            tolerance=tolerance,
        )
        for axis in ("x", "y")
    }
    snap_maps = {axis: mapping for axis, mapping in snap_maps.items() if mapping}
    changed_walls: list[str] = []
    removed_walls: list[str] = []
    changed_spaces: list[str] = []
    changed_openings: list[str] = []

    if snap_maps:
        for wall_id, wall in list(design_model.get("walls", {}).items()):
            source = wall.get("source", {}) if isinstance(wall, dict) else {}
            if not isinstance(source, dict) or source.get("import_id") != chosen_id:
                continue
            snapped_path: list[list[float]] = []
            changed = False
            for point in wall.get("path", []):
                snapped_point, point_changed = snap_point(
                    point,
                    snap_maps,
                    coordinate_match_tolerance=coordinate_match_tolerance,
                )
                snapped_path.append(snapped_point)
                changed = changed or point_changed
            if changed:
                wall["path"] = snapped_path
                wall.pop("execution", None)
                changed_walls.append(wall_id)
            if wall_length(wall.get("path", [])) <= min_wall_length:
                removed_walls.append(wall_id)
                del design_model["walls"][wall_id]

        for space_id, space in design_model.get("spaces", {}).items():
            source = space.get("source", {}) if isinstance(space, dict) else {}
            if not isinstance(source, dict) or source.get("import_id") != chosen_id:
                continue
            changed = False
            if isinstance(space.get("footprint"), list):
                footprint = []
                for point in space["footprint"]:
                    snapped_point, point_changed = snap_point(
                        point,
                        snap_maps,
                        coordinate_match_tolerance=coordinate_match_tolerance,
                    )
                    footprint.append(snapped_point)
                    changed = changed or point_changed
                space["footprint"] = footprint
            bounds = space.get("bounds")
            if isinstance(bounds, dict):
                for key in ("min", "max"):
                    if key in bounds:
                        snapped_point, point_changed = snap_point(
                            bounds[key],
                            snap_maps,
                            coordinate_match_tolerance=coordinate_match_tolerance,
                        )
                        bounds[key] = snapped_point
                        changed = changed or point_changed
                if "min" in bounds and "max" in bounds:
                    space["center"] = [
                        (float(bounds["min"][0]) + float(bounds["max"][0])) / 2,
                        (float(bounds["min"][1]) + float(bounds["max"][1])) / 2,
                        (float(bounds["min"][2]) + float(bounds["max"][2])) / 2,
                    ]
            if changed:
                space.pop("execution", None)
                changed_spaces.append(space_id)

    if changed_walls or removed_walls or changed_spaces:
        for opening_id in imported_ids_in_model(design_model, chosen_id)["openings"]:
            opening = design_model.get("openings", {}).get(opening_id)
            if isinstance(opening, dict):
                opening.pop("execution", None)
                changed_openings.append(opening_id)

    changed_model_ids = [
        *changed_spaces,
        *changed_walls,
        *removed_walls,
        *changed_openings,
    ]
    changed_model_ids = list(dict.fromkeys(changed_model_ids))
    active_changed_model_ids = [
        entity_id for entity_id in changed_model_ids if entity_id not in removed_walls
    ]

    generated_model = session.setdefault("generated_model", {})
    if removed_walls and isinstance(generated_model.get("wall_ids"), list):
        generated_model["wall_ids"] = [
            wall_id for wall_id in generated_model["wall_ids"] if wall_id not in removed_walls
        ]
    if isinstance(generated_model.get("changed_model_ids"), list):
        generated_model["changed_model_ids"] = [
            entity_id
            for entity_id in generated_model["changed_model_ids"]
            if entity_id not in removed_walls
        ]
        for entity_id in active_changed_model_ids:
            if entity_id not in generated_model["changed_model_ids"]:
                generated_model["changed_model_ids"].append(entity_id)

    action = {
        "created_at": utc_now(),
        "action": "normalize_imported_wall_alignment",
        "tolerance": tolerance,
        "coordinate_match_tolerance": coordinate_match_tolerance,
        "min_wall_length": min_wall_length,
        "snap_maps": {
            axis: {str(source): target for source, target in mapping.items()}
            for axis, mapping in snap_maps.items()
        },
        "changed_walls": changed_walls,
        "removed_walls": removed_walls,
        "changed_spaces": changed_spaces,
        "changed_openings": changed_openings,
        "notes": notes,
    }
    if changed_model_ids:
        add_import_quality_flag(
            design_model,
            chosen_id,
            "exterior_wall_alignment_normalized",
            message="Imported exterior wall segments were snapped to shared boundary lines.",
        )
        add_import_quality_flag(
            design_model,
            chosen_id,
            "dimension_chain_conflict_resolved",
            severity="warning",
            message="Near-boundary dimension-chain conflict was resolved by exterior wall snapping.",
        )
        design_model["updated_at"] = utc_now()
        mark_execution_dirty(
            design_model,
            reason="import_wall_alignment_normalized",
            source="normalize_imported_wall_alignment",
            details={"import_id": chosen_id, "changed_model_ids": changed_model_ids},
        )

    saved, save_errors = save_design_model(str(design_model_path), design_model)
    if not saved:
        raise ValueError("; ".join(save_errors))

    manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    manifest["status"] = "repaired" if changed_model_ids else manifest.get("status", "imported")
    manifest["quality_flags"] = dedupe_quality_flags(
        [
            *manifest.get("quality_flags", []),
            *(
                [
                    "exterior_wall_alignment_normalized",
                    "dimension_chain_conflict_resolved",
                ]
                if changed_model_ids
                else []
            ),
        ]
    )
    append_processing_step(
        manifest,
        "normalize_imported_wall_alignment",
        details=action,
    )
    manifest.setdefault("repair_history", []).append(action)
    saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
    if not saved_manifest:
        raise ValueError("; ".join(manifest_errors))

    interpretation_path = import_session_path(root, chosen_id) / "extracted" / "interpretation.json"
    if interpretation_path.exists():
        try:
            interpretation = json.loads(interpretation_path.read_text(encoding="utf-8"))
            interpretation.setdefault("processing_notes", []).append(
                "Normalized near-boundary exterior wall alignment."
            )
            interpretation.setdefault("repairs", []).append(action)
            interpretation_path.write_text(
                json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except json.JSONDecodeError:
            pass

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "status": "normalized" if changed_model_ids else "unchanged",
        "snap_maps": action["snap_maps"],
        "coordinate_match_tolerance": coordinate_match_tolerance,
        "changed_walls": changed_walls,
        "removed_walls": removed_walls,
        "changed_spaces": changed_spaces,
        "changed_openings": changed_openings,
        "changed_model_ids": changed_model_ids,
        "active_changed_model_ids": active_changed_model_ids,
        "quality_flags": session.get("quality_flags", []),
    }


def repair_imported_corner_notch(
    project_path: str | Path,
    import_id: str,
    *,
    corner: str,
    horizontal_offset: float,
    vertical_offset: float,
    target_space_id: str | None = None,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    min_wall_length: float = DEFAULT_MIN_WALL_LENGTH,
    notes: str | None = None,
) -> dict[str, Any]:
    """Add a source-backed exterior corner notch to imported working truth."""
    if corner not in VALID_CORNER_NOTCHES:
        raise ValueError(f"corner must be one of: {', '.join(sorted(VALID_CORNER_NOTCHES))}")
    if horizontal_offset <= 0:
        raise ValueError("horizontal_offset must be positive.")
    if vertical_offset <= 0:
        raise ValueError("vertical_offset must be positive.")
    if coordinate_match_tolerance <= 0:
        raise ValueError("coordinate_match_tolerance must be positive.")
    if min_wall_length < 0:
        raise ValueError("min_wall_length must be non-negative.")

    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    session = design_model.get("import_sessions", {}).get(chosen_id)
    if not isinstance(session, dict):
        raise ValueError(f"import session not found in design_model.json: {chosen_id}")

    bounds = imported_plan_bounds(design_model, chosen_id)
    min_x, max_x, min_y, max_y = bounds
    if horizontal_offset >= max_x - min_x:
        raise ValueError("horizontal_offset must be smaller than imported width.")
    if vertical_offset >= max_y - min_y:
        raise ValueError("vertical_offset must be smaller than imported depth.")

    geometry = corner_notch_geometry(bounds, corner, horizontal_offset, vertical_offset)
    corner_point = geometry["corner_point"]
    horizontal_wall = find_boundary_wall_at_corner(
        design_model,
        chosen_id,
        corner_point,
        geometry["top_axis"],
        coordinate_match_tolerance=coordinate_match_tolerance,
    )
    side_wall = find_boundary_wall_at_corner(
        design_model,
        chosen_id,
        corner_point,
        geometry["side_axis"],
        coordinate_match_tolerance=coordinate_match_tolerance,
    )
    if horizontal_wall is None or side_wall is None:
        raise ValueError(
            "corner boundary walls not found; run source review before corner repair."
        )

    horizontal_wall_id, horizontal_wall_payload = horizontal_wall
    side_wall_id, side_wall_payload = side_wall
    changed_walls: list[str] = []
    removed_walls: list[str] = []
    added_walls: list[str] = []
    changed_spaces: list[str] = []
    changed_openings: list[str] = []
    opening_offset_adjustments: dict[str, float] = {}

    horizontal_changed, horizontal_offset_adjustment = replace_wall_endpoint(
        horizontal_wall_payload,
        corner_point,
        geometry["top_endpoint"],
        tolerance=coordinate_match_tolerance,
    )
    if horizontal_changed:
        changed_walls.append(horizontal_wall_id)
        if horizontal_offset_adjustment:
            opening_offset_adjustments[horizontal_wall_id] = horizontal_offset_adjustment
    side_changed, side_offset_adjustment = replace_wall_endpoint(
        side_wall_payload,
        corner_point,
        geometry["side_endpoint"],
        tolerance=coordinate_match_tolerance,
    )
    if side_changed:
        changed_walls.append(side_wall_id)
        if side_offset_adjustment:
            opening_offset_adjustments[side_wall_id] = side_offset_adjustment

    for wall_id, wall in (
        (horizontal_wall_id, horizontal_wall_payload),
        (side_wall_id, side_wall_payload),
    ):
        if wall_length(wall.get("path", [])) <= min_wall_length:
            removed_walls.append(wall_id)
            design_model["walls"].pop(wall_id, None)

    vertical_wall_id = f"{chosen_id}_{corner}_notch_vertical"
    horizontal_return_wall_id = f"{chosen_id}_{corner}_notch_horizontal"
    reference_wall = horizontal_wall_payload or side_wall_payload
    design_model.setdefault("walls", {})[vertical_wall_id] = wall_payload_from_reference(
        vertical_wall_id,
        geometry["vertical_return"],
        reference_wall,
    )
    design_model["walls"][horizontal_return_wall_id] = wall_payload_from_reference(
        horizontal_return_wall_id,
        geometry["horizontal_return"],
        reference_wall,
    )
    added_walls.extend([vertical_wall_id, horizontal_return_wall_id])

    if target_space_id:
        space = design_model.get("spaces", {}).get(target_space_id)
        if not isinstance(space, dict):
            raise ValueError(f"target space not found: {target_space_id}")
        source = space.get("source", {})
        if not isinstance(source, dict) or source.get("import_id") != chosen_id:
            raise ValueError("target_space_id must belong to the selected import session.")
        space["footprint"] = notched_space_footprint(
            space,
            corner,
            horizontal_offset,
            vertical_offset,
        )
        space.pop("execution", None)
        changed_spaces.append(target_space_id)

    if changed_walls or added_walls or removed_walls or changed_spaces:
        for opening_id in imported_ids_in_model(design_model, chosen_id)["openings"]:
            opening = design_model.get("openings", {}).get(opening_id)
            if isinstance(opening, dict):
                offset_adjustment = opening_offset_adjustments.get(opening.get("host_wall"))
                if offset_adjustment and "offset" in opening:
                    opening["offset"] = max(0.0, float(opening["offset"]) - offset_adjustment)
                opening.pop("execution", None)
                changed_openings.append(opening_id)

    changed_model_ids = list(
        dict.fromkeys(
            [
                *changed_spaces,
                *changed_walls,
                *added_walls,
                *removed_walls,
                *changed_openings,
            ]
        )
    )
    active_changed_model_ids = [
        entity_id for entity_id in changed_model_ids if entity_id not in removed_walls
    ]

    generated_model = session.setdefault("generated_model", {})
    if isinstance(generated_model.get("wall_ids"), list):
        generated_model["wall_ids"] = [
            wall_id for wall_id in generated_model["wall_ids"] if wall_id not in removed_walls
        ]
        for wall_id in added_walls:
            if wall_id not in generated_model["wall_ids"]:
                generated_model["wall_ids"].append(wall_id)
    if isinstance(generated_model.get("changed_model_ids"), list):
        generated_model["changed_model_ids"] = [
            entity_id
            for entity_id in generated_model["changed_model_ids"]
            if entity_id not in removed_walls
        ]
        for entity_id in active_changed_model_ids:
            if entity_id not in generated_model["changed_model_ids"]:
                generated_model["changed_model_ids"].append(entity_id)

    action = {
        "created_at": utc_now(),
        "action": "repair_imported_corner_notch",
        "corner": corner,
        "horizontal_offset": horizontal_offset,
        "vertical_offset": vertical_offset,
        "coordinate_match_tolerance": coordinate_match_tolerance,
        "min_wall_length": min_wall_length,
        "target_space_id": target_space_id,
        "changed_walls": changed_walls,
        "added_walls": added_walls,
        "removed_walls": removed_walls,
        "changed_spaces": changed_spaces,
        "changed_openings": changed_openings,
        "opening_offset_adjustments": opening_offset_adjustments,
        "notes": notes,
    }

    add_import_quality_flag(
        design_model,
        chosen_id,
        "exterior_corner_notch_repaired",
        message="Imported exterior corner notch was restored from source-backed repair.",
    )
    add_import_quality_flag(
        design_model,
        chosen_id,
        "source_backed_boundary_step_added",
        severity="warning",
        message="A missing source-backed exterior boundary step was added to working truth.",
    )
    design_model["updated_at"] = utc_now()
    mark_execution_dirty(
        design_model,
        reason="import_corner_notch_repaired",
        source="repair_imported_corner_notch",
        details={"import_id": chosen_id, "changed_model_ids": changed_model_ids},
    )

    saved, save_errors = save_design_model(str(design_model_path), design_model)
    if not saved:
        raise ValueError("; ".join(save_errors))

    manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    manifest["status"] = "repaired"
    manifest["quality_flags"] = dedupe_quality_flags(
        [
            *manifest.get("quality_flags", []),
            "exterior_corner_notch_repaired",
            "source_backed_boundary_step_added",
        ]
    )
    append_processing_step(
        manifest,
        "repair_imported_corner_notch",
        details=action,
    )
    manifest.setdefault("repair_history", []).append(action)
    saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
    if not saved_manifest:
        raise ValueError("; ".join(manifest_errors))

    interpretation_path = import_session_path(root, chosen_id) / "extracted" / "interpretation.json"
    if interpretation_path.exists():
        try:
            interpretation = json.loads(interpretation_path.read_text(encoding="utf-8"))
            interpretation.setdefault("processing_notes", []).append(
                "Restored a missing exterior corner notch from source-backed repair."
            )
            interpretation.setdefault("repairs", []).append(action)
            interpretation_path.write_text(
                json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except json.JSONDecodeError:
            pass

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "status": "repaired",
        "corner": corner,
        "horizontal_offset": horizontal_offset,
        "vertical_offset": vertical_offset,
        "target_space_id": target_space_id,
        "changed_walls": changed_walls,
        "added_walls": added_walls,
        "removed_walls": removed_walls,
        "changed_spaces": changed_spaces,
        "changed_openings": changed_openings,
        "changed_model_ids": changed_model_ids,
        "active_changed_model_ids": active_changed_model_ids,
        "quality_flags": session.get("quality_flags", []),
    }


def review_imported_boundary_coverage(
    project_path: str | Path,
    import_id: str,
    *,
    min_gap_length: float = DEFAULT_MIN_BOUNDARY_GAP_LENGTH,
    max_opening_gap_length: float = DEFAULT_MAX_OPENING_GAP_LENGTH,
    infer_source_evidence_short_gaps: bool = True,
    max_source_evidence_gap_length: float = DEFAULT_MAX_SOURCE_EVIDENCE_SHORT_GAP_LENGTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    require_structural_endpoints: bool = True,
) -> dict[str, Any]:
    """Review whether imported space footprints are covered by explicit walls."""
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    session = design_model.get("import_sessions", {}).get(chosen_id)
    if not isinstance(session, dict):
        raise ValueError(f"import session not found in design_model.json: {chosen_id}")

    gaps = imported_boundary_coverage_gaps(
        design_model,
        chosen_id,
        min_gap_length=min_gap_length,
        max_opening_gap_length=max_opening_gap_length,
        infer_source_evidence_short_gaps=infer_source_evidence_short_gaps,
        max_source_evidence_gap_length=max_source_evidence_gap_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
        require_structural_endpoints=require_structural_endpoints,
    )
    recommended = [gap for gap in gaps if gap["repair_recommended"]]
    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "status": "gaps_found" if gaps else "covered",
        "gap_count": len(gaps),
        "recommended_repair_count": len(recommended),
        "min_gap_length": min_gap_length,
        "max_opening_gap_length": max_opening_gap_length,
        "infer_source_evidence_short_gaps": infer_source_evidence_short_gaps,
        "max_source_evidence_gap_length": max_source_evidence_gap_length,
        "coordinate_match_tolerance": coordinate_match_tolerance,
        "require_structural_endpoints": require_structural_endpoints,
        "gaps": gaps,
    }


def repair_imported_boundary_coverage(
    project_path: str | Path,
    import_id: str,
    *,
    min_gap_length: float = DEFAULT_MIN_BOUNDARY_GAP_LENGTH,
    max_opening_gap_length: float = DEFAULT_MAX_OPENING_GAP_LENGTH,
    infer_source_evidence_short_gaps: bool = True,
    max_source_evidence_gap_length: float = DEFAULT_MAX_SOURCE_EVIDENCE_SHORT_GAP_LENGTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    require_structural_endpoints: bool = True,
    max_repairs: int = 20,
    notes: str | None = None,
) -> dict[str, Any]:
    """Add source-backed walls for high-confidence imported boundary gaps."""
    if max_repairs <= 0:
        raise ValueError("max_repairs must be positive.")

    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    session = design_model.get("import_sessions", {}).get(chosen_id)
    if not isinstance(session, dict):
        raise ValueError(f"import session not found in design_model.json: {chosen_id}")

    initial_gaps = imported_boundary_coverage_gaps(
        design_model,
        chosen_id,
        min_gap_length=min_gap_length,
        max_opening_gap_length=max_opening_gap_length,
        infer_source_evidence_short_gaps=infer_source_evidence_short_gaps,
        max_source_evidence_gap_length=max_source_evidence_gap_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
        require_structural_endpoints=require_structural_endpoints,
    )
    repair_candidates = [gap for gap in initial_gaps if gap["repair_recommended"]]
    added_walls: list[str] = []
    unchanged_walls: list[str] = []
    repaired_gaps: list[dict[str, Any]] = []

    for gap in repair_candidates[:max_repairs]:
        wall_id, added = add_imported_boundary_wall(
            design_model,
            chosen_id,
            start_point=gap["start_point"],
            end_point=gap["end_point"],
            coordinate_match_tolerance=coordinate_match_tolerance,
        )
        if added:
            added_walls.append(wall_id)
            repaired_gaps.append({**gap, "wall_id": wall_id})
        else:
            unchanged_walls.append(wall_id)

    changed_model_ids = list(dict.fromkeys(added_walls))
    generated_model = session.setdefault("generated_model", {})
    if isinstance(generated_model.get("wall_ids"), list):
        for wall_id in added_walls:
            if wall_id not in generated_model["wall_ids"]:
                generated_model["wall_ids"].append(wall_id)
    if isinstance(generated_model.get("changed_model_ids"), list):
        for wall_id in added_walls:
            if wall_id not in generated_model["changed_model_ids"]:
                generated_model["changed_model_ids"].append(wall_id)

    if added_walls:
        add_import_quality_flag(
            design_model,
            chosen_id,
            "import_boundary_coverage_repaired",
            message="Imported space footprint gaps were repaired with explicit walls.",
        )
        add_import_quality_flag(
            design_model,
            chosen_id,
            "source_backed_boundary_wall_added",
            severity="warning",
            message="A missing source-backed boundary wall was added to working truth.",
        )
        design_model["updated_at"] = utc_now()
        mark_execution_dirty(
            design_model,
            reason="import_boundary_coverage_repaired",
            source="repair_imported_boundary_coverage",
            details={"import_id": chosen_id, "changed_model_ids": changed_model_ids},
        )

    remaining_gaps = imported_boundary_coverage_gaps(
        design_model,
        chosen_id,
        min_gap_length=min_gap_length,
        max_opening_gap_length=max_opening_gap_length,
        infer_source_evidence_short_gaps=infer_source_evidence_short_gaps,
        max_source_evidence_gap_length=max_source_evidence_gap_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
        require_structural_endpoints=require_structural_endpoints,
    )

    if added_walls:
        saved, save_errors = save_design_model(str(design_model_path), design_model)
        if not saved:
            raise ValueError("; ".join(save_errors))

    action = {
        "created_at": utc_now(),
        "action": "repair_imported_boundary_coverage",
        "min_gap_length": min_gap_length,
        "max_opening_gap_length": max_opening_gap_length,
        "infer_source_evidence_short_gaps": infer_source_evidence_short_gaps,
        "max_source_evidence_gap_length": max_source_evidence_gap_length,
        "coordinate_match_tolerance": coordinate_match_tolerance,
        "require_structural_endpoints": require_structural_endpoints,
        "max_repairs": max_repairs,
        "initial_gap_count": len(initial_gaps),
        "recommended_repair_count": len(repair_candidates),
        "added_walls": added_walls,
        "unchanged_walls": unchanged_walls,
        "remaining_gap_count": len(remaining_gaps),
        "repaired_gaps": repaired_gaps,
        "notes": notes,
    }

    manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    if added_walls:
        manifest["status"] = "repaired"
        manifest["quality_flags"] = dedupe_quality_flags(
            [
                *manifest.get("quality_flags", []),
                "import_boundary_coverage_repaired",
                "source_backed_boundary_wall_added",
            ]
        )
    append_processing_step(
        manifest,
        "repair_imported_boundary_coverage",
        details=action,
    )
    manifest.setdefault("repair_history", []).append(action)
    saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
    if not saved_manifest:
        raise ValueError("; ".join(manifest_errors))

    interpretation_path = import_session_path(root, chosen_id) / "extracted" / "interpretation.json"
    if interpretation_path.exists():
        try:
            interpretation = json.loads(interpretation_path.read_text(encoding="utf-8"))
            interpretation.setdefault("processing_notes", []).append(
                "Reviewed imported footprint boundary coverage and repaired high-confidence missing walls."
            )
            interpretation.setdefault("repairs", []).append(action)
            interpretation_path.write_text(
                json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except json.JSONDecodeError:
            pass

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "status": "repaired" if added_walls else "unchanged",
        "initial_gap_count": len(initial_gaps),
        "recommended_repair_count": len(repair_candidates),
        "added_walls": added_walls,
        "unchanged_walls": unchanged_walls,
        "changed_model_ids": changed_model_ids,
        "repaired_gaps": repaired_gaps,
        "remaining_gap_count": len(remaining_gaps),
        "remaining_gaps": remaining_gaps,
        "quality_flags": session.get("quality_flags", []),
    }


def review_imported_wall_space_consistency(
    project_path: str | Path,
    import_id: str,
    *,
    min_segment_length: float = DEFAULT_MIN_SHELL_OVERREACH_LENGTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
) -> dict[str, Any]:
    """Review imported walls for segments outside imported space footprints."""
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    session = design_model.get("import_sessions", {}).get(chosen_id)
    if not isinstance(session, dict):
        raise ValueError(f"import session not found in design_model.json: {chosen_id}")

    overreach_segments = imported_wall_space_overreach_segments(
        design_model,
        chosen_id,
        min_segment_length=min_segment_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
    )
    recommended = [
        segment for segment in overreach_segments if segment["repair_recommended"]
    ]
    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "status": "overreach_found" if overreach_segments else "consistent",
        "overreach_count": len(overreach_segments),
        "recommended_repair_count": len(recommended),
        "min_segment_length": min_segment_length,
        "coordinate_match_tolerance": coordinate_match_tolerance,
        "overreach_segments": overreach_segments,
    }


def repair_imported_shell_overreach(
    project_path: str | Path,
    import_id: str,
    *,
    min_segment_length: float = DEFAULT_MIN_SHELL_OVERREACH_LENGTH,
    coordinate_match_tolerance: float = DEFAULT_COORDINATE_MATCH_TOLERANCE,
    min_wall_length: float = DEFAULT_MIN_WALL_LENGTH,
    fill_resulting_boundary_gaps: bool = True,
    max_repairs: int = 20,
    notes: str | None = None,
) -> dict[str, Any]:
    """Trim or remove imported wall segments outside imported space footprints."""
    if min_segment_length <= 0:
        raise ValueError("min_segment_length must be positive.")
    if coordinate_match_tolerance <= 0:
        raise ValueError("coordinate_match_tolerance must be positive.")
    if min_wall_length < 0:
        raise ValueError("min_wall_length must be non-negative.")
    if max_repairs <= 0:
        raise ValueError("max_repairs must be positive.")

    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    session = design_model.get("import_sessions", {}).get(chosen_id)
    if not isinstance(session, dict):
        raise ValueError(f"import session not found in design_model.json: {chosen_id}")

    initial_overreach_segments = imported_wall_space_overreach_segments(
        design_model,
        chosen_id,
        min_segment_length=min_segment_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
    )
    repair_candidates = [
        segment
        for segment in initial_overreach_segments
        if segment["repair_recommended"]
    ][:max_repairs]

    remove_intervals_by_wall: dict[str, list[tuple[float, float]]] = {}
    for segment in repair_candidates:
        remove_intervals_by_wall.setdefault(segment["wall_id"], []).append(
            (float(segment["interval"][0]), float(segment["interval"][1]))
        )

    trimmed_walls: list[str] = []
    removed_walls: list[str] = []
    split_walls: list[str] = []
    added_walls: list[str] = []
    unchanged_walls: list[str] = []
    repaired_overreach_segments: list[dict[str, Any]] = []

    for wall_id, remove_intervals in remove_intervals_by_wall.items():
        wall = design_model.get("walls", {}).get(wall_id)
        if not isinstance(wall, dict):
            continue
        path = wall.get("path", [])
        kept_paths = split_wall_path_by_removing_intervals(
            path,
            remove_intervals,
            coordinate_match_tolerance=coordinate_match_tolerance,
            min_wall_length=min_wall_length,
        )
        if not kept_paths:
            design_model["walls"].pop(wall_id, None)
            removed_walls.append(wall_id)
        else:
            wall["path"] = kept_paths[0]
            wall.pop("execution", None)
            trimmed_walls.append(wall_id)
            for index, kept_path in enumerate(kept_paths[1:], start=1):
                split_wall_id = f"{wall_id}_kept_{index}"
                existing = design_model["walls"].get(split_wall_id)
                if isinstance(existing, dict):
                    if existing.get("path") == kept_path:
                        unchanged_walls.append(split_wall_id)
                        continue
                    raise ValueError(
                        f"wall_id already exists with different geometry: {split_wall_id}"
                    )
                design_model["walls"][split_wall_id] = wall_payload_from_reference(
                    split_wall_id,
                    kept_path,
                    wall,
                )
                split_walls.append(split_wall_id)
        for segment in repair_candidates:
            if segment["wall_id"] == wall_id:
                repaired_overreach_segments.append(segment)

    added_boundary_gaps: list[dict[str, Any]] = []
    if fill_resulting_boundary_gaps and (trimmed_walls or removed_walls or split_walls):
        boundary_gaps = imported_boundary_coverage_gaps(
            design_model,
            chosen_id,
            min_gap_length=min_segment_length,
            coordinate_match_tolerance=coordinate_match_tolerance,
            require_structural_endpoints=True,
        )
        for gap in [gap for gap in boundary_gaps if gap["repair_recommended"]][
            :max_repairs
        ]:
            wall_id, added = add_imported_boundary_wall(
                design_model,
                chosen_id,
                start_point=gap["start_point"],
                end_point=gap["end_point"],
                coordinate_match_tolerance=coordinate_match_tolerance,
            )
            if added:
                added_walls.append(wall_id)
                added_boundary_gaps.append({**gap, "wall_id": wall_id})
            else:
                unchanged_walls.append(wall_id)

    changed_openings: list[str] = []
    removed_openings: list[str] = []
    if trimmed_walls or removed_walls or split_walls or added_walls:
        for opening_id in imported_ids_in_model(design_model, chosen_id)["openings"]:
            opening = design_model.get("openings", {}).get(opening_id)
            if not isinstance(opening, dict):
                continue
            if opening.get("host_wall") in removed_walls:
                design_model["openings"].pop(opening_id, None)
                removed_openings.append(opening_id)
                continue
            opening.pop("execution", None)
            changed_openings.append(opening_id)

    changed_model_ids = list(
        dict.fromkeys(
            [
                *trimmed_walls,
                *removed_walls,
                *split_walls,
                *added_walls,
                *changed_openings,
                *removed_openings,
            ]
        )
    )
    active_changed_model_ids = [
        entity_id
        for entity_id in changed_model_ids
        if entity_id not in removed_walls and entity_id not in removed_openings
    ]
    sync_generated_wall_ids(
        session,
        added_walls=[*split_walls, *added_walls],
        removed_walls=removed_walls,
        changed_model_ids=active_changed_model_ids,
    )
    generated_model = session.setdefault("generated_model", {})
    if removed_openings and isinstance(generated_model.get("opening_ids"), list):
        generated_model["opening_ids"] = [
            opening_id
            for opening_id in generated_model["opening_ids"]
            if opening_id not in removed_openings
        ]
    if removed_openings and isinstance(generated_model.get("changed_model_ids"), list):
        generated_model["changed_model_ids"] = [
            entity_id
            for entity_id in generated_model["changed_model_ids"]
            if entity_id not in removed_openings
        ]

    changed = bool(changed_model_ids)
    if changed:
        add_import_quality_flag(
            design_model,
            chosen_id,
            "import_shell_overreach_repaired",
            message="Imported wall segments outside space footprints were trimmed or removed.",
        )
        add_import_quality_flag(
            design_model,
            chosen_id,
            "source_backed_shell_trimmed",
            severity="warning",
            message="Source-backed imported shell geometry was trimmed to match space footprints.",
        )
        design_model["updated_at"] = utc_now()
        mark_execution_dirty(
            design_model,
            reason="import_shell_overreach_repaired",
            source="repair_imported_shell_overreach",
            details={"import_id": chosen_id, "changed_model_ids": changed_model_ids},
        )

    remaining_overreach_segments = imported_wall_space_overreach_segments(
        design_model,
        chosen_id,
        min_segment_length=min_segment_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
    )
    remaining_boundary_gaps = imported_boundary_coverage_gaps(
        design_model,
        chosen_id,
        min_gap_length=min_segment_length,
        coordinate_match_tolerance=coordinate_match_tolerance,
        require_structural_endpoints=True,
    )

    if changed:
        saved, save_errors = save_design_model(str(design_model_path), design_model)
        if not saved:
            raise ValueError("; ".join(save_errors))

    action = {
        "created_at": utc_now(),
        "action": "repair_imported_shell_overreach",
        "min_segment_length": min_segment_length,
        "coordinate_match_tolerance": coordinate_match_tolerance,
        "min_wall_length": min_wall_length,
        "fill_resulting_boundary_gaps": fill_resulting_boundary_gaps,
        "max_repairs": max_repairs,
        "initial_overreach_count": len(initial_overreach_segments),
        "recommended_repair_count": len(repair_candidates),
        "trimmed_walls": trimmed_walls,
        "removed_walls": removed_walls,
        "split_walls": split_walls,
        "added_walls": added_walls,
        "unchanged_walls": unchanged_walls,
        "changed_openings": changed_openings,
        "removed_openings": removed_openings,
        "repaired_overreach_segments": repaired_overreach_segments,
        "added_boundary_gaps": added_boundary_gaps,
        "remaining_overreach_count": len(remaining_overreach_segments),
        "remaining_boundary_gap_count": len(remaining_boundary_gaps),
        "notes": notes,
    }

    manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    if changed:
        manifest["status"] = "repaired"
        manifest["quality_flags"] = dedupe_quality_flags(
            [
                *manifest.get("quality_flags", []),
                "import_shell_overreach_repaired",
                "source_backed_shell_trimmed",
            ]
        )
    append_processing_step(
        manifest,
        "repair_imported_shell_overreach",
        details=action,
    )
    manifest.setdefault("repair_history", []).append(action)
    saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
    if not saved_manifest:
        raise ValueError("; ".join(manifest_errors))

    interpretation_path = import_session_path(root, chosen_id) / "extracted" / "interpretation.json"
    if interpretation_path.exists():
        try:
            interpretation = json.loads(interpretation_path.read_text(encoding="utf-8"))
            interpretation.setdefault("processing_notes", []).append(
                "Reviewed wall-space consistency and repaired source-backed shell overreach."
            )
            interpretation.setdefault("repairs", []).append(action)
            interpretation_path.write_text(
                json.dumps(interpretation, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except json.JSONDecodeError:
            pass

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "status": "repaired" if changed else "unchanged",
        "initial_overreach_count": len(initial_overreach_segments),
        "recommended_repair_count": len(repair_candidates),
        "trimmed_walls": trimmed_walls,
        "removed_walls": removed_walls,
        "split_walls": split_walls,
        "added_walls": added_walls,
        "unchanged_walls": unchanged_walls,
        "changed_openings": changed_openings,
        "removed_openings": removed_openings,
        "changed_model_ids": changed_model_ids,
        "active_changed_model_ids": active_changed_model_ids,
        "repaired_overreach_segments": repaired_overreach_segments,
        "added_boundary_gaps": added_boundary_gaps,
        "remaining_overreach_count": len(remaining_overreach_segments),
        "remaining_overreach_segments": remaining_overreach_segments,
        "remaining_boundary_gap_count": len(remaining_boundary_gaps),
        "remaining_boundary_gaps": remaining_boundary_gaps,
        "quality_flags": session.get("quality_flags", []),
    }


def rescale_imported_model(
    project_path: str | Path,
    import_id: str,
    *,
    scale_factor: float | None = None,
    target_width: float | None = None,
    target_depth: float | None = None,
) -> dict[str, Any]:
    """Rescale imported plan geometry in working truth."""
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    session = design_model.get("import_sessions", {}).get(chosen_id)
    if not isinstance(session, dict):
        raise ValueError(f"import session not found in design_model.json: {chosen_id}")

    scale = session.get("scale", {})
    current_width = float(scale.get("width") or DEFAULT_IMPORTED_WIDTH)
    current_depth = float(scale.get("depth") or DEFAULT_IMPORTED_DEPTH)
    if scale_factor is not None:
        if scale_factor <= 0:
            raise ValueError("scale_factor must be positive.")
        scale_x = scale_y = float(scale_factor)
        new_width = current_width * scale_x
        new_depth = current_depth * scale_y
        scale_source = "scale_factor"
    else:
        if target_width is None and target_depth is None:
            raise ValueError("scale_factor, target_width, or target_depth is required.")
        if target_width is not None and target_width <= 0:
            raise ValueError("target_width must be positive.")
        if target_depth is not None and target_depth <= 0:
            raise ValueError("target_depth must be positive.")
        scale_x = float(target_width / current_width) if target_width else 1.0
        scale_y = float(target_depth / current_depth) if target_depth else scale_x
        new_width = current_width * scale_x
        new_depth = current_depth * scale_y
        scale_source = "target_dimensions"

    changed = imported_ids_in_model(design_model, chosen_id)
    for space_id in changed["spaces"]:
        space = design_model["spaces"][space_id]
        bounds = space["bounds"]
        bounds["min"] = scale_point_xy(bounds["min"], scale_x, scale_y)
        bounds["max"] = scale_point_xy(bounds["max"], scale_x, scale_y)
        if "center" in space:
            space["center"] = scale_point_xy(space["center"], scale_x, scale_y)
        if "footprint" in space:
            space["footprint"] = [
                scale_point_xy(point, scale_x, scale_y)
                for point in space["footprint"]
            ]
    for wall_id in changed["walls"]:
        wall = design_model["walls"][wall_id]
        wall["path"] = [scale_point_xy(point, scale_x, scale_y) for point in wall["path"]]
        wall["thickness"] = float(wall["thickness"]) * ((scale_x + scale_y) / 2)
    for opening_id in changed["openings"]:
        opening = design_model["openings"][opening_id]
        host_wall = design_model["walls"].get(opening.get("host_wall"), {})
        path = host_wall.get("path", [])
        is_y_axis = (
            len(path) >= 2
            and abs(float(path[0][0]) - float(path[1][0]))
            < abs(float(path[0][1]) - float(path[1][1]))
        )
        axis_scale = scale_y if is_y_axis else scale_x
        opening["offset"] = float(opening["offset"]) * axis_scale
        opening["width"] = float(opening["width"]) * axis_scale

    history = list(scale.get("history", []))
    history.append(
        {
            "created_at": utc_now(),
            "source": scale_source,
            "previous_width": current_width,
            "previous_depth": current_depth,
            "width": new_width,
            "depth": new_depth,
            "scale_x": scale_x,
            "scale_y": scale_y,
        }
    )
    session["scale"] = {
        "units": "mm",
        "source": scale_source,
        "confidence": 1.0,
        "width": new_width,
        "depth": new_depth,
        "history": history,
    }
    session.setdefault("quality_flags", [])
    session["quality_flags"] = [
        flag for flag in session["quality_flags"] if flag != "scale_estimated"
    ]
    design_model["updated_at"] = utc_now()
    mark_execution_dirty(
        design_model,
        reason="import_rescaled",
        source="rescale_imported_model",
        details={"import_id": chosen_id, "scale_x": scale_x, "scale_y": scale_y},
    )
    saved, save_errors = save_design_model(str(design_model_path), design_model)
    if not saved:
        raise ValueError("; ".join(save_errors))

    manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    manifest["status"] = "repaired"
    manifest["scale"] = session["scale"]
    manifest["quality_flags"] = [
        flag for flag in manifest.get("quality_flags", []) if flag != "scale_estimated"
    ]
    append_processing_step(
        manifest,
        "rescale_imported_model",
        details={"scale_x": scale_x, "scale_y": scale_y},
    )
    manifest.setdefault("repair_history", []).append(
        {
            "created_at": utc_now(),
            "action": "rescale",
            "scale": session["scale"],
        }
    )
    saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
    if not saved_manifest:
        raise ValueError("; ".join(manifest_errors))

    return {
        "project_path": str(root),
        "design_model_path": str(design_model_path),
        "import_id": chosen_id,
        "status": "rescaled",
        "scale_x": scale_x,
        "scale_y": scale_y,
        "scale": session["scale"],
        "changed_model_ids": changed,
    }


def review_model_against_import_source(
    project_path: str | Path,
    import_id: str,
    *,
    target_id: str | None = None,
) -> dict[str, Any]:
    """Return source evidence and model entities for a later repair."""
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    design_model_path = find_design_model_path(root)
    design_model, errors = load_design_model(str(design_model_path))
    if errors or design_model is None:
        raise ValueError("; ".join(errors))
    ids = imported_ids_in_model(design_model, chosen_id)
    matched: dict[str, Any] = {}
    if target_id:
        for collection_name, entity_ids in ids.items():
            if target_id in entity_ids:
                matched[collection_name] = {
                    target_id: design_model[collection_name][target_id]
                }
    else:
        matched = {
            collection_name: {
                entity_id: design_model.get(collection_name, {}).get(entity_id)
                for entity_id in entity_ids
            }
            for collection_name, entity_ids in ids.items()
        }

    return {
        "project_path": str(root),
        "import_id": chosen_id,
        "manifest_path": str(manifest_file),
        "source": manifest.get("source", {}),
        "scale": manifest.get("scale", {}),
        "quality_flags": manifest.get("quality_flags", []),
        "target_id": target_id,
        "matched_model_entities": matched,
        "evidence": {
            "source_file": manifest.get("source", {}).get("stored_path"),
            "interpretation_file": str(
                Path("imports")
                / chosen_id
                / "extracted"
                / "interpretation.json"
            ),
        },
    }


def repair_imported_region(
    project_path: str | Path,
    import_id: str,
    *,
    target_width: float | None = None,
    target_depth: float | None = None,
    wall_thickness: float | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Apply a simple source-backed repair to imported working truth."""
    root = Path(project_path).expanduser().resolve()
    chosen_id = import_safe_id(import_id)
    actions: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None

    if target_width is not None or target_depth is not None:
        result = rescale_imported_model(
            root,
            chosen_id,
            target_width=target_width,
            target_depth=target_depth,
        )
        actions.append({"action": "rescale", "result": result})

    if wall_thickness is not None:
        if wall_thickness <= 0:
            raise ValueError("wall_thickness must be positive.")
        design_model_path = find_design_model_path(root)
        design_model, errors = load_design_model(str(design_model_path))
        if errors or design_model is None:
            raise ValueError("; ".join(errors))
        changed = imported_ids_in_model(design_model, chosen_id)
        for wall_id in changed["walls"]:
            design_model["walls"][wall_id]["thickness"] = float(wall_thickness)
        mark_execution_dirty(
            design_model,
            reason="import_wall_thickness_repaired",
            source="repair_imported_region",
            details={"import_id": chosen_id, "wall_thickness": wall_thickness},
        )
        saved, save_errors = save_design_model(str(design_model_path), design_model)
        if not saved:
            raise ValueError("; ".join(save_errors))
        actions.append(
            {
                "action": "update_wall_thickness",
                "wall_ids": changed["walls"],
                "wall_thickness": wall_thickness,
            }
        )

    manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    manifest["status"] = "repaired"
    manifest.setdefault("repair_history", []).append(
        {
            "created_at": utc_now(),
            "action": "repair_imported_region",
            "notes": notes,
            "actions": actions,
        }
    )
    append_processing_step(
        manifest,
        "repair_imported_region",
        details={"notes": notes, "action_count": len(actions)},
    )
    saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
    if not saved_manifest:
        raise ValueError("; ".join(manifest_errors))

    review = review_model_against_import_source(root, chosen_id)
    return {
        "project_path": str(root),
        "import_id": chosen_id,
        "status": "repaired" if actions else "review_recorded",
        "actions": actions,
        "notes": notes,
        "review": review,
        "rescale_result": result,
    }
