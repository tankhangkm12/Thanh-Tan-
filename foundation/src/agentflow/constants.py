"""Fixed values used across agentflow: file names, enums, exit codes and keys.

No other module should spell these values as string literals.
"""

from enum import IntEnum, StrEnum

PACKAGE_NAME = "agentflow"
SCHEMA_VERSION = 1
ENCODING = "utf-8"

# Workspace layout (relative to the project root).
WORKSPACE_DIR = ".agentflow"
STATE_FILE = "state.json"
STATE_MD_FILE = "STATE.md"
CONFIG_FILE = "config.yaml"
WORKFLOW_COPY_FILE = "workflow.yaml"
DECISIONS_DIR = "decisions"
TASKS_DIR = "tasks"
PROJECT_DIR = "project"
KNOWLEDGE_DIR = "knowledge"
WORKSPACE_SUBDIRS = (DECISIONS_DIR, TASKS_DIR, PROJECT_DIR, KNOWLEDGE_DIR)
# Per-task files: <workspace>/tasks/<task id>/reports/<step id>.md
REPORTS_DIR = "reports"
MARKDOWN_SUFFIX = ".md"
GITKEEP_FILE = ".gitkeep"
EXCLUDE_ENTRY = f"{WORKSPACE_DIR}/"
TMP_SUFFIX = ".tmp"

# Schemas shipped inside the package.
SCHEMAS_DIR = "schemas"
WORKFLOW_SCHEMA_FILE = "workflow.schema.json"
STATE_SCHEMA_FILE = "state.schema.json"
CONFIG_SCHEMA_FILE = "config.schema.json"
EXTENSION_SCHEMA_FILE = "extension.schema.json"
EXTENSIONS_DIR = "extensions"
YAML_SUFFIX = ".yaml"

# Git plumbing.
GIT_EXECUTABLE = "git"
GIT_TOPLEVEL_ARGS = ("rev-parse", "--show-toplevel")
GIT_PATH_ARGS = ("rev-parse", "--git-path")
GIT_EXCLUDE_PATH = "info/exclude"

# Where a server that does not run in the project finds it, and where agentflow keeps per-user files.
PROJECT_DIR_ENV = "AGENTFLOW_PROJECT_DIR"
SHELL_PWD_ENV = "PWD"
USER_DIR_ENV = "AGENTFLOW_HOME"
USER_DIR_NAME = ".agentflow"
ACTIVE_PROJECT_FILE = "active-project.txt"
ANSWER_OPTION = "--answer"
USER_CONFIG_FILE = "user.yaml"
DEFAULT_KNOWLEDGE_DIR_NAME = "knowledge"
# When this environment variable names a file, every hook call appends one JSON line to it (for diagnosing CLIs).
HOOK_LOG_ENV = "AGENTFLOW_HOOK_LOG"
TOOL_TIMEOUT_SECONDS = 15
VERSION_FLAG = "--version"
ENGINE_INFO_ARG = "info"

# Gitflow: where each task type branches from.
MAIN_BRANCH = "main"
DEVELOP_BRANCH = "develop"
PROTECTED_BRANCHES = frozenset({MAIN_BRANCH, DEVELOP_BRANCH})
BRANCH_SEPARATOR = "/"

# Task ids look like T-001; branch slugs come from the task title.
TASK_ID_PREFIX = "T-"
TASK_ID_DIGITS = 3
SLUG_MAX_LENGTH = 40
SLUG_FALLBACK = "task"
COMMIT_PREFIX_SEPARATOR = ": "
# Git trailer that ties a commit to a plan item.
PLAN_ITEM_TRAILER = "Plan-Item"
SUMMARY_FILE = "summary.md"
LESSONS_DIR = "lessons"
LESSONS_HEADING = "Bài học đề xuất"
# The review report section where the reviewer says whether the project documents must change.
DRIFT_HEADING = "Đề xuất cập nhật hồ sơ"
DRIFT_NONE_TEXT = "không có"

# Secret scanning with Gitleaks in a container. The image is pinned on purpose.
GITLEAKS_IMAGE = "zricethezav/gitleaks:v8.24.0"
SCAN_TIMEOUT_SECONDS = 900
# Exit code Gitleaks is told to use for "leaks found", so it differs from its own errors.
GITLEAKS_LEAKS_EXIT_CODE = 99
CONTAINER_REPO_DIR = "/repo"


