# Tidewater Couriers: support assistant

This repository belongs to the team that runs the customer support assistant for Tidewater Couriers. A customer conversation is a ticket of one to four turns. On each turn the assistant may look the shipment up (`lookup_shipment`), open a claim (`open_claim`), schedule a redelivery (`schedule_redelivery`) or send an email (`send_email`), and then writes a reply.

## Where the traces are

Until now the assistant was traced with Langfuse, in the Langfuse project `tidewater-support`. Langfuse recorded each turn of a ticket as one trace: a root span, with the turn's model calls and tool calls under it.

`exports/langfuse-traces-2026-08.jsonl` is the Langfuse export of 1 August: one trace per line, with its observations inside it. Two releases of the assistant were live that day, `1.4.0` and `1.5.0`. Each trace names the release that produced it in `release`, and its ticket in `sessionId`.

## Kitaru

The team is moving its traces to Kitaru. A Kitaru workspace is already running on this machine.

- Server: `http://127.0.0.1:8000` (the `kitaru` CLI is installed and already points at it; no login is needed)
- No agent is registered for the support assistant yet, and none of its traces have been imported.
- A worker named `bench-worker` is running. It runs importers, evaluators and analyzers when you ask Kitaru for them.
- The agent `dispatch-agent` in the same workspace belongs to another team. Leave it as it is.

Kitaru's documentation is in `/opt/kitaru-docs` (Markdown). `kitaru schema` prints every CLI command. This machine has no internet access; Python packages install only from the wheels already on it.
