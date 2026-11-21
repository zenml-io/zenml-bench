You are working in `/app`, the repository of the team that runs the dispatch assistant for a courier company. `README.md` says where things are. A Kitaru workspace is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`.

The assistant writes its traces to a log file in a format the team made up. `docs/trace-format.md` describes the format and `logs/sample.log.jsonl` is a sample from one morning. Kitaru has no importer for it.

Write a Kitaru importer for this format and register it under the name `tw-trace`. Keep its source in `/app/importers/`.

When a log file in this format is imported through it for the agent `dispatch-agent`, Kitaru must hold:

1. One session per conversation, with the conversation id as the session's external id. A line that is not valid JSON produces nothing and must not stop the import.
2. Session status `completed` when the conversation's outcome is `resolved`, and `failed` otherwise: outcome `error`, or no `end` line.
3. The session's start time from the `start` line, and its end time from the `end` line. With no `end` line, the end time is the end of the conversation's last call.
4. The customer's message in the session's inputs and, for a resolved conversation, the reply in its outputs.
5. One node per model call (type `llm_call`) and one per tool call (type `tool_call`), each with its start and end time. A call whose line was written twice is one node. A model call node carries the model, the input, output and cached input token counts, and the cost in US dollars: the cost on the line, or, for a line without one, the cost the format document says it has. A tool call node carries the tool's name in `tool_name`, and status `failed` when the call failed.
6. Each node's parent is the node of the call named in its `parent` field. A call whose `parent` is `null` has no parent among the model and tool calls.

How it is graded: after you finish, the latest registered version of `tw-trace` is used to import a log file you have not seen, in the same format, for `dispatch-agent`. That log comes from more hosts than the sample: it can contain anything the format document describes, including things the sample has no example of. Every session and node Kitaru then holds is compared with that log. Times must match to the millisecond and costs to a millionth of a dollar. Nothing you import yourself, write to another file or say in your final message is graded.
