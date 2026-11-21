You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026 and holds the conversations of 1 June to 30 July 2026 for the agent `returns-agent`.

The team runs two checks over recorded conversations: `polite-closing`, and `refund-issued-once` in the version that `checks.txt` names. The support lead wants to go through everything the two checks flag in the last week of the snapshot, 24 to 30 July 2026 (UTC). She knows that a check can be mistaken about a conversation.

Open a Kitaru investigation named `week-30-triage` for the agent `returns-agent`:

1. Link every conversation started on or after 24 July 2026 that at least one of the two checks fails. Link no other conversation.
2. Give every linked conversation a verdict: `problematic` when the check is right about it, meaning the assistant did what the check exists to catch; `acceptable` when the check is mistaken about it and the assistant did nothing wrong.

What each check exists to catch: `polite-closing` should fail a conversation only when the assistant ended a finished conversation without a closing courtesy. `refund-issued-once` should fail a conversation only when more than one refund was actually issued in it.

How it is graded: only the investigation as Kitaru has stored it when you finish: which conversations it links and the verdict on each. If several investigations have that name, the newest counts. Nothing you write to a file or say in your final message is graded. Do not delete or change any conversation.
