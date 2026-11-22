You are working in `/app`, the repository of the team that runs the appointment assistant for a chain of veterinary clinics. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 20 July 2026 and holds the conversations of 1 June to 20 July 2026 for the agent `booking-agent`.

The cost of the assistant's model calls per conversation rose by more than a third between the week before 21 June and the week after 25 June. Release 1.2.0 rolled out on exactly those days, and the team wants to know whether the release did it.

Find out what raised the cost, then record your answer:

1. Create a Kitaru cohort named `cost-rise`, for the agent `booking-agent`. It holds the conversations that account for the rise, over the whole period since it began: the ones that would not have happened, or would have cost what an ordinary conversation costs, without the cause.
2. Write `/app/answer.json` with one field, `cause`, set to one of these:
   - `new_release`: a release of the assistant changed what a conversation costs
   - `traffic_mix_changed`: a different kind of conversation started arriving; the assistant handles each kind as it did before
   - `model_changed`: another model, or other prices, for the same calls
   - `retry_loop`: calls being repeated
   - `config_changed`: a setting in `agent/config.yaml`
   - `prompt_grew`: longer instructions sent with every call

How it is graded: the members of the cohort `cost-rise` as Kitaru has stored them when you finish, and the field of `/app/answer.json`. For the cohort: at least 90% of its members must be conversations that belong in it, and it must hold at least 90% of the conversations that belong in it. If the cohort has several versions, the latest one counts. The cause must be right. Do not delete or change any conversation, and do not change or commit anything in this repository except `/app/answer.json`.
