# MapleLens Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local git repo `C:\Development\maplelens` with an empty Python package, a working screen-only guard, agent instructions + shared Claude settings, CI, and the open-source community files — nothing pushed.

**Architecture:** One stdlib-only guard script is the single enforcement point for the screen-only rule; CI and a Claude `PostToolUse` hook both call it. `AGENTS.md` is the one source of agent instructions; `CLAUDE.md` imports it. Everything else is static docs/config.

**Tech Stack:** Python 3.12, uv, ruff, pytest, GitHub Actions, Dependabot.

**Spec:** `docs/superpowers/specs/2026-11-01-maplelens-harness-design.md` — read it first; this plan points at its sections instead of repeating them.

## Global Constraints

- Screen-only rule text: copy **verbatim** from the spec section "The non-negotiable rule" into README, CONTRIBUTING and AGENTS.md.
- `requires-python = ">=3.12"`. Runtime `dependencies = []`. Dev group: `pytest`, `ruff` only.
- Guard is stdlib-only and scans `src/` and `scripts/` (excluding itself), never `tests/`.
- No absolute paths or personal settings in any committed file. Personal Claude settings → `.claude/settings.local.json` (gitignored).
- License MIT. README states "Unofficial fan project; not affiliated with Nexon."
- Default branch `main`. **Never push or create a remote.**
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Non-ASCII source files on Windows** (Korean/emoji comments): guard must read UTF-8 explicitly, not the cp1252 default, and still detect violations. → `test_non_ascii_file_still_checked` (Task 1).
2. **Name lookalikes** (`import mousepad`, `import keyboard_layout`, `ShowSendMessageBox`): must not be flagged; only exact top-level modules and whole Win32 names (optional `A`/`W` suffix). → `test_lookalikes_not_flagged` (Task 1).
3. **Submodule imports** (`import scapy.all`, `from frida.core import x`): flagged by top-level name. → `test_flags_banned_import` (Task 1).
4. **Half-written file during a Claude edit** (syntax error): guard must not crash with a traceback; it skips the import check for that file and still runs the name check. → `test_syntax_error_does_not_crash` (Task 1).
5. **Run from another working directory** (CI, hook): with no args the guard resolves `src/` and `scripts/` from its own location, not cwd. → `test_repo_is_clean_from_any_cwd` (Task 1).

---

### Task 0: Folder and owner inputs

- [ ] **Step 1: Ask the owner** for (a) the name for the LICENSE copyright line, (b) the contact for the Code of Conduct enforcement section (an email, or "use GitHub private reporting"). Do not use their account email without asking — it would be published.
- [ ] **Step 2: Check tools.** Run `uv --version` and `git config user.name`. Expected: a version line, and a name. If uv is missing, stop and tell the owner (`winget install astral-sh.uv`). If git identity is missing, ask the owner.
- [ ] **Step 3: Create the repo.** Create `C:\Development\maplelens`, `git init -b main`, move the session there, and move the spec and this plan into `docs/superpowers/specs/` and `docs/superpowers/plans/`.

