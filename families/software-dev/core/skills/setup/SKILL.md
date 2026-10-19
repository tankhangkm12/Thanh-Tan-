---
name: setup
description: Set up agentflow for an existing project. Use before the first task, or when the project changed a lot. Asks the person where the project's documents are, has the scout read them and the code, and writes the project profile, architecture, sources and conventions for the person to confirm.
---
# Set up a project

Use `agentflow` and its tools for everything below. Never create or edit files under `.agentflow/` by hand.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job.

1. Call the `status` tool (or run `agentflow status`).
   - No workspace yet: run `agentflow init --workflow <path to dev-core's workflow.yaml>` as the start skill describes.
   - A task is open: stop. Project documents are written when no task is open; ask the person to finish or cancel the task first.
2. **Ask the person** where the project's documents are: paths of files or folders (requirements and the project's vision or mission, architecture notes, a backlog or TODO list, contributing guide, ADRs, README, wiki exports). Wait for the answer. Do not look for documents yourself and do not search the disk or home directories; read only the paths you were given, plus the project's own code. If the person says there are none, the scout works from the code alone.
3. Hand the paths to the `scout` agent (in Claude Code by calling the agent of that name, in Antigravity by using the agent of the same name). It reads the documents and the code, finds the build, test and lint commands, and writes the documents with `project_write`: `profile` (with its `## Mission` section), `architecture`, `sources`, `conventions` and `roadmap`. Conventions it inferred from code are marked `status: unconfirmed`, and so are the ones it took from documents. Where a document and the code disagree it writes a question under `## Câu hỏi mở` instead of choosing.
4. Tell the person what is now in `.agentflow/project/` and what is left for them:
   - read the files (`profile`, `architecture`, `sources`, `conventions`, `roadmap`), and run `agentflow project status` to see what is missing or unconfirmed;
   - the open questions (`S1`, `S2`, ...) need their answer;
   - confirm what they agree with by running the commands themselves (in Claude Code type them with the `!` prefix): the mission with `agentflow project confirm mission`, roadmap items with `agentflow project confirm R1 R2`, the conventions with `agentflow project confirm PC-01 PC-02` (`--all` confirms every convention, nothing else), the whole profile or architecture with `agentflow project confirm profile architecture`. The mission and the roadmap items stay unconfirmed until then; a status of a roadmap item is theirs too (`agentflow roadmap set R3 dropped`).

   You never run `agentflow project confirm`, `agentflow roadmap set` or `agentflow decide`: confirming is the person's authority. `agentflow task new` warns while the mission, the roadmap or conventions are still unconfirmed.
