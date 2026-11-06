"""release.yml must check and build before it publishes, and publish a version only once.

The fork runs are the real test; these keep the file from drifting away from ci.yml.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def _run_lines(path: Path) -> list[str]:
    """The commands of a workflow's single-line `run:` steps, in order."""
    return re.findall(r"^\s*-?\s*run: (\S.*)$", path.read_text(encoding="utf-8"), re.M)


def _release() -> str:
    return (WORKFLOWS / "release.yml").read_text(encoding="utf-8")


def test_runs_every_ci_check_before_publishing():
    text = _release()
    publish = text.index("gh release create")
    for check in _run_lines(WORKFLOWS / "ci.yml"):
        if check.startswith("uv run"):
            assert -1 < text.find(check) < publish, check


def test_builds_with_the_build_group_before_publishing():
    text = _release()
    publish = text.index("gh release create")
    assert -1 < text.find("uv sync --locked --group build") < publish
    assert -1 < text.find("scripts/build_installer.py") < publish


def test_publish_attaches_the_setup_exe_with_generated_notes():
    publish = _release().split("gh release create", 1)[1].split("\n\n", 1)[0]
    assert "MapleLens-Setup-" in publish
    assert "--generate-notes" in publish


def test_only_on_push_to_main_and_never_two_at_once():
    text = _release()
    assert re.search(r"^on:\n  push:\n    branches: \[main\]\n", text, re.M)
    assert re.search(r"^concurrency:", text, re.M)
    assert "contents: write" in text


def test_stops_when_the_tag_exists():
    text = _release()
    assert "git ls-remote" in text
    assert "already released" in text
    assert text.index("already released") < text.index("gh release create")
