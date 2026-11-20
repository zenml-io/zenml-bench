You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026 and holds the conversations of 1 June to 30 July 2026 for the agent `returns-agent`.

The support lead has time to read six conversations from the last week of the snapshot, 24 to 30 July 2026 (UTC). She wants the ones in which the assistant got something wrong: it broke one of the shop's rules or one of the team's expectations. `README.md`, the team's evaluators and the reviewers' verdicts on the cohort `reviewed-july` show what those are. She does not want conversations in which the assistant did nothing wrong, and some of the team's checks fail conversations that are fine.

Open a Kitaru investigation named `week-30-review` for the agent `returns-agent`:

1. Link between three and six conversations, all started on or after 24 July 2026, and in every one of them the assistant got something wrong.
2. The linked conversations must show at least two different kinds of mistake.
3. Give every linked conversation the verdict `problematic`.

How it is graded: only the investigation as Kitaru has stored it when you finish: which conversations it links and the verdict on each. If several investigations have that name, the newest counts. Nothing you write to a file or say in your final message is graded. Do not delete or change any conversation.
