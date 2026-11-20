# Larkspur Goods: returns assistant

This repository belongs to the team that runs the returns assistant for Larkspur Goods, an online shop. The assistant answers one customer message per conversation: it looks up the order (`lookup_order`), refunds it or declines (`issue_refund`), and writes the reply the customer reads.

## Where the recorded conversations are

Every conversation is recorded in a Kitaru workspace that is already running on this machine.

- Server: `http://127.0.0.1:8000` (the `kitaru` CLI is installed and already points at it; no login is needed)
- Agent: `returns-agent`, with three releases: version 1 = `1.3.0`, version 2 = `1.4.0`, version 3 = `1.4.1`
- History: about 3,000 conversations from 1 June to 30 July 2026. This workspace is a snapshot taken on 30 July 2026; nothing newer exists.
- A worker named `bench-worker` is running. It runs evaluators, importers and analyzers when you ask Kitaru for them.

Kitaru's documentation is in `/opt/kitaru-docs` (Markdown). `kitaru schema` prints every CLI command. This machine has no internet access; Python packages install only from the wheels already on it.

## What a recorded conversation holds

Each conversation is one Kitaru session. Its `outputs.reply` is the text the customer read. Its nodes are the assistant's model calls and tool calls, in order; a tool call node has the tool's arguments in `inputs` and its result in `outputs`. The order service sometimes times out, and the assistant then calls `lookup_order` again.

A session's `metadata` says how the conversation ended: `end_reason` is `resolved` when the assistant gave its final answer, and `idle_timeout` when the assistant asked the customer for more detail and the customer never came back. `metadata.agent_release` is the release that served it.

## Evaluators

`evaluators/` holds the checks this team runs over recorded conversations.

- `refund_issued_once.py` is registered in Kitaru as `refund-issued-once`. Version 2 is the current source; version 1 counted rejected refund calls too.
- `polite_closing.py` is registered as `polite-closing`: the team expects every finished conversation to end with one of three closing courtesies.
