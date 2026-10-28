---
name: refactor
description: Start a refactor task with agentflow - restructure code without changing what it does; the tests must pass before and after. Use when the person types /dev-core:refactor.
---
# /dev-core:refactor

Do every step of the start skill (`/dev-core:start`; its file is `skills/start/SKILL.md` in this plugin: in Claude Code `${CLAUDE_PLUGIN_ROOT}/skills/start/SKILL.md`, in Antigravity under `~/.gemini/antigravity-cli/plugins/dev-core/skills/start/`), with one difference: the type is `refactor` (`--type refactor`) and the size is `normal` (no `--size`; for a tiny one the person types `/dev-core:start-small`). The test-spec step works the other way round: the tests must pass on the code as it is, and keep passing after the change.

This command fixes these choices; what the start skill says about choosing a type or a size does not apply. Use `agentflow` for everything, run each `agentflow` command on its own line, and never push, merge or open a pull request.
