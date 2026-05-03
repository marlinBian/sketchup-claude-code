"""Autonomous-first source import into editable project truth."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
VALID_CORNER_NOTCHES = {"top_left", "top_right", "bottom_left", "bottom_right"}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"}
CAD_EXTENSIONS = {".dwg", ".dxf"}


def utc_now() -> str:
    """Return an ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
            "unknown": 0.42,
        }.get(source_type, 0.42)
    return {
        "dwg": 0.52,
        "dxf": 0.52,
        "pdf": 0.45,
        "image": 0.38,
        "sketchup": 0.4,
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
    if source_type in {"pdf", "image"}:
        flags.append("raster_or_document_interpretation")
    if source_type in {"dwg", "dxf"}:
        flags.append("cad_layers_not_semantically_verified")
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
            "representation": "placeholder",
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
            "representation": "placeholder",
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
    design_model.setdefault("metadata", {})
    design_model["metadata"]["execution_sync"] = {
        "status": "dirty",
        "reason": reason,
        "source": source,
        "updated_at": utc_now(),
        "details": details,
    }


def import_floorplan_to_model(
    project_path: str | Path,
    *,
    source_path: str | Path | None = None,
    import_id: str | None = None,
    label: str | None = None,
    width: float | None = None,
    depth: float | None = None,
    wall_height: float = DEFAULT_WALL_HEIGHT,
    wall_thickness: float = DEFAULT_WALL_THICKNESS,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate editable working truth from an imported source file."""
    root = Path(project_path).expanduser().resolve()
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
    elif import_id is not None:
        chosen_id = import_safe_id(import_id)
        manifest, manifest_file = load_project_import_manifest(root, chosen_id)
    else:
        raise ValueError("source_path or import_id is required.")

    if width is not None and width <= 0:
        raise ValueError("width must be positive when provided.")
    if depth is not None and depth <= 0:
        raise ValueError("depth must be positive when provided.")
    if wall_height <= 0 or wall_thickness <= 0:
        raise ValueError("wall_height and wall_thickness must be positive.")

    source_type = str(manifest["source"].get("source_type", "unknown"))
    has_explicit_dimensions = width is not None and depth is not None
    model_width = float(width if width is not None else DEFAULT_IMPORTED_WIDTH)
    model_depth = float(depth if depth is not None else DEFAULT_IMPORTED_DEPTH)
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

    design_model_path = find_design_model_path(root)
    design_model, model_errors = load_design_model(str(design_model_path))
    if model_errors or design_model is None:
        raise ValueError("; ".join(model_errors))

    removed = remove_previous_import_entities(design_model, chosen_id)
    design_model.setdefault("spaces", {})[ids["space_id"]] = space_payload(
        chosen_id,
        width=model_width,
        depth=model_depth,
        wall_height=wall_height,
        confidence=confidence,
        assumptions=assumptions,
    )
    design_model.setdefault("walls", {}).update(
        wall_payloads(
            chosen_id,
            width=model_width,
            depth=model_depth,
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            confidence=confidence,
            assumptions=assumptions,
        )
    )
    design_model.setdefault("openings", {}).update(
        opening_payloads(
            chosen_id,
            width=model_width,
            depth=model_depth,
            confidence=confidence,
            assumptions=assumptions,
        )
    )
    design_model.setdefault("import_sessions", {})[chosen_id] = {
        "source_file": manifest["source"]["stored_path"],
        "source_type": source_type,
        "status": "imported",
        "manifest_path": project_relative_path(root, manifest_file),
        "scale": {
            "units": "mm",
            "source": "user_dimensions" if has_explicit_dimensions else "estimated",
            "confidence": 1.0 if has_explicit_dimensions else 0.35,
            "width": model_width,
            "depth": model_depth,
        },
        "quality_flags": flags,
        "generated_model": generated_model,
    }
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
        details={"import_id": chosen_id, "changed_model_ids": generated_model["changed_model_ids"]},
    )

    saved, save_errors = save_design_model(str(design_model_path), design_model)
    if not saved:
        raise ValueError("; ".join(save_errors))

    interpretation = {
        "version": "1.0",
        "import_id": chosen_id,
        "created_at": utc_now(),
        "autonomous_first": True,
        "assumptions": assumptions,
        "quality_flags": flags,
        "generated_model": generated_model,
    }
    extracted_path = import_session_path(root, chosen_id) / "extracted" / "interpretation.json"
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
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
            "interpretation_path": project_relative_path(root, extracted_path),
        },
    )
    saved_manifest, manifest_errors = save_import_manifest(manifest_file, manifest)
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
        "summary": {
            "space_count": 1,
            "wall_count": len(ids["wall_ids"]),
            "opening_count": len(ids["opening_ids"]),
            "scale_source": design_model["import_sessions"][chosen_id]["scale"]["source"],
            "confidence": confidence,
        },
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
