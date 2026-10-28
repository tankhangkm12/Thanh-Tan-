---
name: business-logic
description: Write or change the business rules of a backend service (validation, calculations, state changes, transactions) in the layer where the project keeps them. Use for plan items about domain behaviour rather than transport or storage.
---
# Implement business logic

This skill does not assume any language or framework. Learn the structure from the project itself.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`. You never push, merge or open a pull request; that is the person's job.

1. Find where the project keeps domain rules (services, use cases, domain objects, whatever it calls them) by reading how two or three existing features are built. Put new rules in that same layer.
2. Write the rule down first as examples: inputs, expected outputs, and the cases that must be refused. These become the tests (backend-testing skill) and the item's `done-when`.
3. Keep rules independent of transport and storage: no request objects, no HTTP codes, no raw query strings in the rule itself. Depend on the data-access abstractions the project already has.
4. Decide the transaction boundary: a rule that changes several records either changes all of them or none. Follow how the project starts and ends transactions. Make operations safe to retry where the contract allows it.
5. Be explicit about errors: use the project's error types so the API layer can map them (see the api-implementation skill). Do not swallow errors and do not return success after a partial failure.
6. Money, time and identifiers need care: use the project's existing types for them, never floating point for money, and take the clock as a dependency so tests can control it.
7. Run the item's `done-when` check and commit with `agentflow commit "<what changed>" --item <code>`.

If the rule needs a new table, column or index, that is a db-engineer item (see the db-migration skill). Do not write migrations yourself.
