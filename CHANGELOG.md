# Changelog

Mọi thay đổi đáng chú ý của repo này được ghi ở đây. Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Repo chứa nhiều thành phần có số phiên bản riêng: `agentflow` (foundation), `dev-core`, `dev-backend`. Số phiên bản hiện tại: agentflow 0.6.0, dev-core 0.5.0, dev-backend 0.3.0. Chưa có bản phát hành (tag) nào; bản đầu tiên dự kiến là `v1.0.0` (xem [docs/release.md](docs/release.md)).

## [Unreleased]

### Added

- Khóa test đã duyệt (dev-core, agentflow): bước khai `lock_on_approval: true` (`test-spec`) khóa file khi người `task approve`: ghi `tasks/<task>/locked-files.json` (sha256, `kind`, `scope`) và hash của nó vào `integrity.json` (`locked_files_sha256`; sửa tay hay xóa: mã 37). Khóa gồm file test của báo cáo, file hạ tầng tester khai ở mục `## Hạ tầng test`, và file cấu hình test có sẵn theo tên (`conftest.py`, `pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`... khóa nguyên file); `pyproject.toml`, `setup.cfg`, `package.json` chỉ khóa phần cấu hình test (`[tool.pytest...]`, `[tool:pytest]`, `jest`/`vitest`, `scripts.test`), sửa dependency hay phần khác không cần amend. Checklist `test-spec` có thêm các dòng `L<n>` (nguồn `locked-files`). Hook `pre-tool` từ chối (mọi role, cả hai CLI) tool file và lệnh shell ghi, xóa, đổi tên, copy đè file khóa, `git rm|mv`, `git checkout|restore` từ commit khác, và tạo mới file cấu hình test; `agentflow commit` từ chối commit đụng file khóa. Cổng mới `locked-files-intact` (ở `implement`, `test`, `security`, `review`) và cổng `tests-pass` (trước mọi lệnh) so hash ở cây làm việc và HEAD; lệnh chỉ đọc mới `agentflow tests check`. `verify-red.json` ghi thêm hash từng file; duyệt `test-spec` từ chối nếu file đổi sau lúc chạy đỏ. Cảnh báo khi test viết bằng ngôn ngữ agentflow chưa nhận ra.
- `agentflow tests amend <file>... --reason "..." [--accept-green]` (lệnh của người; guard từ chối agent mọi dạng gọi): mở cửa sổ đổi một test đã duyệt, ghi `decisions/*-tests-amend.md`. Cửa sổ đóng khi `agentflow commit` file đó; khóa nhận hash mới. Trước khi commit, agentflow chạy lại lệnh của các mục dùng file trong checkout tạm của commit lúc chạy đỏ (mã cũ) và ghi `verify-red.json["reverified"]`; test sửa xong **xanh trên mã cũ** thì commit bị chặn, trừ khi người mở cửa sổ với `--accept-green` (cần lý do, ghi vào `decisions/`).
- Đổi lệnh test bị phát hiện: `test_command` và `test_timeout_minutes` sửa ngoài `agentflow config set` làm `task new|advance|approve` báo mã 37 (hash trong `integrity.json`); `agentflow state accept` chấp nhận lại. Bộ chạy `agentflow.testrun` bỏ `PYTEST_ADDOPTS` và `PYTEST_PLUGINS` khỏi môi trường.
- Nâng cấp lên agentflow 0.6.0, dev-core 0.5.0, dev-backend 0.3.0: chạy `uv tool install --force --reinstall ./foundation` (hook cũ không biết khóa), cập nhật plugin (`claude plugin update dev-core@thanh-tan-plugins`, `agy plugin install` lại) và ở dự án đang dùng `agentflow workflow sync` để workflow có `lock_on_approval` và gate mới. Task đang chạy dở trước khi nâng cấp không có khóa.
- Bước `test-spec` giữa `plan` và `implement` (dev-core, agentflow): tester viết test trước cho `done-when` từng mục, báo cáo mỗi mục một khối (`tests`, `command`, `red: fail`, `reason`, `output`, hoặc `không có — <cách kiểm>`); gate `test-spec-valid` kiểm khối, file test (có thật, đã commit, lệnh nhắc tới file test của mục) và **tự chạy lại** lệnh, đòi đỏ; kết quả ở `verify-red.json`; `agentflow tests verify-red` làm tương tự theo yêu cầu. Bước cần người duyệt kể cả task small; checklist có một ô mỗi mục (nguồn `spec-items`).
- Gate `tests-pass` ở bước `test`: agentflow tự chạy lệnh test của dự án (setting `test_command`, hoặc dòng `- test-command:` của profile đã xác nhận; `test_timeout_minutes`, mặc định 15 phút) và chạy lại các lệnh của `test-spec` (đỏ trước, xanh sau); kết quả ở `tests-pass.json` (kèm `spec_results`). Thiếu lệnh thì chặn, trừ task chỉ có mục `kind: other`. Dùng chung bộ chạy `agentflow.testrun` với `verify-red`.
- Checklist duyệt cho mỗi bước cần người (dev-core, agentflow): bước khai `approval_checklist` (câu cố định, mã `K1..`) và `approval_items` (`plan-items`, `review-conventions`, `drift-proposals`) trong `workflow.yaml`; khi bước chuyển sang `awaiting_approval`, agentflow ghi `.agentflow/tasks/<task>/approve-<bước>.md` (vòng làm lại giữ file cũ thành `approve-<bước>.<n>.md`). `agentflow task approve` từ chối (mã 36) khi còn ô chưa tick hoặc khung/đầu file bị đổi, và ghi ghi chú của người vào `decisions/<task>-<bước>-approval.md`. Bước cuối của task có `--roadmap Rn` có ô `(tùy chọn) roadmap: Mục Rn đã hoàn thành?`: tick thì mục chuyển `done`. Các câu cố định chỉ nằm trong `core/workflow.yaml`; `tools/build.py` sinh khối trong `USAGE.md` (giữa `<!-- BEGIN:checklists -->` và `<!-- END:checklists -->`) và `--check` báo lệch.
- Toàn vẹn và nhật ký (agentflow): `.agentflow/integrity.json` giữ hash `state.json` và hash khung từng checklist; `task new`/`advance`/`approve` từ chối (mã 37) khi `state.json` bị đổi ngoài agentflow. Hook `pre-tool` ghi `.agentflow/audit.jsonl` các lệnh/tool chạm `state.json`, `STATE.md`, `integrity.json`, `approve-*.md`, `locked-files.json`, `confirmations.json`; `task approve` từ chối khi có lệnh được cho qua mà có khả năng ghi vào checklist của bước hoặc `state.json`. Lệnh của người mới `agentflow state accept --reason "..."` (ghi `decisions/`). Giới hạn ghi ở `docs/architecture.md`, mục "Mô hình bảo vệ duyệt".
- `agentflow doctor` cảnh báo khi `agentflow` trên PATH lệch phiên bản với bản đang chạy và in lệnh `uv tool install --force --reinstall ./foundation`.
- README: KHÔNG dùng `agy --dangerously-skip-permissions` với plugin (đã thử: `force_ask` không có tác dụng).
- Tài liệu release gitflow cho người làm tay: [docs/release.md](docs/release.md).
- `CHANGELOG.md`.
- Guard hỏi người trước `agentflow task approve` và `agentflow task cancel` (agentflow): quyết định mới `ask` (Claude Code `permissionDecision: "ask"`, Antigravity `force_ask`, bỏ qua "Always Allow"), thắng `allow`, thua `deny`. Đã thử thật ngày 18/10/2026 (claude 2.1.302, agy 1.4.0, bảng trong [docs/architecture.md](docs/architecture.md)): hook `ask` vẫn hỏi ở `default`, `acceptEdits` và `bypassPermissions`; `dontAsk` chặn; agy ở `--dangerously-skip-permissions` vẫn chạy lệnh.
- Guard nhận `agentflow` ở mọi dạng gọi, cho cả lệnh `ask` lẫn lệnh `deny` của người (trước đây chỉ khi nó đứng đầu dòng): `uv run [--project|--with|--]`, `uvx`, `uv tool run`, `python -m agentflow`, wrapper (`timeout`, `nohup`, `env`, `xargs`...), tiền tố biến môi trường, `bash -lc`, `Start-Process -ArgumentList`, `python -c`/`node -e`. Nội dung đưa vào trình thông dịch (heredoc, pipe, here-string) được quét như lệnh; không đọc được trước thì hỏi. Thân heredoc đưa cho lệnh không chạy nó (`agentflow report`, `cat`, `tee`) vẫn là dữ liệu.
- README Bước 4: khối `deny` cho `.claude/settings*.json` và `state.json`, `permissions.disableBypassPermissionsMode: "disable"` (chặn cả chính bạn bật bypass ở dự án đó), `ask` chỉ còn `task approve`/`task cancel` (`decide` do hook từ chối). Giới hạn của Antigravity ghi ở README, USAGE và architecture.
- Gate `drift-reviewed` ở bước `review` của `dev-core`: báo cáo review phải có mục `## Đề xuất cập nhật hồ sơ` (`không có`, hoặc `- <tài liệu>: <đề xuất>` với `profile`, `mission`, `architecture`, `conventions`, `roadmap`). Chỉ kiểm hình thức; người kiểm tính đúng ở checklist Review. Role `reviewer` ghi mục này (chỉ đề xuất, không sửa hồ sơ). Cần `agentflow workflow sync` cho workspace có sẵn.
- Mission và roadmap cấp dự án (dev-core, agentflow): mục `## Mission` trong `profile.md` (scout lấy từ tài liệu người đưa) và `.agentflow/project/roadmap.md` (mục `R1`, `R2`..., trạng thái `todo|doing|done|dropped`, `goal`, `docs`). Xác nhận bằng hash trong `project/confirmations.json`: `agentflow project confirm mission|profile|architecture|R1` (agent sửa nội dung thì tự `unconfirmed`; `--all` vẫn chỉ gồm quy ước). Lệnh mới `agentflow project status`, `agentflow roadmap list`, `agentflow roadmap set Rn <trạng thái>` (lệnh của người). `agentflow task new --roadmap Rn` gắn task với mục (chuyển sang `doing`, ghi vào `state.json`, `STATE.md`, `status`, `summary.md`); task xong không tự đóng mục. `agentflow status` gợi ý mục tiếp theo; `task new` cảnh báo (không chặn) khi thiếu mission/roadmap, chưa xác nhận, hay không gắn mục. Ghi đè tài liệu dự án lưu bản cũ ở `project/history/`; mục roadmap đã xác nhận mà agent bỏ đi hiện ở `project status` (`removed:`). Mã lỗi mới 35 `ROADMAP_INVALID`.
- `spec-delta.md` và replan (dev-core, agentflow): khi seal, agentflow ghi `tasks/<task>/spec-delta.md` (đề xuất của reviewer, thay đổi thật của task từ git, liên kết mission/roadmap). Skill mới `replan` cho scout cập nhật hồ sơ rồi ghi `replan.md` bằng tool MCP `replan_write` hoặc `agentflow replan write`; replan chỉ ở trạng thái `proposed` cho tới khi người đọc và chạy `agentflow replan done` (đặt `replanned_at`, cập nhật `summary.md`, xóa dòng `removed:`) hoặc `agentflow replan skip <task> --reason "..."`. `agentflow replan status` (chỉ đọc) và cảnh báo của `task new` khi chưa replan. Hai lệnh `replan done` và `replan skip` là lệnh của người (guard từ chối khi agent chạy); replan không bao giờ tự đóng mục roadmap. Ghi lại `replan.md` lưu bản cũ ở `project/history/`. Trường tùy chọn mới `replanned_at` trong `state.json`.
- Trạng thái thật của nhóm design-system trong README và PLAN.md (dòng `**Trạng thái:**`), khóa bằng `tools/test_family_status.py`.

