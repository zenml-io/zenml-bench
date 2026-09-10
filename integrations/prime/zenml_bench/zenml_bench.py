"""zenml-bench as a verifiers v1 taskset (Prime Intellect Environments Hub).

The tasks are the Harbor task directories in https://github.com/zenml-io/zenml-bench; this module only tells
verifiers where to find them and which image each one runs in. Rewards come from each task's own verifier
(`/logs/verifier/reward.json`), so nothing is re-implemented here. See docs/publishing.md in that repo.

    uv run eval zenml-bench -m <model> ...     # verifiers v1 CLI (`vf-eval` is the legacy runner and cannot load this)

Images: verifiers never builds a task's `environment/Dockerfile`; it only pulls or reuses an image by name. Every
zenml-bench task is Dockerfile-only (the Dockerfile copies the project in and seeds the ZenML store), so this
taskset names one prebuilt image per task from `image_template` and tells the Harbor loader to accept the
Dockerfile. Build them with `scripts/build_task_images.sh` (local docker runtime) or push them to a registry and
point `image_template` at it (Prime sandboxes).
"""
from pathlib import Path

import verifiers.v1 as vf
from verifiers.v1.tasksets.harbor import HarborConfig, HarborEnv, HarborTask, HarborTaskset

REPO = "zenml-io/zenml-bench"
VERSION = "0.1.0"


class ZenmlBenchConfig(HarborConfig):
    # Hub id once public (`harbor publish --public`): "zenml/zenml-bench@0.1.0". Until then, resolve the dataset
    # from the repo's registry.json via Harbor's --repo route, pinned to the v0.1 tag (no Hub credentials needed).
    dataset: str = f"zenml-bench@{VERSION}"
    repo: str | None = f"{REPO}@v0.1"
    registry_path: Path | None = Path("registry.json")
    # One prebuilt image per task; `{task}` is the task directory name (b10-why-did-it-fail, ...). The default is
    # the tag `scripts/build_task_images.sh` produces for the local docker runtime; override with a registry ref
    # (e.g. "ghcr.io/zenml-io/zenml-bench-{task}:0.1.0") for Prime sandboxes.
    image_template: str = f"zenml-bench/{{task}}:{VERSION}"
    ignore_dockerfile: bool = True
    # Keep the task-authored timeouts: the research tasks (r1-clock, r1-bare-clock) state a wall-clock budget in the
    # instruction, and dropping it changes the task.
    ignore_timeouts: bool = False


class ZenmlBenchTaskset(HarborTaskset, vf.Taskset[HarborTask, ZenmlBenchConfig]):
    def load(self) -> list[HarborTask]:
        template = self.config.image_template
        return [
            HarborTask(
                task.data.model_copy(update={"image": template.format(task=Path(task.data.task_dir).name)}),
                task.config,
            )
            for task in super().load()
        ]


def load_taskset(config: ZenmlBenchConfig | None = None) -> ZenmlBenchTaskset:
    return ZenmlBenchTaskset(config or ZenmlBenchConfig())


# verifiers resolves plugins through `__all__`: exactly one Taskset subclass, and the Harbor env so separate-verifier
# grading and `--env.verifier-runtime` work if a task ever asks for them.
__all__ = ["ZenmlBenchConfig", "ZenmlBenchTaskset", "HarborEnv", "load_taskset"]
