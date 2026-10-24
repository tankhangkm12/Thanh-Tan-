---
name: debug
description: Find the root cause of a bug in a software-dev project before fixing it, using agentflow. Use when the person reports an error or a wrong behaviour whose cause is not known yet, or asks to debug or investigate. The debugger agent reproduces it and writes a diagnosis; it never changes code. Then offers a bugfix task built on that diagnosis.
---
# Debug a failure

Use `agentflow` for everything below. Never create or edit files under `.agentflow/` by hand.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`.

You never push, merge or open a pull request; that is the person's job. You do not fix the bug here.

1. Run `agentflow status`. If a task is open and the failure belongs to it, the continue skill already calls the debugger when the task comes back to `implement`; tell the person and ask whether they still want a diagnosis now. Otherwise go on.
2. Get the symptom from the person: what they did, what happened, what they expected, the error text or the failing test. Ask only for what is missing.
3. Hand it to the `debugger` agent (in Claude Code the agent `debugger`, in Antigravity the agent of the same name), with the symptom in the person's words. It reproduces the failure, finds the root cause and saves a diagnosis (`D-001`, ... when no task is open).
4. Tell the person, in a few lines: the cause, the evidence (`file:line`), where the diagnosis is (`agentflow diagnosis show D-001`), and the fix it proposes.
5. Offer to start a `bugfix` task from it (the start skill). If they agree, start it and tell the orchestrator to read the diagnosis (`agentflow diagnosis show <code>`): its `## Nguyên nhân` and `## Test tái hiện` sections become the requirements and the test the tester writes first. A small, clear fix can be a `--size small` task.
