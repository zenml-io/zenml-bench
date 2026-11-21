# The dispatch assistant's trace log

One JSON object per line, appended when the event finishes. Lines from different conversations are mixed together, because conversations overlap. All times are seconds since 1970-01-01 UTC, with fractions.

Every line has `conv` (the conversation id) and `kind`.

| `kind` | written when | fields |
|---|---|---|
| `start` | the customer's message arrives | `ts`, `customer_msg`, `channel` |
| `llm` | a model call finishes | `span`, `parent`, `ts_start`, `ts_end`, `model`, `usage`, `cost_microusd` |
| `tool` | a tool call finishes | `span`, `parent`, `ts_start`, `ts_end`, `tool`, `ok`, `args`, `result` |
| `end` | the conversation finishes | `ts`, `outcome`, and `reply` or `error` |

- `span` is unique inside its conversation. `parent` is the `span` that made this call, or `null`. A tool call's parent is the model call that asked for it, or another tool call when one tool calls another. A model call's parent is `null` when the assistant made the call, or a tool call when a tool calls a model itself (the route planner does).
- `usage` has `in` and `out` (tokens). `cached` (input tokens read from the provider's cache) is present only when the provider reported it; when it is missing, none were cached.
- `cost_microusd` is the call's cost in millionths of a US dollar.
- `ok` is `false` when the tool call failed; `result` then holds the error.
- `outcome` is `resolved` (with `reply`, the text the customer read) or `error` (with `error`). If the assistant process died, the conversation has no `end` line at all.
- The writer is sometimes killed in the middle of a line. Such a line is not valid JSON and carries no information.
