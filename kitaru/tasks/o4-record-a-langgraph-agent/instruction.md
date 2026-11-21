You are working in `/app`, the repository of the team that runs the helpdesk assistant for an online shop. `README.md` says where things are. The assistant's conversations are recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`.

The team's second assistant, the parcel chaser, is a LangGraph agent that leaves no trace: when a customer complains about a note it sent, nobody can see what it looked up. `README.md`, section "The parcel chaser", says what it is and how it is run.

Record it in Kitaru, so that its runs can be read and replayed:

1. Every run of the chaser must be recorded: one Kitaru session per order, under an agent named `parcel-chaser`, with the run's model calls and tool calls. The chaser is started from `/app` as `python -m chaser.agent <order id>`, exactly like that, with nothing in the environment that names a Kitaru agent, version or session.
2. Register a version of `parcel-chaser` that Kitaru can replay. A recorded run must replay to completion against the agent's newest version with every tool answered from the recording (tool policy `{"default": {"type": "history", "scope": "baseline", "on_miss": "fail"}}`).
3. The notes the chaser writes must not change, and the command must keep printing the note. Leave `helpdesk-agent` and its code as they are.

How it is graded: orders you have not seen are run through the command as another user. Kitaru must then hold one completed session per order under `parcel-chaser`, with a model call for every step and a tool call for every lookup (the tool's name, the order as its argument, a result). Some of those sessions are then replayed against the newest version of `parcel-chaser`, on a worker started as another user, with that tool policy: every replay must complete with the same tool calls, and the order service must receive no request while they run. Nothing you write to another file or say in your final message is graded.
