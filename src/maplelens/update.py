"""The pure part of the update check: GitHub's latest-release reply -> what to offer.

No network here. The app fetches the reply and downloads the file; this module only
reads the reply, compares versions and checks the downloaded file's digest.
"""

import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HOME_REPO = "or-keren/maplelens"  # the project's own page; never follows the override
REPO = os.environ.get("MAPLELENS_UPDATE_REPO") or HOME_REPO

_VERSION = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")


@dataclass(frozen=True)
class Release:
    version: str  # "X.Y.Z", without the "v"
    url: str  # the platform's asset's browser_download_url
    digest: str | None  # "sha256:<hex>" as GitHub gives it; None means it can't be verified


def _version(text) -> tuple[int, int, int] | None:
    m = _VERSION.fullmatch(text) if isinstance(text, str) else None
    return tuple(int(g) for g in m.groups()) if m else None


def asset_name(version: str, platform: str) -> str:
    return f"MapleLens-{version}.dmg" if platform == "darwin" else f"MapleLens-Setup-{version}.exe"


def parse_latest(reply, platform: str | None = None) -> Release | None:
    """A `releases/latest` reply -> this platform's asset, or None when there's nothing to offer."""
    platform = platform or sys.platform
    if not isinstance(reply, dict):
        return None
    tag = reply.get("tag_name")
    if not isinstance(tag, str) or not tag.startswith("v") or _version(tag[1:]) is None:
        return None
    version = tag[1:]
    assets = reply.get("assets")
    if not isinstance(assets, list):
        return None
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") != asset_name(version, platform):
            continue
        url = asset.get("browser_download_url")
        if not isinstance(url, str):
            return None
        digest = asset.get("digest")
        return Release(version, url, digest if isinstance(digest, str) else None)
    return None


def is_newer(release: Release, running) -> bool:
    latest, current = _version(release.version), _version(running)
    return latest is not None and current is not None and latest > current


def digest_ok(path: Path, digest) -> bool:
    """True only when `digest` is `sha256:<hex>` and matches the file."""
    if not isinstance(digest, str):
        return False
    algo, _, want = digest.partition(":")
    if algo != "sha256" or not want:
        return False
    try:
        with open(path, "rb") as f:
            got = hashlib.file_digest(f, "sha256").hexdigest()
    except OSError:
        return False
    return got == want.lower()


def can_update(frozen: bool, platform: str) -> bool:
    """Only the installed app (Windows or Mac) updates itself: source runs never ask."""
    return bool(frozen) and platform in ("win32", "darwin")
