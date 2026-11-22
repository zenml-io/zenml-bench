# Tidewater Couriers: support assistant

This repository belongs to the team that runs the customer support assistant for Tidewater Couriers. A customer conversation is a ticket of one to four turns. On each turn the assistant may look the shipment up (`lookup_shipment`), open a claim (`open_claim`), schedule a redelivery (`schedule_redelivery`) or send an email (`send_email`), and then writes a reply.

## Where the traces are

Until now the assistant was traced with Langfuse, in the Langfuse project `tidewater-support`. Langfuse recorded each turn of a ticket as one trace: a root span, with the turn's model calls and tool calls under it.

Every night a job exports the last two days of traces from Langfuse to `exports/nightly/support-<date>.jsonl` (one trace per line, with its observations inside it; `sessionId` is the ticket) and then runs `bin/nightly_import.sh <file>`, which imports the file into Kitaru. A file covers two days, so every ticket is in two files.

## Kitaru

The team is moving its traces to Kitaru. A Kitaru workspace is already running on this machine.

- Server: `http://127.0.0.1:8000` (the `kitaru` CLI is installed and already points at it; no login is needed)
- Agent: `support-assistant`, one release (version 1). Every nightly file up to `support-2026-08-07.jsonl` has been imported.
- Cohort `reviewed-week-31`: tickets the support leads have read.
- A worker named `bench-worker` is running. It runs importers, evaluators and analyzers when you ask Kitaru for them.
- The agent `dispatch-agent` in the same workspace belongs to another team. Leave it as it is.

Kitaru's documentation is in `/opt/kitaru-docs` (Markdown). `kitaru schema` prints every CLI command. This machine has no internet access; Python packages install only from the wheels already on it.
