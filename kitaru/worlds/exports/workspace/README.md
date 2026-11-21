# Tidewater Couriers: dispatch assistant

This repository belongs to the team that runs the dispatch assistant for Tidewater Couriers. The assistant answers one customer message per conversation: it finds the parcel (`find_parcel`), sometimes plans a route (`plan_route`, which calls `geocode` itself) or messages the customer (`notify_customer`), and writes a reply.

## Where the traces are

The assistant does not use a tracing product. It appends one JSON line per event to a log file. `docs/trace-format.md` describes the format. `logs/sample.log.jsonl` is one morning of that log (60 conversations).

## Kitaru

The team wants its traces in Kitaru. A Kitaru workspace is already running on this machine.

- Server: `http://127.0.0.1:8000` (the `kitaru` CLI is installed and already points at it; no login is needed)
- Agent: `dispatch-agent`, one release (version 1). No conversations have been imported yet.
- A worker named `bench-worker` is running. It runs importers, evaluators and analyzers when you ask Kitaru for them.

Kitaru's documentation is in `/opt/kitaru-docs` (Markdown). `kitaru schema` prints every CLI command. This machine has no internet access; Python packages install only from the wheels already on it.

`importers/` is where the team keeps importer source.
