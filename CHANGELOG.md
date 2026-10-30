# Changelog

Mọi thay đổi đáng chú ý của repo này được ghi ở đây. Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Repo chứa nhiều thành phần có số phiên bản riêng: `thanhtan` (foundation), `dev-core`, `dev-backend`. Số phiên bản hiện tại: thanhtan 1.0.0, dev-core 1.0.0, dev-backend 1.0.0 (trước 1.0.0 động cơ tên là `agentflow`). Tag `v0.7.0` đánh dấu bản đã dùng ổn định trước 0.8.0; cách phát hành: [docs/release.md](docs/release.md).

## [Unreleased]

### Added

- Giấy phép MIT (`LICENSE`); mọi manifest plugin khai `"license": "MIT"`.
- `plugin.json` (Antigravity) của cả sáu plugin có thêm `version` (theo manifest Claude Code), `displayName`, `author`, `license`, `homepage`, `repository`, `keywords`, và `suggestedPrompts` cho dev-core và dev-backend: các trường Plugin Marketplace của Antigravity (ra mắt 29/10/2026) dùng; marketplace bỏ qua plugin không có `version`. Test `tools/test_plugin_manifests.py` giữ hai manifest khớp nhau.
- `tools/install.py --from-github`: cài plugin từ GitHub (nhánh `develop`) thay vì bản clone; Antigravity dùng `agy plugin install https://github.com/tankhangkm12/Thanh-Tan-/tree/develop/<thư mục plugin>`. README Bước 2b có cách cài từ GitHub và ghi chú về marketplace của Antigravity.

- Logo cho cả sáu plugin (`assets/logo.png`, 512×512): `logo` trong `plugin.json` (Antigravity) và `icon` trong `.claude-plugin/plugin.json`.

### Changed

- `docs/release.md`: nâng `version` ở cả `plugin.json` của Antigravity; kiểm bằng `agy plugin validate --strict`.
- File riêng của Claude Code chuyển vào `claude/` để `agy plugin validate --strict` qua (trước đó báo "never loaded" và trả lỗi): `dev-core/.mcp.json` thành `claude/mcp.json`, `hooks/hooks.json` của dev-core và design-core thành `claude/hooks.json`; `.claude-plugin/plugin.json` trỏ tới chúng qua `mcpServers` và `hooks`. Claude Code vẫn nạp đủ 3 hook và server MCP `thanhtan` (đã thử bằng `claude plugin details`). Nâng cấp: `claude plugin marketplace update thanh-tan-plugins` rồi `claude plugin update dev-core@thanh-tan-plugins` (và `design-core@thanh-tan-plugins`).

## [1.0.0] - 2026-10-29

thanhtan 1.0.0, dev-core 1.0.0, dev-backend 1.0.0.

### Changed

- **`agentflow` đổi tên thành `thanhtan`**: lệnh, package Python, server MCP (tool thành `mcp__plugin_dev-core_thanhtan__*`), biến môi trường (`THANHTAN_HOME`, `THANHTAN_PROJECT_DIR`, `THANHTAN_HOOK_LOG`, `THANHTAN_CACHE_DIR`), hook, skill, agent, workflow và tài liệu. Ví dụ: `thanhtan status`, `thanhtan doctor`, `thanhtan task approve`, `thanhtan tests check`, `thanhtan tests amend`, `thanhtan workflow sync`.
  - `agentflow` vẫn chạy như **bí danh** của cùng chương trình (in một dòng nhắc tên mới; hook, `mcp`, `guard` thì không), sẽ bỏ ở bản sau. Biến `AGENTFLOW_*` vẫn được đọc khi `THANHTAN_*` chưa đặt.
  - Guard coi `agentflow` như `thanhtan` ở mọi dạng gọi (cả trong script), nên bí danh không vượt được hook.
  - Tag duyệt mới là `thanhtan/<task>/approved`; tag `agentflow/<task>/approved` cũ vẫn tính là đã duyệt và vẫn được bảo vệ. Không ref nào trong git dự án bị viết lại.

### Added

