"""Build MapleLens for Windows: freeze it with PyInstaller into dist/MapleLens/.

Usage: uv run --group build python scripts/build_installer.py --freeze-only
Before the freeze it writes the exe's version info from pyproject.toml; after it, it copies
the license texts into dist/MapleLens/licenses/. The build fails if the app holds fewer
templates or minimap pictures than src/, or if MapleLens.exe --self-check exits non-zero.
The installer step (Inno Setup) comes later; for now only --freeze-only runs.
"""

import argparse
import importlib.metadata
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGING = REPO / "packaging" / "windows"
SPEC = PACKAGING / "maplelens.spec"
DIST = REPO / "dist"
WORK = REPO / "build"
# maplelens.spec reads the version info from here
VERSION_FILE = WORK / "version_info.txt"
EXE = DIST / "MapleLens" / "MapleLens.exe"
LICENSES = DIST / "MapleLens" / "licenses"
SRC_PKG = REPO / "src" / "maplelens"
BUNDLE_PKG = DIST / "MapleLens" / "_internal" / "maplelens"
# Data folders, relative to the package, whose PNG count must survive the freeze.
COUNTED = ["readers/templates", "data/minimaps"]


def _dist_file(dist: str, name: str) -> Callable[[], Path]:
    """The file of installed distribution `dist` whose path ends with `name`."""

    def find() -> Path:
        for f in importlib.metadata.distribution(dist).files or []:
            if str(f).replace("\\", "/").endswith(name):
                return Path(f.locate())
        sys.exit(f"no {name} in the installed {dist}")

    return find


# license file shipped in licenses/ -> where it comes from
LICENSE_SOURCES: dict[str, Callable[[], Path]] = {
    "NOTICE.txt": lambda: PACKAGING / "NOTICE.txt",
    "MapleLens-LICENSE.txt": lambda: REPO / "LICENSE",
    # the PySide6 wheels carry only Qt's commercial license text, so the GNU texts live here
    "PySide6-Qt-LGPL-3.0.txt": lambda: PACKAGING / "licenses" / "lgpl-3.0.txt",
    "PySide6-Qt-GPL-3.0.txt": lambda: PACKAGING / "licenses" / "gpl-3.0.txt",
    "OpenCV-LICENSE.txt": _dist_file("opencv-python-headless", "dist-info/LICENSE.txt"),
    "OpenCV-LICENSE-3RD-PARTY.txt": _dist_file(
        "opencv-python-headless", "dist-info/LICENSE-3RD-PARTY.txt"
    ),
    "numpy-LICENSE.txt": _dist_file("numpy", "dist-info/licenses/LICENSE.txt"),
    "winrt-LICENSE.txt": _dist_file("winrt-runtime", "dist-info/licenses/LICENSE"),
    "Python-LICENSE.txt": lambda: Path(sys.base_prefix) / "LICENSE.txt",
}


def read_version(pyproject: Path = REPO / "pyproject.toml") -> str:
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def version_info(version: str) -> str:
    """PyInstaller's version-info file for `version` (X.Y.Z): Properties -> Details."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit(f"version {version} isn't X.Y.Z, which the exe's file version needs")
    nums = (*map(int, version.split(".")), 0)
    strings = {
        "FileDescription": "MapleLens",
        "FileVersion": version,
        "InternalName": "MapleLens",
        "LegalCopyright": "Copyright (c) or-keren. MIT License.",
        "OriginalFilename": "MapleLens.exe",
        "ProductName": "MapleLens",
        "ProductVersion": version,
    }
    structs = ",\n        ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings.items())
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={nums},
    prodvers={nums},
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        {structs},
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""


def copy_licenses(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name, source in LICENSE_SOURCES.items():
        shutil.copyfile(source(), dest / name)


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
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(version_info(read_version()), encoding="utf-8")
    run(freeze_cmd())
    check_bundle(SRC_PKG, BUNDLE_PKG)
    copy_licenses(LICENSES)
    try:
        run([str(EXE), "--self-check"])
    except subprocess.CalledProcessError:
        sys.exit(f"{EXE.name} --self-check failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
