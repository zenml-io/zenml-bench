You are working in `/app`, the repository of the team that runs the customer support assistant for a courier company. `README.md` says where things are. A Kitaru workspace is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`.

The assistant's traces are in Langfuse and the team is moving to Kitaru. Langfuse recorded each turn of a ticket as its own trace. In Kitaru the team wants one session per ticket.

Write `bin/import_tickets.sh`. It takes the path of one Langfuse observations export as its only argument, imports that file into Kitaru for `support-assistant@1`, and returns when the import has finished. `exports/langfuse-observations-2026-08-01.jsonl` is such a file. Then run the script on that file.

After the script has run on an export, Kitaru must hold, under `support-assistant`:

1. One session per ticket in the export, with the external id `tidewater-support:<ticket id>`, created by a Kitaru import through Kitaru's built-in Langfuse importer.
2. In each session, every turn of that ticket, in the order the turns happened, and no turn of another ticket.
3. No session for a trace that has no ticket.

How it is graded: first the sessions Kitaru holds for `exports/langfuse-observations-2026-08-01.jsonl` are compared with that file. Then your script is run, as you, on an export of another day that you have not seen, and the sessions it creates are compared with that file in the same way. Nothing you write to another file or say in your final message is graded.
