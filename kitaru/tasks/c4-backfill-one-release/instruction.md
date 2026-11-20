You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

Release 1.4.1 of the returns assistant went live on 22 July 2026. Since then the team has corrected its `refund-issued-once` check: version 2 is registered in Kitaru and its source is `evaluators/refund_issued_once.py`.

Give release 1.4.1 results from the corrected check:

1. Evaluate every conversation that release 1.4.1 served with version 2 of `refund-issued-once`.
2. Leave earlier releases alone. At most 30 conversations from earlier releases may carry results from version 2.
3. Do not run more than you need: when you finish, Kitaru must hold no more than 1,400 results from version 2 in total.

How it is graded: only what Kitaru has stored when you finish. Nothing you write to a file or say in your final message is graded.
