"""Load the clinic history into a running Kitaru server and give the workspace its git history. Runs once, as root,
while the image is built.

Registers the booking agent and its three releases, imports one JSONL file per release through the real JSONL importer,
and stops the build if the server's counts disagree with the plan. Then it commits the workspace in five steps, so the
repository shows when each release and each configuration change happened, and records two commit ids for the grader."""
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

WORLD = Path(__file__).parent
APP = Path("/app")
RELEASES = ["1.1.0", "1.2.0", "1.3.0"]
TOOLS = ["--command", "python -m booking_agent", "--working-dir", "/app"] + [x for t in ("search_clinics", "check_availability", "book_appointment", "lookup_booking", "reschedule_appointment",
                                                                                             "get_care_sheet", "register_owner", "register_pet", "request_records", "send_forms") for x in ("--tool", t)]


def kitaru(*args: str) -> dict[str, Any]:
    out = subprocess.run(["kitaru", *args, "-o", "json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        data = {"ok": False, "error": (out.stdout + out.stderr)[-1500:]}
    if not data.get("ok"):
        sys.exit(f"kitaru {' '.join(args)} failed: {json.dumps(data.get('error'))[:1500]}")
    return data


def load_history() -> None:
    plan = json.loads((WORLD / "plan.json").read_text())
    kitaru("agent", "register", "booking-agent", "--description", "Fernhill Vets appointment assistant: finds a clinic, books, moves bookings, answers care questions.",
           "--display-version", RELEASES[0], *TOOLS)
    for release in RELEASES[1:]:
        kitaru("agent", "version", "register", "booking-agent", "--display-version", release, *TOOLS)
    created = {}
    for number, release in enumerate(RELEASES, start=1):
        packed, plain = WORLD / f"sessions-{release}.jsonl.gz", Path(f"/tmp/sessions-{release}.jsonl")
        with gzip.open(packed, "rb") as src, plain.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        t0 = time.time()
        kitaru("session", "import", str(plain), "--importer", "kitaru/kitaru-jsonl@latest", "--agent", f"booking-agent@{number}",
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


def swap(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        sys.exit(f"workspace file does not contain exactly one {old!r}")
    return text.replace(old, new)


def build_repo() -> None:
    """Commit the workspace as it was at five moments. The last state is the files as they are on disk."""
    final = {p: (APP / p).read_text() for p in ("CHANGELOG.md", "agent/VERSION", "agent/config.yaml", "agent/prompt.md", "agent/tools.py", "README.md")}
    log = final["CHANGELOG.md"]
    before_13 = final | {"agent/VERSION": "1.2.0\n", "CHANGELOG.md": log[:log.index("## 1.3.0")] + log[log.index("## 1.2.0"):],
                         "agent/tools.py": swap(final["agent/tools.py"], "EXACT_MATCH_FIRST = True  # 1.3.0: ask the clinic search for the exact name before anything else", "EXACT_MATCH_FIRST = False")}
    before_cap = before_13 | {"agent/config.yaml": swap(final["agent/config.yaml"], "max_tokens: 120", "max_tokens: 400")}
    before_offer = before_cap | {"agent/prompt.md": swap(final["agent/prompt.md"], "- The litter check-up offer (from 27 June) covers one visit per litter; the limit of three animals per online booking still applies.\n", "")}
    first = before_offer | {"agent/VERSION": "1.1.0\n", "CHANGELOG.md": log[:log.index("## 1.3.0")] + log[log.index("## 1.1.0"):],
                            "agent/prompt.md": swap(before_offer["agent/prompt.md"], "- Greet briefly.\n", "- Greet the customer by name and thank them for choosing Fernhill Vets.\n")}
    steps = [(first, "2026-05-29T09:00:00Z", "Appointment assistant 1.1.0"), (before_offer, "2026-06-20T16:30:00Z", "Release 1.2.0: shorter greeting"),
             (before_cap, "2026-06-26T11:10:00Z", "prompt: wording for the litter check-up offer"), (before_13, "2026-07-01T08:05:00Z", "config: cap reply length to bring latency down"),
             (final, "2026-07-08T17:45:00Z", "Release 1.3.0: clinic search asks for the exact match first")]
    def git(*args: str, date: str | None = None) -> str:
        env = {"HOME": "/home/agent", "PATH": os.environ["PATH"], "GIT_AUTHOR_NAME": "fernhill", "GIT_AUTHOR_EMAIL": "dev@fernhill.example", "GIT_COMMITTER_NAME": "fernhill", "GIT_COMMITTER_EMAIL": "dev@fernhill.example"}
        if date:
            env |= {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        out = subprocess.run(["runuser", "-u", "agent", "--", "env", *(f"{k}={v}" for k, v in env.items()), "git", "-C", str(APP), *args], capture_output=True, text=True)
        if out.returncode:
            sys.exit(f"git {' '.join(args)} failed: {out.stderr[-500:]}")
        return out.stdout.strip()
    subprocess.run(["chown", "-R", "agent:agent", str(APP)], check=True)
    git("init", "-q", "-b", "main")
    ids = []
    for files, date, subject in steps:
        for rel, text in files.items():
            (APP / rel).write_text(text)
        subprocess.run(["chown", "-R", "agent:agent", str(APP)], check=True)
        git("add", "-A")
        git("commit", "-q", "-m", subject, date=date)
        ids.append(git("rev-parse", "HEAD"))
    if git("status", "--porcelain"):
        sys.exit("the workspace is not clean after its last commit")
    Path("/etc/kitaru-bench/clinic.json").write_text(json.dumps({"head": ids[-1], "config_commit": ids[3]}))
    os.chmod("/etc/kitaru-bench/clinic.json", 0o600)  # the grader's record; root only
    print("repository:", len(ids), "commits, head", ids[-1][:10], flush=True)


if __name__ == "__main__":
    load_history()
    build_repo()