### Task 1: Package skeleton + screen-only guard

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/maplelens/__init__.py`, `uv.lock`, `tests/fixtures/screens/.gitkeep`
- Create: `scripts/check_screen_only.py`
- Test: `tests/test_screen_only_guard.py`

**Interfaces:**
- Produces: CLI `python scripts/check_screen_only.py [PATH ...]`. PATH = file or directory (walked for `*.py`). No args → `<repo>/src` and `<repo>/scripts`, where `<repo>` = `Path(__file__).resolve().parent.parent`. The guard file itself is always skipped.
- Output: one line per violation on **stderr**: `<path>:<line>: banned import '<module>'` or `<path>:<line>: banned Win32 call '<name>'`.
- Exit: `0` clean, `2` violations. (2, not 1, because Claude Code feeds a hook's stderr back to the model only on exit 2; CI treats any non-zero as failure.)
- Module constants: `BANNED_MODULES` and `BANNED_WIN32` — exactly the lists in the spec section "Screen-only guard", each entry with a short comment saying why.

- [ ] **Step 1: Scaffold.** Run `uv init --lib --name maplelens --python 3.12` in the repo, then edit `pyproject.toml`: description `"Screen-reading-only overlay for MapleStory Classic."`, `license = "MIT"`, keep the uv build backend; add
  ```toml
  [dependency-groups]
  dev = ["pytest>=8", "ruff>=0.6"]

  [tool.pytest.ini_options]
  testpaths = ["tests"]

  [tool.ruff]
  line-length = 100

  [tool.ruff.lint]
  select = ["E", "F", "I", "UP", "B"]
  ```
  Reduce `src/maplelens/__init__.py` to a one-line docstring. `.gitignore`: standard Python (`__pycache__/`, `*.pyc`, `.venv/`, `dist/`, `.pytest_cache/`, `.ruff_cache/`) plus `.claude/settings.local.json`. Delete any `README.md` uv created (Task 4 writes it). Run `uv sync`. Expected: creates `.venv` and `uv.lock`.

- [ ] **Step 2: Write the failing tests** in `tests/test_screen_only_guard.py`. Helper `run_guard(*args, cwd=None)` → `subprocess.run([sys.executable, GUARD, *args], capture_output=True, text=True, cwd=cwd)` where `GUARD = Path(__file__).resolve().parent.parent / "scripts" / "check_screen_only.py"`.
  ```python
  def test_flags_banned_import(tmp_path):
      f = tmp_path / "bad.py"
      f.write_text("import pymem\nfrom scapy.all import sniff\nimport frida.core\n", encoding="utf-8")
      r = run_guard(str(f))
      assert r.returncode == 2
      assert "bad.py:1: banned import 'pymem'" in r.stderr
      assert "bad.py:2: banned import 'scapy'" in r.stderr
      assert "bad.py:3: banned import 'frida'" in r.stderr


  def test_flags_win32_name(tmp_path):
      f = tmp_path / "bad.py"
      f.write_text("x = 1\nk32.ReadProcessMemory(h)\nuser32.SendMessageW(w)\n", encoding="utf-8")
      r = run_guard(str(f))
      assert r.returncode == 2
      assert "bad.py:2: banned Win32 call 'ReadProcessMemory'" in r.stderr
      assert "bad.py:3: banned Win32 call 'SendMessage'" in r.stderr


  def test_clean_file_passes(tmp_path):
      f = tmp_path / "ok.py"
      f.write_text("import json\nfrom pathlib import Path\n", encoding="utf-8")
      assert run_guard(str(f)).returncode == 0


  def test_lookalikes_not_flagged(tmp_path):
      f = tmp_path / "ok.py"
      f.write_text(
          "import mousepad\nimport keyboard_layout\nShowSendMessageBox()\n", encoding="utf-8"
      )
      assert run_guard(str(f)).returncode == 0


  def test_non_ascii_file_still_checked(tmp_path):
      f = tmp_path / "bad.py"
      f.write_text("# 메이플 ✓\nimport pymem\n", encoding="utf-8")
      r = run_guard(str(f))
      assert r.returncode == 2 and "bad.py:2" in r.stderr


  def test_syntax_error_does_not_crash(tmp_path):
      f = tmp_path / "half.py"
      f.write_text("def broken(:\n    OpenProcess(1)\n", encoding="utf-8")
      r = run_guard(str(f))
      assert "Traceback" not in r.stderr
      assert r.returncode == 2 and "half.py:2: banned Win32 call 'OpenProcess'" in r.stderr


  def test_directory_arg_walks_py_files(tmp_path):
      (tmp_path / "pkg").mkdir()
      (tmp_path / "pkg" / "a.py").write_text("import pyautogui\n", encoding="utf-8")
      (tmp_path / "pkg" / "notes.txt").write_text("import pymem\n", encoding="utf-8")
      r = run_guard(str(tmp_path))
      assert r.returncode == 2 and "pyautogui" in r.stderr and "pymem" not in r.stderr


  def test_repo_is_clean_from_any_cwd(tmp_path):
      assert run_guard(cwd=tmp_path).returncode == 0
  ```

- [ ] **Step 3: Run tests to verify they fail.** Run `uv run pytest -v`. Expected: all FAIL (guard file missing → non-zero/`can't open file`), `test_repo_is_clean_from_any_cwd` included.