- `thanhtan workspace remote <url>` / `save` / `load` / `status`: mang `.ThanhTan/`, nhánh task và tag duyệt sang máy khác qua repo riêng tư của bạn (clone ở `~/.ThanhTan/store/`, mỗi dự án một thư mục theo `origin`). `load` tự trỏ workflow vào dev-core cài ở máy mới. `save` từ chối khi máy khác đã lưu sau lần cuối, `load` từ chối ghi đè thay đổi chưa lưu (`--force` để bỏ qua); mã 39 `WORKSPACE_SYNC`. Không bao giờ push lên remote của dự án.
- `thanhtan task export [T-002] [--branch] [--message]`: nhánh mới gồm một commit `<loại>: <tiêu đề>` chứa cả task, đặt trên commit task tách ra; không checkout, không push; mã 40 `EXPORT_FAILED`.
- `thanhtan permissions install [--check] [--user]`: gộp quy tắc permissions của README Bước 4 (giờ ở `data/claude-permissions.json`, test giữ trùng README) vào `.claude/settings.json`; giữ quy tắc của bạn, bỏ quy tắc `agentflow` cũ và quy tắc `allow` cho `task approve|cancel`. README Bước 4 thêm `thanhtan workspace status` vào `allow`.
- `workspace remote|save|load`, `task export`, `permissions install` là lệnh của người: hook từ chối khi agent chạy.
- `tools/install.py`: in lời báo lỗi thật của uv; gỡ tool `agentflow` cũ trước khi cài `thanhtan`; trên Windows liệt kê tiến trình đang giữ file của thanhtan và chỉ dừng chúng khi bạn đồng ý.

### Nâng cấp từ 0.8.0

- Đóng mọi phiên Claude Code và Antigravity, rồi ở thư mục repo: `git pull` và `uv run --python 3.12 tools/install.py --backend` (thay cho `uv tool install --force --reinstall ./foundation`; nó gỡ tool `agentflow` cũ).
- Ở mỗi dự án, khi không có task đang dở: `thanhtan permissions install`, rồi `thanhtan workflow sync`. Mở phiên mới.
- Làm trên nhiều máy: tạo một repo GitHub riêng tư trống, rồi `thanhtan workspace remote <url>` và `thanhtan workspace save`.

## [0.8.0] - 2026-10-28

agentflow 0.8.0, dev-core 0.7.0, dev-backend 0.4.0.

### Changed

- Thư mục làm việc đổi tên (agentflow): `.agentflow/` của dự án thành `.ThanhTan/`, `~/.agentflow/` thành `~/.ThanhTan/`. Lệnh `agentflow` và biến `AGENTFLOW_*` giữ nguyên. Lệnh `agentflow` đầu tiên trong một dự án chỉ có `.agentflow/` tự đổi tên nó (giữ mọi task, báo một dòng, thêm `.ThanhTan/` vào `.git/info/exclude`); dự án có cả hai thư mục bị từ chối (mã 38 `WORKSPACE_CONFLICT`) tới khi người giữ một. Thư mục cũ vẫn được hook bảo vệ như thư mục mới cho tới khi đổi tên. Đổi tên lỗi trên Windows (phiên đang mở giữ file): agentflow báo đóng phiên Claude Code và Antigravity rồi chạy lại.
- Cỡ task theo lệnh (dev-core): `/dev-core:start` luôn cỡ `normal` (feature hoặc bugfix), không còn tự đoán cỡ. Lệnh mới `/dev-core:start-small` (cỡ `small`, feature/bugfix/refactor/chore), `/dev-core:hotfix`, `/dev-core:refactor`, `/dev-core:chore`. Lệnh không hợp với yêu cầu thì skill nói lệnh nào hợp và dừng.

### Added

- Cài một lệnh (`uv run tools/install.py`): cài hoặc cập nhật `agentflow` bằng Python 3.12 do uv quản lý (không dùng `python` trên PATH: tránh lỗi "Python was not found" của lối tắt Microsoft Store và môi trường tool trỏ tới Python đã gỡ), plugin của Claude Code (thêm hoặc cập nhật marketplace, `install` hoặc `update`) và Antigravity. `--backend`, `--design`, `--only claude|agy`, `--check` (chỉ kiểm, không đổi gì). Báo cách xử lý khi file bị phiên đang mở giữ. Không đụng tới dự án nào.
- Nhánh gốc của task do dự án chọn (agentflow, dev-core): `agentflow task new --base <nhánh>` và cài đặt `git.base.default`, `git.base.<feature|bugfix|hotfix|refactor|chore>`, `git.main_branch`, `git.develop_branch` (`agentflow config set`, việc của người). Thứ tự chọn: `--base`, loại task, mặc định chung, rồi `develop` (hotfix: `main`). Task ghi `base` vào `state.json` lúc tạo (task cũ vẫn đọc được: nhánh gốc suy từ tiền tố nhánh); `scope`, `review-map`, `scan`, `spec-delta.md`, `summary.md` (kể cả lệnh merge hotfix) so với đúng nhánh gốc; `status` và `STATE.md` hiện `base`. `task new` đòi nhánh gốc có trên máy (báo cách xử lý) và cảnh báo khi nó tụt so với `origin`. `config set` từ chối khóa `git.*` lạ và tên nhánh sai, `config check` báo giá trị sai viết tay. Hook và `agentflow guard` bảo vệ thêm các nhánh đã đặt tên và nhánh gốc của task đang mở (agent không commit, merge, rebase trên đó). Skill `start` truyền `--base` khi người nói rõ nhánh.

