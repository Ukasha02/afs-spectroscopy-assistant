"""Make the KB cache available to the app without publishing the AFS materials.

Locally, `make kb` builds kb/cache/ from materials/. On the hosted app, kb/cache/ is downloaded at
startup from a PRIVATE GitHub repo using a read-only fine-grained token from the host's secrets:

  KB_REPO  = "owner/private-repo"   (contains chunks.jsonl and cases.json at the repo root)
  KB_TOKEN = "github_pat_..."       (fine-grained, read-only, that repo only)
"""

import json
import os
import urllib.request

from afs_assistant import config

FILES = ("chunks.jsonl", "cases.json")


def ensure_kb() -> str:
    """Return 'local', 'downloaded' or 'missing'."""
    if all((config.KB_CACHE_DIR / f).exists() for f in FILES):
        return "local"
    repo, token = os.getenv("KB_REPO"), os.getenv("KB_TOKEN")
    if not (repo and token):
        return "missing"
    config.KB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/contents/{name}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed GitHub API URL)
            (config.KB_CACHE_DIR / name).write_bytes(resp.read())
    json.loads((config.KB_CACHE_DIR / "cases.json").read_text())  # fail early on a bad download
    return "downloaded"
