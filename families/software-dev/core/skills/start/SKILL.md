---
name: start
description: Start a new feature or bugfix task of normal size with thanhtan. Use when the person types /dev-core:start or wants to begin a feature or a bugfix and no task is active. Sets up the workspace if needed, creates the gitflow branch and runs the confirm step. The other kinds of task have their own commands - start-small, hotfix, refactor, chore - and follow these same steps.
---
# Start a task

**Which command fixes what.** The command the person typed fixes the type and the size; never change them, never guess a size. When the request does not fit the command, say which command fits and stop: the person types it.

| Command | Type | Size |
|---|---|---|
| `/dev-core:start` | `feature` or `bugfix`, from the request | `normal` (no `--size`) |
| `/dev-core:start-small` | `feature`, `bugfix`, `refactor` or `chore`, from the request | `small` (`--size small`) |
| `/dev-core:hotfix` | `hotfix` | `hotfix` by itself (no `--size`) |
| `/dev-core:refactor` | `refactor` | `normal` (no `--size`) |
| `/dev-core:chore` | `chore` | `normal` (no `--size`) |

These steps are the same for all of them.

Use `thanhtan` for everything below. Never create or edit files under `.ThanhTan/` by hand.

Run every `thanhtan` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job.

1. Run `thanhtan status`.
   - If it says there is no workspace, set one up from the project root (a git repository with `main` and `develop` branches). Run `thanhtan init --workflow <path to this plugin's workflow.yaml>`.
     The file is `workflow.yaml` in the root of the dev-core plugin. In Claude Code that is `${CLAUDE_PLUGIN_ROOT}/workflow.yaml`; in Antigravity it is under `~/.gemini/antigravity-cli/plugins/dev-core/`. If the path is not filled in, search for a `dev-core/workflow.yaml` under `~/.claude/plugins` or that Antigravity folder.
   - If a task is already active, do not start another: use the continue skill, or ask the person whether to cancel it (`thanhtan task cancel`).
2. Look at the roadmap with `thanhtan roadmap list` (and the `next roadmap:` line of `thanhtan status`): the task should serve one item, `R1`, `R2`, ... A short request is enough: "làm R2" (do R2) names the item, and "làm tiếp" (go on) means the item of the `next roadmap:` line; say which one you took. Ask the person which one when it is not obvious from the request; never pick for them. Read the item with `thanhtan roadmap show <Rn>`: its documents are the request, so do not ask the person to describe the task or fill in a template. If the project has no roadmap, or the request fits no item, go on without one: `thanhtan task new` only warns.
3. Take the title from the roadmap item when the task serves one (shorten it if needed). Otherwise ask the person for a short title. Take the type and the size from the table above; where the table leaves a choice of type, infer it from the request, and ask when it is not obvious. What the types mean: `feature` and `bugfix` add or fix behaviour; `refactor` restructures code without changing what it does; `chore` is upkeep that keeps the behaviour, such as a dependency upgrade; `hotfix` is an urgent fix of what is released. For `refactor` and `chore` the test-spec step works the other way round: the tests must pass on the code as it is, and keep passing after the change. A `small` task (at most 3 plan items) skips the approval of the plan (confirm and review still need the person) and its security step runs only Gitleaks and Semgrep. A `hotfix`: no approval of the plan, at most 3 plan items, every scan; confirm, test-spec and review still need the person, and when it is done thanhtan prints the commands the person runs to merge it into `main` and back into `develop`. Do not ask for a roadmap item for a hotfix.
4. The working tree must be clean. If `thanhtan` says it is not, show the person what is uncommitted and ask what to do; do not discard anything.
5. Run `thanhtan task new "<title>" --type <type> --roadmap <Rn>` (add `--size small` only for `/dev-core:start-small`; leave `--roadmap` out only when no item fits). **The branch the task starts from** is the project's choice (`git.base.*` settings, else develop; main for a hotfix): do not pass `--base` unless the person names a branch ("tách từ feature/login", "branch off release/2"), then add `--base <that branch>` exactly as they wrote it. Never pick a base yourself. The command prints `created on branch <task branch> from <base>`: say it aloud, and if it warns that the base is behind origin, tell the person and stop before going on, so they can `git pull` first (cancel the task with `thanhtan task cancel` if they want to start over). The item moves to `doing`; finishing the task never closes it, a person does (`thanhtan roadmap set Rn done`). Read the warnings it prints aloud to the person: an unconfirmed mission or roadmap item is theirs to confirm, not yours. It creates the branch `<type>/T-001-<slug>` and switches to it. If it says the previous task has no approval tag, tell the person: they run `thanhtan task seal <id>` themselves. If it warns that the previous task was never replanned, or that its replan is only proposed, tell the person and offer the replan skill (`replan`); they close it with `thanhtan replan done` or `thanhtan replan skip` themselves.
6. Carry on with the continue skill. It runs the **confirm** step with the orchestrator agent and stops at the person's approval; after the approval it keeps going by itself. The cycle is confirm, plan, **test-spec** (the tester writes the tests first and thanhtan checks that they fail; a person approves, small task or not), implement, test, security, review.
