---
name: status
description: Show where the software-dev workflow stands with agentflow. Use when the person asks about progress, the current step, the active task or what happens next. Read-only.
---
# Show the workflow status

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job.

1. Run `agentflow status` and, for the next action only, `agentflow next`.
2. Report in a few lines: the active task (id, title, branch, and the roadmap item it serves when `status` prints a `roadmap:` line), the current step and its role, the state (in progress, waiting for approval, blocked), the rework rounds used (for example 1/3), and what comes next, including the `next roadmap:` suggestion when `status` prints one. `agentflow project status` (read-only) tells whether the mission, profile, architecture, conventions and roadmap are confirmed, and `agentflow replan status` (read-only) where the replan of the latest finished task stands (`pending`, `proposed`, `done`, `skipped`, ...).
3. If the person wants detail, read the reports in `.ThanhTan/tasks/<task>/reports/`, the summary `.ThanhTan/tasks/<task>/summary.md` of a finished task, and any file in `.ThanhTan/decisions/`. You may read `.ThanhTan/STATE.md`.
4. If `agentflow` says there is no workspace, say so and point to the start skill.

This skill only reads. Do not change task state and never edit files under `.ThanhTan/`.