### Nâng cấp từ 0.7.0

- Chạy `uv run --python 3.12 tools/install.py` (thêm `--backend` nếu dùng dev-backend) từ thư mục repo sau `git pull`; nó thay cho `uv tool install --force --reinstall ./foundation`, `claude plugin update dev-core@thanh-tan-plugins` và `agy plugin install` lại. Mở phiên mới để nạp các lệnh `/dev-core:start-small`, `hotfix`, `refactor`, `chore`.
- Ở mỗi dự án: lệnh `agentflow` đầu tiên đổi `.agentflow/` thành `.ThanhTan/` (đóng phiên Antigravity đang mở trước); rồi `agentflow workflow sync` để chép workflow mới (checklist nhắc `.ThanhTan/`). Quy tắc permissions của Claude Code viết theo `.agentflow/` thì đổi thành `.ThanhTan/` (README Bước 4).

## [0.7.0] - 2026-10-28

agentflow 0.7.0, dev-core 0.6.0, dev-backend 0.3.0 (tag `v0.7.0`).

### Added

- Hotfix nhanh (dev-core, agentflow): mục `types` của workflow nhận `size: <profile>`, cỡ mặc định của loại task khi không có `--size` (profile phải có trong `sizes`). dev-core khai `hotfix: {size: hotfix}` và profile `hotfix`: bỏ duyệt `plan`, tối đa 3 mục kế hoạch, chạy đủ các bản quét; vẫn duyệt ở `confirm`, `test-spec`, `review`. `task new --type hotfix` không cảnh báo thiếu `--roadmap`. Hotfix xong thì `summary.md` có mục `## Merge the hotfix` và `task approve` in các lệnh để người merge vào `main` (kèm tag) và merge ngược về `develop`. Cần `agentflow workflow sync`.
- Yêu cầu lấy từ tài liệu (dev-core, agentflow): `/dev-core:start làm R2` (hay `làm tiếp`) là đủ; skill `start` lấy tiêu đề từ mục roadmap và orchestrator đọc `goal` cùng mọi tài liệu ở dòng `docs` của mục (lệnh chỉ đọc mới `agentflow roadmap show Rn`) để tự viết mục tiêu, phạm vi và yêu cầu, chỉ hỏi khi tài liệu mâu thuẫn. Cổng mới `requirements-sourced` (bước `confirm` của dev-core): mỗi `- Y1: ...` phải kết thúc bằng `(nguồn: <tài liệu>[:dòng|:dòng-dòng|#mục])` trỏ vào tài liệu của mục `## Tài liệu` (hay file trong thư mục được liệt kê, link được liệt kê; file phải có thật, dòng phải nằm trong file), hoặc `(nguồn: người dùng)`. Checklist `confirm` thêm câu đối chiếu nguồn. README Bước 4 thêm `agentflow roadmap list` và `roadmap show` vào `allow`.

