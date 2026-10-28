"""The thanhtan MCP server: the ``WorkspaceService`` as tools an agent can call.

The tools are thin: each one calls the service, so a rule the CLI enforces is enforced here too, and a broken
rule comes back as a tool error whose text says what to do. Only what an agent may do is offered; approving,
cancelling, sealing, deciding, extensions, settings and the personal knowledge store are a person's.
"""

import functools
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from thanhtan.constants import (
    KNOWLEDGE_SEARCH_DEFAULT_LIMIT,
    MCP_SERVER_NAME,
    READ_ONLY_TOOLS,
    ProjectSection,
    ToolName,
)
from thanhtan.errors import ThanhTanError
from thanhtan.interfaces import ProjectLocator, WorkspaceService
from thanhtan.projectlocator import EnvironmentProjectLocator
from thanhtan.services import WorkspaceServices

INSTRUCTIONS = (
    "thanhtan keeps the state of a software task in .ThanhTan/. Use these tools instead of editing files there. "
    "A tool that refuses says why; follow its message. Approving a step, cancelling, sealing, deciding, "
    "confirming a replan and changing settings are for a person and are not offered."
)


class CurrentProjectServices:
    """``WorkspaceService`` for the project the locator finds, looked up again on every call.

    A server outlives many commands (a workspace may even be created after it started), so nothing is cached.
    """

    def __init__(self, locator: ProjectLocator | None = None) -> None:
        self._locator = locator or EnvironmentProjectLocator()

    def _service(self) -> WorkspaceService:
        return WorkspaceServices(self._locator.find())

    def status(self):
        return self._service().status()

    def next_step(self):
        return self._service().next_step()

    def plan_check(self):
        return self._service().plan_check()

    def write_report(self, step, content):
        return self._service().write_report(step, content)

    def write_project(self, section, content):
        return self._service().write_project(section, content)

    def write_replan(self, content):
        return self._service().write_replan(content)

    def write_diagnosis(self, content):
        return self._service().write_diagnosis(content)

    def scan_summary(self):
        return self._service().scan_summary()

    def conventions(self):
        return self._service().conventions()

    def knowledge_search(self, query, limit):
        return self._service().knowledge_search(query, limit)

    def knowledge_read(self, file):
        return self._service().knowledge_read(file)


def _guarded(function: Callable[..., Any]) -> Callable[..., Any]:
    """Turn a broken rule into a tool error and a result into plain data."""

    @functools.wraps(function)
    def call(*args: Any, **kwargs: Any) -> Any:
        try:
            result = function(*args, **kwargs)
        except ThanhTanError as exc:
            raise ToolError(str(exc)) from exc
        if isinstance(result, (list, tuple)):
            return [asdict(item) for item in result]
        return asdict(result)

    return call


def build_server(service: WorkspaceService) -> MCPServer:
    server = MCPServer(MCP_SERVER_NAME, instructions=INSTRUCTIONS)

    def register(name: ToolName, description: str, function: Callable[..., Any]) -> None:
        hints = ToolAnnotations(readOnlyHint=name in READ_ONLY_TOOLS, destructiveHint=False)
        server.tool(name=str(name), description=description, annotations=hints)(_guarded(function))

    def status() -> dict[str, Any]:
        return service.status()

    def next_step() -> dict[str, Any]:
        return service.next_step()

    def plan_check() -> dict[str, Any]:
        return service.plan_check()

    def report_write(step: str, content: str) -> dict[str, Any]:
        return service.write_report(step, content)

    def project_write(section: ProjectSection, content: str) -> dict[str, Any]:
        return service.write_project(section, content)

    def replan_write(content: str) -> dict[str, Any]:
        return service.write_replan(content)

    def diagnosis_write(content: str) -> dict[str, Any]:
        return service.write_diagnosis(content)

    def scan_summary() -> dict[str, Any]:
        return service.scan_summary()

    def conventions() -> list[dict[str, Any]]:
        return service.conventions()

    def knowledge_search(query: str, limit: int = KNOWLEDGE_SEARCH_DEFAULT_LIMIT) -> list[dict[str, Any]]:
        return service.knowledge_search(query, limit)

    def knowledge_read(file: str) -> dict[str, Any]:
        return service.knowledge_read(file)

    register(ToolName.STATUS, "The workflow, the active task (step, status, branch, rework round) and what comes next.", status)
    register(ToolName.NEXT_STEP, "What to do next: start_task, continue, await_approval or blocked.", next_step)
    register(
        ToolName.PLAN_CHECK,
        "Check the active task's plan report. Returns {ok, problems}; problems are things to fix in the plan, not a tool failure.",
        plan_check,
    )
    register(
        ToolName.REPORT_WRITE,
        "Save the report of the CURRENT step of the open task (Markdown). Refused for another step and once the step has passed.",
        report_write,
    )
    register(
        ToolName.PROJECT_WRITE,
        "Save a project document (profile, architecture, sources or conventions) under .ThanhTan/project/. "
        "Refused while a task is open.",
        project_write,
    )
    register(
        ToolName.REPLAN_WRITE,
        "Propose the replan of the latest finished task (Markdown with the sections 'Mục roadmap đã hoàn thành' and "
        "'Đề xuất cải tiến quy trình'). It only proposes: a person reads it and says it is done. Refused while a task is open.",
        replan_write,
    )
    register(
        ToolName.DIAGNOSIS_WRITE,
        "Keep a diagnosis of a failure (Markdown with at least '## Tái hiện' and '## Nguyên nhân'). With a task open it is "
        "kept for that task's rework round; with none it becomes D-001, D-002, ... for a bugfix task. Never changes a task.",
        diagnosis_write,
    )
    register(ToolName.SCAN_SUMMARY, "Results of the scans run for the active task and the blocking findings left.", scan_summary)
    register(
        ToolName.CONVENTIONS,
        "The conventions to work to, merged from decisions, the project and the person's own store (highest priority first). "
        "`enforced` is false for project conventions nobody confirmed yet.",
        conventions,
    )
    register(
        ToolName.KNOWLEDGE_SEARCH,
        "Search the knowledge files a person copied into .ThanhTan/knowledge/ (case-insensitive). Returns file, line and text.",
        knowledge_search,
    )
    register(ToolName.KNOWLEDGE_READ, "Read one file of .ThanhTan/knowledge/ by its relative path.", knowledge_read)
    return server


def serve(locator: ProjectLocator | None = None) -> None:
    """Run the server on stdio until the client disconnects."""
    build_server(CurrentProjectServices(locator)).run("stdio")
