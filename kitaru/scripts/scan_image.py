# /// script
# requires-python = ">=3.11"
# ///
"""Leak scan for a Docker image, run before the image is pushed anywhere and again on the pushed copy.

    uv run kitaru/scripts/scan_image.py <image> [--secrets-from FILE ...] [--keep]

Prints counts and file paths only, never a secret's value. Exit code 1 if a blocking check finds anything.

What it looks at: every layer of the image, not only the final file system. A file added by one
build step and deleted by a later one is gone from the running container but still sits in the earlier
layer, where anyone who pulls the image can read it. The scan also covers the build history and the
image's configuration (environment variables, labels), which record every `ARG` and `ENV` value.

Checks:

1. BLOCKING, exact values. Every secret this machine holds is collected (the `.env` files given with
   `--secrets-from`, secret-looking shell variables, and the credential files of the tools used here)
   and searched for byte by byte, plain and base64. No pattern guessing: if one of our real keys is in
   the image, this finds it, and it cannot fire on a look-alike.
2. BLOCKING, identity. The user's home path, login name, git email and this machine's host name.
3. BLOCKING, files that should not exist: `.env` files, private keys, cloud and tool credential files,
   and the Kitaru server's generated settings.
4. REVIEW, pattern scanner. `trufflehog filesystem --no-verification` over all layers (no candidate is
   sent anywhere). Third-party packages ship example keys in tests and docs, so hits inside package
   folders are counted separately and do not block; hits anywhere else block.
"""
import argparse
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path

HOME = Path.home()
CREDENTIAL_FILES = ["~/.modal.toml", "~/.cache/huggingface/token", "~/.prime/config.json", "~/.codex/auth.json", "~/.config/gh/hosts.yml",
                    "~/.config/harbor/credentials.json", "~/.harbor/credentials.json", "~/.docker/config.json", "~/.netrc", "~/.pypirc", "~/.npmrc",
                    "~/.aws/credentials", "~/.config/openai/auth.json", "~/.claude/.credentials.json"]
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.I)
VALUE = re.compile(r"[A-Za-z0-9_\-./+=:]{20,}")
FORBIDDEN_FILE = re.compile(r"(^|/)(\.env(\..+)?|id_(rsa|ed25519|ecdsa)|.*\.pem|credentials(\.json)?|\.netrc|\.pypirc|\.npmrc|\.modal\.toml|auth\.json|server\.env|keys\.env|hosts\.yml)$")
FORBIDDEN_OK = re.compile(r"(site-packages|dist-packages|node_modules|/usr/share|/usr/lib|/etc/ssl|/etc/ca-certificates|/usr/local/lib/python[\d.]+/(test|ensurepip|idlelib))")
PACKAGE_DIR = re.compile(r"(site-packages|dist-packages|node_modules|/usr/share/|/usr/lib/|/var/lib/dpkg|/opt/kitaru-wheels|/opt/kitaru-docs|/ensurepip/_bundled/)")


