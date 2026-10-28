---
name: replan
description: Replan the project documents after a finished software-dev task, using agentflow. Use when the person asks to replan, or when a task is done and sealed and the next one is about to start. Brings the profile, architecture, conventions and roadmap up to date from what the task really did; the person reads, confirms and closes it.
---
# Replan after a task

Use `agentflow` and its tools for everything below. Never create or edit files under `.ThanhTan/` by hand.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job.

1. Run `agentflow replan status`. Its first line is `replan: <state>`, the second names the task:
   - `pending`: the latest finished task has no replan yet. Go on with step 2.
   - `proposed`: a replan is already written (`.ThanhTan/tasks/<task>/replan.md`) and waits for the person. Do not write another unless they ask; go to step 4.
   - `task-open`: a task is open or blocked (a `blocked` task counts as open). Stop: project documents are written between tasks. Ask the person to finish or cancel that task first.
   - `not-sealed`: the finished task has no approval tag. Tell the person to run `agentflow task seal <task>` themselves, then replan.
   - `done` or `skipped`: there is nothing left to do; say so.
   - `no-finished-task`: no task is finished yet; there is nothing to replan.
2. Hand the work to the `scout` agent (in Claude Code by calling the agent of that name, in Antigravity by using the agent of the same name), and name the task. It reads `.ThanhTan/tasks/<task>/summary.md` and `.ThanhTan/tasks/<task>/spec-delta.md`, rewrites the documents that are no longer true with `project_write` (they become unconfirmed), then saves the replan with the `replan_write` tool.
3. Run `agentflow replan status` again. It must say `proposed`; if the scout was refused, read the reason, have it fix the report and try again.
4. Tell the person what is now theirs, and wait. The replan is only a proposal until they say it is done:
   - read `.ThanhTan/tasks/<task>/replan.md` and `.ThanhTan/tasks/<task>/spec-delta.md`, and the documents the scout rewrote (`agentflow project status` shows what is unconfirmed, and `removed:` lines for confirmed roadmap items the scout took out);
   - confirm what they agree with: `agentflow project confirm profile architecture` (and `mission`, `R1 R2`, `PC-01` as needed);
   - close the roadmap items the replan names under "Mục roadmap đã hoàn thành" when they agree: `agentflow roadmap set R1 done` (replan never does it);
   - finish with `agentflow replan done`, or, to leave the task without a replan on purpose, `agentflow replan skip <task> --reason "..."`. In Claude Code they type commands with the `!` prefix.

You never run `agentflow project confirm`, `agentflow roadmap set`, `agentflow replan done` or `agentflow replan skip`: confirming and closing are the person's authority. `agentflow task new` only warns while the latest replan is pending or proposed.
