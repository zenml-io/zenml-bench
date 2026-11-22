# What the `tw-trace` importer is meant to produce

When a log file in the format of `docs/trace-format.md` is imported through `tw-trace` for `dispatch-agent`, Kitaru should hold:

1. One session per conversation, with the conversation id as the session's external id. A line that is not valid JSON produces nothing and does not stop the import.
2. Session status `completed` when the conversation's outcome is `resolved`, and `failed` otherwise: outcome `error`, or no `end` line.
3. The session's start time from the `start` line, and its end time from the `end` line. With no `end` line, the end time is the end of the conversation's last call.
4. The customer's message in the session's inputs and, for a resolved conversation, the reply in its outputs.
5. One node per model call (type `llm_call`) and one per tool call (type `tool_call`), each with its start and end time. A model call node carries the model, the input, output and cached input token counts, and the cost in US dollars. A tool call node carries the tool's name in `tool_name`, and status `failed` when the call failed.
6. Each node's parent is the node of the call named in its `parent` field. A call whose `parent` is `null` has no parent among the model and tool calls.

Times match the log to the millisecond and costs to a millionth of a dollar.
