# dev-core

Plugin lõi của nhóm **software-dev**. Giữ những gì mọi plugin `dev-*` dùng chung. Các plugin `dev-*` còn lại phụ thuộc vào `dev-core`.

## Có gì bên trong

| Thành phần | Vị trí | Việc làm |
|---|---|---|
| Workflow 6 bước | `workflow.yaml` | Đọc bởi `thanhtan init --workflow`; khai báo `tiered_roles` và hai cỡ task `normal`/`small` (xem [README gốc](../../../README.md#chế-độ-nhẹ-task-nhỏ)) |
| 5 skill | `skills/{setup,start,continue,status,approve}/SKILL.md` | Hồ sơ hóa dự án (hỏi người đường dẫn tài liệu rồi giao cho scout), bắt đầu task, làm tiếp, xem trạng thái, duyệt |
| 8 role, 9 agent | nguồn `src/roles/*.md` | `orchestrator`, `planner`, `implementer` (agent `implementer-fast` và `implementer-deep`), `tester`, `security`, `reviewer`, `scout` (đọc dự án, chỉ ghi qua `project_write`), `debugger` (tái hiện lỗi, tìm nguyên nhân, chỉ ghi chẩn đoán qua `diagnosis_write`) |
| Server MCP | `.mcp.json` (Claude Code), `mcp_config.json` (Antigravity) | Chạy `thanhtan mcp serve`: 9 tool cho agent (xem [architecture](../../../docs/architecture.md#tool-mcp)) |
| Hook | `hooks/hooks.json` (Claude Code), `hooks.json` (Antigravity) | Chặn lệnh git nguy hiểm, `git commit` trực tiếp và mọi ghi vào `.ThanhTan/` (tool ghi file; lệnh shell ở mức cố gắng tốt nhất), nạp tóm tắt task đầu phiên, nhắc cập nhật trạng thái khi dừng (chỉ khi bước đang chạy và đã có báo cáo mới) |

`workflow.yaml` còn khai báo `read_only_roles` (đồng bộ với `READ_ONLY_ROLES` của `build.py`, một test giữ hai danh sách bằng nhau) và `agent_dirs` (`claude/agents`, `agents`) để `thanhtan role grant` biết chép agent nào sang `.claude/agents/` của dự án. Xem [Cấp tool theo dự án](../../../README.md#cấp-tool-theo-dự-án-cho-role).

Skill gọi lệnh `thanhtan` và không bao giờ sửa tay file trong `.ThanhTan/`. Hook chỉ hoạt động trong dự án đã có `.ThanhTan/`.

Trong Claude Code, tên đầy đủ của skill là `/dev-core:setup`, `/dev-core:start`, `/dev-core:continue`, `/dev-core:status`, `/dev-core:approve`.

## Agent được sinh từ một nguồn

Sửa role ở `src/roles/<role>.md` (frontmatter `name`, `description`, `capabilities: [read, edit, run, workspace, project]` + nội dung prompt), rồi chạy:

```
uv run tools/build.py           # sinh claude/agents/*.md, agents/*.md và cập nhật danh sách agents trong manifest
uv run tools/build.py --check   # báo lỗi nếu file sinh ra đã cũ
```

Role có thể đặt model: `settings:` (một agent) hoặc `variants:` (một agent cho mỗi tier, tên `<role>-fast` và `<role>-deep`), mỗi mục có `claude: {model, effort}` và `antigravity: {model}`:

```
variants:
  fast:
    claude: {model: sonnet, effort: low}
    antigravity: {model: flash}
  deep:
    claude: {model: sonnet, effort: high}
    antigravity: {model: pro}
```

Trên Claude Code cả hai tier đều là Sonnet, khác nhau ở effort. Để dùng Opus cho `deep`, đổi dòng `claude` của `deep` thành `{model: opus, effort: medium}` rồi `uv run tools/build.py`; Opus tốn giới hạn sử dụng hơn. Build chỉ nhận giá trị trong tài liệu của từng CLI (Claude Code: `sonnet|opus|haiku|fable|inherit`, `low|medium|high|xhigh|max`; Antigravity: `inherit|flash|pro`, không có effort). Role không khai báo gì thì `inherit`. `workflow.yaml` có `tiered_roles: [implementer]` để `thanhtan plan assign` biết role nào có hai agent.

Không sửa tay `claude/agents/` và `agents/`. `build.py` đổi quyền trừu tượng thành tên tool thật của từng CLI, từ chối tên tool lạ và từ chối cấp quyền sửa file cho `orchestrator`, `planner`, `security`, `reviewer`, `scout`.

| Quyền | Claude Code | Antigravity |
|---|---|---|
| `read` | Read, Glob, Grep | view_file, list_dir, find_by_name, grep_search |
| `edit` | Edit, Write | write_to_file, replace_file_content, multi_replace_file_content |
| `run` | Bash, PowerShell | run_command |
| `workspace` | tool MCP `mcp__plugin_dev-core_thanhtan__*` (status, next_step, plan_check, report_write, scan_summary, conventions, knowledge_*) | không thêm gì: `tools:` của Antigravity chỉ nhận tool dựng sẵn, và tool MCP tới mọi agent |
| `project` | `project_write` (chỉ role `scout`) | như trên |

Lưu ý: tool chạy lệnh về lý thuyết vẫn có thể ghi file. Với các role chỉ đọc, đây là giới hạn của hai CLI chứ không phải của plugin; prompt của role cấm việc đó.

## Cài đặt

```
/plugin install dev-core --marketplace tankhangkm12/Thanh-Tan-
```

Chi tiết cả hai CLI: [README gốc](../../../README.md#cài-đặt). Cần cài `thanhtan` trước thì hook mới chạy.
