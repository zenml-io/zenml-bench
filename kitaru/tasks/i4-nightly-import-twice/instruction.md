You are working in `/app`, the repository of the team that runs the customer support assistant for a courier company. `README.md` says where things are. A Kitaru workspace is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`.

Every night `bin/nightly_import.sh` imports a Langfuse export into Kitaru for `support-assistant`. Each nightly file covers the last two days, so every ticket arrives twice; the second time Kitaru is supposed to skip it. For the last two nights that has not happened: Kitaru now holds more sessions than there are tickets.

Repair the script and repair what Kitaru holds. When you are done:

1. Every ticket in the files in `exports/nightly/` is in Kitaru exactly once under `support-assistant`, as a session with the external id `tidewater-support:<ticket id>` created by a Kitaru import through the built-in Langfuse importer. There are no other sessions under `support-assistant`.
2. Every session that already had such an external id before you started is still there: the same session, not a deleted and re-imported copy. The cohort `reviewed-week-31` is unchanged.
3. `bin/nightly_import.sh <file>` imports a nightly file so that a ticket Kitaru already holds is skipped and a new ticket is created once. Running it a second time on the same file changes nothing.

How it is graded: the sessions under `support-assistant` are compared with the nightly files and with what was there before you started. Then your script is run twice, as you, on the next night's file, and the sessions are compared again. Nothing you write to another file or say in your final message is graded.
