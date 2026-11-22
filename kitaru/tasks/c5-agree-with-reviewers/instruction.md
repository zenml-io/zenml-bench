You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

The support leads reviewed 40 conversations by hand. Those conversations are the Kitaru cohort `reviewed-july`, and each carries the reviewer's verdict as an evaluation named `human_review`, with the reviewer's reason in its `explanation`.

The team wants a check that reaches the reviewers' verdicts without a person reading anything.

1. Write a Kitaru evaluator and register it under the name `matches-review`. Keep its source in `/app/evaluators/`.
2. It must report `passed = false` for a conversation the reviewers would fail and `passed = true` for one they would pass. If it returns several results for a conversation, the conversation counts as failed when any of them has `passed = false`.
3. It must keep agreeing with the reviewers on conversations they never read.

How it is graded: after you finish, the latest registered version of `matches-review` is run on the 40 reviewed conversations and on conversations you have not seen that were judged by the same reviewers' rules. It must agree with the reviewers on both. Nothing you write to a file or say in your final message is graded.
