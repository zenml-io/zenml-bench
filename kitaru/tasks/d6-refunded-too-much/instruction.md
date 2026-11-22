You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026 and holds the conversations of 1 June to 30 July 2026 for the agent `returns-agent`.

Finance has found refunds in its ledger that are larger than the order they belong to. Nobody knows how many there are or when they happened.

Create a Kitaru cohort named `over-refunds`, for the agent `returns-agent`, that holds every conversation in which the assistant refunded more money, in total, than the order's total.

How it is graded: only the members of the cohort `over-refunds` as Kitaru has stored them when you finish: at least 90% of its members must be conversations that belong in it, and it must hold at least 90% of the conversations that belong in it. If the cohort has several versions, the latest one counts. Nothing you write to a file or say in your final message is graded. Do not delete or change any conversation.
