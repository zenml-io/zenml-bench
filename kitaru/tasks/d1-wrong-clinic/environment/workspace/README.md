# Fernhill Vets: appointment assistant

This repository belongs to the team that runs the appointment assistant for Fernhill Vets, a chain of ten veterinary clinics in three towns. The assistant answers one customer message per conversation: it finds the clinic (`search_clinics`), checks free slots (`check_availability`), books (`book_appointment`), moves a booking (`lookup_booking`, `reschedule_appointment`), or answers a question about care (`get_care_sheet`). For a new patient it also registers the owner and the animals (`register_owner`, `register_pet`, `request_records`, `send_forms`).

## Where the recorded conversations are

Every conversation is recorded in a Kitaru workspace that is already running on this machine.

- Server: `http://127.0.0.1:8000` (the `kitaru` CLI is installed and already points at it; no login is needed)
- Agent: `booking-agent`, with three releases: version 1 = `1.1.0`, version 2 = `1.2.0`, version 3 = `1.3.0`. `CHANGELOG.md` says what each changed and when.
- History: about 3,200 conversations from 1 June to 20 July 2026. This workspace is a snapshot taken on 20 July 2026; nothing newer exists.
- A worker named `bench-worker` is running. It runs evaluators, importers and analyzers when you ask Kitaru for them.

Kitaru's documentation is in `/opt/kitaru-docs` (Markdown). `kitaru schema` prints every CLI command. This machine has no internet access; Python packages install only from the wheels already on it.

## What a recorded conversation holds

Each conversation is one Kitaru session. Its `inputs.message` is what the customer wrote and its `outputs.reply` is the text the customer read. Its nodes are the assistant's model calls and tool calls, in order; a tool call node has the tool's arguments in `inputs` and its result in `outputs`.

A session's `metadata.source` says where the customer came from (`web`, `app`, `phone-transfer`, `partner-portal`) and `metadata.agent_release` is the release that served it.

## This repository

- `agent/prompt.md`: the assistant's instructions.
- `agent/config.yaml`: the model settings the assistant runs with. A change here takes effect when it is merged; it needs no release.
- `agent/tools.py`: the tools the assistant can call, and the limits the booking tool enforces.
- `CHANGELOG.md`: releases.

The scheduling API behind the tools belongs to another team and is not in this repository.
