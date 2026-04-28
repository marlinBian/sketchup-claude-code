"""Tests for runtime skill installation."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from mcp_server.cli import main
from mcp_server.runtime_skills import (
    install_runtime_skills,
    packaged_runtime_skills_source,
    skill_target_paths,
)


def make_runtime_skill_source(tmp_path):
    source = tmp_path / "skills"
    skill_dir = source / "bathroom_planning"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Bathroom Planning\n", encoding="utf-8")
    (source / "styles.md").write_text("# Styles\n", encoding="utf-8")
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
    assert (project_path / ".agents" / "skills" / "styles.md").exists()
    assert result["installs"]["codex"]["file_count"] == 2
    assert result["installs"]["claude"]["file_count"] == 2


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
