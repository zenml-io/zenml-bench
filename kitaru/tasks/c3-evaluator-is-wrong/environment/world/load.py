"""Load the storefront history into a running Kitaru server. Runs once, as root, while the image is built.

Registers the returns agent and its three releases, imports one JSONL file per release through the
real JSONL importer (so every session carries an import id and a worker task id), registers the
example evaluator, and stops the build if the server's counts disagree with the plan.
"""
import gzip
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

WORLD = Path(__file__).parent
RELEASES = ["1.3.0", "1.4.0", "1.4.1"]
# Kitaru requires a run command for every agent version. This world's history is imported, and the
# shop's agent code is not in the image, so the command names a module that does not exist here.
TOOLS = ["--command", "python -m returns_agent", "--working-dir", "/app", "--tool", "lookup_order", "--tool", "issue_refund"]


def kitaru(*args: str) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "error": (out.stdout + out.stderr)[-1500:]}
    if not data.get("ok"):
        sys.exit(f"kitaru {' '.join(args)} failed: {json.dumps(data.get('error'))[:1500]}")
    return data


def main() -> None:
    plan = json.loads((WORLD / "plan.json").read_text())
    kitaru("agent", "register", "returns-agent", "--description", "Larkspur Goods returns assistant: looks up an order, refunds or declines, confirms to the customer.",
           "--display-version", RELEASES[0], *TOOLS)
    for release in RELEASES[1:]:
        kitaru("agent", "version", "register", "returns-agent", "--display-version", release, *TOOLS)
    created = {}
    for number, release in enumerate(RELEASES, start=1):
        packed, plain = WORLD / f"sessions-{release}.jsonl.gz", Path(f"/tmp/sessions-{release}.jsonl")
        with gzip.open(packed, "rb") as src, plain.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        t0 = time.time()
        kitaru("session", "import", str(plain), "--importer", "kitaru/kitaru-jsonl@latest", "--agent", f"returns-agent@{number}",
               "--media-type", "application/x-ndjson", "--tag", "history", "--wait", "--timeout", "3000", "--request-timeout", "300")
        imports = kitaru("import", "list", "--size", "1")["items"]
        result = next(t for t in kitaru("job", "get", imports[0]["job_id"], "--tasks")["item"]["tasks"] if t["kind"] == "importer")["result"]
        created[release] = result["created"]
        print(f"release {release}: {result} in {time.time() - t0:.0f}s", flush=True)
        if result["failed"] or result["skipped"]:
            sys.exit(f"import of {release} was not clean: {result}")
        plain.unlink()
    if created != plan["by_version"]:
        sys.exit(f"server holds {created}, the plan says {plan['by_version']}")
    # The team's checks. `refund-issued-once` has two versions: the first from a file that is not kept
    # in the workspace, the second from the workspace's current source.
    kitaru("evaluator", "register", "refund-issued-once", "--script", str(WORLD / "old" / "refund_issued_once_v1.py"), "--entrypoint", "evaluate",
           "--description", "Passes when a conversation issued at most one refund.")
    kitaru("evaluator", "version", "register", "refund-issued-once", "--script", "/app/evaluators/refund_issued_once.py", "--entrypoint", "evaluate")
    kitaru("evaluator", "register", "polite-closing", "--script", "/app/evaluators/polite_closing.py", "--entrypoint", "evaluate",
           "--description", "Passes when the reply ends with a closing courtesy.")
    first, last = (kitaru("session", "list", "--size", "1", "--sort", order)["items"][0] for order in ("created:asc", "created:desc"))
    print(json.dumps({"created": created, "first": [first["number"], first["started_at"]], "last": [last["number"], last["started_at"]]}))


if __name__ == "__main__":
    main()
