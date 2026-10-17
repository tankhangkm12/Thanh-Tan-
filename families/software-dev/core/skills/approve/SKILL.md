---
name: approve
description: Approve the software-dev step that is waiting for a person, or resume a blocked task, using agentflow. Use only when the person explicitly says to approve or to resume. Never use it on your own initiative.
---
# Approve a step

Approval is the person's decision. Do this only after the person has clearly asked for it in this conversation.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job.

1. Run `agentflow status` and tell the person what they are approving: the step (confirm, plan or review), and the report that backs it (`.agentflow/tasks/<task>/reports/<step>.md`). Summarise the report in a few lines.
2. If the step is `awaiting_approval`, and the person confirmed, run `agentflow task approve`. The task moves to the next step, or is done after the last one. Approving the last step also writes `summary.md`, `spec-delta.md` and the approval tag; afterwards offer the replan skill (`replan`) to bring the project documents up to date before the next task.
3. If the task is `blocked`, explain why (read the latest failing report) and that approving means "go on anyway": the task returns to `implement` with the rework rounds reset, and a record is written to `.agentflow/decisions/`. Ask for a short reason and run `agentflow task approve --reason "<reason>"`. If the person would rather stop, offer `agentflow task cancel`.
4. If the person does not agree with a step's result, do not approve. Record the step as failed with `agentflow task advance --result fail` if they want it reworked.
5. Run `agentflow status` and report the new state.
6. Unless the task is done or needs another person's decision, carry on straight away with the continue skill: run the following steps without asking again, until the next step that needs approval, a blocked task or a question only the person can answer.

Never edit files under `.agentflow/` by hand.