def collect_secrets(extra_env_files: list[Path]) -> set[str]:
    """Every secret value on this machine worth 20+ characters. Values stay in memory and in one
    temp file with mode 600 that is deleted before the scan returns."""
    values: set[str] = set()
    for name, value in os.environ.items():
        if SECRET_NAME.search(name):
            values.add(value)
    for path in extra_env_files:
        for line in path.read_text(errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                values.add(line.split("=", 1)[1].strip().strip("'\""))
    for raw in CREDENTIAL_FILES:
        path = Path(raw).expanduser()
        if path.is_file():
            values.update(VALUE.findall(path.read_text(errors="ignore")))
    try:
        values.add(subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20).stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Keep real secrets: long enough, not a path, a URL or a plain word.
    return {v for v in values if len(v) >= 20 and not v.startswith(("/", "http", "~")) and re.search(r"\d", v) and re.search(r"[A-Za-z]", v)}


def identity_strings() -> list[str]:
    email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout.strip()
    host = socket.gethostname().split(".")[0]
    return [s for s in {str(HOME), HOME.name, email, host} if len(s) >= 5]


def unpack_layers(image: str, into: Path) -> list[Path]:
    """`docker save` the image and unpack each layer into its own folder."""
    saved = into / "image.tar"
    subprocess.run(["docker", "save", image, "-o", str(saved)], check=True)
    raw = into / "raw"
    with tarfile.open(saved) as tar:
        tar.extractall(raw, filter="tar")
    saved.unlink()
    manifest = json.loads((raw / "manifest.json").read_text())[0]
    layers = []
    for number, layer in enumerate(manifest["Layers"]):
        target = into / f"layer-{number:02d}"
        target.mkdir()
        with tarfile.open(raw / layer) as tar:
            members = [m for m in tar.getmembers() if m.isfile() or m.isdir()]  # no devices, no links out of the folder
            tar.extractall(target, members=members, filter="tar")
        subprocess.run(["chmod", "-R", "u+rwX", str(target)], check=False)  # images hold files only root may read; unreadable means unscanned
        layers.append(target)
    return layers


def grep_fixed(patterns: list[str], roots: list[Path]) -> list[str]:
    """Files under `roots` containing any of the fixed strings, binary files included. Uses ripgrep
    (macOS grep takes over 15 minutes for 70 strings over 4 GB; ripgrep takes seconds). The strings go
    through a private file so they never appear in a process list."""
    if not patterns:
        return []
    if not shutil.which("rg"):
        sys.exit("ripgrep (rg) is required for the exact-value search")
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        os.chmod(f.name, 0o600)
        f.write("\n".join(patterns) + "\n")
    try:
        out = subprocess.run(["rg", "--files-with-matches", "--text", "--fixed-strings", "--no-ignore", "--hidden",
                              "--file", f.name, *map(str, roots)], capture_output=True, text=True)
        if out.returncode not in (0, 1):  # 1 = no match; 2 = it could not read something, which would leave a gap
            sys.exit(f"ripgrep could not search everything: {out.stderr[-600:]}")
        return [line for line in out.stdout.splitlines() if line]
    finally:
        os.unlink(f.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--secrets-from", type=Path, action="append", default=[], help="a .env file whose values must not be in the image (repeatable)")
    ap.add_argument("--keep", action="store_true", help="keep the unpacked layers for inspection")
    a = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix="scan-image-"))
    blocking = 0

    def report(label: str, hits: list[str], blocks: bool = True) -> None:
        nonlocal blocking
        shown = sorted({h.replace(str(work), "") for h in hits})
        print(f"{'BLOCK ' if blocks and shown else 'ok    ' if not shown else 'review'} {label}: {len(shown)}")
        for h in shown[:15]:
            print(f"         {h}")
        if blocks and shown:
            blocking += 1

    try:
        layers = unpack_layers(a.image, work)
        meta = work / "metadata.txt"
        meta.write_text(subprocess.run(["docker", "history", "--no-trunc", "--format", "{{.CreatedBy}}", a.image], capture_output=True, text=True).stdout
                        + subprocess.run(["docker", "inspect", a.image], capture_output=True, text=True).stdout)
        roots = [*layers, meta]
        files = sum(1 for layer in layers for _ in layer.rglob("*"))
        secrets = collect_secrets(a.secrets_from)
        encoded = {base64.b64encode(s.encode()).decode().rstrip("=") for s in secrets}
        print(f"image {a.image}: {len(layers)} layers, {files} files; {len(secrets)} secret values from this machine checked\n")

        report("files containing one of this machine's secret values (plain or base64)", grep_fixed(sorted(secrets | encoded), roots))
        report("files containing the home path, login name, git email or host name", grep_fixed(identity_strings(), roots))
        forbidden = [str(p) for layer in layers for p in layer.rglob("*") if p.is_file() and FORBIDDEN_FILE.search(str(p)) and not FORBIDDEN_OK.search(str(p))]
        report("credential-style files outside package folders", forbidden)

        if shutil.which("trufflehog"):
            out = subprocess.run(["trufflehog", "filesystem", *map(str, layers), "--no-verification", "--no-update", "--json"], capture_output=True, text=True)
            ours, packaged = [], Counter()
            for line in out.stdout.splitlines():
                try:
                    finding = json.loads(line)
                    path = finding["SourceMetadata"]["Data"]["Filesystem"]["file"]
                except (json.JSONDecodeError, KeyError):
                    continue
                if PACKAGE_DIR.search(path):
                    packaged[finding.get("DetectorName", "?")] += 1
                else:
                    ours.append(f"{path}  [{finding.get('DetectorName', '?')}]")
            report("pattern-scanner findings outside third-party package folders", ours)
            print(f"review pattern-scanner findings inside third-party packages (example keys in their tests and docs): {sum(packaged.values())} {dict(packaged.most_common(6))}")
        else:
            print("review trufflehog is not installed; the pattern scan was skipped")
        print("\nCLEAN: no blocking finding" if not blocking else f"\nNOT CLEAN: {blocking} blocking check(s) found something")
        return 1 if blocking else 0
    finally:
        if a.keep:
            print(f"layers kept in {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