class ExitCode(IntEnum):
    OK = 0
    ERROR = 1
    USAGE = 2
    MISSING_REQUIREMENT = 3
    NOT_GIT_REPO = 4
    NO_WORKSPACE = 5
    INVALID_WORKFLOW = 6
    INVALID_STATE = 7
    WORKFLOW_MISMATCH = 8
    WORKFLOW_NOT_FOUND = 9
    SYNC_BLOCKED = 10
    INVALID_CONFIG = 11
    TASK_CONFLICT = 12
    NO_ACTIVE_TASK = 13
    INVALID_TRANSITION = 14
    DIRTY_WORKING_TREE = 15
    BRANCH_PROBLEM = 16
    NOTHING_STAGED = 17
    SECRETS_FOUND = 18
    ENGINE_NOT_RUNNING = 19
    SCAN_FAILED = 20
    GIT_FAILED = 21
    INVALID_INPUT = 22
    UNKNOWN_STEP = 23
    PLAN_INVALID = 24
    GATE_FAILED = 25
    TASK_NOT_SEALED = 26
    SCAN_BLOCKED = 27
    EXTENSION_INVALID = 28
    SETTINGS_INVALID = 29
    REPORT_REFUSED = 30
    PROJECT_WRITE_REFUSED = 31
    KNOWLEDGE_NOT_FOUND = 32
    CONVENTIONS_INVALID = 33
    ROLE_GRANT_REFUSED = 34
    ROADMAP_INVALID = 35


class ToolName(StrEnum):
    """The MCP tools agentflow offers an agent. Nothing that is a person's call (approve, cancel, seal, decide,
    extensions, settings, pushing knowledge, confirming conventions) is on this list."""

    STATUS = "status"
    NEXT_STEP = "next_step"
    PLAN_CHECK = "plan_check"
    REPORT_WRITE = "report_write"
    PROJECT_WRITE = "project_write"
    SCAN_SUMMARY = "scan_summary"
    CONVENTIONS = "conventions"
    KNOWLEDGE_SEARCH = "knowledge_search"
    KNOWLEDGE_READ = "knowledge_read"


MCP_SERVER_NAME = "agentflow"
# The tools that only read the workspace (the rest write a report or a project document).
READ_ONLY_TOOLS = frozenset(
    {
        ToolName.STATUS,
        ToolName.NEXT_STEP,
        ToolName.PLAN_CHECK,
        ToolName.SCAN_SUMMARY,
        ToolName.CONVENTIONS,
        ToolName.KNOWLEDGE_SEARCH,
        ToolName.KNOWLEDGE_READ,
    }
)


class CheckKind(StrEnum):
    """How a convention is checked. A closed set: a new kind needs code in agentflow."""

    PLAN = "plan"
    SEMGREP = "semgrep"
    REVIEW = "review"


class PlanRuleKind(StrEnum):
    """The plan rules a ``check: plan`` convention can switch on."""

    ITEM_ORDER = "item-order"
    LAYER_ORDER = "layer-order"


class ConventionStatus(StrEnum):
    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"


class ConventionPrefix(StrEnum):
    """Code prefix per source: project conventions, decisions of a person, the personal knowledge store."""

    PROJECT = "PC"
    DECISION = "DC"
    PERSONAL = "KC"


class ConventionField(StrEnum):
    CHECK = "check"
    RULE = "rule"
    STATUS = "status"
    SOURCE = "source"
    DESCRIPTION = "description"
    OVERRIDES = "overrides"
    # Parameters of a ``layer-order`` plan rule: the layers from first to last, and the paths it is limited to.
    LAYERS = "layers"
    SCOPE = "scope"
    DOCS = "docs"
    CODE = "code"


class ConventionSource(StrEnum):
    """Where an effective convention came from, in the order of priority."""

    DECISION = "decisions"
    PROJECT = "project"
    PERSONAL = "knowledge"


CONVENTIONS_FILE = "conventions.md"
DECISION_ANSWER_INFIX = "answer"
DECISION_ANSWER_KIND = "convention-answer"
DECISION_SCOPE_PROJECT = "project"
OPEN_QUESTIONS_HEADING = "## Câu hỏi mở"
SETUP_QUESTION_PATTERN = r"S\d+"
SEMGREP_RULE_SUFFIXES = (".yaml", ".yml")


