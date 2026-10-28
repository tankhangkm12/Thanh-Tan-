# Ghi chú MCP (đã thử thật, 2026-10-10)

Thử bằng một plugin tạm có `.mcp.json` / `mcp_config.json` trỏ tới một server stdio dựng bằng SDK `mcp` 2.3.0.

## Claude Code 2.1.296

- Server của plugin đăng ký là `plugin:<plugin>:<server>` và tool có tên `mcp__plugin_<plugin>_<server>__<tool>` (ví dụ `mcp__plugin_probe-mcp_thanhtan__ok`). `claude -p` gọi được khi tên đó nằm trong `--allowedTools`.
- Subagent của plugin có `tools:` là danh sách cho phép: ghi đúng tên đầy đủ trên là subagent gọi được tool, không ghi thì không. Vì vậy `tools/build.py` ghi tên tool MCP vào từng agent theo role.
- `--allowedTools` nhận nhiều giá trị, nên prompt phải đi qua stdin.

## Antigravity 1.3.3

- Plugin khai báo server ở `mcp_config.json` (cùng dạng `mcpServers`); server hiện ra với tên `<plugin>_<server>` (ví dụ `probe-mcp_thanhtan`), tool giữ tên gốc (`ok`). `agy -p` gọi được.
- Trường `tools:` của agent **chỉ nhận tool dựng sẵn**. Ghi tên tool MCP dưới bất kỳ dạng nào (`ok`, `server/ok`, `mcp_server_ok`, `mcp(server/ok)`, tên server) đều làm agent không khởi động được: `unknown component: tool "..." not found in registry`.
- Agent có `tools:` vẫn gọi được tool MCP (thử với `tools: [view_file]`). Nghĩa là **không giới hạn tool MCP theo role được** trong Antigravity.
- Hệ quả: các luật phải do server tự kiểm (xem `project_write`: chỉ ghi khi không có task đang mở; nội dung quy ước phải đúng định dạng). Quyền theo role chỉ có ở Claude Code.
- Tài liệu không có biến "gốc plugin", nên `command` của server là `thanhtan` (cần cài global, như hook).
- Server của plugin Antigravity chạy với thư mục làm việc là **thư mục plugin** (`~/.gemini/config/plugins/<plugin>`), không phải dự án. `mcp_config.json` không thay biến (`${workspaceFolder}`, `${cwd}`, `${PWD}`… đều giữ nguyên chữ), và server không nhận được `roots` từ client. Biến môi trường `PWD` là của shell đã chạy `agy`, nên chỉ đúng khi chạy từ terminal trong dự án. Vì vậy `thanhtan` có `EnvironmentProjectLocator`: thư mục làm việc, `THANHTAN_PROJECT_DIR`, `PWD`, rồi file `~/.ThanhTan/active-project.txt` (`THANHTAN_HOME` đổi thư mục này) mà hook Antigravity viết mỗi khi chạy trong một dự án có workspace.
- Đã thử thật bằng `agy -p` và `claude -p` (`uv run tools/trial_cli.py --mcp`): cả hai gọi `status`, `report_write` và bị từ chối khi ghi báo cáo của bước không phải bước hiện tại.
- Vì thế `thanhtan role grant` (xem [architecture.md](architecture.md#cấp-tool-theo-dự-án)) **không sinh gì** cho Antigravity: role vốn thấy mọi MCP đã cài, grant chỉ được ghi nhận trong `config.yaml` cho đồng bộ với Claude Code, và `thanhtan role list` nói rõ điều đó. Luật "role chỉ đọc chỉ nhận tool đọc" vẫn kiểm lúc ghi nhận, nhưng không có gì chặn một agent Antigravity gọi tool ghi của MCP đã cài: cần giới hạn thật thì chỉ cài MCP đó khi cần.
- Một tiến trình `thanhtan mcp serve` đang chạy (ví dụ trong một phiên `agy` đang mở) giữ file `thanhtan.exe`, nên `uv tool install --force --reinstall` báo `Access is denied`. Đóng phiên đó, hoặc cài vào đúng venv của tool: `uv pip install --python <venv>\Scripts\python.exe --reinstall ./foundation`.
