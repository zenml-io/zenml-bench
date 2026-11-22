# /// script
# requires-python = ">=3.11"
# dependencies = ["modal>=1.6"]
# ///
"""Build the per-task images on Modal, and optionally push them to Docker Hub.

Prime's runner (verifiers) never builds a task's Dockerfile; it needs one prebuilt image per task. Modal's machines
are amd64, the CPU type those images must have, so building there avoids emulating amd64 on an Apple-silicon Mac,
where the step that starts PostgreSQL and loads a world's history is slow and fails.

One Modal sandbox with Docker inside it gets each task's `environment/` folder from the given git ref (not from the
working folder, so nothing uncommitted and nothing from this machine can enter an image) and builds
`<repo>:<task>-<version>`.

    uv run kitaru/scripts/build_on_modal.py --ref kitaru-v0.1 c1-rule-from-builtins        # build only: a test
    DOCKERHUB_USERNAME=... DOCKERHUB_TOKEN=... uv run kitaru/scripts/build_on_modal.py --ref kitaru-v0.1 --push

With `--push`, the Docker Hub login is passed to that one sandbox as environment variables and is not stored on Modal.
"""
import argparse
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[2]
DIND_IMAGE = "docker:28.3.3-dind"
# Modal runs the Docker daemon without iptables or a bridge network, so builds use the sandbox's own network.
DAEMON_CONFIG = '{"iptables": false, "bridge": "none"}'


def run(sandbox: modal.Sandbox, command: str, quiet: bool = False) -> None:
    process = sandbox.exec("sh", "-c", command)
    for line in process.stdout:
        if not quiet:
            print(line, end="", flush=True)
    process.wait()
    if process.returncode != 0:
        print(process.stderr.read()[-3000:], file=sys.stderr)
        raise RuntimeError(f"exit code {process.returncode}: {command[:120]}")


def export_tasks(ref: str, tasks: list[str], out: Path) -> list[str]:
    """Write each task's `environment/` folder at `ref` under `out/<task>/` and return the task names."""
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", ref, "kitaru/tasks"], check=True, capture_output=True).stdout
    names = set()
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts  # kitaru/tasks/<task>/environment/...
            if len(parts) < 4 or parts[3] != "environment" or (tasks and parts[2] not in tasks):
                continue
            member.name = str(Path(parts[2], *parts[4:]))
            tar.extract(member, out, filter="data")
            names.add(parts[2])
    return sorted(names)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="*", help="task directory names; default: every task")
    ap.add_argument("--ref", required=True, help="git ref to build from, e.g. kitaru-v0.1")
    ap.add_argument("--repo", default="zenmldocker/kitaru-bench-tasks")
    ap.add_argument("--version", default="0.1.0")
    ap.add_argument("--push", action="store_true")
    # One at a time: builds share the sandbox's network, and each build starts PostgreSQL and the Kitaru server on
    # the same ports while it loads its history. Two different builds side by side collide and fail.
    ap.add_argument("--parallel", type=int, default=1)
    a = ap.parse_args()
    os.environ.setdefault("MODAL_ENVIRONMENT", "dev")
    secrets = []
    if a.push:
        login = {k: os.environ[k] for k in ("DOCKERHUB_USERNAME", "DOCKERHUB_TOKEN")}
        secrets = [modal.Secret.from_dict(login)]
    with tempfile.TemporaryDirectory() as tmp:
        names = export_tasks(a.ref, a.tasks, Path(tmp))
        if not names:
            sys.exit("no tasks found at that ref")
        image = (modal.Image.from_registry(DIND_IMAGE)
                 .dockerfile_commands(f"RUN mkdir -p /etc/docker && echo '{DAEMON_CONFIG}' > /etc/docker/daemon.json")
                 .add_local_dir(tmp, "/tasks"))
        app = modal.App.lookup("kitaru-bench-build", create_if_missing=True)
        os.environ["MODAL_SANDBOX_V2"] = "1"  # the sandbox generation that can run Docker
        sandbox = modal.Sandbox.create(app=app, image=image, secrets=secrets, cpu=8, memory=32768, timeout=4 * 60 * 60,
                                       experimental_options={"enable_docker": True})
    print(f"sandbox {sandbox.object_id}: {len(names)} task(s) from {a.ref}")
    try:
        for _ in range(30):
            probe = sandbox.exec("docker", "info")
            probe.wait()
            if probe.returncode == 0:
                break
            time.sleep(2)
        else:
            raise RuntimeError("Docker did not start in the sandbox")
        if a.push:
            run(sandbox, 'echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USERNAME" --password-stdin', quiet=True)
        one = (f'docker build -q --network host -t {a.repo}:$1-{a.version} /tasks/$1 > /tmp/$1.log 2>&1'
               f' && echo "built $1" || {{ echo "FAILED $1"; tail -40 /tmp/$1.log; exit 1; }}')
        if a.push:
            one = (f'docker build -q --network host -t {a.repo}:$1-{a.version} /tasks/$1 > /tmp/$1.log 2>&1'
                   f' && docker push -q {a.repo}:$1-{a.version} >> /tmp/$1.log 2>&1'
                   f' && echo "pushed $1 $(docker image inspect --format "{{{{index .RepoDigests 0}}}}" {a.repo}:$1-{a.version})"'
                   f' || {{ echo "FAILED $1"; tail -40 /tmp/$1.log; exit 1; }}')
        run(sandbox, f"sh -c '{one}' sh {names[0]}")
        if names[1:]:
            run(sandbox, f"printf '%s\\n' {' '.join(names[1:])} | xargs -P {a.parallel} -I{{}} sh -c '{one}' sh {{}}")
        run(sandbox, f"docker images --format '{{{{.Repository}}}}:{{{{.Tag}}}} {{{{.Size}}}}' | grep '^{a.repo}:' | sort")
    finally:
        sandbox.terminate()


if __name__ == "__main__":
    main()
