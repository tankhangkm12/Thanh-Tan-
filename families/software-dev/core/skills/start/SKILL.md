---
name: start
description: Start a new software-dev task with agentflow. Use when the person wants to begin a feature, bugfix or hotfix and no task is active. Sets up the workspace if needed, creates the gitflow branch and runs the confirm step.
---
# Start a task

Use `agentflow` for everything below. Never create or edit files under `.agentflow/` by hand.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job.

1. Run `agentflow status`.
   - If it says there is no workspace, set one up from the project root (a git repository with `main` and `develop` branches). Run `agentflow init --workflow <path to this plugin's workflow.yaml>`.
     The file is `workflow.yaml` in the root of the dev-core plugin. In Claude Code that is `${CLAUDE_PLUGIN_ROOT}/workflow.yaml`; in Antigravity it is under `~/.gemini/antigravity-cli/plugins/dev-core/`. If the path is not filled in, search for a `dev-core/workflow.yaml` under `~/.claude/plugins` or that Antigravity folder.
   - If a task is already active, do not start another: use the continue skill, or ask the person whether to cancel it (`agentflow task cancel`).
2. Look at the roadmap with `agentflow roadmap list` (and the `next roadmap:` line of `agentflow status`): the task should serve one item, `R1`, `R2`, ... Ask the person which one when it is not obvious from the request; never pick for them. If the project has no roadmap, or the request fits no item, go on without one: `agentflow task new` only warns.
3. Ask the person for a short title and the type: `feature`, `bugfix` (both branch from `develop`) or `hotfix` (from `main`). Infer them from the request when it is obvious. Also pick the size: `normal` (the default) or `small`, for a tiny, well-bounded change that fits in at most 3 plan items. A small task skips the approval of the plan (confirm and review still need the person) and its security step runs only Gitleaks and Semgrep. Use `small` only when the person asks for it or the request is clearly that small; when in doubt use `normal`.
4. The working tree must be clean. If `agentflow` says it is not, show the person what is uncommitted and ask what to do; do not discard anything.
5. Run `agentflow task new "<title>" --type <type> --roadmap <Rn>` (add `--size small` for a small task; leave `--roadmap` out only when no item fits). The item moves to `doing`; finishing the task never closes it, a person does (`agentflow roadmap set Rn done`). Read the warnings it prints aloud to the person: an unconfirmed mission or roadmap item is theirs to confirm, not yours. It creates the branch `<type>/T-001-<slug>` and switches to it. If it says the previous task has no approval tag, tell the person: they run `agentflow task seal <id>` themselves.
6. Carry on with the continue skill. It runs the **confirm** step with the orchestrator agent and stops at the person's approval; after the approval it keeps going by itself.
