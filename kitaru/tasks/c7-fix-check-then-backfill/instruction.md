You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

The team's `polite-closing` check (source: `evaluators/polite_closing.py`) fails about one conversation in twenty. Either the assistant is being rude to customers that often, or the check is wrong. Find out which, and repair what is at fault.

The team's intent for the check: a conversation should fail only when the assistant ended a finished conversation without a closing courtesy.

If the check is at fault:

1. Register a corrected version of it under the same name, `polite-closing`, and keep its source in `evaluators/polite_closing.py`. If your evaluator returns several results for a conversation, the conversation counts as failed when any of them has `passed = false`.
2. Give the current release results from the corrected check. Release 1.4.1 of the returns assistant went live on 22 July 2026: every conversation it served must carry a result from the latest version of `polite-closing`.
3. Leave earlier releases alone. At most 30 conversations from earlier releases may carry results from the latest version.
4. Do not run more than you need: when you finish, Kitaru must hold no more than 1,400 results from `polite-closing` in total, counting every version of it.

How it is graded: first, what Kitaru has stored when you finish: which conversations carry results from the latest version of `polite-closing`, how many results there are, and whether the latest version failed the right conversations of release 1.4.1. Then the latest version is run on conversations you have not seen: it must fail the ones where the assistant really was curt and pass the others. Nothing you write to a file or say in your final message is graded.
