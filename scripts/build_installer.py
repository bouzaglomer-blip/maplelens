"""Build MapleLens for Windows: freeze it with PyInstaller into dist/MapleLens/.

Usage: uv run --group build python scripts/build_installer.py --freeze-only
The installer step (Inno Setup) comes later; for now only --freeze-only runs.
"""

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "packaging" / "windows" / "maplelens.spec"
DIST = REPO / "dist"
WORK = REPO / "build"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def freeze_cmd() -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
    ]


def main(argv: list[str] | None = None, run: Callable[[list[str]], None] = _run) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--freeze-only", action="store_true", help="build dist/MapleLens/ only")
    args = parser.parse_args(argv)
    if not args.freeze_only:
        sys.exit("the installer step isn't written yet: use --freeze-only")
    run(freeze_cmd())
    return 0


if __name__ == "__main__":
    sys.exit(main())
