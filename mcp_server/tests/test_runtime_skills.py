"""Tests for runtime skill installation."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from mcp_server.cli import main
from mcp_server.runtime_skills import (
    RUNTIME_SKILL_MANIFEST,
    install_runtime_skills,
    packaged_runtime_skills_source,
    runtime_skill_status,
    skill_target_paths,
)


def make_runtime_skill_source(tmp_path):
    source = tmp_path / "skills"
    skill_dir = source / "bathroom_planning"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Bathroom Planning\n", encoding="utf-8")
    style_dir = source / "styles"
    style_dir.mkdir()
    (style_dir / "SKILL.md").write_text("# Styles\n", encoding="utf-8")
    return source


def test_skill_target_paths_are_project_local(tmp_path):
    targets = skill_target_paths(tmp_path / "design")

    assert targets["codex"] == tmp_path / "design" / ".agents" / "skills"
    assert targets["claude"] == tmp_path / "design" / ".claude" / "skills"


def test_install_runtime_skills_copies_codex_and_claude_targets(tmp_path):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"

    result = install_runtime_skills(project_path, source_dir=source)

    assert result["installed"] is True
    assert (project_path / ".agents" / "skills" / "bathroom_planning" / "SKILL.md").exists()
    assert (project_path / ".claude" / "skills" / "bathroom_planning" / "SKILL.md").exists()
    assert (project_path / ".agents" / "skills" / "styles" / "SKILL.md").exists()
    assert result["installs"]["codex"]["file_count"] == 2
    assert result["installs"]["claude"]["file_count"] == 2
    manifest = json.loads(
        (
            project_path / ".agents" / "skills" / RUNTIME_SKILL_MANIFEST
        ).read_text(encoding="utf-8")
    )
    assert set(manifest["hashes"]) == {
        "bathroom_planning/SKILL.md",
        "styles/SKILL.md",
    }


def test_install_runtime_skills_dry_run_does_not_copy(tmp_path):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"

    result = install_runtime_skills(project_path, source_dir=source, dry_run=True)

    assert result["installed"] is False
    assert result["dry_run"] is True
    assert not (project_path / ".agents").exists()
    assert result["installs"]["codex"]["installed_files"]


def test_install_runtime_skills_requires_force_for_local_changes(tmp_path):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"
    install_runtime_skills(project_path, source_dir=source)
    target_file = project_path / ".agents" / "skills" / "bathroom_planning" / "SKILL.md"
    target_file.write_text("# Local Edit\n", encoding="utf-8")

    try:
        install_runtime_skills(project_path, source_dir=source)
    except FileExistsError as error:
        assert "--force" in str(error)
    else:
        raise AssertionError("Expected FileExistsError")


def test_install_runtime_skills_force_replaces_local_changes(tmp_path):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"
    install_runtime_skills(project_path, source_dir=source)
    target_file = project_path / ".agents" / "skills" / "bathroom_planning" / "SKILL.md"
    target_file.write_text("# Local Edit\n", encoding="utf-8")

    result = install_runtime_skills(project_path, source_dir=source, force=True)

    assert result["installed"] is True
    assert target_file.read_text(encoding="utf-8") == "# Bathroom Planning\n"


def test_install_runtime_skills_force_removes_previously_installed_stale_files(tmp_path):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"
    install_runtime_skills(project_path, source_dir=source)
    stale_source = source / "legacy"
    stale_source.mkdir()
    (stale_source / "SKILL.md").write_text("# Legacy\n", encoding="utf-8")
    install_runtime_skills(project_path, source_dir=source, force=True)
    stale_target = project_path / ".agents" / "skills" / "legacy" / "SKILL.md"
    assert stale_target.exists()

    (stale_source / "SKILL.md").unlink()
    stale_source.rmdir()
    result = install_runtime_skills(project_path, source_dir=source, force=True)

    assert "legacy/SKILL.md" in result["installs"]["codex"]["stale_files"]
    assert not stale_target.exists()
    manifest = project_path / ".agents" / "skills" / RUNTIME_SKILL_MANIFEST
    assert manifest.exists()


def test_runtime_skill_status_reports_clean_install(tmp_path):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"
    install_runtime_skills(project_path, source_dir=source)

    status = runtime_skill_status(project_path, source_dir=source)

    assert status["ok"] is True
    assert status["checks"]["codex"]["matching_count"] == 2
    assert status["checks"]["claude"]["matching_count"] == 2
    assert status["checks"]["codex"]["modified_files"] == []


def test_runtime_skill_status_detects_modified_and_missing_files(tmp_path):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"
    install_runtime_skills(project_path, source_dir=source)
    codex_skill = project_path / ".agents" / "skills" / "bathroom_planning" / "SKILL.md"
    claude_skill = project_path / ".claude" / "skills" / "styles" / "SKILL.md"
    codex_skill.write_text("# Local Edit\n", encoding="utf-8")
    claude_skill.unlink()

    status = runtime_skill_status(project_path, source_dir=source)

    assert status["ok"] is False
    assert status["checks"]["codex"]["modified_files"] == [
        "bathroom_planning/SKILL.md"
    ]
    assert status["checks"]["claude"]["missing_files"] == ["styles/SKILL.md"]


def test_cli_install_skills_outputs_json(tmp_path, capsys):
    source = make_runtime_skill_source(tmp_path)
    project_path = tmp_path / "design"

    exit_code = main(
        [
            "install-skills",
            str(project_path),
            "--source-dir",
            str(source),
        ]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    assert data["installed"] is True
    assert (project_path / ".agents" / "skills" / "bathroom_planning" / "SKILL.md").exists()


def test_packaged_runtime_skills_source_points_to_installed_runtime():
    source = packaged_runtime_skills_source()

    assert source.name == "runtime_skills"
    assert source.parent.name == "packaged"


def test_product_runtime_skills_are_skill_directories():
    skills_dir = Path(__file__).resolve().parents[2] / "skills"
    top_level_markdown = sorted(path.name for path in skills_dir.glob("*.md"))
    skill_dirs = sorted(path for path in skills_dir.iterdir() if path.is_dir())

    assert top_level_markdown == []
    assert skill_dirs
    assert all((path / "SKILL.md").exists() for path in skill_dirs)


def test_wheel_contains_packaged_runtime_skills(tmp_path):
    if shutil.which("uv") is None:
        return

    project_root = Path(__file__).resolve().parents[1]
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [
            "uv",
            "build",
            "--wheel",
            "--out-dir",
            str(dist_dir),
            str(project_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(dist_dir.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    assert "mcp_server/packaged/runtime_skills/bathroom_planning/SKILL.md" in names
    assert "mcp_server/packaged/runtime_skills/designer_workflow/SKILL.md" in names
    assert "mcp_server/packaged/runtime_skills/styles/SKILL.md" in names