- Hướng dẫn sử dụng nhóm software-dev: [families/software-dev/USAGE.md](families/software-dev/USAGE.md) (chọn plugin theo loại dự án, chuẩn bị một lần, khuôn yêu cầu task, chọn chế độ, checklist duyệt, lệnh của người, tiết kiệm token, xử lý tình huống). Mục "Dùng cùng dev-core" trong README của `dev-backend` (dữ liệu cần thêm, ví dụ done-when cho Squawk và Schemathesis) và của `dev-design`, `dev-frontend`, `dev-infra` (còn là khung). README gốc và `families/software-dev/README.md` link tới USAGE.md.
- Chuẩn tài liệu của plugin trong [docs/architecture.md](docs/architecture.md): core của nhóm có `USAGE.md` với mục `## Khuôn yêu cầu task`, plugin con có mục `## Dùng cùng <tên core>`, README gốc link tới USAGE.md của mọi nhóm có core. `tools/docs_standard.py` và `tools/test_docs_standard.py` cưỡng chế chuẩn này (thiếu USAGE.md, thiếu mục khuôn hoặc khối code, thiếu mục "Dùng cùng ...", README gốc thiếu link, link tương đối hỏng; lỗi nêu tên file).

- Tier theo mục kế hoạch: `tier: fast|deep` (thiếu là deep), `plan check` kiểm giá trị, `agentflow plan assign` cho biết agent nào nhận mục nào, `tiered_roles` trong `workflow.yaml`.
- `dev-core`: hai agent `implementer-fast` (Claude Code `sonnet`/`low`, Antigravity `flash`) và `implementer-deep` (`sonnet`/`high`, `pro`) sinh từ `variants` trong nguồn role; `db-engineer` là một agent duy nhất (`sonnet`/`high`, `pro`). `tools/build.py` kiểm model/effort theo tài liệu từng CLI. Skill `continue` giao từng mục cho đúng agent.
- Luật plan `layer-order`: quy ước `layers:` (thứ tự các lớp) và `scope:` (tùy chọn) do dự án khai báo; mặc định kiểm trên toàn bộ kế hoạch. `agentflow decide --layers --scope`.
- `summary.md` ghi tier và layer của từng mục.
- `tools/smoke_modes.py` và `tools/fake_mcp_server.py`: smoke tier, layer-order, role grant và task small; `tools/trial_cli.py --modes`: thử thật bằng `agy -p`.
- Chế độ nhẹ: `agentflow task new --size small|normal` (mặc định `normal`). Mục `sizes` trong `workflow.yaml` mô tả cỡ (bước bỏ duyệt, số mục kế hoạch tối đa, tool scan theo bước); `small` của dev-core bỏ duyệt `plan` (vẫn kiểm `plan check`), tối đa 3 mục, bước `security` chỉ chạy Gitleaks và Semgrep. Size nằm trong `state.json`, `STATE.md`, `status` và `summary.md`. Skill `start` và prompt planner biết cỡ nhỏ.

