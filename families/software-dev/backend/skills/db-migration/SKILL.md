---
name: db-migration
description: Write a safe database migration with both an up and a down direction and prove it by running both with the project's own commands on the database in its container. Use for plan items that change the database schema; only the db-engineer role does this.
---
# Write a database migration

Only the **db-engineer** role writes migrations. Other roles ask for a db-engineer plan item instead.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`. You never push, merge or open a pull request; that is the person's job.

## Learn the project, do not guess

Run each on its own: `agentflow config get backend.db.engine`, `agentflow config get backend.migrations_dir`, `agentflow config get backend.migrate_up_command`, `agentflow config get backend.migrate_down_command`. Open the newest migrations in that folder and copy their naming, numbering and style.

## Write it

1. One migration, one purpose. Keep it small enough to review.
2. Write the **up** direction and a **down** direction that truly undoes it (drop what up created, restore what up removed). If data would be lost going down, say so in a comment at the top of the file.
3. Prefer changes that are safe on a running system: add columns as nullable or with a safe default and tighten later; create indexes in the way that does not block writes where the engine supports it; avoid rewriting a large table in one step; split a risky change into steps across migrations.
4. Make a migration safe to run again where the engine allows: guard creation and removal with existence checks.
5. Set timeouts for locks and statements at the top when the engine supports it, so a stuck migration fails instead of blocking the database.
6. Never put real data or secrets in a migration. Seed data belongs in the project's seeding mechanism.

## Prove it

Run the project's up command, then the down command, then the up command again, against the database in its container. All three must succeed. Do not mark the item done on a reading of the SQL alone. The item's `done-when` must name both the up and the down command (the plan check refuses a migration item without them).

When the database is PostgreSQL the test step lints the changed migrations with Squawk and blocks on any finding; read its output in `.ThanhTan/tasks/<task>/scans/` and fix the migration rather than asking for a suppression. For other databases that lint is skipped and the report says so.

Commit with `agentflow commit "<what changed>" --item <code>`.
