from __future__ import annotations

import json
from pathlib import Path


def load_manifest(manifest_path: str | Path) -> set[str]:
    """Load a Django/Webpack-style staticfiles manifest.

    Accepts either:
    - Django ManifestStaticFilesStorage format: `{"paths": {"name": "hashed-name"}, ...}`
    - Webpack manifest format: `{"name": "hashed-name", ...}`
    - Vite manifest format: `{"name": {"file": "hashed-name", ...}, ...}`

    Returns the set of hashed (immutable) URL paths. Each path is normalized
    with a leading slash so it can be compared against the request path.
    """
    path = Path(manifest_path)
    if not path.is_file():
        return set()

    with open(path, "rb") as f:
        data = json.load(f)

    hashed: set[str] = set()

    # Django format
    if isinstance(data, dict) and "paths" in data and isinstance(data["paths"], dict):
        for hashed_name in data["paths"].values():
            if isinstance(hashed_name, str):
                hashed.add(_normalize(hashed_name))
        return hashed

    # Webpack or Vite
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, str):
                hashed.add(_normalize(value))
            elif isinstance(value, dict) and "file" in value:
                hashed.add(_normalize(value["file"]))
    return hashed


def _normalize(p: str) -> str:
    return p if p.startswith("/") else "/" + p