- Cấp tool theo dự án cho role: `agentflow role grant|revoke|list|sync` (việc của người). Claude Code: sinh `.claude/agents/project-<agent>.md` cục bộ (loại khỏi git qua `.git/info/exclude`) mang thêm tool MCP đã cấp, không sửa plugin; Antigravity chỉ ghi nhận. Role chỉ đọc (`read_only_roles` trong `workflow.yaml`) chỉ nhận tool đọc, đúng tên. `plan assign --cli` trả tên agent cấp dự án khi có. Hook chặn agent ghi vào `project-*.md`.

### Changed

- Claude Code: tier `deep` của `implementer` đổi từ `opus`/`medium` sang `sonnet`/`high`, và `db-engineer` (dev-backend) từ `opus`/`medium` sang `sonnet`/`high`, để bớt tốn giới hạn sử dụng; Antigravity giữ `flash`/`pro`. Bảng tier ở README và USAGE, ví dụ `variants` ở core README, mô tả agent ở skill `continue` và README dev-backend khớp theo; `tools/test_tier_defaults.py` giữ các tài liệu khớp nguồn role.
- Agent `dev-core:implementer` được thay bằng `dev-core:implementer-fast` và `dev-core:implementer-deep` (role trong kế hoạch vẫn là `implementer`).
- README liệt kê đủ 7 role của `dev-core` (thêm `scout`).
- `families/software-dev/README.md`: mục gate bằng tool mô tả Semgrep, Trivy, Gitleaks, Squawk, Schemathesis và các gate của plan/review.
- `docs/architecture.md`: thêm lệnh `agentflow hook`, danh sách lệnh chỉ người được chạy trong guard đầy đủ.

