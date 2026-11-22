# Tidewater Couriers: dispatch assistant

This repository belongs to the team that runs the dispatch assistant for Tidewater Couriers. The assistant answers one customer message per conversation: it finds the parcel (`find_parcel`), sometimes plans a route (`plan_route`, which calls `geocode` and a larger model itself) or messages the customer (`notify_customer`), and writes a reply.

## Where the traces are

The assistant does not use a tracing product. It appends one JSON line per event to a log file. `docs/trace-format.md` describes the format. `logs/2026-08.log.jsonl` is August's log (450 conversations) and `logs/sample.log.jsonl` is one morning (60 conversations).

## Kitaru

The team keeps its traces in Kitaru. A Kitaru workspace is already running on this machine.

- Server: `http://127.0.0.1:8000` (the `kitaru` CLI is installed and already points at it; no login is needed)
- Agent: `dispatch-agent`, one release (version 1).
- Importer: `tw-trace`, one version. Its source is `importers/tw_trace.py`. `docs/kitaru-mapping.md` says what it is meant to produce.
- August's log has been imported through `tw-trace` for `dispatch-agent`.
- A worker named `bench-worker` is running. It runs importers, evaluators and analyzers when you ask Kitaru for them.

Kitaru's documentation is in `/opt/kitaru-docs` (Markdown). `kitaru schema` prints every CLI command. This machine has no internet access; Python packages install only from the wheels already on it.

`docs/usage-2026-08.md` is the model provider's usage report for August.
