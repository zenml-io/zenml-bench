You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

The team's `polite-closing` check (source: `evaluators/polite_closing.py`) fails about one conversation in twenty. Either the assistant is being rude to customers that often, or the check is wrong. Find out which, and repair what is at fault.

The team's intent for the check: a conversation should fail only when the assistant ended a finished conversation without a closing courtesy.

If the check is at fault, register a corrected version of it under the same name, `polite-closing`, and keep its source in `evaluators/polite_closing.py`. If your evaluator returns several results for a conversation, the conversation counts as failed when any of them has `passed = false`.

How it is graded: after you finish, the latest registered version of `polite-closing` is run on conversations you have not seen. It must fail the ones where the assistant really was curt and pass the others. Nothing you write to a file or say in your final message is graded.