## Các mốc trước khi có bản phát hành

Các mục dưới đây tóm tắt lịch sử `git log`, theo thứ tự mốc.

### M13 - smoke và chuẩn bị phát hành (agentflow 0.5.0, dev-core 0.4.0, dev-backend 0.2.0)

- Smoke test của dev-core và dev-backend bao quát setup, thứ tự kế hoạch, câu hỏi, quy ước, gate review.
- Kiểm tra cài đặt xác nhận scout, skill setup và server MCP trong cả hai CLI.
- File khóa phụ thuộc `uv.lock` cho agentflow 0.5.0.

### M12 - quy ước và kho kiến thức

- Quy ước từ ba nguồn (`decisions/` > `project/conventions.md` > kho cá nhân), lệnh `agentflow conventions` và tool MCP `conventions`.
- Ba cách kiểm quy ước: `plan` (luật `item-order`, trường `kind`), `semgrep` (rule do người viết, chạy trong container chỉ đọc) và `review` (gate `conventions-reviewed`).
- Câu hỏi "Chưa có quy ước" trong kế hoạch chặn cho tới khi người trả lời bằng `agentflow decide --answer`.
- Kho kiến thức cá nhân ngoài mọi repo (`knowledge init|pull|push`), tool MCP `knowledge_search`/`knowledge_read` chỉ đọc.
- Bài học đề xuất ở cuối báo cáo review được tách thành file khi seal.

