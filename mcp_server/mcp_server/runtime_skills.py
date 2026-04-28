"""Runtime skill installation helpers for designer projects."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


RUNTIME_SKILL_TARGETS = {
    "codex": Path(".agents") / "skills",
    "claude": Path(".claude") / "skills",
}
RUNTIME_SKILL_MANIFEST = ".sketchup-agent-runtime-skills.json"


def repo_root_from_package() -> Path:
    """Return the source checkout root when running from this repository."""
    return Path(__file__).resolve().parents[2]


def packaged_runtime_skills_source() -> Path:
    """Return runtime skills bundled inside an installed package."""
    return Path(__file__).resolve().parent / "packaged" / "runtime_skills"


def default_runtime_skills_source() -> Path:
    """Return the source runtime skills directory."""
    repo_source = repo_root_from_package() / "skills"
    if repo_source.exists():
        return repo_source
    return packaged_runtime_skills_source()


def skill_target_paths(project_path: str | Path, target: str = "all") -> dict[str, Path]:
    """Return project-local runtime skill target directories."""
    root = Path(project_path).expanduser().resolve()
    if target == "all":
        return {
            name: root / relative_path
            for name, relative_path in RUNTIME_SKILL_TARGETS.items()
        }
    if target not in RUNTIME_SKILL_TARGETS:
        supported = ", ".join(["all", *RUNTIME_SKILL_TARGETS.keys()])
        raise ValueError(f"Unsupported skill target '{target}'. Use one of: {supported}.")
    return {target: root / RUNTIME_SKILL_TARGETS[target]}


def skill_source_files(source: Path) -> dict[str, Path]:
    """Return runtime skill source files keyed by POSIX relative path."""
    files = [path for path in source.rglob("*") if path.is_file()]
    return {
        path.relative_to(source).as_posix(): path
        for path in sorted(files, key=lambda item: item.relative_to(source).as_posix())
    }


def file_sha256(path: Path) -> str:
    """Return a sha256 hash for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_runtime_skill_manifest(target: Path) -> dict[str, Any]:
    """Read an installed runtime skill manifest, returning an empty shape on error."""
    manifest_path = target / RUNTIME_SKILL_MANIFEST
    if not manifest_path.exists():
        return {"files": [], "hashes": {}}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"files": [], "hashes": {}, "manifest_error": "Invalid JSON"}
    if not isinstance(manifest, dict):
        return {"files": [], "hashes": {}, "manifest_error": "Manifest is not an object"}
    manifest.setdefault("files", [])
    manifest.setdefault("hashes", {})
    return manifest


def copy_skill_tree(
    source: Path,
    target: Path,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy runtime skill files while protecting local edits by default."""
    if not source.exists():
        raise FileNotFoundError(f"Runtime skills source not found: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"Runtime skills source is not a directory: {source}")

    source_files = skill_source_files(source)
    relative_files = sorted(source_files.keys())
    manifest_path = target / RUNTIME_SKILL_MANIFEST
    previous_manifest = read_runtime_skill_manifest(target)
    previous_files = [
        str(path)
        for path in previous_manifest.get("files", [])
        if isinstance(path, str)
    ]
    stale_files = sorted(set(previous_files) - set(relative_files))
    conflicts: list[str] = []
    installed_files: list[str] = []
    skipped_files: list[str] = []

    for relative_file, source_file in source_files.items():
        target_file = target / relative_file
        if target_file.exists() and target_file.read_bytes() != source_file.read_bytes():
            if not force:
                conflicts.append(relative_file)
                continue
        if dry_run:
            if target_file.exists() and target_file.read_bytes() == source_file.read_bytes():
                skipped_files.append(relative_file)
            else:
                installed_files.append(relative_file)
            continue

        target_file.parent.mkdir(parents=True, exist_ok=True)
        if target_file.exists() and target_file.read_bytes() == source_file.read_bytes():
            skipped_files.append(relative_file)
            continue
        shutil.copy2(source_file, target_file)
        installed_files.append(relative_file)

    if conflicts:
        raise FileExistsError(
            "Runtime skill target has local changes. Use --force to replace: "
            + ", ".join(conflicts)
        )

    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        if force:
            for stale_file in stale_files:
                stale_path = target / stale_file
                if stale_path.exists() and stale_path.is_file():
                    stale_path.unlink()
        manifest_path.write_text(
            json.dumps(
                {
                    "source": str(source),
                    "files": relative_files,
                    "hashes": {
                        relative_path: file_sha256(source_file)
                        for relative_path, source_file in source_files.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return {
        "target": str(target),
        "file_count": len(source_files),
        "installed_files": installed_files,
        "skipped_files": skipped_files,
        "stale_files": stale_files,
        "dry_run": dry_run,
    }


def runtime_skill_status(
    project_path: str | Path,
    target: str = "all",
    source_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compare installed project-local runtime skills with the current source."""
    source = (
        Path(source_dir).expanduser().resolve()
        if source_dir
        else default_runtime_skills_source()
    )
    if not source.exists():
        raise FileNotFoundError(f"Runtime skills source not found: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"Runtime skills source is not a directory: {source}")

    source_files = skill_source_files(source)
    expected_files = sorted(source_files.keys())
    targets = skill_target_paths(project_path, target=target)
    checks: dict[str, Any] = {}

    for target_name, target_path in targets.items():
        manifest = read_runtime_skill_manifest(target_path)
        previous_files = {
            str(path)
            for path in manifest.get("files", [])
            if isinstance(path, str)
        }
        missing_files: list[str] = []
        modified_files: list[str] = []
        matching_files: list[str] = []

        for relative_path, source_file in source_files.items():
            installed_file = target_path / relative_path
            if not installed_file.exists():
                missing_files.append(relative_path)
                continue
            if installed_file.read_bytes() != source_file.read_bytes():
                modified_files.append(relative_path)
                continue
            matching_files.append(relative_path)

        stale_files = sorted(previous_files - set(expected_files))
        manifest_error = manifest.get("manifest_error")
        ok = (
            target_path.is_dir()
            and not missing_files
            and not modified_files
            and not stale_files
            and manifest_error is None
        )
        checks[target_name] = {
            "ok": ok,
            "target": str(target_path),
            "manifest": str(target_path / RUNTIME_SKILL_MANIFEST),
            "manifest_error": manifest_error,
            "expected_count": len(expected_files),
            "matching_count": len(matching_files),
            "missing_files": missing_files,
            "modified_files": modified_files,
            "stale_files": stale_files,
        }

    return {
        "project_path": str(Path(project_path).expanduser().resolve()),
        "source": str(source),
        "target": target,
        "ok": all(item["ok"] for item in checks.values()),
        "checks": checks,
    }


def install_runtime_skills(
    project_path: str | Path,
    target: str = "all",
    source_dir: str | Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Install designer runtime skills into project-local agent skill directories."""
    source = (
        Path(source_dir).expanduser().resolve()
        if source_dir
        else default_runtime_skills_source()
    )
    targets = skill_target_paths(project_path, target=target)
    installs = {
        name: copy_skill_tree(source, target_path, force=force, dry_run=dry_run)
        for name, target_path in targets.items()
    }

    return {
        "project_path": str(Path(project_path).expanduser().resolve()),
        "source": str(source),
        "target": target,
        "installed": not dry_run,
        "force": force,
        "dry_run": dry_run,
        "installs": installs,
    }
