You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026 and holds the conversations of 1 June to 30 July 2026 for the agent `returns-agent`.

The bill for the assistant's model calls was far above normal on two separate days in this period. The team wants to know what happened on each.

Find the two days, then record your answer. Call the earlier day spike 1 and the later day spike 2.

1. Create two Kitaru cohorts for the agent `returns-agent`, named `cost-spike-1` and `cost-spike-2`. Each holds the conversations that account for that day's extra cost: the ones that would not have happened, or would have cost what a normal conversation costs, without that day's cause.
2. Write `/app/answer.json` in this shape:

```json
{"cost-spike-1": {"date": "YYYY-MM-DD", "cause": "..."}, "cost-spike-2": {"date": "YYYY-MM-DD", "cause": "..."}}
```

   Dates are UTC. Each `cause` is one of `new_release`, `served_model_changed`, `retry_loop`, `longer_replies`, `traffic_increase`, `price_change`.

How it is graded: the members of the two cohorts as Kitaru has stored them when you finish, and `/app/answer.json`. For each cohort: at least 90% of its members must be conversations that belong in it, and it must hold at least 90% of the conversations that belong in it. If the cohort has several versions, the latest one counts. Both dates and both causes must be right. Do not delete or change any conversation.
