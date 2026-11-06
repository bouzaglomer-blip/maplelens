"""Build MapleLens for Windows: freeze it with PyInstaller into dist/MapleLens/.

Usage: uv run --group build python scripts/build_installer.py --freeze-only
After the freeze, the build fails if the app holds fewer templates or minimap pictures
than src/, or if MapleLens.exe --self-check exits non-zero.
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
EXE = DIST / "MapleLens" / "MapleLens.exe"
SRC_PKG = REPO / "src" / "maplelens"
BUNDLE_PKG = DIST / "MapleLens" / "_internal" / "maplelens"
# Data folders, relative to the package, whose PNG count must survive the freeze.
COUNTED = ["readers/templates", "data/minimaps"]


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


def check_bundle(src: Path, bundle: Path) -> None:
    """Exit if `bundle` holds fewer PNGs than `src` in any COUNTED folder."""
    for rel in COUNTED:
        want = len(list((src / rel).rglob("*.png")))
        have = len(list((bundle / rel).rglob("*.png")))
        if have < want:
            sys.exit(f"bundle has {have} of {want} PNGs in {rel}")


def main(argv: list[str] | None = None, run: Callable[[list[str]], None] = _run) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--freeze-only", action="store_true", help="build dist/MapleLens/ only")
    args = parser.parse_args(argv)
    if not args.freeze_only:
        sys.exit("the installer step isn't written yet: use --freeze-only")
    run(freeze_cmd())
    check_bundle(SRC_PKG, BUNDLE_PKG)
    try:
        run([str(EXE), "--self-check"])
    except subprocess.CalledProcessError:
        sys.exit(f"{EXE.name} --self-check failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
