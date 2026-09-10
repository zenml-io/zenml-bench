# RL-training a small open model on zenml-bench tasks: Tinker, prime-rl, and the alternatives

Status: research note, 10 September 2026. Sources are primary (official docs, repos, pricing pages) and every claim carries a URL. Verbatim quotes are in quotation marks; everything else is paraphrase. Items I could not confirm are marked "not verified".

## 0. The short answer

The plumbing exists and is better than expected. Three separate trainers can consume our Harbor task directories unchanged: Thinking Machines' Tinker cookbook (`harbor_rl` recipe), Prime Intellect's verifiers v1 (built-in Harbor taskset, trainable in prime-rl or their hosted Lab), and SkyRL (`examples/train_integrations/harbor`). Harbor 0.22.0 itself, the version we have installed, ships a Tinker backend for its Terminus 2 agent that records the exact token IDs and log-probabilities of every model call, which is the piece that makes a trajectory usable for training.

The hard part is not the trainer. It is that our episodes are long (a frontier model needs 8 to 13 minutes and 20 to 25 tool calls on R1), our reward is 0/1, and a 4B to 9B model has a 32K to 64K context window. Every published small-model result on Terminal-Bench-style tasks ends in the single digits to mid-twenties percent, and every one of them built thousands of easier tasks first because a reward that is almost always 0 teaches nothing. Our benchmark has about twenty tasks. So the realistic plan is: baseline first, and expect the answer to "is it saturated?" to be "no, it is at the floor", which is the opposite problem.

## 1. Tinker

### What it is