- [ ] **Step 4: Implement `scripts/check_screen_only.py`** with `find_violations(path: Path) -> list[str]` and `main(argv: list[str]) -> int`, `if __name__ == "__main__": sys.exit(main(sys.argv[1:]))`. Read files with `encoding="utf-8", errors="replace"`. Imports via `ast` (`Import` → each `alias.name.split(".")[0]`; `ImportFrom` with `level == 0` → `module.split(".")[0]`); on `SyntaxError` skip the import check. Win32 names via one regex over each line: `\b(?:NAME1|NAME2|...)[AW]?\b`, case-sensitive, report the base name. Module docstring: what it is, "a speed bump against honest mistakes, not a security boundary".

- [ ] **Step 5: Run tests to verify they pass.** Run `uv run pytest -v`. Expected: 8 passed. Then `uv run ruff check` and `uv run ruff format --check` → clean (run `uv run ruff format` first if needed).

- [ ] **Step 6: Commit.**
  ```bash
  git add pyproject.toml uv.lock .gitignore .python-version src scripts tests docs
  git commit -m "feat: package skeleton and screen-only guard"
  ```

### Task 2: Agent harness

**Files:**
- Create: `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`

**Interfaces:**
- Consumes: guard CLI and exit codes from Task 1; `BANNED_MODULES` list.

- [ ] **Step 1: Write `AGENTS.md`** (≤ 80 lines) with the six sections, in order, from the spec section "Agent instructions". Commands section lists exactly: `uv sync`, `uv run pytest`, `uv run ruff check`, `uv run ruff format`, `uv run python scripts/check_screen_only.py`. Add one line: don't write the banned names in comments or docstrings under `src/`/`scripts/` — the guard matches text.
- [ ] **Step 2: Write `CLAUDE.md`** containing only `@AGENTS.md`.
- [ ] **Step 3: Write `.claude/settings.json`:**
  - `"$schema": "https://json.schemastore.org/claude-code-settings.json"`
  - `permissions.allow`: `Bash(uv sync *)`, `Bash(uv run pytest *)`, `Bash(uv run ruff *)`, `Bash(uv run python scripts/check_screen_only.py *)`, `Bash(git status *)`, `Bash(git diff *)`, `Bash(git log *)` — and each also without the trailing ` *` so the bare command matches.
  - `permissions.deny`: for every module M in `BANNED_MODULES`: `Bash(uv add *M*)`, `Bash(pip install *M*)`, `Bash(uv pip install *M*)`.
  - `hooks.PostToolUse`: one entry, matcher `Edit|Write`, command `uv run --project "$CLAUDE_PROJECT_DIR" python "$CLAUDE_PROJECT_DIR/scripts/check_screen_only.py"` (quoted: paths may contain spaces).
- [ ] **Step 4: Validate JSON.** Run `uv run python -c "import json; json.load(open('.claude/settings.json'))"`. Expected: no output, exit 0.
- [ ] **Step 5: Verify the hook (manual).** In a Claude Code session in the repo, add `import pymem` to `src/maplelens/__init__.py` via Edit. Expected: hook feedback quoting `banned import 'pymem'`. Revert the edit; `git diff` is empty for that file.
- [ ] **Step 6: Commit.**
  ```bash
  git add AGENTS.md CLAUDE.md .claude/settings.json
  git commit -m "chore: agent instructions and shared Claude settings"
  ```

