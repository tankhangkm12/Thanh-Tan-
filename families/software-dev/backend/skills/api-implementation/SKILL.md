---
name: api-implementation
description: Implement or change an API endpoint of a backend service so that it matches the project's API contract and conventions. Use for plan items that add, change or remove an endpoint, route or request/response shape.
---
# Implement an API endpoint

This skill does not assume any language or framework. Learn the stack from the project itself.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`. You never push, merge or open a pull request; that is the person's job.

1. Read the settings that matter: `agentflow config get backend.openapi.spec` (the contract file, if the project has one) and `agentflow config get backend.test_command`. If a setting is not set, say so; do not invent a value.
2. Read the contract first. If the project has an OpenAPI spec, the endpoint's path, method, parameters, status codes and response schema come from it. If the plan item changes the contract, change the spec in the same item and keep the code and the spec in step.
3. Find how the existing endpoints are written: where routes are declared, how input is validated, how errors become responses, how authentication and authorisation are applied, how logging is done. Copy that structure; do not introduce a new pattern.
4. Keep the endpoint thin: parse and validate input, call the business logic (see the business-logic skill), map the result or error to a response. No business rules and no raw data access inside the handler unless the project already does it that way.
5. Cover the failure cases the contract lists: invalid input, missing resource, not allowed, conflict. Never leak internal errors, stack traces or secrets in a response.
6. Add or update tests with the backend-testing skill, run the item's `done-when` check, then commit with `agentflow commit "<what changed>" --item <code>`.

Do not touch migrations: only the db-engineer role may. If the endpoint needs a schema change, tell the caller that a db-engineer item is needed.
