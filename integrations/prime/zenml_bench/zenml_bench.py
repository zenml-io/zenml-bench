"""zenml-bench as a verifiers v1 taskset (Prime Intellect Environments Hub).

The tasks are the Harbor task directories in https://github.com/zenml-io/zenml-bench; this module only tells
verifiers where to find them. Rewards come from each task's own verifier (`/logs/verifier/reward.json`), so
nothing is re-implemented here. See docs/publishing.md in that repo.

    uv run vf-eval zenml-bench -m <model>            # after `prime env install` or a local `uv pip install -e .`
"""
from pathlib import Path

import verifiers.v1 as vf
from verifiers.v1.tasksets.harbor import HarborConfig, HarborTask, HarborTaskset

REPO = "zenml-io/zenml-bench"


class ZenmlBenchConfig(HarborConfig):
    # Hub id once published (`harbor publish`): "zenml/zenml-bench@0.1.0". Until then, resolve the dataset from the
    # repo's registry.json via Harbor's --repo route, pinned to the v0.1 tag.
    dataset: str = "zenml-bench@0.1.0"
    repo: str | None = f"{REPO}@v0.1"
    registry_path: Path | None = Path("registry.json")
    # Keep the task-authored timeouts: the research tasks (r1-clock, r1-bare-clock) state a wall-clock budget in the
    # instruction, and dropping it changes the task.
    ignore_timeouts: bool = False


class ZenmlBenchTaskset(HarborTaskset, vf.Taskset[HarborTask, ZenmlBenchConfig]):
    pass


def load_taskset(config: ZenmlBenchConfig | None = None) -> ZenmlBenchTaskset:
    return ZenmlBenchTaskset(config or ZenmlBenchConfig())
