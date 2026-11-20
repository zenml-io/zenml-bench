# Larkspur Goods: returns assistant

This repository belongs to the team that runs the returns assistant for Larkspur Goods, an online shop. The assistant answers one customer message per conversation: it looks up the order (`lookup_order`), refunds it or declines (`issue_refund`), and writes the reply the customer reads.

## Where the recorded conversations are

Every conversation is recorded in a Kitaru workspace that is already running on this machine.

- Server: `http://127.0.0.1:8000` (the `kitaru` CLI is installed and already points at it; no login is needed)
- Agent: `returns-agent`, with three releases: version 1 = `1.3.0`, version 2 = `1.4.0`, version 3 = `1.4.1`
- History: about 3,000 conversations from 1 June to 30 July 2026. This workspace is a snapshot taken on 30 July 2026; nothing newer exists.
- A worker named `bench-worker` is running. It runs evaluators, importers and analyzers when you ask Kitaru for them.

Kitaru's documentation is in `/opt/kitaru-docs` (Markdown). `kitaru schema` prints every CLI command. This machine has no internet access; Python packages install only from the wheels already on it.

## Evaluators

`evaluators/` holds the checks this team runs over recorded conversations. `refund_issued_once.py` is registered in Kitaru as `refund-issued-once`.
