import subprocess
import sys
from pathlib import Path
import yaml
import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "vulnquest-security-analyst"

def test_skill_manifest_valid_yaml():
    skill_md = SKILL_DIR / "SKILL.md"
    assert skill_md.exists()

    content = skill_md.read_text(encoding="utf-8")
    assert content.startswith("---")

    parts = content.split("---", 2)
    assert len(parts) >= 3

    frontmatter = yaml.safe_load(parts[1])
    assert frontmatter["name"] == "vulnquest-security-analyst"
    assert "description" in frontmatter
    assert "version" in frontmatter
    assert "author" in frontmatter
    assert "license" in frontmatter
    assert "inputs" in frontmatter
    assert "outputs" in frontmatter

def test_run_skill_script_cli(tmp_path):
    script_path = SKILL_DIR / "scripts" / "run_skill.py"
    assert script_path.exists()

    demo_file = tmp_path / "test_target.py"
    demo_file.write_text('password = "TestHardcodedSecret123"\n', encoding="utf-8")

    cmd = [sys.executable, str(script_path), "--file", str(demo_file), "--format", "json"]
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)

    import json
    data = json.loads(p.stdout)
    assert "findings" in data
    assert any(f["rule_id"] == "VQ003" for f in data["findings"])
