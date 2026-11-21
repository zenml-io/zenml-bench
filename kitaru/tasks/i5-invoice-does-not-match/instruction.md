You are working in `/app`, the repository of the team that runs the dispatch assistant for a courier company. `README.md` says where things are. A Kitaru workspace is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`.

The assistant's trace log is imported into Kitaru through the team's own importer, `tw-trace`. August's log was imported that way. Finance has noticed that the cost Kitaru shows for August is about a third lower than what the model provider billed (`docs/usage-2026-08.md`). The log is complete and correct, and it agrees with the bill.

Find out why Kitaru disagrees with the log, and repair it. When you are done:

1. `tw-trace` has a new version that produces what `docs/kitaru-mapping.md` describes, for any log in this format. The version that is registered now stays registered.
2. What Kitaru holds for August under `dispatch-agent` agrees with August's log in every point of `docs/kitaru-mapping.md`: one session per conversation, with the conversation id as its external id, created by a Kitaru import through `tw-trace`.

How it is graded: every session and node Kitaru holds for August is compared with August's log. Then the latest version of `tw-trace` is used to import a log you have not seen, in the same format, and every session and node is compared with that log. Nothing you write to another file or say in your final message is graded.