Tinker is a hosted training service where you write the training loop on your laptop and their GPUs do the heavy lifting. Their own words: "A cloud training API that gives you full control over your data, algorithms, and models. Write training loops locally — Tinker handles the GPUs." (https://tinker-docs.thinkingmachines.ai/). It only trains LoRA adapters, meaning a small set of extra weights bolted onto a frozen base model rather than changing every weight: "Tinker implements low-rank adaptation (LoRA) fine-tuning, not full fine-tuning" (https://tinker-docs.thinkingmachines.ai/lora-primer).

The four calls you build a loop from are `forward_backward` (compute gradients), `optim_step` (apply them), `sample` (generate text from the current weights), and `save_state` (https://thinkingmachines.ai/tinker/). Two kinds of checkpoint exist: `save_weights_for_sampler` saves weights only, for generating text, while `save_state` also saves the optimizer state so you can resume training (https://tinker-docs.thinkingmachines.ai/tutorials/core-concepts/weights/). Checkpoints are addressed by paths like `tinker://<run_id>/sampler_weights/<name>`.

### Models available today

The model list moved to https://tinker-docs.thinkingmachines.ai/tinker/models/ (the old pricing and available-models URLs now 404). Small options relevant to us, with their training price per million tokens from that page:

| Tinker ID | Size | Context | Train $/M tokens |
|---|---|---|---|
| `Qwen/Qwen3.5-4B` | 4B dense | 64K | 0.737 |
| `Qwen/Qwen3.5-9B` | 9B dense | 64K | 1.463 |
| `Qwen/Qwen3-8B` | 8B dense | 32K | 0.44 |
| `openai/gpt-oss-20b` | 21B, 3.6B active | 32K | 0.396 |
| `Qwen/Qwen3.6-35B-A3B` | 35B MoE, 3B active | 64K | 1.177 |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` | 30B MoE, 3B active | 64K | 0.44 |

Llama is gone. The page lists a 12 June 2026 retirement of "Llama-3.3-70B-Instruct, Llama-3.1-70B, Llama-3.1-8B, Llama-3.1-8B-Instruct, Llama-3.2-3B, Llama-3.2-1B", and also of `Qwen3-30B-A3B`, `Qwen3-32B` and `Qwen3-4B-Instruct-2507`. Some docs pages still show Llama-3.1-8B in example commands; those are stale.

### Pricing and access

Sign-up is a plain link with no waitlist wording: "Join here. If you're a university or organization looking for wide scale access, contact" them (https://thinkingmachines.ai/tinker/). Billing: "All prices are per million tokens. Checkpoint storage is charged at $0.10 per GB per month." and "We provide an 80% discount on cached prefill tokens." (https://tinker-docs.thinkingmachines.ai/tinker/models/). Three prices per model: prefill (reading the prompt), sample (generating), train. For `Qwen/Qwen3.5-4B` they are $0.33, $1.005 and $0.737 per million. Whether new accounts get free credits: not verified, no docs page says.

### The RL recipe and its Env abstraction

The cookbook's RL code lives in `tinker_cookbook/rl/` (https://github.com/thinking-machines-lab/tinker-cookbook/tree/main/tinker_cookbook/rl). An environment is a small class with two methods. From `types.py` (https://raw.githubusercontent.com/thinking-machines-lab/tinker-cookbook/main/tinker_cookbook/rl/types.py):

```python
Action: TypeAlias = list[int]          # the tokens the model produced
Observation: TypeAlias = tinker.ModelInput   # the tokens the model sees next

class Env(ABC):
    async def initial_observation(self) -> tuple[Observation, StopCondition] | InitialObservationOverflow: ...
    async def step(self, action: Action, *, extra: ActionExtra | None = None) -> StepResult: ...
```

`StepResult` carries `reward`, `episode_done`, `next_observation`, `next_stop_condition`. Notice that actions and observations are lists of token IDs, not text. That is deliberate: the trainer never re-tokenizes anything, so the tokens it trains on are exactly the tokens the model produced. An `EnvGroupBuilder` makes a group of environments that share a prompt (the "group" in GRPO-style training, where each rollout's reward is compared against its siblings), and an `RLDataset` hands out batches of builders.

The training loop (`rl/train.py`) supports an async mode: `async_config` with `max_steps_off_policy`, documented as "If samples are generated from a sample more than this many steps ago, we will skip training on them". The default loss is `importance_sampling`, with `ppo` and CISPO as alternatives; all three correct for the sampled tokens having come from a slightly older version of the weights (https://tinker-docs.thinkingmachines.ai/tutorials/core-concepts/loss-functions/). There is a `rollout_error_tolerance` knob, a retry budget for flaky sandboxes, which we will need.

### The Harbor integration: `harbor_rl`

This is the recipe that matters. It is described as "RL training on Harbor formatted tasks (e.g., Terminal Bench 2.0) with sandboxed code execution" (https://tinker-docs.thinkingmachines.ai/cookbook/recipes/harbor-rl/). It reads task directories with exactly our layout (`environment/Dockerfile`, `tests/test.sh`, `instruction.md`, `task.toml`).

How one episode runs, from `harbor_env.py` and `harbor_tools.py` (https://raw.githubusercontent.com/thinking-machines-lab/tinker-cookbook/main/tinker_cookbook/recipes/harbor_rl/harbor_env.py, https://raw.githubusercontent.com/thinking-machines-lab/tinker-cookbook/main/tinker_cookbook/recipes/harbor_rl/harbor_tools.py):

1. The recipe builds the task's Dockerfile into a Modal image (`modal.Image.from_dockerfile`) and starts a Modal sandbox. Modal is the only sandbox backend; "No local backend is present". The sandbox protocol is five methods (`run_command`, `read_file`, `write_file`, `send_heartbeat`, `cleanup`), so a local-Docker backend would be ours to write.
2. The model gets one tool, `bash`, with output capped at 16,384 characters and a 120-second default command timeout.
3. When the episode ends, the recipe uploads `tests/` into the sandbox, runs `bash /tests/test.sh`, and reads the reward from `/logs/verifier/reward.txt`, else `reward.json["reward"]`, else 0.0. Grader timeout defaults to 60 seconds. Our graders write `reward.json`, so they work as-is, but our verifier budgets (`[verifier] timeout_sec = 900` on R1) are far above 60 seconds and would need the knob raised.
4. Defaults in `train.py`: `max_turns = 10`, `max_trajectory_tokens = 32 * 1024`, `context_overflow_reward = -0.1`, `group_size = 4`, `groups_per_batch = 8`.

Their own evaluation numbers are sobering. With Kimi-K2.6 at 32K context and 200 turns they report SWE-Bench Verified 29.0% and Terminal-Bench 2.0 15.7%, and "All ERRORs are context window overflow (`prompt_tokens + max_tokens > 32768`)"; the harness has "no advanced features like context compatification" (same recipe page). For a 10-to-25-minute episode where the agent runs a ZenML pipeline and reads its logs, this is the main risk.

Two more relevant recipes: `verifiers_rl` ("allows all text-based environments from the Environments Hub to be used with Tinker", https://tinker-docs.thinkingmachines.ai/cookbook/recipes/verifiers-rl/) ships a `TinkerAsyncOpenAIClient` that looks like an OpenAI client but samples from Tinker in-process, returning tokens and log-probabilities; and `agent_rl` trains tool discovery over MCP in Modal containers (https://tinker-docs.thinkingmachines.ai/cookbook/recipes/agent-rl/).

### Sampling from a checkpoint outside the training loop

Yes, three ways.

OpenAI-compatible HTTP: base URL `https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1`, Tinker API key as bearer token, model ID equal to a checkpoint path such as `tinker://.../sampler_weights/000043` or a base model name. "Both /completions and /chat/completions endpoints are supported" and "You can keep training and sample from the same checkpoint simultaneously." But: "Currently, OpenAI-compatible inference is meant for testing and internal use with low internal traffic, rather than large, high-throughput, user-facing deployments." (https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/openai/). Whether it accepts a `tools` argument for function calling is not documented; not verified.

Anthropic-compatible HTTP: `https://tinker.thinkingmachines.dev/services/tinker-prod/anthropic/api`; "Point `ANTHROPIC_BASE_URL` at Tinker" to run Claude Code against your checkpoint, with tool use supported (https://tinker-docs.thinkingmachines.ai/tinker/compatible-apis/anthropic/). Same low-traffic caveat.

Download the weights: `weights.download()` "fetches a checkpoint archive from Tinker storage and extracts it to a local directory"; `build_lora_adapter()` produces a HuggingFace-format adapter "for serving with vLLM or SGLang"; `build_hf_model()` merges it into the base (https://tinker-docs.thinkingmachines.ai/tutorials/deployment/lora-adapter/, https://tinker-docs.thinkingmachines.ai/tutorials/deployment/export-hf/).

### Tokenization consistency

Tinker's answer to the "did the trainer see the same tokens the model produced?" problem is its `renderers` package, which replaces HuggingFace chat templates. "Tinker's default renderers are designed to produce identical tokens to HuggingFace's apply_chat_template." with one exception for a multi-turn efficiency mode on thinking models (https://tinker-docs.thinkingmachines.ai/rendering). Because the RL loop passes token lists rather than text, and the sampled log-probabilities go straight into the training record, there is no re-tokenization step where drift could creep in. Multi-turn efficiency note: if each turn's prompt is the previous prompt plus the previous answer as a prefix, the whole episode trains as one sequence; if not, it is one sequence per turn, which is much more expensive (https://tinker-docs.thinkingmachines.ai/rl/sequence-extension).

### Harbor already has a Tinker backend (local finding)

The Harbor we have installed (0.22.0) contains `harbor/llms/tinker.py`, a `TinkerLLM` class that "can be used as a drop-in replacement for LiteLLM when running Terminus 2 agent evaluations" and is selected with `llm_backend="tinker"` on Terminus 2. It takes `model_name` (base model, e.g. `Qwen/Qwen3-8B`) and optional `model_path` (`tinker://run-id/weights/checkpoint-001`), picks the renderer via `tinker_cookbook.model_info`, samples with `sampling_client.sample_async`, and with `collect_rollout_details=True` stores `prompt_token_ids`, `completion_token_ids` and `logprobs` per call. Terminus 2 collects those into `AgentContext.rollout_details` (`harbor/models/agent/rollout_detail.py`). The extra is `uv pip install harbor[tinker]` and pulls `tinker>=0.14.0` and `tinker-cookbook>=0.1.0`. The litellm backend does the equivalent for vLLM servers by sending `logprobs=True` and `extra_body["return_token_ids"]=True` (`harbor/llms/lite_llm.py`). Harbor's RL docs confirm this direction: rollouts need tokens either by "Intercepting tokens from a vLLM server" or "Returning tokens as part of the agent result metadata" (https://www.harborframework.com/docs/training-workflows/rl).

So there are two ways to pair Tinker with our tasks: the cookbook's `harbor_rl` recipe (its own bash-tool agent, Modal sandboxes), or Harbor's Terminus 2 with `llm_backend=tinker` producing token-level trajectories that a custom loop feeds to `forward_backward`. A third-party project, `abundant-ai/harbor-trainer`, claims to do exactly the second thing (https://github.com/abundant-ai/harbor-trainer); not verified beyond its README.

## 2. prime-rl and verifiers

### Architecture

prime-rl runs three processes (https://docs.primeintellect.ai/prime-rl/overview). Inference is a "vLLM-backed server (or fleet) holding the current policy". The orchestrator is a "Lightweight CPU process that owns the data plane across many verifiers training and eval environments": it runs the multi-turn rollouts, computes advantages, packs batches. The trainer is an "FSDP2 process group that consumes packed rollouts and steps the optimizer". Rollouts move orchestrator to trainer over ZMQ; weights move trainer to inference over NCCL, or via the filesystem when LoRA is on.

It is asynchronous by design: "while the trainer is producing π_n from rollouts at step n, inference is already generating the rollouts for step n+1 using π_{n-1}" (https://docs.primeintellect.ai/prime-rl/algorithms). Staleness is bounded: "requests are dropped if they were generated by too old a policy; you control this with the max_off_policy_steps value" (https://www.primeintellect.ai/blog/rl-at-1t-scale). The default loss is IPO, "an importance-weighted policy-gradient term with a squared log-ratio KL regularizer", with GRPO-style group baselines. LoRA is supported by adding `[model.lora]` with `rank`, `alpha`, `target_modules` (https://github.com/PrimeIntellect-ai/prime-rl, `docs/advanced.md`). Model families listed in the README table include Qwen3, GLM, GPT-OSS, Nemotron, MiniMax.

### Hardware if you run it yourself

"You need at least one NVIDIA GPU (RTX 3090/4090/5090, A100, H100, H200, or B200). Single-GPU runs are supported for debugging." The realistic minimum is two GPUs, one for inference and one for training; `configs/basic/` are "small, 2-GPU (1 trainer + 1 inference) configs" (https://docs.primeintellect.ai/prime-rl/overview). The closest example to our size, `examples/basic/wiki-search`, trains Qwen3-4B with LoRA rank 8 on "8 GPUs (6 for inference, 2 for training)". No document states a minimum for an 8B model specifically; not verified.

### Hosted training: Lab

Prime Intellect runs a hosted training service and it is out of beta: "Today, Lab is out of beta and generally available to everyone." Lab "trains a LoRA adapter with our open-source prime-rl trainer" and is multi-tenant, "which is what lets us price runs per token rather than per cluster-hour" (https://www.primeintellect.ai/blog/lab-is-open). Workflow: `prime lab setup`, `prime train init`, `prime train run configs/rl/<x>.toml`, `prime train logs <id> -f` (https://docs.primeintellect.ai/hosted-training/getting-started).

Prices per million tokens, input / output / train (https://docs.primeintellect.ai/hosted-training/models-and-pricing):

| Model | Input | Output | Train |
|---|---|---|---|
| Qwen3.5-4B | 0.10 | 0.30 | 0.30 |
| Qwen3.5-9B | 0.20 | 0.60 | 0.60 |
| Qwen3.5-35B-A3B | 0.25 | 0.75 | 1.00 |
| gpt-oss-20b | 0.10 | 0.30 | 0.40 |
| Nemotron-3.5-Lightning-30B-A3B | 0.15 | 0.45 | 0.60 |

That is roughly two to three times cheaper per token than Tinker for the same models. Environments supported: "single-turn Q&A, multi-turn tool calling, stateful sandbox sessions, etc." (https://docs.primeintellect.ai/hosted-training/environment-model). Full fine-tuning "is in closed beta. Access is gated per-team" (https://docs.primeintellect.ai/hosted-training/full-finetuning). Not verified: any wall-clock limit per rollout on hosted runs, and whether sandbox time is billed on top.

### How an environment is defined

verifiers has two generations. The legacy classes (https://docs.primeintellect.ai/verifiers/legacy/environments): `MultiTurnEnv` "implements the main rollout loop"; `SingleTurnEnv` is that with one turn; `ToolEnv` adds tool calling; `StatefulToolEnv` lets the environment inject hidden arguments; `SandboxEnv` and `PythonEnv` "handle containerized execution automatically"; `CliAgentEnv` "runs agent code in remote sandboxes with API interception". A module exposes `load_environment(...)` returning an env. The loop, in their words:

```python
state = await self.setup_state(state)
while not await self.is_completed(state):
    prompt_messages = await self.get_prompt_messages(state)
    response = await self.get_model_response(state, prompt_messages)
    await self.add_model_response(state, prompt_messages, response)
```

You implement `env_response(messages, state) -> messages` (what the world says back) and, optionally, `setup_state`.

verifiers v1 (July 2026) splits this into three parts: "A taskset defines the work to be done, i.e. the data, tools, and scoring. A harness is the program that solves the task and produces a rollout ... The rollout happens inside a runtime, which can be local (as a subprocess or Docker) or in sandboxes" (https://docs.primeintellect.ai/verifiers/v1/architecture). The key mechanism: "The harness does not call the provider endpoint directly"; instead "model traffic goes through an interception server" that records every request, and in training mode records tokens and log-probabilities. That is what lets an unmodified CLI agent (Codex, Claude Code, Terminus 2, mini-SWE-agent) be trained on: the harness thinks it is talking to OpenAI, but the proxy is writing down every token. Harnesses shipped: "Claude Code, Codex, the tool-enabled `bash` harness, the CDP-driven `browser_use` harness, and the minimal tool-less `null` harness" (https://docs.primeintellect.ai/verifiers/v1/harnesses), plus Terminus 2, Kimi Code and Mini-SWE-Agent per the v1 announcement (https://www.primeintellect.ai/blog/verifiers-v1).

### Harbor tasks in verifiers v1

There is a built-in Harbor taskset. Porting Terminal-Bench 2 is a subclass: `class TerminalBench2Config(HarborConfig): dataset = "terminal-bench/terminal-bench-2"`. "No need for a reward function, as it will get inherited from the Harbor dataset"; "The score is read from `/logs/verifier/reward.json`" (https://docs.primeintellect.ai/verifiers/v1/harbor). Task timeouts are ignored by default (`ignore_timeouts = true`). The first sandbox using an image triggers a platform build "(for VM sandboxes this build can take ~10 minutes)", after which starts take seconds.

### Sandboxes

Prime sandboxes are "disposable, isolated environments for AI-assisted coding, benchmarking, and quick experiments" (https://docs.primeintellect.ai/sandboxes/overview). They now boot Docker images as hardware-isolated microVMs (Docker-in-sandbox works). Custom images: "push your own Docker images and use them in sandboxes with all your dependencies pre-installed". Pricing: CPU $0.05 per core-hour, memory $0.01 per GB-hour, disk $0.001 per GB-hour; their example "1 CPU, 2 GB RAM, 10 GB disk = $0.08/hour". Limits: 1 to 16 cores, 64 GB RAM, timeout default 60 minutes and can be removed; account cap 512 active sandboxes. One `execute_command` call runs at most 15 minutes (https://docs.primeintellect.ai/sandboxes/sdk). That 15-minute limit matters for our R1 task, where a single pipeline run can take a few minutes; it is per command, not per episode, so it is fine unless an agent chains everything into one command.

### Existing terminal and SWE environments

The official catalog `PrimeIntellect-ai/research-environments` (https://github.com/PrimeIntellect-ai/research-environments) has a `terminal/` group (`terminal_bench_2`, `tmax` with 14,600 tasks, `terminal_lego`, `openthoughts_tblite`) and a `swe/` group (`swebench_verified`, `swesmith_env`, `r2e_gym`, `deep_swe`, and more). Their scaling post claims "~135,000 prebuilt task images co-located with sandboxes" (https://www.primeintellect.ai/blog/scaling-agentic-rl). prime-rl's own examples for SWE and terminal work are at 30B and above; the one concrete throughput figure is "GLM-4.5-Air in a custom harness on ScaleSWE ... on 6 H200 nodes in 2 days" (https://github.com/PrimeIntellect-ai/prime-rl/tree/main/examples). No small-model terminal example ships.

### Token consistency

prime-rl uses a separate `renderers` package with the same philosophy as Tinker's: "For RL the trainer must see the exact token ids the sampler saw." (https://github.com/PrimeIntellect-ai/renderers). Their measured example of what goes wrong when you re-render text with a chat template: on Qwen3.5-35B, full re-rendering produced "77 training samples from 64 rollouts (32 breaks)" versus zero breaks when carrying tokens forward. Concretely: the template turns a tool result `false` into the string `"False"`, or splits a word into different byte-pair pieces, and the trainer is now scoring tokens the model never emitted. The orchestrator therefore drives rollouts "without re-tokenizing across turns" (https://docs.primeintellect.ai/prime-rl/overview).

## 3. Other options, one paragraph each

SkyRL (Berkeley Sky Lab and Anyscale, https://github.com/NovaSky-AI/SkyRL) has the most direct Harbor integration of any self-run trainer: "SkyRL never manages the sandbox or agent directly. The vLLM inference engine is exposed as an HTTP endpoint, and the Harbor agent calls it through LiteLLM as if it were any OpenAI-compatible API." (https://docs.skyrl.ai/docs/harbor). It runs Harbor's own `terminus-2` by default with `max_turns: 32`, reads the reward from Harbor's verifier result, and supports `daytona, docker, e2b, modal, runloop, gke` as sandbox types. Its example trains `Qwen/Qwen3-8B` on 8 GPUs (4 inference engines, tensor-parallel 2) with 32K context and 8 samples per prompt (`examples/train_integrations/harbor/run_codecontest.sh`). LoRA exists since v0.2.0 but with caveats ("LoRA adapters are saved to disk and reloaded rather than synchronized in-memory", https://skyrl.readthedocs.io/en/latest/examples/lora.html) and no shipped example combines it with the Harbor path. Harbor's RL docs name SkyRL as the implemented integration: "we have worked with the SkyRL team to implement their interface for RL on Harbor tasks" (https://www.harborframework.com/docs/training-workflows/rl). Self-run only; you rent 4 to 8 H100-class GPUs.

OpenPipe ART (https://github.com/OpenPipe/ART) is alive after the CoreWeave acquisition (release v0.5.19 on 14 August 2026) and its hosted path is now W&B Training "Serverless RL" with a `ServerlessBackend`; "Full training runs typically cost $15-200 in GPU time" (https://art.openpipe.ai/getting-started/installation-setup). The model sits behind an OpenAI-compatible client, LoRA is the default, and trajectories "support tool calls and responses". But there is no sandbox or coding-agent example, and the docs flag "Qwen 3 family (with limitations for multi-turn workflows)". We would write the Harbor-to-trajectory plumbing ourselves.

Unsloth GRPO (https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide) is a memory-efficient layer under TRL for single-GPU training; it reports "54.33GB total memory for Llama 3.1 8B" at 20K context with 8 generations. Its own loop is single-turn reward functions. For agents it points at ART: "ART (Agent Reinforcement Trainer) built on top of Unsloth's GRPOTrainer, is a tool that makes training multi-turn agents possible and easy." (https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide/training-ai-agents-with-rl). Not an agentic RL loop on its own.

HuggingFace TRL (v1.13.0, 10 September 2026) has a native Harbor adapter, `trl.experimental.harbor.HarborSpec(dataset, agent="bash", environment_type="docker"|"e2b"|"daytona"|"modal")`, whose reward "reads the Harbor verifier's scalar per rollout"; the example uses `Qwen/Qwen3-4B` with 8 generations and 25 tool-call iterations (https://huggingface.co/docs/trl/harbor). Two caveats: it trains TRL's own bash harness, not Terminus 2 ("TRL's integration is the external-agent pattern, and only that pattern is supported for now"), and "sandbox provisioning is therefore sequential across the generation batch", which is bad for 10-minute episodes. A second path, `AsyncGRPOTrainer` with a `HarnessRolloutWorker` and an OpenEnv proxy, captures "each turn's token ids and logprobs" from a real agent (OpenCode); the HF blog trained Qwen3-8B on 2×H200 and moved reward from 0.27 to 0.71 in 10 steps on 32 problems (https://huggingface.co/blog/sergiopaniego/trl-openenv-harness-training). LoRA via `peft_config`. Cheapest self-run entry at 1 to 2 GPUs.

Modal (https://modal.com/pricing) is a hosting option rather than a trainer: H100 about $3.95/hour, A100-80GB about $2.50/hour, L40S about $1.95/hour, CPU about $0.047 per core-hour. Sandboxes take custom images with "a timeout of up to 24 hours" (https://modal.com/docs/guide/sandbox); the Starter plan allows "100 containers + 10 GPU concurrency", Team "5000 containers + 50 GPU concurrency". Modal is the sandbox backend for Tinker's `harbor_rl`, one of SkyRL's options, and a TRL option, so a Modal account is useful whichever trainer we pick. Their published RL example is single-turn GRPO on TRL (https://modal.com/docs/examples/grpo_trl).

Briefly: verl has a generic multi-turn "agent loop" interface but no first-party Harbor loop (https://verl.readthedocs.io/en/latest/advance/agent_loop.html). NVIDIA NeMo Gym lists Harbor among its environment libraries and NeMo RL supports LoRA GRPO, but Gym is "in early development" (https://github.com/NVIDIA-NeMo/Gym). rLLM's DeepSWE trained Qwen3-32B for "six days on 64 H100 GPUs" with "512 Docker containers in parallel" (https://www.together.ai/blog/deepswe), which is the scale of a serious agentic run.

### Published small-model results on Terminal-Bench-style tasks

| Work | Model | Hardware | Terminal-Bench 2.0 before → after |
|---|---|---|---|
| Endless Terminals (https://arxiv.org/abs/2601.16443) | Llama-3.2-3B, Qwen2.5-7B, Qwen3-8B | "4 A100s for about 2 days"; "8 B200s for about 8 hours" | 0→2.2%, 2.2→3.4%, 1.1→6.7% |
| OpenThoughts-Agent v1 (https://www.openthoughts.ai/blog/agent) | Qwen3-8B | "24xA100" (RLOO) | 0→4.9% (SFT), RL gain "~2%" |
| TMax (https://arxiv.org/abs/2606.23321) | Qwen3.5 2B to 27B | 8 H100 nodes, "2–3 days" | 9B reaches 27% |
| terminal-bench-rl (https://github.com/Danau5tin/terminal-bench-rl) | Qwen3-8B | "2x A100s ... for over 60 steps" | 13.75% (TB-1 era) |

Every one of these built or used thousands of tasks (Endless Terminals ~2,500, TMax 14,600). All of them note that plain GRPO is unstable on this kind of reward; TMax says "naive GRPO struggles to remain stable".

## 4. The hard part, stated concretely

Episode length and throughput. Our R1 comparison runs with Claude Code took 8 to 13 agent-minutes, 19 to 25 tool calls, and 1 to 3 pipeline runs each (`results/r1-clock-improve-within-budget-cmp.jsonl`). A small model will be slower and clumsier, so plan on 15 minutes. Suppose 64 rollouts per training step and 100 steps, which is a modest run:

| Parallel containers | Waves per step | Minutes per step (15 min episode + ~3 min build and grade) | Wall clock for 100 steps |
|---|---|---|---|
| 64 | 1 | ~18 | ~30 hours |
| 16 | 4 | ~72 | ~5 days |
| 4 (a laptop) | 16 | ~290 | ~20 days |

Total container time is 6,400 episodes × 0.3 hours ≈ 1,900 container-hours. At Prime sandbox prices for 2 cores and 4 GB (about $0.14/hour) that is roughly $270; at Modal CPU prices roughly $250. Async training (prime-rl's default, Tinker's `async_config`) hides some of this by generating the next batch while the current one trains, but it cannot make a 15-minute episode shorter.

Token cost. Each turn re-sends the whole conversation, so prefill dominates. If a 40-turn episode averages 16K tokens of prompt per turn, that is 640K prefill tokens and perhaps 20K generated tokens per episode; over 6,400 episodes that is about 4 billion prefill tokens. On Tinker's `Qwen3.5-4B` prices ($0.33 prefill, with an 80% discount on cached prefix) the prefill is $270 to $1,350 depending on cache hit rate, sampling about $130, training about $150. On Prime Lab ($0.10 input, $0.30 output, $0.30 train for the same model) roughly a third of that. Order of magnitude: $500 to $2,000 in tokens for a 100-step run, plus sandboxes.

Sparse 0/1 reward. GRPO-style training compares each rollout to its siblings on the same task. If all 8 rollouts of a task score 0, the group carries no signal and is discarded (Tinker's `remove_constant_reward_groups`). If a 4B model scores 0 on nineteen of our twenty tasks, almost every batch is empty and nothing is learned. This is why every published small-model run built thousands of easier tasks first. Our lever is the research family's continuous metric (`gap_closed`) and per-task shaped signals, but the plan's rule 6 (binary reward for the score, extra numbers as metrics) exists for good reason: a trainer will optimise the shaped number rather than the real outcome. A safer middle ground is a curriculum of easier variants (smaller budgets, more hints) that produce some 1s, not partial credit on the real tasks.

Credit assignment. With one reward at the end of a 40-turn episode, every token in every turn gets the same advantage. That is standard (Tinker's `harbor_rl`, prime-rl, SkyRL all do it) and it works, slowly. Tinker's cookbook has a `multiturn_weight_assignment_test.py` covering the token bookkeeping; nothing more clever ships.

Context length. Tinker's own Harbor recipe reports every error as context overflow at 32K. Our tasks print pipeline logs, ZenML CLI output and stack traces. A 64K model (`Qwen3.5-4B`, `Qwen3.5-9B`) is the minimum sensible choice, and the harness should truncate tool output aggressively (Tinker's recipe caps at 16K characters per command; Terminus 2 has `enable_summarize`).

The off-policy-by-mistake problem. The model produced tokens; the harness turned them into text; the trainer re-tokenizes the text with a chat template and gets slightly different tokens. Now the trainer computes probabilities for tokens the model never emitted, the importance ratios blow up, and training diverges without an obvious error. Both Tinker (`renderers`, token-list actions) and prime-rl (`renderers`, interception proxy) solve it by never round-tripping through text. Harbor's Terminus 2 with `llm_backend=tinker` or with vLLM's `return_token_ids` solves it the same way. The rule: whatever harness runs the rollout must hand the trainer token IDs and log-probabilities, never text.

Can the small model use the tools at all? Terminus 2 does not use native function calling; it asks the model to emit commands in a fixed text format that it parses (`terminus_json_plain_parser.py`, `terminus_xml_plain_parser.py`). That is friendlier to small models than JSON tool calls. TMax found a mini-SWE-agent-style harness beat Terminus 2 for small models (https://arxiv.org/abs/2606.23321). Expect the untrained baseline to fail mostly on format and on never running the pipeline, which is exactly what RL is good at fixing first.

## 5. Benchmark-first: running an open model on our tasks today

Harbor's `-m` flag takes a litellm model string and `--ak key=value` passes agent constructor arguments (`harbor run --help`). Which agents accept an arbitrary endpoint, from `harbor/agents/model_connection.py` and the agent sources in the installed 0.22.0:

- `terminus-2`: runs on the host, not in the container, and drives the container over tmux. The model call goes through litellm with `api_base` as a constructor argument and `llm_backend` either `litellm` or `tinker`. A local vLLM server is `-m hosted_vllm/Qwen/Qwen3.5-9B --ak api_base=http://localhost:8000/v1`; Harbor warns that "Model info is required when using hosted_vllm models" (`max_input_tokens`, `max_output_tokens`, cost fields), which is easiest to supply through a job config file rather than the CLI. Because the model call happens on the host, our tasks' `allowlist` network mode is irrelevant for this agent.
- `terminus-2` with `--ak llm_backend=tinker -m Qwen/Qwen3.5-9B`: samples the untrained base model from Tinker with the exact renderer the training loop will use, and records token IDs and log-probabilities into the trial. This is the cleanest baseline because it is the same tokenizer, same renderer and same sampling stack as the later training run. Needs `harbor[tinker]` and `TINKER_API_KEY`.
- `mini-swe-agent`: runs inside the container; reads `OPENAI_BASE_URL` or `OPENAI_API_BASE` and `MSWEA_API_KEY`, and passes provider env vars through. The container must be able to reach the endpoint, so the task's `allowed_hosts` needs the vLLM host or the provider added, or the run needs a network-open variant.
- `openhands`: inside the container; `LLM_BASE_URL` and `LLM_API_KEY`, or `--ak api_base=...`.
- `codex`: inside the container; provider fixed to `openai`, honours `OPENAI_BASE_URL`, so a vLLM or OpenRouter endpoint works if the model speaks the Responses API well enough.
- `claude-code`: inside the container; honours `ANTHROPIC_BASE_URL`, which is how Tinker's Anthropic-compatible endpoint would plug in.

Simplest first baseline with no GPU: OpenRouter. Harbor's provider table includes `openrouter` with `OPENROUTER_API_KEY` and base URL `https://openrouter.ai/api/v1`, so `harbor run -p tasks/r1-improve-within-budget --agent terminus-2 -m openrouter/qwen/qwen3.5-9b --env-file .env -k 3` runs today, once the key is in `.env`. Our `scripts/run_baselines.py` already takes `--agent harness:model`, so the same matrix machinery applies. OpenRouter cannot return token IDs, so it is for the pass-rate number only, not for trajectories.

## 6. Recommended path

Recommendation: Tinker for the training run, Terminus 2 as the harness, Modal as the sandbox, `Qwen/Qwen3.5-9B` (64K context) as the model, with `Qwen3.5-4B` as the cheap fallback. Prime Lab is the close second and cheaper per token; pick it instead if the verifiers v1 Harbor taskset runs our tasks without changes, because then there is nothing to write at all. SkyRL is the choice only if we rent GPUs anyway.

Steps, in order:

1. Baseline with no training (one day). Put an OpenRouter key in `.env`, run `terminus-2` on all tasks with `qwen/qwen3.5-9b` and `qwen/qwen3.5-4b`, 5 attempts each, using `run_baselines.py`. Expect near-zero pass rates; record per-task numbers and read a few trajectories to see whether failures are format, never running the pipeline, or context overflow.
2. Repeat the baseline through Tinker's sampler (half a day). Install `harbor[tinker]`, run `terminus-2 --ak llm_backend=tinker`, confirm `rollout_details` contains token IDs and log-probabilities. This proves the exact stack we will train through, and gives us trajectories to inspect.
3. Decide the reward and curriculum (one day of design). Pick the tasks with any nonzero rate. For the rest, write easier variants (larger clock, hint in the instruction, smaller pipeline). Keep the real tasks' reward binary. This step is where the run succeeds or fails.
4. Wire our tasks into `harbor_rl` (two to four days). The recipe needs: a Modal account and our base image pushed or built from the Dockerfile; the grader timeout raised from 60 seconds to our verifier budget; `max_turns` raised from 10 to something like 40; tool output truncation tuned; `setup_store.sh` semantics preserved (the recipe builds the image from `environment/`, which is where our seeded stores live, so this should hold). Alternatively, the Prime Lab route: subclass `HarborConfig` pointing at our task directory, `prime train run`, and see what breaks.
5. Small smoke run (one day, tens of dollars). 4 tasks, group size 4, 8 groups per batch, 5 steps. Check that rewards are not all zero, that no group is dropped for constant reward, and that the importance ratios stay near 1.
6. The real run (one to three days wall clock, $500 to $2,000 tokens plus $300 sandboxes). 100 steps, 64 rollouts per step, async on.
7. Re-benchmark (one day). Download the adapter, or point `terminus-2 --ak llm_backend=tinker --ak model_path=tinker://...` at the checkpoint, and rerun step 1 on the held-out tasks. Also rerun on a public Terminal-Bench subset to check we did not just overfit twenty tasks.

Pieces that need writing: the easier task variants (step 3); a small config and glue for `harbor_rl` (Modal image build from our base image, timeouts, turn caps); a script that turns a Harbor job directory into an aggregate reward table for the before/after comparison (`analyse_trajectories.py` mostly covers this); and, if we want Terminus 2 rather than the recipe's bash-tool agent during training, a training loop that consumes `rollout_details` from Harbor trials and calls `forward_backward` (this is the `harbor-trainer` shape, a few hundred lines, and the riskiest piece).

Main risks, in order: the reward is all zeros and the run learns nothing (mitigation: curriculum in step 3, and checking step 5 before spending); context overflow on pipeline logs (mitigation: 64K model, output truncation); grading time and flaky sandboxes at scale (mitigation: `rollout_error_tolerance`, generous grader timeout); overfitting to twenty tasks, which our held-out set and a Terminal-Bench subset will show; and the plan's own framing, which says training "is a free option created by the format; the project is not justified on it and nothing depends on it" (`docs/2026-09-09-plan.md`). This note does not change that; it says the option is real and costs roughly a week of work and low thousands of dollars to exercise.