### M11 - scout và hồ sơ dự án

- Role `scout` và skill `setup` hồ sơ hóa dự án vào `.agentflow/project/`.
- Tool MCP `project_write`; quy ước agent ghi luôn là `unconfirmed`, chỉ người `agentflow project confirm`.
- `agentflow task new` cảnh báo khi còn quy ước chưa xác nhận.

### M10 - server MCP

- `agentflow mcp serve` (SDK `mcp`, stdio) với các tool `status`, `next_step`, `plan_check`, `report_write`, `scan_summary`; `WorkspaceService` dùng chung cho CLI và MCP.
- Báo cáo chỉ ghi được cho bước hiện tại đang chạy; báo cáo của bước đã qua là cuối cùng.
- Server tìm dự án qua `cwd`, `AGENTFLOW_PROJECT_DIR`, `PWD` rồi con trỏ `~/.agentflow/active-project.txt` (cho Antigravity).
- Agent của Claude Code nhận tên tool MCP đầy đủ theo role; ghi chú thử thật trong [docs/mcp-notes.md](docs/mcp-notes.md).

### M9 - bảo vệ workspace

- Hook chặn tool ghi file của cả hai CLI và lệnh shell ghi vào `.agentflow/` (mức cố gắng tốt nhất).
- `AGENTFLOW_HOOK_LOG` để chẩn đoán hook.

### M8 - smoke dev-backend

- Smoke end-to-end trên dự án mẫu (PostgreSQL trong Docker, migration lên/xuống, OpenAPI) và kiểm tra cài đặt trong cả hai CLI.

### M7 - extension và dev-backend 0.1.0

- Hợp đồng extension: role, luật đường dẫn, luật plan, tool scan, gate; lệnh `ext` và `config`.
- `dev-backend`: role `db-engineer`, 6 skill, Squawk và Schemathesis.

### M6 - scan (agentflow 0.3.0)

- `agentflow scan` chạy Semgrep, Trivy, Gitleaks trong container (image ghim phiên bản, repo mount chỉ đọc); gate `scans-clean`; `agentflow decide --suppress` cho báo nhầm.

### M5 - dev-core 0.3.0 (agentflow 0.2.0)

- Skill và role chạy từng bước theo vòng lặp, không nối lệnh agentflow, không push/merge/PR.
- Planner kiểm kế hoạch bằng `plan check`; gate `plan-valid`.
- Task xong được seal: `summary.md` và tag duyệt `agentflow/<task>/approved`; commit gắn với mục kế hoạch (`Plan-Item`).
- Guard chặn `git commit` trực tiếp, tag duyệt giả và các lệnh chỉ người được chạy.

### M4 - cài đặt và smoke

- Hướng dẫn cài từng bước cho Claude Code và Antigravity; smoke test end-to-end trên repo tạm.

### M3 - nội dung dev-core (dev-core 0.2.0)

- Skill `start`, `continue`, `status`, `approve`; sáu role sinh từ một nguồn bằng `tools/build.py` cho cả hai CLI.

### M2 - hook

- `agentflow hook` với adapter cho Claude Code và Antigravity; hook của `dev-core`.

### M1 - vòng đời task

- Chuyển trạng thái task thuần (không I/O), vòng làm lại `max_rounds`, `task new|advance|approve|cancel`, `report`, `commit` có quét secret Gitleaks, `guard` chặn lệnh git nguy hiểm.

### M0 - bộ khung và workspace

- Bộ khung repo: marketplace, các plugin `dev-*`, README.
- `agentflow`: `doctor`, `init`, `status`, `next`, `workflow sync`; `.agentflow/` (state, `STATE.md`, bản chép workflow) loại khỏi git qua `.git/info/exclude`.
