You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

The team has two rules:

- No conversation may call `lookup_order` more than three times. The order service sometimes times out and the assistant retries; more than three attempts means it is stuck.
- Every model call must be served by the model the assistant asks for, `gpt-5.4-mini`, and by nothing else: not another model, and not a dated variant of that one.

Check both rules on the week of 9 to 15 July 2026: every conversation that started on or after 9 July 2026, 00:00 UTC, and before 16 July 2026, 00:00 UTC.

1. Use Kitaru's built-in evaluators (their names start with `kitaru/`), a different one for each rule. Do not write your own evaluator.
2. When you finish, every conversation in that week must carry, for each rule, a result from that rule's built-in evaluator whose `passed` is `true` if the conversation follows the rule and `false` if it breaks it. If a conversation ends up with several results from one evaluator, the most recent one whose `passed` is `true` or `false` counts.
3. Do not evaluate the whole history. At most 50 conversations outside that week may carry results from a built-in evaluator.

How it is graded: only what Kitaru has stored when you finish. Nothing you write to a file or say in your final message is graded.
