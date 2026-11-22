"""Grader for I1. Reads the sessions Kitaru holds under `support-assistant` and compares them with the export: one session per
ticket, created through the Langfuse importer under the source identity `tidewater-support`, under the agent version of the
ticket's release."""
import json
import sys
from pathlib import Path

from kitaru_checks import KitaruError, kitaru, list_all, ticket_problems

AGENT = "support-assistant"
WANT = json.loads((Path(__file__).parent / "fixtures" / "expected.json").read_text())


def grade() -> dict:
    agent = kitaru("agent", "get", AGENT, check=False)
    if not agent.get("ok"):
        return {"reward": 0, "reason": f"no agent named {AGENT}"}
    versions = list_all("agent", "version", "list", AGENT)
    by_release: dict[str, list[str]] = {}
    for v in versions:
        by_release.setdefault(v.get("display_version") or "", []).append(v["id"])
    metrics: dict = {"agent_versions": {v["version"]: v.get("display_version") for v in versions}}
    metrics["versions_ok"] = all(len(by_release.get(release, [])) == 1 for release in ("1.4.0", "1.5.0"))
    if not metrics["versions_ok"]:
        return metrics | {"reward": 0, "reason": "the agent needs exactly one version with display version 1.4.0 and one with 1.5.0"}
    sessions = list_all("session", "list", "--agent", AGENT)
    problems = ticket_problems(sessions, WANT["tickets"], WANT["project"], {release: ids[0] for release, ids in by_release.items()})
    wanted = {f"{WANT['project']}:{ticket}" for ticket in WANT["tickets"]}
    importer = kitaru("importer", "get", "kitaru/langfuse")["item"]["id"]
    imports = {i["id"]: i for i in list_all("import", "list")}
    versions_of_langfuse = {v["id"] for v in list_all("importer", "version", "list", "kitaru/langfuse")}
    metrics |= {"tickets_in_export": len(wanted), "sessions_under_agent": len(sessions), "unexpected_sessions": sum(s.get("external_id") not in wanted for s in sessions),
                "tickets_right": len(wanted) - len(problems), "first_problems": dict(sorted(problems.items())[:8]),
                "imports_ok": all((imports.get(s.get("import_id")) or {}).get("importer_version_id") in versions_of_langfuse for s in sessions), "importer_id": importer}
    metrics["reward"] = int(not problems and not metrics["unexpected_sessions"] and metrics["imports_ok"])
    return metrics


if __name__ == "__main__":
    try:
        result = grade()
    except KitaruError as e:
        result = {"reward": 0, "reason": f"grader could not finish: {e}"}
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/metrics.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1), file=sys.stderr)
    print(result["reward"])
