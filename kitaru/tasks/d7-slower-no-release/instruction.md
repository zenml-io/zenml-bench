You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026 and holds the conversations of 1 June to 30 July 2026 for the agent `returns-agent`.

For part of July the assistant's replies took noticeably longer than usual, then went back to normal. The team shipped nothing in that period that should have changed speed.

Find out what changed, then record your answer:

1. Create a Kitaru cohort named `slower-replies`, for the agent `returns-agent`, that holds every conversation that was affected by the change.
2. Write `/app/answer.json` with two fields:
   - `cause`: one of `new_release`, `served_model_changed`, `tool_slower`, `retry_loop`, `longer_conversations`, `traffic_increase`
   - `first_affected_day`: the date (UTC) of the first affected conversation, as `YYYY-MM-DD`

How it is graded: the members of the cohort `slower-replies` as Kitaru has stored them when you finish, and the two fields of `/app/answer.json`. For the cohort: at least 90% of its members must be conversations that belong in it, and it must hold at least 90% of the conversations that belong in it. If the cohort has several versions, the latest one counts. Both fields must be right. Do not delete or change any conversation.
