---
name: hotfix
description: Start a hotfix task with thanhtan - an urgent fix of what is released, from main (or the project's git.base.hotfix). Use when the person types /dev-core:hotfix.
---
# /dev-core:hotfix

Do every step of the start skill (`/dev-core:start`; its file is `skills/start/SKILL.md` in this plugin: in Claude Code `${CLAUDE_PLUGIN_ROOT}/skills/start/SKILL.md`, in Antigravity under `~/.gemini/antigravity-cli/plugins/dev-core/skills/start/`), with one difference: the type is `hotfix` (`--type hotfix`) and the size comes by itself (do not pass `--size`). Do not ask for a roadmap item. When it is done, thanhtan prints the commands the person runs to merge it into `main` and back into `develop`; read them to the person.

This command fixes these choices; what the start skill says about choosing a type or a size does not apply. Use `thanhtan` for everything, run each `thanhtan` command on its own line, and never push, merge or open a pull request.
