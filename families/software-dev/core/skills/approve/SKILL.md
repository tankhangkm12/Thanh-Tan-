---
name: approve
description: Approve the software-dev step that is waiting for a person, or resume a blocked task, using agentflow. Use only when the person explicitly says to approve or to resume. Never use it on your own initiative.
---
# Approve a step

Approval is the person's decision. Do this only after the person has clearly asked for it in this conversation.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job.

1. Run `agentflow status` and tell the person what they are approving: the step (confirm, plan, test-spec or review), and the report that backs it (`.agentflow/tasks/<task>/reports/<step>.md`). Summarise the report in a few lines. Then tell them to open the checklist agentflow wrote for the step, `.agentflow/tasks/<task>/approve-<step>.md`, and tick every box with an x (`- [x]`) once they have checked it; optional boxes (marked `(tùy chọn)`), such as "is roadmap item Rn done?", may stay open. They may add a note under `## Ghi chú của bạn`. For `test-spec` also point them to what agentflow itself recorded when it ran the commands, `.agentflow/tasks/<task>/verify-red.json`: the exit code and the output are agentflow's, the `output` in the report is the tester's own claim. For `test-spec` also tell them what the approval does: the `L` lines of the checklist are the files that become locked (the test files, the test infrastructure the tester declared, the test configuration of the project), and the approval writes `.agentflow/tasks/<task>/locked-files.json` with their hashes. From then on no agent changes them, and if a test must change later the person decides and runs `agentflow tests amend <file> --reason "..."` themselves, then the file is edited and committed with `agentflow commit`. Wait until they say it is ticked.
2. If the step is `awaiting_approval`, and the person confirmed, run `agentflow task approve`. It refuses while a required box is open or the checklist was changed (exit 36), and when the audit log or `state.json` shows a change made outside agentflow (exit 37): relay the message and let the person fix it; only they run `agentflow state accept --reason "..."` after reading the change. The task moves to the next step, or is done after the last one. Approving the last step also writes `summary.md`, `spec-delta.md` and the approval tag; afterwards offer the replan skill (`replan`) to bring the project documents up to date before the next task.
3. If the task is `blocked`, explain why (read the latest failing report) and that approving means "go on anyway": the task returns to `implement` with the rework rounds reset, and a record is written to `.agentflow/decisions/`. Ask for a short reason and run `agentflow task approve --reason "<reason>"`. If the person would rather stop, offer `agentflow task cancel`.
4. If the person does not agree with a step's result, do not approve. Record the step as failed with `agentflow task advance --result fail` if they want it reworked.
5. Run `agentflow status` and report the new state.
6. Unless the task is done or needs another person's decision, carry on straight away with the continue skill: run the following steps without asking again, until the next step that needs approval, a blocked task or a question only the person can answer.

Never tick, edit, fill or recreate the checklist for the person, and never run `agentflow state accept` or `agentflow tests amend`: both are their decisions. Never edit files under `.agentflow/` by hand.
