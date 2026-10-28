---
name: query-review
description: Review database queries and indexes a change adds or modifies for correctness, performance and safety. Use during implementation or review of backend code that reads or writes a database.
---
# Review queries

This skill does not assume any database library. Learn how the project talks to its database, then check each query the change adds or modifies.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`. You never push, merge or open a pull request; that is the person's job.

Find the queries with `git diff` against the base branch of the task (shown by `agentflow status`) and by reading the data-access code the change touches. For each query check:

1. **Correctness.** Joins and filters return exactly the rows the rule needs; null handling is intended; ordering is explicit wherever order matters; pagination has a stable sort key.
2. **Injection.** Values reach the database only through parameters or the project's query builder. String-built queries from input are a must-fix.
3. **Access pattern.** Every filter, join and sort column that runs on a large table has a usable index. Look for queries in loops (one query per row) and for fetching whole tables or all columns when few are needed.
4. **Indexes themselves.** A new index matches a real query, has the right column order, and is created through a db-engineer migration (see the db-migration skill). An index nobody uses costs every write.
5. **Transactions and locking.** Reads that feed a write happen in the same transaction; long transactions do not wait on slow external calls; updates that can race use the project's way of locking or checking versions.
6. **Data exposure.** Only the columns the caller may see are selected; sensitive columns are never logged.

If the database offers a way to show a query plan, use it on the project's own database (the settings and commands are in `agentflow config get backend.*`). Report findings with file and line, severity, and a concrete fix. Do not rewrite code unless the plan item asks for it.
