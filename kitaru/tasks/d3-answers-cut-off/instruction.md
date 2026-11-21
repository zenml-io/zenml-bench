You are working in `/app`, the repository of the team that runs the appointment assistant for a chain of veterinary clinics. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 20 July 2026 and holds the conversations of 1 June to 20 July 2026 for the agent `booking-agent`.

Customers report that the assistant's longer answers stop in the middle of a sentence. No release went out when this started.

Find out what happened, then record your answer:

1. Create a Kitaru cohort named `cut-off-answers`, for the agent `booking-agent`, that holds every conversation whose reply to the customer was cut off.
2. Write `/app/answer.json` with two fields:
   - `commit`: the id of the commit in this repository that caused it: the full id, or at least its first seven characters
   - `first_affected_day`: the date (UTC) of the first affected conversation, as `YYYY-MM-DD`

How it is graded: the members of the cohort `cut-off-answers` as Kitaru has stored them when you finish, and the two fields of `/app/answer.json`. For the cohort: at least 90% of its members must be conversations that belong in it, and it must hold at least 90% of the conversations that belong in it. If the cohort has several versions, the latest one counts. Both fields must be right. Do not delete or change any conversation, and do not change or commit anything in this repository except `/app/answer.json`.
