---
name: contract-test
description: Check that a running backend service honours its OpenAPI contract with Schemathesis, run in a container by agentflow scan. Use at the test step when the project declares an OpenAPI spec and a URL to call.
---
# Contract test against the OpenAPI spec

The contract test runs when the project declares both `backend.openapi.spec` (the spec file) and `backend.openapi.url` (where the running service answers). Otherwise `agentflow scan` skips it and its report says why.

Run every `agentflow` command on its own, as a single command line. Never join commands with `&&`, `;` or `|`. You never push, merge or open a pull request; that is the person's job.

1. Run `agentflow config get backend.openapi.spec` and `agentflow config get backend.openapi.url`. If either is not set, report that the contract test cannot run; a person sets them with `agentflow config set`.
2. The service must be running at that URL with the branch's code and a database holding the schema (the migrations applied with the project's up command). Start it the way the project documents; do not change application code to make a test pass.
3. Run `agentflow scan`. It runs Schemathesis in a container (pinned image, the repository read-only) that reaches the service on the host through the container host name, and stores the result in `.ThanhTan/tasks/<task>/scans/`.
4. Read the result. A failure means the service and the spec disagree: a status code or field the spec does not list, a response that does not match its schema, a crash on generated input, or a server error. Decide which side is wrong:
   - If the code is wrong, record the finding in the test report so the implementer fixes it.
   - If the spec is wrong, the spec changes in an implementer item; say so in the report.
5. The step cannot pass while the contract test fails. A person alone may suppress a finding, with `agentflow decide`; name the finding and ask.
6. If the service is not reachable, that is an environment problem: report it and fail or wait; never record the test as passed.
