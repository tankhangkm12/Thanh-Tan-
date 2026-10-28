# tools

Script build và bảo trì repo. Viết bằng Python, chạy qua uv (`uv run`), không dùng Node.

| Script | Việc làm |
|---|---|
| `build.py` | Sinh agent của Claude Code (`claude/agents/`) và Antigravity (`agents/`) từ `src/roles/` của plugin, cập nhật danh sách `agents` trong manifest. `--check` để kiểm. Xem [dev-core](../families/software-dev/core/README.md) |
| `test_build.py` | Test của `build.py` và của dev-core (role, skill, tool, file sinh ra phải khớp nguồn; quy tắc prompt: không nối lệnh, nói rõ agent không push/merge/PR; khối quy tắc permissions trong README) |
| `smoke.py` | Thử end-to-end `agentflow` (init, task, plan check, commit, scan thật, guard, hook) trên repo tạm. Cần Docker |
| `smoke_backend.py` | Thử end-to-end dev-core + dev-backend trên dự án mẫu (`sample_backend.py`: Python một endpoint, PostgreSQL trong Docker, migration lên/xuống, spec OpenAPI). `--until plan|implement` dừng sớm; `--install-check` cài lại `dev-core`, `dev-backend` vào Claude Code (marketplace local) và Antigravity (đường dẫn local) rồi xác nhận skill, agent, hook được nạp (một lượt `claude -p` ngắn) và in cảnh báo nếu settings của dự án mẫu thiếu quy tắc `ask` bắt buộc |
| `smoke_modes.py`, `fake_mcp_server.py` | Thử end-to-end tier và `layer-order` (thứ tự sai và tier lạ bị từ chối, `plan assign` giao `implementer-fast`/`implementer-deep`), `role grant` (server MCP giả `fake_mcp_server.py` với một tool đọc và một tool ghi: implementer nhận cả server, reviewer bị từ chối tool ghi và cả server, file `project-*.md` có tool, nằm ngoài git, guard và hook chặn agent) và task `small` (bỏ duyệt plan, tối đa 3 mục, chỉ Gitleaks và Semgrep, size trong state và summary). Cần Docker |
| `smoke_support.py`, `conventions_smoke.py` | Phần dùng chung của các smoke (smoke luôn dùng `agentflow` build từ `foundation/` của repo qua `uv sync`, không dùng bản cài trên PATH): `Session`/`expect`, và luồng quy ước (scout ghi qua server MCP thật, người xác nhận và trả lời, rule Semgrep của người, gate review, bài học, các lần ghi bị chặn) |
| `trial_cli.py` | Phiên **thật** của `claude -p` và `agy -p` với plugin đã cài, trong repo tạm: mặc định thử hook (ghi vào `.ThanhTan/` và `git push` bị chặn, `git status` vẫn chạy); `--mcp` thử tool `status`/`report_write`; `--setup` thử skill `setup` và scout; `--modes` (chỉ Antigravity, không tốn giới hạn Claude Code) thử agent `implementer-fast` làm một mục kế hoạch thật qua agentflow và một grant với plugin MCP giả (agent gọi được tool dù `tools:` của agent không liệt kê). Kết luận dựa trên hiệu ứng thật (file có tồn tại không, log hook `AGENTFLOW_HOOK_LOG`), không dựa vào lời model; mỗi CLI được thử lại một lần |
| `test_setup.py`, `test_conventions_prompts.py` | Test câu chữ của role `scout`, skill `setup` và prompt làm việc theo quy ước |
| `test_smoke_backend.py` | Test của các hàm phụ trợ trong smoke_backend (không cần Docker) |
| `docs_standard.py`, `test_docs_standard.py` | Kiểm chuẩn tài liệu của plugin ([architecture](../docs/architecture.md#chuẩn-tài-liệu-của-plugin)): nhóm có core thì cần `USAGE.md` với mục `## Khuôn yêu cầu task` (có khối code), mỗi plugin con có mục `## Dùng cùng <tên core>`, README gốc link tới USAGE.md, link tương đối trong các file đó trỏ đúng. Chạy `uv run tools/docs_standard.py`; test có ca thiếu cố ý trên bản tạm và ca repo thật |
| `test_backend.py` | Test của dev-backend: role `db-engineer`, 6 skill không giả định stack, agent sinh ra khớp nguồn |

```
uv run tools/build.py --check
uv run tools/build.py --plugin families/software-dev/backend --check
uv run --with pyyaml --with pytest pytest tools
```
