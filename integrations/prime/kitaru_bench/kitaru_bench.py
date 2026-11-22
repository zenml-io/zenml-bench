"""kitaru-bench as a verifiers v1 taskset (Prime Intellect Environments Hub).

The tasks are the Harbor task directories under `kitaru/tasks/` in https://github.com/zenml-io/zenml-bench; this
module only tells verifiers where to find them and which image each one runs in. Rewards come from each task's own
verifier (`/logs/verifier/reward.json`), so nothing is re-implemented here.

    uv run vf-run kitaru-bench -m <model> --env.agent.harness.id codex --env.agent.runtime.type docker

Images: verifiers never builds a task's `environment/Dockerfile`; it only pulls or reuses an image by name. Every
task's Dockerfile loads a recorded history into Kitaru's database, so this taskset names one prebuilt image per task
from `image_template` and tells the Harbor loader to accept the Dockerfile. `kitaru/scripts/build_task_images.sh`
builds them under the same names for the local docker runtime.

What verifiers takes from each task: the health check (it starts PostgreSQL, the Kitaru server and a worker before
the agent), the agent's Unix user (`agent`, not root) and the network allow-list.
"""
from pathlib import Path

import verifiers.v1 as vf
from verifiers.v1.tasksets.harbor import HarborConfig, HarborTask, HarborTaskset

REPO = "zenml-io/zenml-bench"
VERSION = "0.1.0"


class KitaruBenchConfig(HarborConfig):
    # Resolved from the repo's registry.json via Harbor's --repo route, pinned to a tag, so installing the
    # environment needs no Harbor Hub credentials. Hub id once public: "zenml/kitaru-bench@0.1.0" (then set
    # `repo` and `registry_path` to None).
    dataset: str = f"kitaru-bench@{VERSION}"
    repo: str | None = f"{REPO}@kitaru-v0.1"
    registry_path: Path | None = Path("registry.json")
    # One prebuilt image per task; `{task}` is the task directory name (c1-rule-from-builtins, ...).
    image_template: str = f"zenmldocker/kitaru-bench-tasks:{{task}}-{VERSION}"
    ignore_dockerfile: bool = True
    # Keep the task-authored timeouts: some tasks need work that takes minutes to run, and the budget is part of
    # the task.
    ignore_timeouts: bool = False


class KitaruBenchTaskset(HarborTaskset, vf.Taskset[HarborTask, KitaruBenchConfig]):
    def load(self) -> list[HarborTask]:
        template = self.config.image_template
        return [
            HarborTask(
                task.data.model_copy(update={"image": template.format(task=Path(task.data.task_dir).name)}),
                task.config,
            )
            for task in super().load()
        ]


def load_taskset(config: KitaruBenchConfig | None = None) -> KitaruBenchTaskset:
    return KitaruBenchTaskset(config or KitaruBenchConfig())


# verifiers resolves plugins through `__all__`: exactly one Taskset subclass.
__all__ = ["KitaruBenchConfig", "KitaruBenchTaskset", "load_taskset"]
