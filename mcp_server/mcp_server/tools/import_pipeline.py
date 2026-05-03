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
