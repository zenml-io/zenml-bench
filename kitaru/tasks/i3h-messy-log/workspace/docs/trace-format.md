# The dispatch assistant's trace log

One JSON object per line, appended when the event finishes. Lines from different conversations are mixed together, because conversations overlap.

Every line has `conv` (the conversation id) and `kind`.

| `kind` | written when | fields |
|---|---|---|
| `start` | the customer's message arrives | `ts`, `customer_msg`, `channel` |
| `llm` | a model call finishes | `span`, `parent`, `ts_start`, `ts_end`, `model`, `usage`, and `cost_microusd` unless it is a batch call |
| `tool` | a tool call finishes | `span`, `parent`, `ts_start`, `ts_end`, `tool`, `ok`, `args`, `result` |
| `end` | the conversation finishes | `ts`, `outcome`, and `reply` or `error` |

- Times (`ts`, `ts_start`, `ts_end`) are seconds since 1970-01-01 UTC, with fractions. Hosts that run version 2 of the writer mark their lines with `"w": 2` and give the same times as ISO 8601 strings with the host's UTC offset, for example `2026-08-03T08:00:05.861928+02:00`. A log file can hold lines from both writers.
- `span` is unique inside its conversation. `parent` is the `span` that made this call, or `null`. A tool call's parent is the model call that asked for it, or another tool call when one tool calls another. A model call's parent is `null` when the assistant made the call, or a tool call when a tool calls a model itself (the route planner does).
- After a timeout the writer writes a call's line again. Two lines of one conversation with the same `span` are one call.
- `usage` has `in` and `out` (tokens). `cached` (input tokens read from the provider's cache) is present only when the provider reported it; when it is missing, none were cached. Cached tokens are counted inside `in`.
- `cost_microusd` is the call's cost in millionths of a US dollar. Calls sent through the provider's batch gateway (the route planner's calls) are billed later, and their lines have no `cost_microusd`. Such a call's cost is its token counts times the price list below, with cached input tokens billed at the cached price and the rest of `in` at the input price.
- `ok` is `false` when the tool call failed; `result` then holds the error.
- `outcome` is `resolved` (with `reply`, the text the customer read) or `error` (with `error`). If the assistant process died, the conversation has no `end` line at all.
- The writer is sometimes killed in the middle of a line. Such a line is not valid JSON and carries no information.

## Price list (US dollars per million tokens)

| model | input | cached input | output |
|---|---|---|---|
| `gpt-5.4-mini` | 0.25 | 0.05 | 2.00 |
| `gpt-5.4` | 0.30 | 0.06 | 1.60 |
