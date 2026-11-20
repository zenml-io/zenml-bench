You are working in `/app`, the repository of the team that runs the returns assistant for an online shop. `README.md` says where things are. Every conversation the assistant has had is recorded in a Kitaru workspace that is already running at `http://127.0.0.1:8000`; the `kitaru` CLI is installed and connected, and Kitaru's documentation is in `/opt/kitaru-docs`. The workspace is a snapshot taken on 30 July 2026.

Customers have complained: in some conversations where a refund was issued in euros, the assistant's reply states an amount 100 times larger than the amount that was actually refunded. The refund itself was for the right amount; the sentence the customer reads is wrong.

Turn this finding into a check that the team can run on any conversation, including ones recorded after today.

1. Write a Kitaru evaluator and register it in the workspace under the name `refund-confirmation-amount`. Keep its source in `/app/evaluators/`.
2. For one conversation, the evaluator must report `passed = false` when the reply states an amount for the refund that is 100 times the amount refunded, and `passed = true` otherwise. A conversation with no refund passes. If your evaluator returns several results for a conversation, the conversation counts as failed when any of them has `passed = false`.

How it is graded: after you finish, the latest registered version of `refund-confirmation-amount` is run on conversations you have not seen, in several currencies, some affected and some not. It must fail the affected ones and pass the others. Nothing you write to a file or say in your final message is graded.
