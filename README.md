# Thanh-Tan-

> **MVP.** Dùng được: plugin `dev-core` (quy trình task, hook an toàn, scan bảo mật, tool MCP, quy ước và kho kiến thức, 7 skill, 8 role) và `dev-backend` (role `db-engineer`, 6 skill, Squawk, Schemathesis) cho Claude Code và Antigravity CLI, chạy trên động cơ `agentflow`. Các plugin `dev-design`, `dev-frontend`, `dev-infra` vẫn là khung.

Trung tâm của nhiều **nhóm plugin** cho Claude Code và Antigravity CLI. Mỗi nhóm có core và chuẩn riêng; mọi nhóm dùng chung một động cơ là `foundation/` (package Python `agentflow`).

## Các nhóm

| Nhóm | Trạng thái | Plugin |
|---|---|---|
| [software-dev](families/software-dev/README.md) ([hướng dẫn sử dụng](families/software-dev/USAGE.md)) | MVP (`dev-core` dùng được) | `dev-core`, `dev-design`, `dev-backend`, `dev-frontend`, `dev-infra` |
| [design-system](families/design-system/README.md) ([hướng dẫn sử dụng](families/design-system/core/USAGE.md)) | Dùng thử được (đã chạy thử G0–G2 trên dự án thật) | `design-core`, `design-architecture` |
| [marketing](families/marketing/README.md) | Dự kiến, chưa xây | — |

Kiến trúc và quy tắc phụ thuộc: [docs/architecture.md](docs/architecture.md).

## Cấu trúc

```
.claude-plugin/marketplace.json   marketplace Claude Code (thanh-tan-plugins)
foundation/                       package agentflow (uv)
families/<nhóm>/<plugin>/         từng plugin: .claude-plugin/plugin.json + plugin.json (Antigravity)
tools/                            build.py (sinh agent), smoke.py (thử end-to-end)
docs/                             tài liệu kiến trúc
```

## Cài đặt từng bước

### Bước 0: yêu cầu

