---
name: start-small
description: Start a small task (size small) with thanhtan - a tiny, well-bounded feature, bugfix, refactor or chore that fits in at most 3 plan items. Use when the person types /dev-core:start-small.
---
# /dev-core:start-small

Do every step of the start skill (`/dev-core:start`; its file is `skills/start/SKILL.md` in this plugin: in Claude Code `${CLAUDE_PLUGIN_ROOT}/skills/start/SKILL.md`, in Antigravity under `~/.gemini/antigravity-cli/plugins/dev-core/skills/start/`), with one difference: the size is `small` (`--size small`); the type is `feature`, `bugfix`, `refactor` or `chore`, inferred from the request (ask when it is not obvious). A hotfix is never small: point to `/dev-core:hotfix`. If the work clearly needs more than 3 plan items, say so and suggest the command of normal size; do not start it as small.

This command fixes these choices; what the start skill says about choosing a type or a size does not apply. Use `thanhtan` for everything, run each `thanhtan` command on its own line, and never push, merge or open a pull request.
