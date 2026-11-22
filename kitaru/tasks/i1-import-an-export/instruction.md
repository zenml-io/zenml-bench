You are working in `/app`, the repository of the team that runs the customer support assistant for a courier company. `README.md` says where things are. A Kitaru workspace is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`.

The assistant's traces are in Langfuse and the team is moving to Kitaru. Import the Langfuse export `exports/langfuse-traces-2026-08.jsonl` into Kitaru.

When you are done, Kitaru must hold:

1. An agent named `support-assistant` that has one version with the display version `1.4.0` and one with the display version `1.5.0`.
2. One session per ticket in the export, holding every turn of that ticket. A ticket's traces share a `sessionId`. Each session was created by a Kitaru import through Kitaru's built-in Langfuse importer.
3. Each session under the agent version whose display version is the `release` named in the ticket's traces.
4. Each session's external id is `tidewater-support:<ticket id>`. That is what the Langfuse importer produces when the import's source identity is the Langfuse project, `tidewater-support`.
5. No other sessions under `support-assistant`.

How it is graded: the sessions Kitaru holds under `support-assistant` are compared with the export: which tickets, under which version, with how many model and tool calls and what cost. Nothing you write to a file or say in your final message is graded.
