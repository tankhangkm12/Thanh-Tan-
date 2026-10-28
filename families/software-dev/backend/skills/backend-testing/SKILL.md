---
name: backend-testing
description: Write and run tests for backend code using the project's own test command and conventions - unit tests for rules, integration tests for data access and endpoints. Use when a backend plan item needs tests or when checking test coverage of a change.
---
# Test backend code

This skill does not assume any language or test framework. Read how the project tests itself, then follow that.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`. You never push, merge or open a pull request; that is the person's job.

1. Run `agentflow config get backend.test_command`. That is how the project runs its tests; use it exactly. If it is not set, say so; do not guess a command.
2. Look at the existing tests: folder layout, naming, fixtures, how the database is provided to integration tests, how time and randomness are controlled. Add tests next to the existing ones in the same style.
3. Test at the right level:
   - **Rules** (business-logic skill): fast tests with no network and no database, one test per example and per refusal.
   - **Data access**: against a real database in its container, not a mock, because the point is that the query works. Each test starts from a known state and cleans up.
   - **Endpoints**: through the application's request entry point, checking status code, body and headers against the API contract.
4. Cover failures as carefully as success: invalid input, missing data, conflicts, permissions, and what happens when a dependency fails.
5. Tests must be deterministic: no sleeping for timing, no dependence on test order, no real external services.
6. Run the full test command before you report. A red or skipped test is reported as it is; never edit a test only to make it pass, and never change application code from the tester role (report it and fail the step instead).

The tester role writes only under the project's test folders. Commit with `agentflow commit "<what changed>"`.