- Task giữ hành vi (dev-core, agentflow): loại task mới `refactor` và `chore` (nhánh từ `develop`); loại task được ghi vào trường `type` của task trong `state.json` (task cũ không có trường này vẫn đọc được) và hiện ở `status`, `STATE.md`, `summary.md`, `stats`. Mục mới `types` của `workflow.yaml` (`refactor: {test_spec: green}`): bước `test-spec` đòi mỗi khối `- green: pass` và agentflow tự chạy lệnh, đòi mã 0 trên code hiện tại (`verify-red.json` ghi `mode`); test được khóa khi duyệt và `tests-pass` đòi vẫn xanh; `tests amend` từ chối test sửa mà đỏ trên code cũ. Prompt `tester`, `planner`, `reviewer`, skill `start` và câu hỏi checklist `test-spec` viết cho cả hai chế độ.
- Debug (dev-core, agentflow): role mới `debugger` (chỉ đọc và chạy lệnh, `read_only_roles`; Claude Code dùng model của phiên, Antigravity `pro`) và skill `/dev-core:debug`: tái hiện lỗi, tìm nguyên nhân gốc, lưu chẩn đoán (`## Tái hiện`, `## Nguyên nhân` bắt buộc). Tool MCP mới `diagnosis_write` và lệnh `agentflow diagnosis write|list|show`: có task đang mở thì lưu `tasks/<task>/diagnoses/round-<n>.md`, không có thì `diagnoses/D-001.md`. Skill `continue` gọi debugger khi task quay lại `implement` từ vòng 2. README Bước 4 thêm `agentflow diagnosis` và `diagnosis_write` vào `allow`.

- `agentflow stats [--task T-001] [--json]` (agentflow, chỉ đọc): mỗi task tốn bao lâu (và bao nhiêu là chờ người duyệt), số lần duyệt, số vòng làm lại theo bước, số lần `blocked`, và cổng nào đã từ chối `pass` bao nhiêu lần; dòng tổng khi có nhiều task. Mỗi lần cổng từ chối, agentflow ghi một dòng vào `tasks/<task>/gate-log.jsonl`. README Bước 4 thêm `agentflow stats` vào `allow`.
- Ghim tài liệu (dev-core, agentflow): bước khai `pin_docs_on_approval: true` (`confirm`) ghi sha256 của các đường dẫn ở mục `## Tài liệu` của báo cáo (file hoặc thư mục; link chỉ ghi lại) vào `tasks/<task>/docs-pinned.json` khi người duyệt. Tài liệu đổi, mất hoặc mới xuất hiện sau đó: `agentflow status` cảnh báo, và nguồn checklist mới `changed-docs` (bước `review`) thêm một ô `TL<n>` phải tick. Prompt `orchestrator` viết mục `## Tài liệu`.
- Review kết luận từng yêu cầu (dev-core, agentflow): cổng mới `requirements-reviewed` (bước `review`) đòi `Y1: đạt ...` hoặc `Y1: chưa đạt ...` cho mỗi yêu cầu của `confirm`; `chưa đạt` thì không cho `pass`. Nguồn checklist mới `review-requirements` thêm một ô `Y<n>` kèm văn bản yêu cầu. Prompt `reviewer` ghi các dòng này. Cần `agentflow workflow sync` cho workspace có sẵn.

- Review chỉ phần đã đổi (dev-core, agentflow): vòng `security` hoặc `review` kết thúc thì agentflow ghi commit đã xem vào `tasks/<task>/review-marks.json`; lệnh chỉ đọc mới `agentflow scope [--step]` cho biết vòng này đọc gì (cả task ở vòng đầu, từ mốc ở các vòng sau, kèm `git diff`, commit, số dòng). Prompt `reviewer` và `security` dùng lệnh này; vòng sau reviewer mở bằng `## Phạm vi` và đóng từng must-fix cũ. `agentflow scan` vẫn quét cả task. Bản đồ review cho người: `agentflow review-map` và tự ghi khi `review` chờ duyệt (`review-map.md`: mục kế hoạch → commit, file, số dòng, kết quả lệnh agentflow chạy, file ngoài `files` của mục).
- Truy vết yêu cầu: báo cáo `confirm` liệt kê `- Y1: ...` ở mục `## Yêu cầu`; mục kế hoạch khai `covers: Y1, ...`; `plan check` từ chối yêu cầu không được phủ và `covers` trỏ mã không có (không kiểm khi `confirm` không liệt kê `Y`). Mục kế hoạch tối đa 10 mục trong `files`.
- `agentflow commit --item` cảnh báo (không từ chối) file đã stage nằm ngoài `files` của mục.

