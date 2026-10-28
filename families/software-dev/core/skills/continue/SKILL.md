---
name: continue
description: Continue the active software-dev task with thanhtan. Use when a task exists and the person asks to carry on, resume after a break, or do the next step. Runs steps one after another with the right role until a step needs a person.
---
# Continue the active task

Use `thanhtan` for everything below. Never create or edit files under `.ThanhTan/` by hand.

Run every `thanhtan` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`. Reports are saved with the `report_write` tool; only when the tool is not available, send the Markdown to `thanhtan report --step <step>` on standard input with a quoted heredoc (`<<'EOF'`), not a pipe.

You never push, merge or open a pull request; that is the person's job.

## The loop

Repeat these until one of the stop conditions below:

1. Run `thanhtan next`. Its first word tells you what to do:
   - `start_task`: there is no active task; use the start skill.
   - `await_approval`: a person has to approve the step. Tell them which step, where its report is and where its checklist is (`.ThanhTan/tasks/<task>/approve-<step>.md`, written when the step passed; they tick it before approving), then stop. The approve skill handles it. Never approve a step yourself.
   - `blocked`: the task failed too many times. Show the person the latest reports in `.ThanhTan/tasks/<task>/reports/`, say the options (approve to resume, or cancel) and stop.
   - `continue`: work on the named step, as below, then go back to 1.
2. Make sure you are on the task's branch (shown by `thanhtan status`). If not, switch with `git switch <branch>`.
3. Hand the step to the role that owns it, in Claude Code by calling the agent of that name and in Antigravity by using the agent of the same name:

   | Step | Role | What it produces |
   |---|---|---|
   | confirm | `orchestrator` | confirmation report |
   | plan | `planner` | plan report that passes `thanhtan plan check` |
   | test-spec | `tester` | tests written first (test directories only), committed, and a test-spec report whose commands fail (for `type: refactor` or `chore`: whose commands pass on the code as it is); `thanhtan tests verify-red` shows it |
   | implement | see below | code, commits through `thanhtan commit`, summary report |
   | test | `tester` | test report; thanhtan itself runs the project's tests and the commands of the test-spec (gate `tests-pass`) |
   | security | `security` | scan results and security report |
   | review | `reviewer` | review report |

   The role saves its report with `report_write` (a report can only be written for the current step, and not again once the step has passed) and records the result with `thanhtan task advance --result pass` (or `fail`).

   **test-spec:** call the `tester`. After it passes the step always waits for a person, small task or not: tell them the report (`reports/test-spec.md`), the result thanhtan recorded (`verify-red.json`) and the checklist (`approve-test-spec.md`), then stop (the approve skill). The implementer must not start before that approval. The approval locks the tests: the test files of the report, the test infrastructure it lists and the test configuration of the project are locked from then on (hook, `thanhtan commit` and the gate `locked-files-intact`, see `thanhtan tests check`). Tell the implementer agents not to touch them; if a locked test looks wrong the implementer stops and you tell the person, who alone can change it with `thanhtan tests amend`.

   **plan:** in a small task (`size: small` in `thanhtan status`) the plan needs no approval: once it passes the check, `thanhtan next` goes straight on to implement. If the plan check lists unanswered questions (`## Chưa có quy ước`), stop: tell the person to answer each with `thanhtan decide --answer Q1 --text "..." --check <plan, semgrep or review>`, then continue.

   **Back at implement after a failure:** when `thanhtan status` shows the task at `implement` with `rework rounds:` 2 or more (the task failed at test, security or review at least twice), call the `debugger` agent first. Give it the task code and tell it to read the latest failing report. It saves a diagnosis for this round (`thanhtan diagnosis list` shows it). Then give the implementer agents the diagnosis as well as the failing report, and tell them to fix the cause it names rather than the symptom. In round 1 skip the debugger: the failing report is usually enough.

   **implement:** read the conventions (`conventions` tool or `thanhtan conventions`) and the approved plan (`.ThanhTan/tasks/<task>/reports/plan.md`). Take its items in order. Run `thanhtan plan assign --cli claude` in Claude Code (`--cli antigravity` in Antigravity): it prints one line per item, `<code> <role> <tier> <agent>`, and the agent is the one to call for that item. The `implementer` role has two agents, `implementer-fast` (a quicker, cheaper setting: Sonnet at low effort in Claude Code, the flash model in Antigravity) for items with `tier: fast` and `implementer-deep` (the stronger setting: Sonnet at high effort in Claude Code, the pro model in Antigravity) for `tier: deep` or no tier; a role without tiers (plugins add roles of their own) has just one agent, with the model and effort its plugin gave it, whatever the item's tier. In Claude Code the agent may be a `project-…` copy of the plugin agent, made by `thanhtan role grant`: it has the extra tools the person granted the role for this project, so call exactly the name printed. Where the CLI lets you choose the model when you call an agent, do not override the agent's own: the tier is already in the agent. Tell the agent the item code, so it commits with `--item <code>`. Keep going through all the items without stopping; the tier only decides which agent does an item. Give the last item's agent the extra job of saving the implement summary and recording the step as passed. If a skill of an installed plugin fits an item, tell the agent to use it.
4. After the role finishes, run `thanhtan status`. A pass that needs no approval means: go back to 1 straight away. Do not ask the person whether to continue.

## Stop conditions

Stop and tell the person where things stand only when:

- the next action is `await_approval` or `blocked`;
- a question is genuinely theirs to decide (do not guess);
- a command was refused for a reason you cannot fix (for example a gate or an unavailable container engine);
- the task is done. Say that `.ThanhTan/tasks/<task>/summary.md` has the summary, that `.ThanhTan/tasks/<task>/spec-delta.md` shows what the task changed in the specification, and that the approval tag `thanhtan/<task>/approved` is on the task branch. Offer the replan skill (`replan`) before the next task. Merging and pushing are the person's job.

A failing test, security or review step sends the task back to `implement` by itself; after 3 rounds the task is blocked.

Only the implementer-type roles change project code, each only for its own plan items.
