"""Runtime skill installation helpers for designer projects."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


RUNTIME_SKILL_TARGETS = {
    "codex": Path(".agents") / "skills",
    "claude": Path(".claude") / "skills",
}


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

    files = [path for path in source.rglob("*") if path.is_file()]
    conflicts: list[str] = []
    installed_files: list[str] = []
    skipped_files: list[str] = []

    for source_file in files:
        relative_path = source_file.relative_to(source)
        target_file = target / relative_path
        if target_file.exists() and target_file.read_bytes() != source_file.read_bytes():
            if not force:
                conflicts.append(str(relative_path))
                continue
        if dry_run:
            if target_file.exists() and target_file.read_bytes() == source_file.read_bytes():
                skipped_files.append(str(relative_path))
            else:
                installed_files.append(str(relative_path))
            continue

        target_file.parent.mkdir(parents=True, exist_ok=True)
        if target_file.exists() and target_file.read_bytes() == source_file.read_bytes():
            skipped_files.append(str(relative_path))
            continue
        shutil.copy2(source_file, target_file)
        installed_files.append(str(relative_path))

    if conflicts:
        raise FileExistsError(
            "Runtime skill target has local changes. Use --force to replace: "
            + ", ".join(conflicts)
        )

    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)

    return {
        "target": str(target),
        "file_count": len(files),
        "installed_files": installed_files,
        "skipped_files": skipped_files,
        "dry_run": dry_run,
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
