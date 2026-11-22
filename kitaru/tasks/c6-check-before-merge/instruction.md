You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

Before a change to the assistant is merged, the team wants one command that says whether a set of conversations is good enough. `checks.txt` lists the team's release checks: one registered evaluator per line, as `name@version`.

Write `bin/check.sh` in this repository. It is called as `bin/check.sh <cohort-name>` from `/app`, where `<cohort-name>` is the name of a Kitaru cohort, and it must:

1. Run every evaluator listed in `checks.txt` on every conversation in the latest version of that cohort, through Kitaru, so the results are stored in the workspace.
2. Exit with status 0 when at least 90% of the cohort's conversations pass every listed evaluator.
3. Exit with status 1 when fewer than 90% do.
4. Exit with status 2 when it could not do its job (for example, the cohort does not exist).

The cohorts the team will run it on are larger than the one cohort in the workspace today: expect a few hundred conversations in one cohort.

How it is graded: after you finish, cohorts you have not seen are created in the workspace and your script is run on each of them, with a Kitaru worker running. For each cohort the exit status must be right, and Kitaru must hold results from the listed evaluators for every conversation in that cohort. Nothing you write to a file or say in your final message is graded.
