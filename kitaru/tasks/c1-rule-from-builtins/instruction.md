You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

The team has a rule: no conversation may call `lookup_order` more than three times. The order service sometimes times out and the assistant retries; more than three attempts means it is stuck.

Check that rule on the most recent week: every conversation that started on or after 24 July 2026, 00:00 UTC.

1. Use one of Kitaru's built-in evaluators (their names start with `kitaru/`). Do not write your own evaluator.
2. When you finish, every conversation in that week must carry a result from the built-in evaluator whose `passed` is `true` if the conversation follows the rule and `false` if it breaks it. If a conversation ends up with several such results, the most recent one counts.
3. Do not evaluate the whole history. At most 50 conversations that started before 24 July may carry results from a built-in evaluator.

How it is graded: only what Kitaru has stored when you finish. Nothing you write to a file or say in your final message is graded.