### Task 3: CI and Dependabot

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/dependabot.yml`

- [ ] **Step 1: Write `ci.yml`:** name `CI`; on `push` to `main` and `pull_request`; one job `check` on `windows-latest`; steps: `actions/checkout@v4`, `astral-sh/setup-uv@v6`, then run `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run python scripts/check_screen_only.py`, `uv run pytest`. Job name `check` is what branch protection will require — README/CONTRIBUTING refer to it.
- [ ] **Step 2: Write `dependabot.yml`:** `version: 2`; two updates, both `schedule.interval: weekly`, `directory: "/"`: `package-ecosystem: uv` and `package-ecosystem: github-actions`.
- [ ] **Step 3: Run the CI steps locally** in order (the five `uv` commands above). Expected: all exit 0. Then check the YAML parses (ephemeral, not added to the project): `uv run --with pyyaml python -c "import yaml, pathlib; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('.github').rglob('*.yml')]"` → exit 0.
- [ ] **Step 4: Commit.**
  ```bash
  git add .github/workflows/ci.yml .github/dependabot.yml
  git commit -m "ci: lint, format, guard and tests on Windows; dependabot"
  ```

### Task 4: Community files

**Files:**
- Create: `README.md`, `CONTRIBUTING.md`, `LICENSE`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug_report.yml`, `.github/ISSUE_TEMPLATE/feature_request.yml`, `.github/ISSUE_TEMPLATE/config.yml`

**Interfaces:**
- Consumes: owner inputs from Task 0; commands from Task 2; CI job name `check` from Task 3.

- [ ] **Step 1: README, CONTRIBUTING, SECURITY, PR template, issue templates** — contents exactly as listed in the spec section "Open-source files". Setup in README/CONTRIBUTING is: `git clone …`, `cd maplelens`, `uv sync`. Issue forms use GitHub issue-form YAML (`name`, `description`, `body` with `textarea`/`input`/`dropdown`); bug form's "windowed/borderless" is a `dropdown` with `Windowed`, `Borderless`, `Fullscreen (not supported)`. `config.yml`: `blank_issues_enabled: false`, one `contact_links` entry pointing to the repo's security policy.
- [ ] **Step 2: LICENSE** — standard MIT text, `Copyright (c) 2026 <owner name from Task 0>`.
- [ ] **Step 3: CODE_OF_CONDUCT** — Contributor Covenant 2.1, unmodified, from contributor-covenant.org; fill the enforcement contact from Task 0.
- [ ] **Step 4: Verify.** Run the YAML check from Task 3 Step 3 again (now covers the issue forms) → exit 0. Run `git grep -nIF 'C:\' -- ':!docs'` and `git grep -nI or303` → no matches (no absolute or personal paths). `uv run pytest` → still passes.
- [ ] **Step 5: Commit.**
  ```bash
  git add README.md CONTRIBUTING.md LICENSE CODE_OF_CONDUCT.md SECURITY.md .github
  git commit -m "docs: readme, contributing guide, license and community files"
  ```

### Task 5: Done check

- [ ] **Step 1: Clean clone.** `git clone C:\Development\maplelens <scratchpad>\clone`, then in it `uv sync && uv run ruff check && uv run python scripts/check_screen_only.py && uv run pytest`. Expected: all exit 0, 8 tests passed.
- [ ] **Step 2: Fresh agent check.** In the repo run `claude -p "What am I not allowed to do in this repo? Answer from what you already know."`. Expected: answer states the screen-only rule (no memory, files, network, or input). If it doesn't, AGENTS.md is too long or the rule isn't first — fix and re-run.
- [ ] **Step 3: Confirm nothing pushed.** `git remote -v` → empty. Report the owner steps from the spec section "Owner steps at push time".