`git`, [`uv`](https://docs.astral.sh/uv/getting-started/installation/), và **Docker Desktop (hoặc Podman) đang chạy** (dùng để quét secret khi `agentflow commit`). Kiểm tra sau khi cài `agentflow` ở bước 1 bằng `agentflow doctor`.

Clone repo (nhánh mặc định là `develop`):

```
git clone https://github.com/tankhangkm12/Thanh-Tan-.git
cd Thanh-Tan-
```

Dưới đây `<repo>` là đường dẫn tới thư mục vừa clone.

### Bước 1: cài `agentflow` (bắt buộc, cả hai CLI đều dùng)

Hook của `dev-core` gọi lệnh `agentflow`, nên nó phải nằm trong PATH.

```
uv tool install --force --reinstall "<repo>/foundation"
agentflow --version
agentflow doctor
```

`agentflow doctor` còn so phiên bản `agentflow` trên PATH với phiên bản đang chạy: nếu lệch phiên bản (sau khi cập nhật plugin hoặc `git pull` mà chưa cài lại) nó cảnh báo và in lệnh `uv tool install --force --reinstall ./foundation` (chạy từ thư mục repo). Hook cũ không hiểu các câu trả lời mới như `ask`, nên đừng bỏ qua cảnh báo này.

Không cần clone cũng được: `uv tool install --force "git+https://github.com/tankhangkm12/Thanh-Tan-#subdirectory=foundation"`.

Nếu terminal không nhận `agentflow`: chạy `uv tool update-shell` rồi mở lại terminal. Sau mỗi lần `git pull` repo, chạy lại lệnh `uv tool install --force --reinstall ...` ở trên. Gỡ: `uv tool uninstall agentflow`.

### Bước 2a: cài vào Claude Code

Cách 1, từ GitHub (không phụ thuộc nhánh đang checkout):

```
claude plugin marketplace add tankhangkm12/Thanh-Tan-
claude plugin install dev-core@thanh-tan-plugins
```

Cách 2, từ bản clone local (Claude Code đọc thẳng thư mục repo, nên nội dung đổi theo nhánh đang checkout; nên để repo ở `develop`):

```
claude plugin marketplace add "<repo>"
claude plugin install dev-core@thanh-tan-plugins
```

Kiểm tra: `claude plugin list` phải thấy `dev-core@thanh-tan-plugins` ở trạng thái enabled. Mở lại Claude Code, gõ `/dev-core:` sẽ thấy `setup`, `start`, `continue`, `status`, `approve`, `replan`, `debug`. 9 agent (8 role, riêng implementer có hai biến thể) hiện dưới tên `dev-core:orchestrator`, `dev-core:planner`, `dev-core:implementer-fast`, `dev-core:implementer-deep`, `dev-core:tester`, `dev-core:security`, `dev-core:reviewer`, `dev-core:scout`, `dev-core:debugger`. (Lệnh `claude plugin details` hiện báo `Agents (0)` do cách đếm của nó; agent vẫn được nạp.) Cập nhật: `claude plugin update dev-core@thanh-tan-plugins`.

### Bước 2b: cài vào Antigravity CLI

**KHÔNG dùng `agy --dangerously-skip-permissions` với plugin này.** Đã thử (agy 1.4.0, 18/10/2026): ở chế độ đó lệnh vẫn chạy và `force_ask` của hook không có tác dụng, nên mọi bước duyệt (`task approve`, `task cancel`) bị bỏ qua. Dùng chế độ mặc định `request-review`.

```
agy plugin install "<repo>/families/software-dev/core"
agy plugin list
agy agents
```

`agy plugin list` phải có `dev-core` với `skills`, `agents`, `hooks`; `agy agents` liệt kê các agent của dev-core (8 role, `implementer` thành `implementer-fast` và `implementer-deep`) (thêm `db-engineer` khi cài dev-backend). `agy plugin install` chép một bản vào máy, nên sau mỗi lần `git pull` hãy chạy lại lệnh cài. Cách cài thẳng từ GitHub cho repo nhiều plugin chưa được xác nhận.

### Cài thêm dev-backend

```
claude plugin install dev-backend@thanh-tan-plugins
agy plugin install "<repo>/families/software-dev/backend"
```

Rồi trong dự án, **bạn** đăng ký extension và đặt cài đặt (xem [dev-backend](families/software-dev/backend/README.md)): `agentflow ext add`, `agentflow config set backend.*`, `agentflow config check`.

### Cài design-system (design-core và design-architecture)

```
claude plugin install design-core@thanh-tan-plugins
claude plugin install design-architecture@thanh-tan-plugins
```

Cần cả hai. Cách dùng, chạy không tương tác và bản Antigravity: [hướng dẫn sử dụng](families/design-system/core/USAGE.md).

### Thay đổi từ agentflow 0.5.0 (dev-core 0.4.0, dev-backend 0.2.0)

- Bước `test-spec` giữa `plan` và `implement`: tester viết test trước, agentflow tự chạy lại lệnh và đòi chúng đỏ; ở bước `test`, gate `tests-pass` tự chạy lệnh test của dự án (đặt bằng `agentflow config set test_command "<lệnh>"`, hoặc dòng `- test-command:` trong profile đã xác nhận) và chạy lại các lệnh của `test-spec` (đỏ trước, xanh sau). Xem mục "Test trước (test-spec)" của [USAGE](families/software-dev/USAGE.md).
- **Khóa test đã duyệt** (agentflow 0.6.0, dev-core 0.5.0, dev-backend 0.3.0): sau khi bạn duyệt `test-spec`, file test, file hạ tầng test tester khai (mục `## Hạ tầng test`) và cấu hình test của dự án (`conftest.py`, `pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`; riêng `pyproject.toml`, `setup.cfg`, `package.json` chỉ khóa phần cấu hình test) bị khóa bằng hash: hook, `agentflow commit` và cổng `locked-files-intact` chặn hoặc phát hiện mọi cách sửa. Đổi test đã duyệt chỉ qua lệnh của bạn `agentflow tests amend <file> --reason "..."`; test sửa xong mà xanh trên mã cũ bị chặn, trừ khi bạn thêm `--accept-green`. Đây là lưới an toàn, không phải sandbox: xem mục "Khóa test đã duyệt" của [USAGE](families/software-dev/USAGE.md) và [docs/architecture.md](docs/architecture.md).
- **Review chỉ phần đã đổi, bản đồ review và truy vết yêu cầu** (agentflow 0.7.0, dev-core 0.6.0): khi task quay lại sửa, `reviewer` và `security` đọc `agentflow scope` và chỉ xem phần đổi từ vòng trước; `review-map.md` cho bạn biết mỗi mục kế hoạch đã đổi file nào; `confirm` liệt kê yêu cầu `Y1..` và `plan check` đòi mỗi yêu cầu có mục `covers`; mục kế hoạch tối đa 10 file. Xem mục "Review khi task quay lại sửa" của [USAGE](families/software-dev/USAGE.md).
- **Đo chi phí, ghim tài liệu, review từng yêu cầu** (chưa phát hành, trên `develop`): `agentflow stats` cho biết mỗi task tốn bao lâu, bao nhiêu vòng, cổng nào chặn; duyệt `confirm` ghim sha256 các tài liệu ở mục `## Tài liệu`, tài liệu đổi sau đó hiện ở `agentflow status` và thành ô phải tick khi duyệt `review`; cổng mới `requirements-reviewed` đòi review ghi `Y1: đạt ...` hoặc `Y1: chưa đạt ...` cho từng yêu cầu. Cần `uv tool install --force --reinstall ./foundation` và `agentflow workflow sync`. Xem mục "Tài liệu của task" và "Tiết kiệm token" của [USAGE](families/software-dev/USAGE.md).
- **Task giữ hành vi và debug** (chưa phát hành, trên `develop`): loại task mới `refactor` và `chore` (nhánh từ `develop`): ở `test-spec` test phải **xanh trên code hiện tại** (`- green: pass`), được khóa khi bạn duyệt và phải vẫn xanh ở bước `test`. Role mới `debugger` (chỉ đọc, chạy lệnh) và skill `/dev-core:debug`: tái hiện lỗi, tìm nguyên nhân gốc, lưu chẩn đoán (`agentflow diagnosis list|show`); skill `continue` tự gọi debugger khi task quay lại `implement` từ vòng 2. Khối permissions thêm `agentflow diagnosis` và tool MCP `diagnosis_write`. Cần cài lại `agentflow`, cập nhật plugin và `agentflow workflow sync`. Xem mục "Task giữ hành vi" và "Debug" của [USAGE](families/software-dev/USAGE.md).
- **Nâng cấp lên bản này**: `git pull` ở bản clone (nhánh `develop`, nhánh mặc định của repo), rồi `uv tool install --force --reinstall ./foundation` (hook cũ không biết khóa), `claude plugin update dev-core@thanh-tan-plugins` (và `dev-backend@thanh-tan-plugins`) hoặc chạy lại `agy plugin install` cho Antigravity, rồi ở mỗi dự án đang dùng `agentflow workflow sync`. Task mở trước khi nâng cấp không có khóa.
- Hook chặn mọi tool ghi file vào `.agentflow/` (Claude Code: `Write`, `Edit`, `NotebookEdit`; Antigravity: `write_to_file`, `replace_file_content`, `multi_replace_file_content`) và các lệnh shell phổ biến ghi vào đó (mức cố gắng tốt nhất, không phải sandbox: `python -c`, script, alias vẫn qua được).
- Server MCP `agentflow mcp serve` (tool `status`, `next_step`, `plan_check`, `report_write`, `project_write`, `scan_summary`, `conventions`, `knowledge_search`, `knowledge_read`) khai báo sẵn trong dev-core; báo cáo không còn cần heredoc. `report_write` chỉ ghi báo cáo của bước hiện tại và không ghi đè báo cáo của bước đã qua.
- Skill `setup` và role `scout` hồ sơ hóa dự án có sẵn; quy ước (`PC-`, `DC-`, `KC-`), câu hỏi "Chưa có quy ước", rule Semgrep của riêng bạn, gate review theo từng quy ước, kho kiến thức cá nhân và bài học đề xuất: xem [Quy ước và kho kiến thức](#quy-ước-và-kho-kiến-thức).
- `agentflow` kéo thêm gói `mcp` (SDK chính thức). Antigravity chạy server MCP trong thư mục plugin nên tìm dự án qua `cwd`, `AGENTFLOW_PROJECT_DIR`, `PWD` rồi `~/.agentflow/active-project.txt` (xem [docs/mcp-notes.md](docs/mcp-notes.md)). Cập nhật `agentflow` khi có phiên `agy` đang mở có thể báo `Access is denied`: đóng phiên đó, hoặc `uv pip install --python <venv của tool>\Scripts\python.exe --reinstall ./foundation`.

### Bước 3: dùng trong một dự án

Dự án phải là repo git có nhánh `main` và `develop`, cây làm việc sạch.

```
cd <dự-án-của-bạn>
agentflow init --workflow "<repo>/families/software-dev/core/workflow.yaml"
```

`.agentflow/` được tạo ở local và tự thêm vào `.git/info/exclude` (không bị commit). Sau đó, trong Claude Code gõ `/dev-core:start` (Antigravity: nhờ agent dùng skill `start`) rồi làm theo hướng dẫn; hoặc tự chạy:

```
agentflow task new "Tiêu đề" --type feature --roadmap R1   # tạo nhánh feature/T-001-..., gắn task với mục R1 của roadmap
agentflow status
agentflow task advance --result pass           # xong bước; bước cần duyệt thì tiếp theo là:
agentflow task approve
agentflow commit "nội dung"                    # quét secret rồi commit với tiền tố T-001:
agentflow workflow sync                        # khi workflow gốc của nhóm thay đổi
```

Hook chỉ hoạt động trong dự án đã có `.agentflow/`; ở dự án khác chúng không làm gì. Khi hook chạy, `git push`, `git commit` trực tiếp (chỉ cho commit qua `agentflow commit`), `reset --hard`, `clean -fd`, `branch -D`, xóa tag, và merge/rebase trên `main`/`develop` bị chặn với agent. Chi tiết: [docs/architecture.md](docs/architecture.md).

### Bước 4 (BẮT BUỘC): quy tắc permissions của Claude Code

Agent chạy hàng loạt lệnh `agentflow`. Để không bị hỏi từng lệnh, thêm quy tắc **allow** cho các lệnh thường ngày. Đồng thời **bắt buộc** thêm quy tắc **ask** cho hai lệnh mang quyền duyệt của người: `agentflow task approve` và `agentflow task cancel`. Thứ tự đánh giá là deny, rồi ask, rồi allow, nên `ask` luôn hỏi bạn dù allow có khớp. Nếu bỏ `ask`, agent có thể tự duyệt bước của chính nó, và workflow mất ý nghĩa.

Dán vào `.claude/settings.json` của dự án (hoặc `~/.claude/settings.json` cho mọi dự án). Cú pháp theo [tài liệu permissions](https://code.claude.com/docs/en/permissions): `Bash(lệnh *)` khớp lệnh có hoặc không có đối số; `Bash(lệnh:*)` là cách viết tương đương; `Edit(<mẫu>)` áp cho mọi tool sửa file của Claude Code (`Write`, `Edit`, `NotebookEdit`).

```json
{
  "permissions": {
    "allow": [
      "Bash(agentflow status *)",
      "Bash(agentflow next *)",
      "Bash(agentflow doctor *)",
      "Bash(agentflow init *)",
      "Bash(agentflow task new *)",
      "Bash(agentflow task advance *)",
      "Bash(agentflow plan check *)",
      "Bash(agentflow report *)",
      "Bash(agentflow commit *)",
      "Bash(agentflow scan *)",
      "Bash(agentflow stats *)",
      "Bash(agentflow diagnosis *)",
      "Bash(agentflow config get *)",
      "Bash(agentflow config check *)",
      "Bash(agentflow ext list *)",
      "Bash(agentflow workflow sync *)",
      "mcp__plugin_dev-core_agentflow__status",
      "mcp__plugin_dev-core_agentflow__next_step",
      "mcp__plugin_dev-core_agentflow__plan_check",
      "mcp__plugin_dev-core_agentflow__report_write",
      "mcp__plugin_dev-core_agentflow__project_write",
      "mcp__plugin_dev-core_agentflow__scan_summary",
      "mcp__plugin_dev-core_agentflow__conventions",
      "mcp__plugin_dev-core_agentflow__knowledge_search",
      "mcp__plugin_dev-core_agentflow__knowledge_read",
      "mcp__plugin_dev-core_agentflow__diagnosis_write",
      "PowerShell(agentflow status *)",
      "PowerShell(agentflow next *)",
      "PowerShell(agentflow task new *)",
      "PowerShell(agentflow task advance *)",
      "PowerShell(agentflow plan check *)",
      "PowerShell(agentflow report *)",
      "PowerShell(agentflow commit *)",
      "PowerShell(agentflow scan *)",
      "PowerShell(agentflow stats *)",
      "PowerShell(agentflow diagnosis *)"
    ],
    "ask": [
      "Bash(agentflow task approve *)",
      "Bash(agentflow task cancel *)",
      "PowerShell(agentflow task approve *)",
      "PowerShell(agentflow task cancel *)"
    ],
    "deny": [
      "Edit(./.claude/settings.json)",
      "Edit(./.claude/settings.local.json)",
      "Edit(./.agentflow/state.json)",
      "Edit(./.agentflow/**/state.json)"
    ],
    "disableBypassPermissionsMode": "disable"
  }
}
```

Ghi chú:

- **Quy tắc `deny` có hiệu lực ở mọi chế độ quyền**, kể cả `bypassPermissions`; quy tắc `ask` cũng vẫn hỏi ở mọi chế độ. Quy tắc **allow** không có tác dụng trong chế độ `bypassPermissions` (mọi thứ đã được duyệt sẵn). Vì vậy khối trên đặt `permissions.disableBypassPermissionsMode: "disable"`: Claude Code từ chối chế độ bỏ qua quyền ở dự án này. Nó chặn cả chính bạn: muốn chạy `bypassPermissions` ở dự án đó thì phải tự gỡ dòng này. Chỗ chắc nhất cho thiết lập này là managed settings của máy.
- **Quy tắc `Bash` không phải ranh giới bảo mật.** Quy tắc khớp theo văn bản lệnh sau khi bỏ một số wrapper cố định (`timeout`, `time`, `nice`, `nohup`, `stdbuf`, `command`, `builtin`, `xargs`...); nó không khớp `uv run agentflow task approve`, `python -m agentflow task approve`, lệnh gọi bằng đường dẫn đầy đủ, hay `sh -c "..."`. Lớp chính là **hook `pre-tool`** của dev-core: nó đọc `agentflow` ở mọi dạng gọi đó (và `uvx`, `Start-Process`, tiền tố biến môi trường, `bash -lc`, `python -c`, cả nội dung heredoc, pipe hay here-string đưa vào bash/python/node), trả `ask` cho `task approve`/`task cancel` và từ chối các lệnh của người. Quy tắc `ask` ở trên là lớp phụ cho các dạng gọi đơn giản.
- **Allow hẹp.** Tuyệt đối không thêm `Bash(python *)`, `Bash(uv run *)`, `Bash(*)` hoặc `Bash` trần (hay `PowerShell` trần) vào `allow`: chúng cho agent chạy mã tùy ý, nên mọi lớp bảo vệ còn lại chỉ là lưới mỏng. Đã từng thử `Bash(python *)` để heredoc chạy được; đó là rủi ro, không phải khuyến nghị.
- **Sandbox của Claude Code chỉ có trên macOS, Linux và WSL2; Windows gốc không có sandbox.** Cũng không sandbox nào bao các tool file, MCP hay hook. Chặn cứng agent chạy mã tùy ý cùng quyền với bạn thì chỉ có sandbox hoặc quyền hệ điều hành; các lớp ở đây là lưới an toàn (xem [docs/architecture.md](docs/architecture.md), mục "Bảo vệ workspace").
- Claude Code tách lệnh ghép (`&&`, `;`, `|`, xuống dòng) và đòi mỗi lệnh con khớp một quy tắc; vì vậy prompt của dev-core bắt mọi lệnh `agentflow` chạy riêng.
- Báo cáo được ghi bằng tool MCP `report_write` (tên đầy đủ có tiền tố `mcp__plugin_dev-core_agentflow__`), nên không cần heredoc. Lệnh `agentflow report` (nhận nội dung qua heredoc `<<'EOF'`) chỉ còn là dự phòng khi không có tool MCP.
- Tám tool MCP trong `allow` chỉ đọc workspace hoặc ghi báo cáo/hồ sơ dự án theo luật của `agentflow` (báo cáo chỉ cho bước hiện tại và không ghi đè bước đã qua; hồ sơ dự án chỉ ghi khi không có task đang mở). Không có tool MCP cho việc của người (duyệt, hủy, seal, `decide`, extension, `config set`).
- Các lệnh `agentflow decide`, `ext add`, `ext sync`, `config set`, `task seal`, `project confirm`, `roadmap set`, `replan done|skip` là việc của **người**: hook **từ chối** khi agent tự chạy (không phải `ask`, nên không có trong khối trên). Bạn chạy trực tiếp: trong Claude Code gõ `! agentflow decide ...`, hoặc dùng terminal riêng (Antigravity).

### Giới hạn của Antigravity (không có quy tắc ask)

Antigravity CLI không có quy tắc `ask` kiểu `permissions` của Claude Code; chế độ phê duyệt lệnh của chính CLI đó là lớp duy nhất ở phía nó. Phần còn lại do hook `pre-tool` của dev-core đảm nhiệm:

- Với `agentflow task approve` và `task cancel` (mọi dạng gọi như trên Claude Code), hook trả `force_ask`: theo tài liệu của Antigravity, nó bỏ qua bộ nhớ "Always Allow", nên bạn luôn thấy câu hỏi.
- Hook từ chối ghi vào `.agentflow/` (tool file và lệnh shell) và các lệnh của người; `agentflow commit` từ chối commit khi quét ra secret hoặc khi sai nhánh.
- Đã thử thật (agy 1.4.0, 18/10/2026, kết quả ở [docs/architecture.md](docs/architecture.md), mục "Thử thật hook ask"): chế độ mặc định `request-review` hỏi đúng; với `--dangerously-skip-permissions` (tự duyệt mọi lệnh) lệnh vẫn chạy, nên khi dùng chế độ tự duyệt thì `force_ask` không giúp được và chỉ còn các hook deny cùng `agentflow commit`. **KHÔNG dùng `agy --dangerously-skip-permissions` với plugin này** (xem Bước 2b).

### Kiểm tra nhanh toàn bộ

```
uv run tools/smoke.py
```

Chạy `init → task → plan check → advance/approve → commit (Gitleaks thật) → scan (Semgrep, Trivy, Gitleaks thật) → guard → hook` trên một repo tạm, không đụng repo nào khác. Cần Docker đang chạy.

```
uv run tools/smoke_backend.py                    # dev-core + dev-backend trên dự án mẫu (PostgreSQL trong Docker)
uv run tools/smoke_backend.py --only-install-check   # cài lại hai plugin vào Claude Code và Antigravity rồi kiểm tra
uv run tools/smoke_modes.py                           # tier, layer-order, role grant (MCP giả) và task small
uv run tools/trial_cli.py --modes --only agy          # Antigravity thật: agent fast làm một mục, grant với MCP giả
```

### Quy ước và kho kiến thức

Lần đầu trên một dự án có sẵn: gọi skill `setup` (xem hướng dẫn dùng thử ở cuối). Scout đọc tài liệu bạn chỉ và code, rồi viết `.agentflow/project/{profile,architecture,sources,conventions,roadmap}.md`; mọi quy ước ban đầu là `unconfirmed`. Bạn đọc, trả lời câu hỏi mở (`S1`...) và xác nhận bằng `agentflow project confirm PC-01 PC-02` (hoặc `--all`, chỉ gồm quy ước). Scout cũng viết **mission** (mục `## Mission` của `profile.md`, lấy từ tài liệu bạn đưa) và đề xuất **roadmap** (`project/roadmap.md`, mục `R1`, `R2`...): bạn xác nhận bằng `agentflow project confirm mission` và `agentflow project confirm R1 R2`, xem tình trạng bằng `agentflow project status`, đổi trạng thái một mục bằng `agentflow roadmap set R3 dropped`. Tài liệu đã xác nhận mà agent sửa nội dung thì tự về `unconfirmed`. `agentflow task new --roadmap Rn` gắn task với một mục (chuyển sang `doing`; task xong không tự đóng mục, bạn đặt `done`) và cảnh báo khi còn quy ước, mission hoặc mục roadmap chưa xác nhận hay task không gắn mục nào.

Mỗi quy ước có `check:` là `plan` (luật `item-order`: mục `kind: interface` đứng trước mục `kind: implement` đụng cùng file; luật `layer-order`: các mục theo thứ tự lớp của dự án, xem [Tier và thứ tự lớp](#tier-và-thứ-tự-lớp)), `semgrep` (rule do **bạn** viết, để trong `.agentflow/knowledge/semgrep/`, chạy cùng scan ở bước security) hoặc `review` (reviewer ghi `PC-01: đạt` hoặc `vi phạm PC-01 ở file:dòng` cho từng mã). Ưu tiên: `decisions/` > `project/conventions.md` > `knowledge/conventions.md`. Xem bằng `agentflow conventions`.

Khi dự án chưa có quy ước cho một điều planner cần quyết, plan có mục `## Chưa có quy ước` và bị chặn tới khi bạn trả lời: `agentflow decide --answer Q1 --text "Tên bảng số ít" --check review` (thêm `--global` để ghi cả vào kho cá nhân của bạn).

Kho kiến thức cá nhân nằm ngoài mọi repo (mặc định `~/knowledge`, đường dẫn ở `~/.agentflow/user.yaml`): `agentflow knowledge init` tạo khung; `agentflow knowledge pull lessons/x.md semgrep/rule.yaml` chép file bạn chọn vào `.agentflow/knowledge/` cho agent đọc; sau task, `agentflow knowledge push .agentflow/tasks/T-001/lessons/L1.md` đưa một bài học về kho. Agent không bao giờ ghi vào kho.

### Scan bảo mật

Bước `security` chạy `agentflow scan`: Semgrep (chỉ file task đã đổi), Trivy và Gitleaks, mỗi tool trong một container với image ghim phiên bản và repo mount chỉ đọc. Bước không qua được khi Semgrep có mức ERROR, Trivy có HIGH/CRITICAL **đã có bản vá**, hoặc Gitleaks có phát hiện. Docker/Podman không chạy là lỗi cứng. Lần đầu cần mạng (kéo image, tải DB Trivy, tải rule Semgrep vào cache của bạn; rule Semgrep không nằm trong repo vì giấy phép không cho phân phối lại). Báo nhầm chỉ bỏ qua được khi **bạn** chạy `agentflow decide --suppress <id> --reason "..."` (id in trong kết quả `agentflow scan`). Chi tiết: [docs/scan-notes.md](docs/scan-notes.md).

### Kế hoạch (plan) và xác nhận cuối task

Bước `plan` bị chặn nếu kế hoạch không qua `agentflow plan check`. Mỗi mục có dạng:

```
### C1 - Tiêu đề ngắn
- role: implementer
- kind: implement      # interface | implement | other (bắt buộc khi có quy ước item-order)
- tier: fast           # fast | deep (không ghi thì coi là deep)
- layer: domain        # bắt buộc khi có quy ước layer-order
- files: src/a.py, tests/test_a.py
- done-when: `uv run pytest tests/test_a.py`
- docs: https://... (hoặc: không có — <lý do>)
```

### Chế độ nhẹ (task nhỏ)

`agentflow task new "<tiêu đề>" --size small` (mặc định `normal`) dành cho thay đổi nhỏ, rõ ràng. Task `small`:

- **bỏ duyệt ở bước plan**, nhưng `agentflow plan check` vẫn chạy và chặn như thường; kế hoạch tối đa **3 mục**;
- vẫn cần bạn duyệt ở bước `confirm` và `review`;
- bước `security` chỉ chạy **Gitleaks và Semgrep** (kể cả Semgrep với rule của chính bạn khi có quy ước `check: semgrep`); Trivy không chạy. Scan của các bước khác do plugin con thêm (Squawk, Schemathesis ở bước `test` của dev-backend) vẫn chạy.

Size được ghi vào `state.json` (trường `size`), `STATE.md`, `agentflow status` và `summary.md`. Kế hoạch dài hơn 3 mục thì chia thành task khác hoặc bắt đầu lại bằng `normal`. Nghiệp vụ nằm trong `workflow.yaml` của dev-core (mục `sizes`), không nằm trong foundation: xem [architecture.md](docs/architecture.md#foundation--nhóm-hợp-đồng-workflow).

### Cấp tool theo dự án cho role

Mặc định mỗi role chỉ có tool đã ghi trong agent của plugin. Một dự án có thể cho role dùng thêm tool MCP của riêng nó (ví dụ MCP của hệ thống ticket hay cơ sở dữ liệu) mà **không sửa plugin**. Đây là việc của người, agent không chạy được (guard chặn):

```
agentflow role grant implementer mcp__tracker__*          # cả server, hoặc một tool: mcp__tracker__create_issue
agentflow role grant reviewer mcp__tracker__get_issue     # role chỉ đọc: chỉ tool đọc, đúng tên
agentflow role revoke implementer mcp__tracker__*
agentflow role list                                       # grant, agent đang mang chúng, trạng thái current/stale/missing
agentflow role sync                                       # sinh lại sau khi cập nhật plugin
```

Tên tool là tên MCP đầy đủ như Claude Code đặt: `mcp__<server>__<tool>` (server của plugin là `mcp__plugin_<plugin>_<server>__<tool>`); `mcp__<server>` hoặc `mcp__<server>__*` là cả server.

**Role chỉ đọc** (`orchestrator`, `planner`, `security`, `reviewer`, `scout`, `debugger`, khai báo ở `read_only_roles` trong `workflow.yaml`) chỉ được cấp **tool đọc, đúng tên**: không dùng `*` hay tên server, và tên tool phải bắt đầu bằng `get`, `list`, `read`, `search`, `query`, `find`, `describe`, `view` hoặc `status`; tên khác (`write_…`, `create_…`, `update_…`, `getaway`…) bị từ chối. Đây là kiểm tra **theo tên**: agentflow không hỏi được server MCP khác xem tool làm gì, nên hãy tự xem tool đọc trước khi cấp.

**Claude Code.** Tài liệu cho thấy `tools` của agent plugin cố định, `mcpServers` bị bỏ qua với agent plugin, và agent trong `.claude/agents/` của dự án được đọc thêm. Vì vậy `role grant` ghi vào `.agentflow/config.yaml` rồi sinh, cho từng agent của role, một bản sao cấp dự án `.claude/agents/project-<agent>.md` (ví dụ `project-implementer-fast.md`): cùng prompt, cùng model, `tools` được nối thêm tool đã cấp, kèm dòng ghi sha256 của file nguồn. Các file này chỉ ở local: `.claude/agents/project-*.md` được thêm vào `.git/info/exclude` (không sửa `.gitignore`), và hook chặn agent ghi vào chúng. Skill `continue` chạy `agentflow plan assign --cli claude`, lệnh này trả tên `project-…` khi role có grant. Sau khi cập nhật plugin, `agentflow role list` báo `stale` và `agentflow role sync` sinh lại. Muốn bỏ hẳn: `role revoke` (hết grant thì các file bị xóa; chỉ file do agentflow sinh mới bị xóa).

**Antigravity.** Role vốn thấy mọi server MCP đã cài ([docs/mcp-notes.md](docs/mcp-notes.md)), nên `role grant` chỉ **ghi nhận** để cấu hình hai CLI đồng bộ; không sinh file và `plan assign --cli antigravity` luôn trả agent của plugin. Luật dành cho role chỉ đọc vẫn áp dụng khi ghi nhận.

### Tier và thứ tự lớp

**Tier.** Mỗi mục kế hoạch có thể ghi `tier: fast` hoặc `tier: deep`; thiếu thì là `deep`. Planner đề xuất, bạn sửa trực tiếp trong báo cáo plan khi duyệt (hoặc nhờ planner sửa), và `agentflow plan check` từ chối giá trị khác. Skill `continue` chạy `agentflow plan assign` (in `mã role tier agent` cho từng mục) rồi giao mục `fast` cho `implementer-fast`, mục `deep` cho `implementer-deep`; role không chia tier (như `db-engineer` của dev-backend) luôn dùng một agent duy nhất, với model và effort do plugin của role đó đặt (`db-engineer`: Sonnet, effort `high`).

| | fast | deep |
|---|---|---|
| Claude Code | `model: sonnet`, `effort: low` | `model: sonnet`, `effort: high` |
| Antigravity | `model: flash` | `model: pro` |

Giá trị nằm trong nguồn role (`families/software-dev/core/src/roles/implementer.md`, khối `variants`) và được `tools/build.py` sinh ra. **Lưu ý giới hạn sử dụng:** trên Claude Code cả `fast` và `deep` đều là Sonnet, chỉ khác effort (`low` và `high`), và `db-engineer` cũng là Sonnet `high`; Antigravity phân biệt bằng model (`flash` và `pro`) và không có trường effort. Muốn dùng Opus cho mục khó, đổi dòng `deep` của Claude Code thành `claude: {model: opus, effort: medium}` trong nguồn role (với `db-engineer`: khối `settings:` trong `families/software-dev/backend/src/roles/db-engineer.md`), chạy `uv run tools/build.py` rồi cài lại plugin; Opus tốn giới hạn sử dụng hơn Sonnet. Build kiểm giá trị theo danh sách trong tài liệu từng CLI (`sonnet|opus|haiku|fable|inherit` và `low|medium|high|xhigh|max` cho Claude Code; `inherit|flash|pro` cho Antigravity) và từ chối giá trị khác.

**Thứ tự lớp (`layer-order`).** Quy ước do **dự án** khai báo; plugin không có sẵn quy ước nào. Ví dụ trong `project/conventions.md` (hoặc trả lời câu hỏi bằng `agentflow decide`):

```
### PC-04 - Thứ tự lớp
- check: plan
- rule: layer-order
- layers: interface, api, infra, service, domain
- source: docs/architecture.md:12
- description: Làm lớp trước xong mới tới lớp sau.
```

Khi quy ước hiệu lực, mỗi mục kế hoạch phải có `layer:` thuộc danh sách, và **trên toàn bộ kế hoạch** một mục lớp sau không được đứng trước mục lớp trước (mỗi lớp có thể nằm ở thư mục riêng, nên luật không dựa vào thư mục). Muốn thu hẹp, thêm `- scope: src/**, lib/**`: khi đó luật chỉ xét các mục có file khớp một trong các glob đó (và các mục phải ghi `files`). Qua `decide`: `agentflow decide --answer Q1 --text "..." --check plan --rule layer-order --layers "interface, api, infra, service, domain" [--scope "src/**"]`.

Khi bạn duyệt bước cuối, `agentflow` ghi `.agentflow/tasks/<task>/summary.md` (mục, commit, link docs, kết quả scan) và tạo **annotated tag** `agentflow/<task>/approved` (message có mã task, tiêu đề, người duyệt) trên commit cuối của nhánh task. `agentflow task new` từ chối nếu task xong gần nhất chưa có tag này; bạn tạo bù cho task cũ bằng `agentflow task seal <id>` (thêm `--commit <sha>` nếu nhánh đã bị xóa). Agent không bao giờ push, merge hay tạo PR: bạn tự làm.

## Phát triển

```
cd foundation
uv run pytest
uv run --python 3.12 pytest
cd ..
uv run tools/build.py --check
uv run tools/docs_standard.py
uv run --with pyyaml --with pytest pytest tools
claude plugin validate --strict families/software-dev/core
agy plugin validate families/software-dev/core
```

## Dùng thử trên một dự án thật

Hướng dẫn đầy đủ (chọn plugin, khuôn yêu cầu task, checklist duyệt, lệnh của người, tiết kiệm token): [families/software-dev/USAGE.md](families/software-dev/USAGE.md). Các bước tóm tắt:

1. Cài `agentflow`: `uv tool install --force --reinstall ./foundation` (từ thư mục repo này), rồi `agentflow doctor`.
2. Cài plugin vào Claude Code (`claude plugin marketplace add "<repo>"`, `claude plugin install dev-core@thanh-tan-plugins`, `dev-backend@thanh-tan-plugins`) và/hoặc Antigravity (`agy plugin install "<repo>/families/software-dev/core"` và `.../backend`). Mở lại CLI để nạp skill, agent, hook và server MCP.
3. Dán khối `permissions` ở **Bước 4** vào `.claude/settings.json` của dự án. Quy tắc `ask` là bắt buộc.
4. Trong dự án (repo git có `main` và `develop`, cây làm việc sạch): `agentflow init --workflow "<repo>/families/software-dev/core/workflow.yaml"`. Với dev-backend, thêm bước của **bạn**: `agentflow ext add "<repo>/families/software-dev/backend/extension.yaml"`, `agentflow config set backend.*`, `agentflow config check`.
5. **Hồ sơ hóa dự án:** gõ `/dev-core:setup` (Antigravity: nhờ agent dùng skill `setup`). Bạn đưa đường dẫn tài liệu; scout đọc rồi viết `.agentflow/project/*.md`. Mở các file đó, trả lời câu hỏi mở `S1...` bằng `agentflow decide --answer S1 --text "..." --check review`, rồi xác nhận quy ước đồng ý: `agentflow project confirm PC-01 PC-02` (hoặc `--all`), cùng mission và các mục roadmap: `agentflow project confirm mission R1 R2`.
6. **Kho kiến thức (tùy chọn):** `agentflow knowledge init`; đặt rule Semgrep của bạn vào `<kho>/semgrep/` và quy ước cá nhân vào `<kho>/conventions.md`; chép vào dự án bằng `agentflow knowledge pull semgrep/<rule>.yaml conventions.md`.
7. **Làm việc:** `/dev-core:start` (chọn mục roadmap `Rn` cho task; `agentflow roadmap list` để xem), rồi `/dev-core:continue`. Agent tự chạy các bước không cần duyệt và dừng ở `confirm`, `plan`, `review` để bạn `agentflow task approve` (hoặc `/dev-core:approve`). Plan có mục `## Chưa có quy ước` thì bạn trả lời bằng `agentflow decide --answer Q1 ...` rồi để agent chạy tiếp. Phát hiện chặn của scan mà bạn xác nhận là báo nhầm: `agentflow decide --suppress <id> --reason "..."`.
8. **Sau khi xong:** xem `.agentflow/tasks/<task>/summary.md` (mục, commit, scan, "Bài học đề xuất") và `spec-delta.md` (task thật sự đổi gì); gõ `/dev-core:replan` (Antigravity: nhờ agent dùng skill `replan`) để scout đề xuất cập nhật hồ sơ, bạn đọc `replan.md`, xác nhận và chốt bằng `agentflow replan done` (hoặc `agentflow replan skip <task> --reason "..."`) và tag `git tag -l "agentflow/*"`. Bài học đáng giữ: `agentflow knowledge push .agentflow/tasks/<task>/lessons/L1.md`. Merge và push là việc của bạn.

Các lệnh của người (`decide`, `project confirm`, `roadmap set`, `replan done|skip`, `knowledge init|pull|push`, `ext add|sync`, `config set`, `task seal`): trong Claude Code gõ với tiền tố `!`; agent tự chạy sẽ bị hook từ chối.
