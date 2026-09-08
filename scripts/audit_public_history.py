"""Read-only heuristic scan of Git blobs. Never prints matched private values."""
import io
import argparse
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "local_user_path": r"/Us" r"ers/[^/\s<>]+/",
    "email": r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    "mobile_number": r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "api_key_shape": r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})",
    "named_comment_author": r"setSelf\(\{\s*displayName:",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def scan(raw):
    if raw.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                raw = b"\n".join(archive.read(n) for n in archive.namelist() if n.endswith((".xml", ".rels")))
        except zipfile.BadZipFile:
            return ["unreadable_archive"]
    elif b"\0" in raw[:8192]:
        return ["binary_manual_review"]
    text = raw.decode("utf-8", errors="replace")
    return [kind for kind, pattern in PATTERNS.items() if re.search(pattern, text)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", help="Scan only commits reachable from this ref; default: all refs")
    args = parser.parse_args(argv)
    # Resolve user input to a commit hash, never pass an unvalidated option to rev-list.
    scope = git("rev-parse", "--verify", "--end-of-options", args.ref + "^{commit}").decode().strip() if args.ref else "--all"
    tip = scope if args.ref else "HEAD"
    current = {}
    for entry in git("ls-tree", "-r", "-z", tip).split(b"\0"):
        if entry:
            meta, path = entry.split(b"\t", 1)
            current[path.decode()] = meta.split()[2].decode()
    found = []
    seen = set()
    # --all includes local branches/tags/remotes, not unreachable objects/reflogs.
    for line in git("rev-list", "--objects", scope).decode().splitlines():
        oid, _, path = line.partition(" ")
        if not path or oid in seen or git("cat-file", "-t", oid).strip() != b"blob":
            continue
        seen.add(oid)
        kinds = scan(git("cat-file", "blob", oid))
        if kinds:
            found.append({"object": oid, "path": path, "current": current.get(path) == oid, "flags": kinds})
    print(json.dumps({"scope": args.ref or "all refs", "commits": int(git("rev-list", "--count", scope)),
                      "unique_blobs_scanned": len(seen), "findings": found,
                      "limitations": "Heuristic patterns only; binary images need visual review. Commit author metadata is not scanned."},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