class DriftDoc(StrEnum):
    """The project documents a review may propose to change (``- <document>: <proposal>``)."""

    PROFILE = "profile"
    MISSION = "mission"
    ARCHITECTURE = "architecture"
    CONVENTIONS = "conventions"
    ROADMAP = "roadmap"


class ProjectSection(StrEnum):
    """The project documents a scout writes (``.agentflow/project/<section>.md``)."""

    PROFILE = "profile"
    ARCHITECTURE = "architecture"
    SOURCES = "sources"
    CONVENTIONS = "conventions"
    ROADMAP = "roadmap"


# Limits for what the knowledge tools hand to a model.
KNOWLEDGE_TEXT_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".txt", ".json"})
KNOWLEDGE_MAX_FILE_BYTES = 200_000
KNOWLEDGE_SEARCH_DEFAULT_LIMIT = 10
KNOWLEDGE_SEARCH_MAX_LIMIT = 50
KNOWLEDGE_HIT_MAX_CHARS = 240


class TaskType(StrEnum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    HOTFIX = "hotfix"


TASK_BASE_BRANCH = {
    TaskType.FEATURE: DEVELOP_BRANCH,
    TaskType.BUGFIX: DEVELOP_BRANCH,
    TaskType.HOTFIX: MAIN_BRANCH,
}


class TaskEvent(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    APPROVE = "approve"
    CANCEL = "cancel"


# What `task advance --result` accepts.
STEP_RESULTS = (TaskEvent.PASS, TaskEvent.FAIL)


class TaskStatus(StrEnum):
    OPEN = "open"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


# Task statuses that mean the task is still somewhere inside the workflow.
IN_FLIGHT_TASK_STATUSES = frozenset({TaskStatus.OPEN, TaskStatus.BLOCKED})


class StepStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    PASSED = "passed"
    FAILED = "failed"


class HistoryEvent(StrEnum):
    STARTED = "started"
    PASSED = "passed"
    FAILED = "failed"
    APPROVED = "approved"
    BLOCKED = "blocked"
    # A person approved a blocked task, overriding the block.
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    DONE = "done"


class ActionKind(StrEnum):
    START_TASK = "start_task"
    CONTINUE = "continue"
    AWAIT_APPROVAL = "await_approval"
    BLOCKED = "blocked"


class DriftStatus(StrEnum):
    IN_SYNC = "in_sync"
    SOURCE_CHANGED = "source_changed"
    SOURCE_MISSING = "source_missing"


class SyncOutcome(StrEnum):
    UNCHANGED = "unchanged"
    UPDATED = "updated"


class Tool(StrEnum):
    UV = "uv"
    GIT = "git"
    DOCKER = "docker"
    PODMAN = "podman"


class ToolStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"
    WARNING = "warning"


REQUIRED_TOOLS = (Tool.UV, Tool.GIT)
# At least one of these must be installed.
CONTAINER_TOOLS = (Tool.DOCKER, Tool.PODMAN)

INSTALL_URLS = {
    Tool.UV: "https://docs.astral.sh/uv/getting-started/installation/",
    Tool.GIT: "https://git-scm.com/downloads",
    Tool.DOCKER: "https://docs.docker.com/get-started/get-docker/",
    Tool.PODMAN: "https://podman.io/docs/installation",
}


class Command(StrEnum):
    DOCTOR = "doctor"
    INIT = "init"
    STATUS = "status"
    NEXT = "next"
    WORKFLOW = "workflow"
    TASK = "task"
    REPORT = "report"
    COMMIT = "commit"
    GUARD = "guard"
    HOOK = "hook"
    MCP = "mcp"
    PROJECT = "project"
    CONVENTIONS = "conventions"
    KNOWLEDGE = "knowledge"
    ROADMAP = "roadmap"
    PLAN = "plan"
    SCAN = "scan"
    DECIDE = "decide"
    EXT = "ext"
    CONFIG = "config"
    ROLE = "role"


class ProjectCommand(StrEnum):
    CONFIRM = "confirm"
    STATUS = "status"


class RoadmapCommand(StrEnum):
    LIST = "list"
    SET = "set"


class RoadmapStatus(StrEnum):
    """Where a roadmap item stands. Only a person (or agentflow when a task is tied to the item) moves it."""

    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    DROPPED = "dropped"


class RoadmapField(StrEnum):
    STATUS = "status"
    GOAL = "goal"
    DOCS = "docs"


class MissionField(StrEnum):
    """The bullets of the ``## Mission`` section of the project profile."""

    WHY = "why"
    FOR = "for"
    SCOPE = "scope"
    OUT_OF_SCOPE = "out-of-scope"
    SOURCE = "source"


class ConfirmUnit(StrEnum):
    """Project documents (or parts of one) a person confirms by name; an agent can rewrite them but never confirm."""

    MISSION = "mission"
    PROFILE = "profile"
    ARCHITECTURE = "architecture"
    CONVENTIONS = "conventions"
    ROADMAP = "roadmap"


class ConfirmState(StrEnum):
    MISSING = "missing"
    UNCONFIRMED = "unconfirmed"
    CONFIRMED = "confirmed"


# Files under .agentflow/project/ that agentflow writes itself.
CONFIRMATIONS_FILE = "confirmations.json"
HISTORY_DIR = "history"
MISSION_HEADING = "Mission"
ROADMAP_ITEM_PATTERN = r"R[0-9]+"
ROADMAP_FILE_STEM = "roadmap"


class UserConfigKey(StrEnum):
    KNOWLEDGE_DIR = "knowledge_dir"


class KnowledgePlace(StrEnum):
    """Where in the personal store a pushed file goes."""

    LESSONS = "lessons"
    PATTERNS = "patterns"


class KnowledgeCommand(StrEnum):
    INIT = "init"
    PULL = "pull"
    PUSH = "push"


class McpCommand(StrEnum):
    SERVE = "serve"


class WorkflowCommand(StrEnum):
    SYNC = "sync"


class TaskCommand(StrEnum):
    NEW = "new"
    ADVANCE = "advance"
    APPROVE = "approve"
    CANCEL = "cancel"
    SEAL = "seal"


class HookEvent(StrEnum):
    """What a hook is for; each CLI maps its own event names onto these."""

    SESSION_START = "session-start"
    PRE_TOOL = "pre-tool"
    STOP = "stop"


class CliKind(StrEnum):
    CLAUDE = "claude"
    ANTIGRAVITY = "antigravity"


class ReplyKind(StrEnum):
    """What the hook logic wants to tell the CLI; adapters turn it into each CLI's format."""

    NONE = "none"
    DENY = "deny"
    CONTEXT = "context"
    REMINDER = "reminder"


class ClaudeHookKey(StrEnum):
    CWD = "cwd"
    TOOL_NAME = "tool_name"
    TOOL_INPUT = "tool_input"
    COMMAND = "command"
    FILE_PATH = "file_path"
    NOTEBOOK_PATH = "notebook_path"
    STOP_HOOK_ACTIVE = "stop_hook_active"
    HOOK_SPECIFIC_OUTPUT = "hookSpecificOutput"
    HOOK_EVENT_NAME = "hookEventName"
    PERMISSION_DECISION = "permissionDecision"
    PERMISSION_DECISION_REASON = "permissionDecisionReason"
    ADDITIONAL_CONTEXT = "additionalContext"
    SYSTEM_MESSAGE = "systemMessage"


class ClaudeHookValue(StrEnum):
    PRE_TOOL_USE = "PreToolUse"
    SESSION_START = "SessionStart"
    DENY = "deny"


class AntigravityHookKey(StrEnum):
    WORKSPACE_PATHS = "workspacePaths"
    TOOL_CALL = "toolCall"
    NAME = "name"
    ARGS = "args"
    COMMAND_LINE = "CommandLine"
    TARGET_FILE = "TargetFile"
    CWD = "Cwd"
    INVOCATION_NUM = "invocationNum"
    INJECT_STEPS = "injectSteps"
    EPHEMERAL_MESSAGE = "ephemeralMessage"
    DECISION = "decision"
    REASON = "reason"


class AntigravityDecision(StrEnum):
    DENY = "deny"
    # Any value but "continue" lets the agent stop.
    ALLOW_STOP = "allow"


# Antigravity numbers model invocations from 0; only the first one gets the session summary.
ANTIGRAVITY_FIRST_INVOCATION = 0
# What a Antigravity PreToolUse hook prints when it has no objection. An empty string means "no output";
# its handling by `agy` is checked by the install smoke test (see tools/).
# Tools of each CLI that write a file. Claude Code: Write, Edit and NotebookEdit are documented (MultiEdit is
# not any more, but costs nothing to cover). Antigravity: the file tools of its hooks reference.
CLAUDE_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
ANTIGRAVITY_WRITE_TOOLS = frozenset({"write_to_file", "replace_file_content", "multi_replace_file_content"})
ANTIGRAVITY_PRE_TOOL_PASS_OUTPUT = ""
EMPTY_JSON_OBJECT = "{}"


class GuardDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class GuardRule(StrEnum):
    """Why `agentflow guard` denied a shell command."""

    PUSH = "push"
    PROTECTED_BRANCH = "protected-branch"
    RESET_HARD = "reset-hard"
    CLEAN_FORCE_DIRS = "clean-force-dirs"
    BRANCH_FORCE_DELETE = "branch-force-delete"
    TAG_DELETE = "tag-delete"
    DIRECT_COMMIT = "direct-commit"
    APPROVAL_TAG = "approval-tag"
    PERSON_ONLY = "person-only"
    WORKSPACE_WRITE = "workspace-write"


class GuardKey(StrEnum):
    """Keys of the JSON that `agentflow guard` reads and writes."""

    COMMAND = "command"
    CWD = "cwd"
    DECISION = "decision"
    REASON = "reason"
    RULE = "rule"


# Tags `agentflow task approve` creates; nobody else may create refs under this prefix.
APPROVAL_TAG_PREFIX = "agentflow/"
APPROVAL_TAG_SUFFIX = "approved"
TAG_REF_PREFIX = "refs/tags/"
AGENTFLOW_PROGRAM = "agentflow"


class WorkflowKey(StrEnum):
    SCHEMA_VERSION = "schema_version"
    FAMILY = "family"
    MAX_ROUNDS = "max_rounds"
    STEPS = "steps"
    ID = "id"
    NAME = "name"
    ROLE = "role"
    REQUIRES_APPROVAL = "requires_approval"
    ON_FAIL = "on_fail"
    GATES = "gates"
    TIERED_ROLES = "tiered_roles"
    SIZES = "sizes"
    READ_ONLY_ROLES = "read_only_roles"
    AGENT_DIRS = "agent_dirs"


class SizeKey(StrEnum):
    """Keys of the ``sizes`` section of a workflow: named profiles that make a task lighter or heavier."""

    DEFAULT = "default"
    PROFILES = "profiles"
    SKIP_APPROVAL = "skip_approval"
    MAX_PLAN_ITEMS = "max_plan_items"
    SCANS = "scans"


class GateKind(StrEnum):
    """Checks a step must pass before ``task advance --result pass`` is accepted."""

    PLAN_VALID = "plan-valid"
    SCANS_CLEAN = "scans-clean"
    CONVENTIONS_REVIEWED = "conventions-reviewed"
    DRIFT_REVIEWED = "drift-reviewed"


class PlanCommand(StrEnum):
    CHECK = "check"
    ASSIGN = "assign"


class ExtCommand(StrEnum):
    ADD = "add"
    LIST = "list"
    SYNC = "sync"


class RoleCommand(StrEnum):
    GRANT = "grant"
    REVOKE = "revoke"
    LIST = "list"
    SYNC = "sync"


class ReadVerb(StrEnum):
    """What the name of an MCP tool starts with when the tool only reads. A role that is read-only may be granted
    nothing else: agentflow cannot ask another MCP server what a tool does, so it goes by the name."""

    GET = "get"
    LIST = "list"
    READ = "read"
    SEARCH = "search"
    QUERY = "query"
    FIND = "find"
    DESCRIBE = "describe"
    VIEW = "view"
    STATUS = "status"


# Tools a project grants a role are MCP tools: ``mcp__<server>``, ``mcp__<server>__*`` or ``mcp__<server>__<tool>``.
MCP_TOOL_PREFIX = "mcp__"
MCP_TOOL_SEPARATOR = "__"
MCP_WILDCARD = "*"
# The project-level copy of a plugin agent that carries the granted tools (Claude Code reads .claude/agents/).
PROJECT_AGENT_PREFIX = "project-"
CLAUDE_PROJECT_AGENTS_DIR = ".claude/agents"
PROJECT_AGENT_EXCLUDE_ENTRY = f"{CLAUDE_PROJECT_AGENTS_DIR}/{PROJECT_AGENT_PREFIX}*{MARKDOWN_SUFFIX}"
PROJECT_AGENT_MARKER = "Generated by agentflow role sync"


class ConfigCommand(StrEnum):
    GET = "get"
    SET = "set"
    CHECK = "check"


class StateKey(StrEnum):
    SCHEMA_VERSION = "schema_version"
    UPDATED_AT = "updated_at"
    ACTIVE_TASK_ID = "active_task_id"
    TASKS = "tasks"
    ID = "id"
    TITLE = "title"
    STATUS = "status"
    CURRENT_STEP = "current_step"
    STEP_STATUS = "step_status"
    LOOP_ROUND = "loop_round"
    BRANCH = "branch"
    SIZE = "size"
    ROADMAP = "roadmap"
    HISTORY = "history"
    AT = "at"
    STEP = "step"
    EVENT = "event"


class ConfigKey(StrEnum):
    SCHEMA_VERSION = "schema_version"
    WORKFLOW = "workflow"
    FAMILY = "family"
    SOURCE_PATH = "source_path"
    SHA256 = "sha256"
    EXTENSIONS = "extensions"
    SETTINGS = "settings"
    NAME = "name"
    ROLE_GRANTS = "role_grants"


# ----------------------------------------------------------------- plan

class PlanField(StrEnum):
    """Field names of a plan item (a bullet under its ``### C<n>`` heading)."""

    ROLE = "role"
    FILES = "files"
    DONE_WHEN = "done-when"
    DOCS = "docs"
    KIND = "kind"
    TIER = "tier"
    LAYER = "layer"
    # Fields of a question under "Chưa có quy ước".
    ASK = "ask"
    OPTIONS = "options"
    NEEDED_BY = "needed-by"


class PlanItemKind(StrEnum):
    """What a plan item does to its files, for the ``item-order`` convention."""

    INTERFACE = "interface"
    IMPLEMENT = "implement"
    OTHER = "other"


class PlanTier(StrEnum):
    """How much model an item needs: ``fast`` for routine work, ``deep`` for the hard parts. A missing tier means deep."""

    FAST = "fast"
    DEEP = "deep"


DEFAULT_PLAN_TIER = PlanTier.DEEP
# An agent of a tiered role is named <role>-<tier>.
AGENT_NAME_SEPARATOR = "-"
LIST_SEPARATOR = ","

PLAN_ITEM_CODE_PATTERN = r"C[0-9]+"
PLAN_QUESTION_CODE_PATTERN = r"Q[0-9]+"
PLAN_QUESTIONS_HEADING = "Chưa có quy ước"
PLAN_NO_DOCS_PREFIX = "không có"
PLAN_NO_FILES_PREFIX = "không có"

# ----------------------------------------------------------------- scans

SCANS_DIR = "scans"
SCAN_SUMMARY_FILE = "summary.json"
SEMGREP_IMAGE = "semgrep/semgrep:1.180.0"
# Rules a person wrote for their conventions: kept in the knowledge store (``semgrep/``) and copied next to the workspace.
SEMGREP_CONVENTION_RULES_DIR = "semgrep"
CUSTOM_RULES_MOUNT = "/custom-rules"
CUSTOM_RULES_CACHE_DIR = "convention-rules"
TRIVY_IMAGE = "aquasec/trivy:0.75.0"
TRIVY_CACHE_VOLUME = "agentflow-trivy-cache"
SEMGREP_RULES_DIR = "semgrep-rules"
CACHE_DIR_ENV = "AGENTFLOW_CACHE_DIR"
APP_CACHE_DIR = "agentflow"
SEMGREP_RULES_URL = "https://semgrep.dev/c/{ruleset}"
SEMGREP_DEFAULT_RULESETS = ("p/default",)
SEMGREP_RULES_MAX_AGE_SECONDS = 7 * 24 * 3600
FETCH_TIMEOUT_SECONDS = 120
HOST_GATEWAY_NAME = "host.docker.internal"
DECISION_SUPPRESS_SUFFIX = "suppress"


class NetworkMode(StrEnum):
    """Network a scan container gets. Extensions may only ask for ``none`` or ``host-gateway``."""

    NONE = "none"
    BRIDGE = "bridge"
    HOST_GATEWAY = "host-gateway"


class ResultKind(StrEnum):
    """How a scan tool's output becomes findings."""

    JSON_FINDINGS = "json_findings"
    EXIT_CODE = "exit_code"


class ScanStatus(StrEnum):
    CLEAN = "clean"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class FileScope(StrEnum):
    CHANGED = "changed"