- Khóa test đã duyệt (dev-core, agentflow): bước khai `lock_on_approval: true` (`test-spec`) khóa file khi người `task approve`: ghi `tasks/<task>/locked-files.json` (sha256, `kind`, `scope`) và hash của nó vào `integrity.json` (`locked_files_sha256`; sửa tay hay xóa: mã 37). Khóa gồm file test của báo cáo, file hạ tầng tester khai ở mục `## Hạ tầng test`, và file cấu hình test có sẵn theo tên (`conftest.py`, `pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`... khóa nguyên file); `pyproject.toml`, `setup.cfg`, `package.json` chỉ khóa phần cấu hình test (`[tool.pytest...]`, `[tool:pytest]`, `jest`/`vitest`, `scripts.test`), sửa dependency hay phần khác không cần amend. Checklist `test-spec` có thêm các dòng `L<n>` (nguồn `locked-files`). Hook `pre-tool` từ chối (mọi role, cả hai CLI) tool file và lệnh shell ghi, xóa, đổi tên, copy đè file khóa, `git rm|mv`, `git checkout|restore` từ commit khác, và tạo mới file cấu hình test; `agentflow commit` từ chối commit đụng file khóa. Cổng mới `locked-files-intact` (ở `implement`, `test`, `security`, `review`) và cổng `tests-pass` (trước mọi lệnh) so hash ở cây làm việc và HEAD; lệnh chỉ đọc mới `agentflow tests check`. `verify-red.json` ghi thêm hash từng file; duyệt `test-spec` từ chối nếu file đổi sau lúc chạy đỏ. Cảnh báo khi test viết bằng ngôn ngữ agentflow chưa nhận ra.
- `agentflow tests amend <file>... --reason "..." [--accept-green]` (lệnh của người; guard từ chối agent mọi dạng gọi): mở cửa sổ đổi một test đã duyệt, ghi `decisions/*-tests-amend.md`. Cửa sổ đóng khi `agentflow commit` file đó; khóa nhận hash mới. Trước khi commit, agentflow chạy lại lệnh của các mục dùng file trong checkout tạm của commit lúc chạy đỏ (mã cũ) và ghi `verify-red.json["reverified"]`; test sửa xong **xanh trên mã cũ** thì commit bị chặn, trừ khi người mở cửa sổ với `--accept-green` (cần lý do, ghi vào `decisions/`).
- Đổi lệnh test bị phát hiện: `test_command` và `test_timeout_minutes` sửa ngoài `agentflow config set` làm `task new|advance|approve` báo mã 37 (hash trong `integrity.json`); `agentflow state accept` chấp nhận lại. Bộ chạy `agentflow.testrun` bỏ `PYTEST_ADDOPTS` và `PYTEST_PLUGINS` khỏi môi trường.
- Nâng cấp lên agentflow 0.7.0, dev-core 0.6.0, dev-backend 0.3.0: chạy `uv tool install --force --reinstall ./foundation` (hook cũ không biết khóa), cập nhật plugin (`claude plugin update dev-core@thanh-tan-plugins`, `agy plugin install` lại) và ở dự án đang dùng `agentflow workflow sync` để workflow có `lock_on_approval` và gate mới. Task đang chạy dở trước khi nâng cấp không có khóa.
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

### Fixed

- Khóa test trên Linux và macOS (agentflow): đường dẫn kiểu Windows trong lệnh (`Remove-Item .\tests\x.py`) giờ được đọc với `\` là dấu phân cách, nên không lọt qua khóa.

### Changed

- Claude Code: tier `deep` của `implementer` đổi từ `opus`/`medium` sang `sonnet`/`high`, và `db-engineer` (dev-backend) từ `opus`/`medium` sang `sonnet`/`high`, để bớt tốn giới hạn sử dụng; Antigravity giữ `flash`/`pro`. Bảng tier ở README và USAGE, ví dụ `variants` ở core README, mô tả agent ở skill `continue` và README dev-backend khớp theo; `tools/test_tier_defaults.py` giữ các tài liệu khớp nguồn role.
- Agent `dev-core:implementer` được thay bằng `dev-core:implementer-fast` và `dev-core:implementer-deep` (role trong kế hoạch vẫn là `implementer`).
- README liệt kê đủ 7 role của `dev-core` (thêm `scout`).
- `families/software-dev/README.md`: mục gate bằng tool mô tả Semgrep, Trivy, Gitleaks, Squawk, Schemathesis và các gate của plan/review.
- `docs/architecture.md`: thêm lệnh `agentflow hook`, danh sách lệnh chỉ người được chạy trong guard đầy đủ.

### Removed

- Plugin `dev-design` (khung rỗng của nhóm software-dev): thiết kế giao diện và hệ thống đã thành nhóm riêng design-system (`design-core`, `design-architecture`). Máy đã cài thì gỡ bằng `claude plugin uninstall dev-design@thanh-tan-plugins`.

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
