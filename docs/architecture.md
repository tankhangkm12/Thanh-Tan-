# Kiến trúc

## Các tầng

```
foundation/ (thanhtan)      động cơ dùng chung, không mang nghiệp vụ
      │
      ▼
families/<nhóm>/core/        core của nhóm: quy trình, chuẩn, gate của nhóm đó
      │
      ▼
families/<nhóm>/<plugin>/    plugin con: chỉ thêm nghiệp vụ riêng
```

- **foundation**: package Python `thanhtan`, quản lý bằng uv, cài global bằng `uv tool install` để có lệnh `thanhtan`. Không chứa khái niệm của bất kỳ nhóm nào.
- **core của nhóm**: ví dụ `dev-core`. Định nghĩa chuẩn chung của nhóm và dựa trên `foundation`.
- **plugin con**: ví dụ `dev-backend`. Khai báo phụ thuộc vào core của nhóm mình trong `.claude-plugin/plugin.json` (`"dependencies": ["dev-core"]`).

## Quy tắc phụ thuộc

- Chiều phụ thuộc chỉ đi xuống theo sơ đồ trên: plugin con → core nhóm → foundation.
- **Không dùng code chéo nhóm.** Plugin của nhóm này không được import, gọi hay phụ thuộc vào core hoặc plugin của nhóm khác. Thứ gì cần dùng chung giữa các nhóm thì đưa xuống `foundation`, và chỉ khi nó không mang nghiệp vụ.
- `foundation` không được biết đến bất kỳ nhóm nào.

## Mỗi plugin chạy trên hai CLI

| File | Dùng cho | Nội dung |
|---|---|---|
| `.claude-plugin/plugin.json` | Claude Code | `name`, `version`, `description`, `author`, `dependencies` |
| `plugin.json` (gốc plugin) | Antigravity CLI | Chỉ `$schema`, `name`, `description` (schema không cho thêm trường) |

Tên plugin có tiền tố nhóm (`dev-*` cho software-dev). Marketplace Claude Code nằm ở `.claude-plugin/marketplace.json` tại gốc repo.

## Chuẩn tài liệu của plugin

Mọi nhóm và mọi plugin phải có hướng dẫn sử dụng theo ba tầng dưới đây. Chuẩn này **bắt buộc** cho cả nhóm tạo sau này (ví dụ marketing); nhóm chưa có core thì chưa bị kiểm, và bị kiểm từ lúc có `USAGE.md` (ở một trong hai chỗ dưới đây) hoặc `families/<nhóm>/core/workflow.yaml` (có file này mà thiếu `USAGE.md` là lỗi).

| Tầng | File | Nội dung bắt buộc |
|---|---|---|
| Toàn repo | `README.md` ở gốc | Không có khuôn prompt. Chỉ link tới `USAGE.md` của **mọi** nhóm đã có core (ở bảng nhóm), đúng chỗ file đó nằm |
| Core của nhóm | `families/<nhóm>/USAGE.md` **hoặc** `families/<nhóm>/core/USAGE.md` (một trong hai, có cả hai là lỗi) | Mục có tiêu đề đúng `## Khuôn yêu cầu task`, trong đó có ít nhất một khối code chứa khuôn. Khuôn là đầu vào của bước xác nhận (bước đầu của workflow nhóm) |
| Plugin con | `families/<nhóm>/<plugin>/README.md` | Mục `## Dùng cùng <tên core>` (ví dụ `## Dùng cùng dev-core`): dữ liệu cần thêm khi tạo task và ví dụ done-when cho gate của plugin. Plugin con **chỉ thêm**, không có khuôn riêng và không thay khuôn của core. Plugin còn là khung thì mục này nói một câu rằng chưa có phần bổ sung |

- **Tên tiêu đề là bắt buộc; nội dung khuôn do từng nhóm quyết.** Kiểm tự động chỉ xem tiêu đề `## Khuôn yêu cầu task` và khối code dưới nó, không xem các nhãn trong khuôn. Khuôn của software-dev (6 dòng: Loại, Mục tiêu, Xong khi, Trong phạm vi, Ngoài phạm vi, Tài liệu) không áp cho nhóm khác.
- Hướng dẫn chỉ nói về quy trình và môi trường làm việc, không đưa quy ước code, kiến trúc hay stack vào khuôn và ví dụ; ví dụ done-when dùng chỗ trống như `<lệnh test của dự án>`.
- `<tên core>` là `name` trong `.claude-plugin/plugin.json` của `families/<nhóm>/core/`.
- Link tương đối trong các file thuộc chuẩn (README gốc, `families/*/README.md`, mọi `USAGE.md` của nhóm, README của từng plugin) phải trỏ tới file hoặc thư mục có thật; phần sau dấu `#` không được kiểm.
- Cưỡng chế bằng `tools/docs_standard.py` (chạy riêng: `uv run tools/docs_standard.py`; test: `tools/test_docs_standard.py`). Lỗi nêu rõ tên file: thiếu `USAGE.md`, có hai `USAGE.md`, thiếu mục khuôn hoặc khuôn không có khối code, thiếu mục "Dùng cùng ..." ở plugin con, README gốc thiếu link, link hỏng.

## Foundation ↔ nhóm: hợp đồng workflow

Mỗi nhóm khai báo quy trình của mình trong một file `workflow.yaml` đặt trong plugin core của nhóm (ví dụ `families/software-dev/core/workflow.yaml`). Foundation chỉ đọc file này, không import hay gọi code của nhóm.

| Trường | Ý nghĩa |
|---|---|
| `schema_version` | Hiện là `1` |
| `family` | Tên nhóm, dạng `^[a-z][a-z0-9-]*$` |
| `steps[].id`, `name`, `role` | Mã bước, tên hiển thị, role phụ trách (foundation chỉ coi role là chuỗi) |
| `steps[].requires_approval` | Bước cần người duyệt (mặc định `false`) |
| `tiered_roles` | Role có một agent cho mỗi tier của mục kế hoạch (`<role>-fast`, `<role>-deep`); role khác chỉ có một agent. Tùy chọn; mỗi role phải là role của một bước |
| `sizes` | Cỡ task, tùy chọn: `default` và `profiles.<tên>`. Mỗi profile có thể có `skip_approval` (các bước không cần duyệt với cỡ này; phải là bước vốn cần duyệt), `max_plan_items` (số mục tối đa của kế hoạch) và `scans` (bước → id các tool scan được chạy; bước không liệt kê chạy hết). Foundation chỉ đọc các tham số này, không biết cỡ nào ứng với nghiệp vụ gì |
| `read_only_roles` | Role chỉ đọc: `role grant` chỉ cấp cho chúng tool đọc, đúng tên. Tùy chọn |
| `types` | Loại task → khác biệt: `test_spec: green` cho task giữ hành vi (dev-core: `refactor`, `chore`), bước `test-spec` đòi lệnh xanh trên code hiện tại (`- green: pass`), khóa như thường, `tests-pass` đòi vẫn xanh; `tests amend` đòi test sửa vẫn xanh trên code cũ. Loại không ghi thì `red`. `size: <profile>` là cỡ mặc định của loại đó khi không có `--size` (dev-core: `hotfix: {size: hotfix}`); profile phải có trong `sizes`. Loại task được ghi ở trường `type` của task trong `state.json`. Tùy chọn |
| `agent_dirs` | CLI → thư mục (tính từ file workflow) chứa file agent đã sinh, để `role grant` chép sang dự án. Tùy chọn |
| `max_rounds` | Số lần một task được quay lại làm lại (cả workflow) |
| `steps[].on_fail` | Bước đứng trước mà task quay về khi bước này fail |
| `steps[].gates` | Gate bước phải qua trước khi `task advance --result pass` được nhận: `plan-valid` (kế hoạch qua `plan check`, kể cả quy ước `item-order` và mọi câu hỏi "Chưa có quy ước" đã được trả lời), `scans-clean` (kết quả scan không còn mục chặn), `conventions-reviewed` (báo cáo review có một dòng cho từng quy ước `check: review`), `drift-reviewed` (báo cáo review có mục `## Đề xuất cập nhật hồ sơ` đúng khuôn; chỉ kiểm hình thức), `requirements-reviewed` (báo cáo review có `Y1: đạt ...` hoặc `Y1: chưa đạt ...` cho từng yêu cầu của bước đầu; có `chưa đạt` thì không cho `pass`), `requirements-sourced` (mỗi `- Y1: ...` của báo cáo bước này kết thúc bằng `(nguồn: ...)`: tài liệu của mục `## Tài liệu`, có `:dòng`/`#mục` tùy chọn, file trong thư mục được liệt kê, link được liệt kê, hoặc `người dùng`; file phải có thật, dòng phải nằm trong file). Mỗi lần cổng từ chối, thanhtan ghi một dòng vào `tasks/<task>/gate-log.jsonl` (đọc bởi `thanhtan stats`) |
| `steps[].pin_docs_on_approval` | Khi người duyệt bước, ghi sha256 của các đường dẫn ở mục `## Tài liệu` của báo cáo vào `tasks/<task>/docs-pinned.json` (`docpin.py`); nguồn checklist `changed-docs` và `thanhtan status` báo tài liệu đã đổi. Link chỉ được ghi lại |

Các bước chạy theo thứ tự trong danh sách; không có bước "loop" riêng. Fail ở bước có `on_fail` thì task quay về bước đó và số vòng tăng 1. Hết `max_rounds`, hoặc bước không có `on_fail`, thì task chuyển `blocked`, cần người quyết định.

File được kiểm hai lớp: JSON Schema (`foundation/src/thanhtan/schemas/workflow.schema.json`, editor có thể dùng qua dòng `# yaml-language-server: $schema=...`) và kiểm tham chiếu trong Python (id không trùng, `on_fail` trỏ tới bước đứng trước).

## Hợp đồng extension (plugin con ↔ foundation)

Plugin con khai báo một file `extension.yaml` (ví dụ `families/software-dev/backend/extension.yaml`). Foundation chỉ đọc file này, không import code của plugin và không biết plugin dùng để làm gì. Schema: [`foundation/src/thanhtan/schemas/extension.schema.json`](../foundation/src/thanhtan/schemas/extension.schema.json). `schema_version` là phiên bản của **hợp đồng** (hiện là `1`), khác với version của plugin.

| Khóa | Ý nghĩa |
|---|---|
| `name`, `family` | Tên extension; family phải trùng family của workflow đang dùng |
| `settings` | `key` (khóa gốc trong cấu hình dự án) và `schema` (JSON Schema) cho các cài đặt mà extension đọc; `config check` kiểm theo đây |
| `roles` | Role mới, thêm vào bộ role hợp lệ của `plan check` |
| `path_rules` | Đường dẫn chỉ một số role được đụng: áp lên `files` của mục kế hoạch và lên file staged khi `thanhtan commit --item` |
| `plan_rules` | Mục đụng các đường dẫn đó thì `done-when` phải chứa nguyên văn các chuỗi (thường là lệnh của dự án) |
| `scan_tools` | Tool quét mới: image **ghim phiên bản**, `network` (`none` hoặc `host-gateway`), file đã đổi cần quét, `args`, `when` (điều kiện theo cài đặt) với `skip_note`, và cách đọc kết quả (`json_findings` với trường rule/mức độ và danh sách mức chặn, hoặc `exit_code`) |
| `gates` | Gate thêm cho từng bước (`plan-valid`, `scans-clean`) |

- Placeholder duy nhất: `${config:<khóa>}`, `${host_url:<khóa>}` (đổi `localhost` thành `host.docker.internal`) và `${files}` (cả một đối số). Chỉ được trỏ vào cài đặt dưới khóa của chính extension.
- Extension không chạy được code trên máy chủ: mọi tool chạy trong container, repo mount chỉ đọc, mặc định không có mạng. `host-gateway` chỉ thêm `--add-host host.docker.internal:host-gateway` để container gọi vào dịch vụ đang chạy trên máy chủ; không dùng `--network host`.
- `thanhtan ext add <file>` (việc của người) kiểm schema, family, trùng role/tool, bước tham chiếu có trong workflow, rồi chép vào `.ThanhTan/extensions/<name>.yaml` và ghi tên, đường dẫn nguồn, sha256 vào `config.yaml`. Role/gate/tool lấy từ bản chép, không nhân đôi sang config. `ext list` báo lệch (`source_changed`/`source_missing`), `ext sync` đồng bộ lại.
- Cài đặt dự án nằm ở mục `settings` của `.ThanhTan/config.yaml`; `thanhtan config get|set|check`. `config set` là việc của người.
- Một test (`tests/test_boundaries.py`) bảo đảm mã nguồn foundation không chứa từ vựng của plugin nào.

## Workspace của dự án

`thanhtan init --workflow <file>` tạo `.ThanhTan/` ở gốc repo git của dự án. Thư mục này chỉ ở local: init ghi `.ThanhTan/` vào `.git/info/exclude` của dự án, không sửa `.gitignore`. Trước 0.8.0 thư mục tên là `.agentflow/` (`LEGACY_WORKSPACE_DIR`): `find_workspace` và `init` gọi `migrate_legacy_workspace`, đổi tên nó thành `.ThanhTan/` khi chỉ có thư mục cũ (thêm dòng exclude mới, báo một dòng ở stderr), từ chối với mã 38 `WORKSPACE_CONFLICT` khi có cả hai, và báo đóng phiên đang mở khi đổi tên lỗi. Cho tới lúc đổi tên, `pathguard` và `lockguard` nhận cả hai tên. `~/.agentflow/` của người dùng được đổi thành `~/.ThanhTan/` theo cùng cách (`projectlocator.user_dir`; không đổi được thì dùng tại chỗ).

```
.ThanhTan/
  state.json      nguồn sự thật về trạng thái (kiểm theo state.schema.json)
  STATE.md        sinh lại từ state.json mỗi lần ghi, không sửa tay
  config.yaml     family, source_path và sha256 của workflow gốc lúc chép
  workflow.yaml   bản chép của workflow: status/next dùng bản này
  decisions/      mỗi lần người duyệt tiếp một task bị blocked ghi một file
  tasks/T-001/reports/<bước>.md   báo cáo của từng bước (thanhtan report)
  tasks/T-001/summary.md, spec-delta.md   do thanhtan sinh lúc seal (spec-delta: cái task thật sự đổi)
  tasks/T-001/replan.md                   đề xuất replan của scout (replan_write); chỉ "proposed" tới khi người chạy replan done
  project/        profile.md (có mục ## Mission), architecture.md, sources.md, conventions.md, roadmap.md,
                  confirmations.json (hash của cái người đã xác nhận), history/ (bản trước của tài liệu bị ghi đè)
  knowledge/
```

- Chạy lại `init` không ghi đè `state.json` hay bản chép workflow; chỉ tạo phần còn thiếu và cập nhật `source_path`. Đổi sang workflow của nhóm khác thì bị từ chối.
- Khi bản gốc đổi (sha khác), `status`/`next`/`init` cảnh báo và gợi ý `thanhtan workflow sync`. Khi bản gốc không còn, thanhtan dùng bản chép và cảnh báo.
- `workflow sync` kiểm bản gốc theo schema trước, rồi mới thay bản chép. Có task đang `open`/`blocked` thì từ chối, trừ khi có `--force`; kể cả với `--force`, sync vẫn bị từ chối nếu workflow mới bỏ mất bước mà một task đang đứng.

**Cỡ task.** `--size` chọn một profile của `sizes` trong workflow (thiếu thì lấy `default`; workflow không có `sizes` thì không nhận `--size`). Cỡ được ghi vào task (`size` trong `state.json`, `STATE.md`, `status`, `summary.md`) và có ba tác dụng: bước nằm trong `skip_approval` pass là đi tiếp luôn (gate vẫn chạy, nên `plan-valid` vẫn kiểm kế hoạch); kế hoạch dài hơn `max_plan_items` bị `plan check` từ chối; `thanhtan scan` và gate `scans-clean` chỉ xét các tool nằm trong `scans` của bước đó. Với `software-dev`: `small` bỏ duyệt `plan`, tối đa 3 mục, bước `security` chạy `gitleaks`, `semgrep` và `semgrep-conventions`.

Task trong `state.json` có `id` (`T-001`), `title`, `status` (`open`/`blocked`/`done`/`cancelled`), `current_step`, `step_status` (`in_progress`/`awaiting_approval`/`passed`/`failed`), `loop_round`, `branch` (chuỗi hoặc `null`), `size` (tùy chọn, chỉ có khi workflow có `sizes`) và `history`.

## Lệnh thanhtan

| Lệnh | Việc làm | Exit code khác 0 khi |
|---|---|---|
| `thanhtan doctor` | Kiểm uv, git (bắt buộc) và docker/podman (cần ít nhất một); in link cài chính thức cho công cụ thiếu | Thiếu công cụ bắt buộc. Engine container không chạy chỉ là cảnh báo |
| `thanhtan init --workflow <file>` | Tạo hoặc bổ sung `.ThanhTan/` | Không phải repo git, workflow không hợp lệ, khác nhóm |
| `thanhtan status` | Task đang mở, bước hiện tại, việc tiếp theo | Chưa có workspace, state hỏng |
| `thanhtan next` | Bước tiếp theo, dạng `<loại>: <mô tả>` | Như `status` |
| `thanhtan workflow sync [--force]` | Thay bản chép workflow bằng bản gốc đã kiểm | Bản gốc lỗi hoặc mất, khác nhóm, có task đang chạy |
| `thanhtan task new "<tiêu đề>" --type feature\|bugfix\|hotfix\|refactor\|chore [--size <cỡ>] [--roadmap Rn] [--base <nhánh>]` | Tạo nhánh `<type>/T-001-<slug>` từ nhánh gốc (`--base`, rồi `git.base.<loại>`, rồi `git.base.default`, rồi `develop`; `main` cho hotfix) và ghi task cùng nhánh gốc (`base` trong `state.json`); `--roadmap` gắn task với một mục roadmap (chuyển mục sang `doing`). Không có `--size` thì lấy cỡ của loại task (mục `types`), rồi cỡ mặc định. Cảnh báo (không chặn) khi thiếu mission/roadmap, chưa xác nhận, hoặc không có `--roadmap` (trừ task `hotfix`) | Cây làm việc chưa sạch, đã có task mở, thiếu nhánh gốc; `--roadmap` sai mã, không có roadmap, mục `done`/`dropped` |
| `thanhtan task advance --result pass\|fail` | Ghi kết quả bước hiện tại | Không có task, bước không ở trạng thái cho phép |
| `thanhtan task approve [--reason ...]` | Duyệt bước đang chờ; với task `blocked` là người cho làm tiếp (ghi `decisions/`) | Như trên |
| `thanhtan task cancel` | Hủy task đang mở | Không có task đang mở |
| `thanhtan task seal <id>` | Việc của người: ghi `summary.md` và tag duyệt cho task đã xong mà chưa có (`--commit <sha>` khi nhánh đã xóa) | Task chưa xong, đã có tag, không thấy commit |
| `thanhtan scope [--step <bước>]` | Chỉ đọc: phạm vi review của vòng này (cả task, hoặc từ commit mà vòng trước của bước đã xem, ghi trong `review-marks.json`), kèm lệnh `git diff`, commit và số dòng từng file | Không có task đang mở |
| `thanhtan review-map` | Ghi `tasks/<task>/review-map.md`: mỗi mục kế hoạch → commit, file, số dòng, kết quả lệnh thanhtan đã chạy, file ngoài `files` của mục (cũng tự ghi khi `review` chờ duyệt) | Không có task đang mở |
| `thanhtan scan [--all]` | Chạy trong container các scan của bước hiện tại (bước `security`: Semgrep, Trivy, Gitleaks; plugin có thể thêm tool cho bước khác). Ghi `tasks/<task>/scans/` | Có phát hiện chặn (`SCAN_BLOCKED`), cây làm việc chưa sạch, engine container không chạy |
| `thanhtan decide --suppress <id> --reason ...` | Việc của người: ghi `decisions/<task>-suppress-<mã>.md` để bỏ qua một báo nhầm của scan | Không có phát hiện đó trong kết quả scan, thiếu `--reason` |
| `thanhtan ext add <file>` / `ext list` / `ext sync [tên] [--force]` | Đăng ký, liệt kê, đồng bộ extension (`add`, `sync` là việc của người) | File không hợp lệ, sai family, trùng role/tool, nguồn mất |
| `thanhtan config get <khóa>` / `config set <khóa> <giá trị>` / `config check` | Đọc, đặt (việc của người), kiểm cài đặt dự án theo schema của các extension | Chưa đặt (`SETTINGS_INVALID`) |
| `thanhtan plan check [--file f]` | Kiểm kế hoạch: mã `C<n>`, role hợp lệ, `done-when`, `docs` | Có mục sai (mã `PLAN_INVALID`) |
| `thanhtan plan assign` | In `mã role tier agent` cho từng mục của kế hoạch đang dùng (tier thiếu là `deep`; agent là `<role>-<tier>` nếu role nằm trong `tiered_roles`, ngược lại là `<role>`) | Chưa có báo cáo plan |
| `thanhtan role grant <role> <tool>` / `revoke` / `sync` | Việc của người: cấp (hoặc thu hồi) cho role một tool MCP trong dự án này, ghi vào `role_grants` của `config.yaml`; với Claude Code sinh `.claude/agents/project-<agent>.md` mang thêm tool đó (`sync` sinh lại theo plugin đang cài) | Role không có, tool không phải tên/mẫu MCP, role chỉ đọc bị cấp tool không đọc hoặc mẫu (`ROLE_GRANT_REFUSED`), không thấy file agent của plugin, đã cấp rồi / chưa cấp |
| `thanhtan role list` | Grant của dự án, agent đang mang chúng và trạng thái (`current`, `stale`, `missing`), ghi chú Antigravity | |
| `thanhtan report --step <bước>` | Ghi stdin vào `tasks/<task>/reports/<bước>.md` | Bước không có trong workflow, nội dung rỗng |
| `thanhtan commit "<nội dung>" [--item C1]` | Scan secret rồi commit với tiền tố `T-001: `; `--item` ghi trailer `Plan-Item: C1` | Sai nhánh, không có gì staged, thấy secret, engine container không chạy, mục không có trong plan |
| `thanhtan project confirm <mã...>\|--all` | Việc của người: xác nhận quy ước (`PC-01`, `status: confirmed` trong `project/conventions.md`), mission (`mission`), `profile`, `architecture` hoặc mục roadmap (`R1`), lưu hash trong `project/confirmations.json`; `--all` chỉ gồm quy ước | Mã không có, tài liệu chưa có, mission thiếu trường, file có lỗi; một mã sai thì không xác nhận gì |
| `thanhtan project status` | Chỉ đọc: `mission:`, `profile:`, `architecture:`, `conventions:`, `roadmap:` là `missing`/`unconfirmed`/`confirmed`, và `removed: R4 (confirmed)` cho mục roadmap đã xác nhận mà agent bỏ đi | Chưa có workspace |
| `thanhtan roadmap list` | Chỉ đọc: `R1 [todo] Tiêu đề` kèm `(unconfirmed)` | Chưa có workspace |
| `thanhtan roadmap set <Rn> todo\|doing\|done\|dropped` | Việc của người: đổi trạng thái một mục roadmap (không làm mục mất xác nhận) | Mã không có, chưa có roadmap |
| `thanhtan conventions` | Liệt kê quy ước đã gộp từ decisions, project và kho cá nhân (quy ước chưa xác nhận ghi rõ là gợi ý) | |
| `thanhtan decide --answer <Q1\|S1> --text ... --check plan\|semgrep\|review [--rule r] [--overrides code] [--global]` | Việc của người: trả lời câu hỏi (của plan hoặc của setup), sinh quy ước `DC-NN` trong `decisions/`; `--global` ghi thêm `KC-NN` vào kho cá nhân | Không có câu hỏi đó, thiếu `--text`/`--check`, đã trả lời, quy ước không hợp lệ |
| `thanhtan knowledge init [--dir D]` / `pull <file...>` / `push <file> [--as lessons\|patterns]` | Việc của người: tạo khung kho cá nhân; chép file người chọn vào `.ThanhTan/knowledge/`; đưa một bài học từ workspace về kho | Đường dẫn ra ngoài kho/workspace, file đã có ở đích |
| `thanhtan replan status` | Chỉ đọc: `replan: no-finished-task\|task-open\|not-sealed\|pending\|proposed\|done\|skipped` và `task: <id>` |
| `thanhtan replan write` | stdin: đề xuất replan của task xong gần nhất (`tasks/<task>/replan.md`); từ chối khi có task mở/blocked, thiếu hai mục bắt buộc hay nêu mục roadmap lạ |
| `thanhtan replan done` / `thanhtan replan skip <task> --reason ...` | Việc của người: xác nhận replan đã `proposed` là xong (`replanned_at`, summary, xóa `removed:`) / chủ động bỏ qua |
| `thanhtan tests verify-red` / `tests check` / `tests amend <file>... --reason ... [--accept-green]` | `verify-red`: ở bước test-spec chạy lại lệnh của báo cáo, đòi đỏ. `check` (chỉ đọc): so hash file khóa với cây làm việc và HEAD. `amend` (việc của người): mở cửa sổ đổi file đã khóa | `verify-red`/`check`: có lệnh không đỏ / file lệch (mã `GATE_FAILED`). `amend`: thiếu `--reason`, file không khóa, chưa có khóa |
| `thanhtan mcp serve` | Chạy server MCP trên stdio (do Claude Code/Antigravity khởi động) | |
| `thanhtan hook <pre-tool\|session-start\|stop> --cli claude\|antigravity` | Trả lời hook của CLI (JSON trên stdin): chặn lệnh và ghi nguy hiểm, nạp tóm tắt task đầu phiên, nhắc khi dừng | Không bao giờ: lỗi chỉ báo ra stderr, hook luôn thoát 0 để không làm hỏng agent |
| `thanhtan guard` | Đọc `{"command","cwd"}` từ stdin, in `{"decision","rule","reason"}` | Input không phải JSON hợp lệ |

### Vòng đời task

`task new` → mỗi bước: `task advance --result pass` → (bước cần duyệt) `task approve` → bước kế. Fail ở `test`/`security`/`review` quay thẳng về `implement`, đếm vòng; hết `max_rounds` (mặc định 3) thì task `blocked` và chỉ người mới `task approve` để cho làm tiếp (vòng reset về 0, ghi một file vào `decisions/`) hoặc `task cancel`. Đi hết bước cuối thì task `done`. Chỉ một task mở tại một thời điểm.

### Tên `thanhtan` (từ 1.0.0)

Package, lệnh, server MCP (`mcp__plugin_dev-core_thanhtan__*`) và biến môi trường (`THANHTAN_HOME`, `THANHTAN_PROJECT_DIR`, `THANHTAN_HOOK_LOG`, `THANHTAN_CACHE_DIR`) mang tên `thanhtan`. Tên trước 1.0.0 còn được nhận: `agentflow` là bí danh của cùng chương trình (`cli.legacy_main` in một dòng nhắc tên mới ra stderr, trừ `hook`, `mcp`, `guard` mà CLI tự gọi); `envvars.get` đọc `AGENTFLOW_*` khi `THANHTAN_*` chưa đặt; guard (`PROGRAM_NAMES`, `scriptscan`) coi `agentflow` như `thanhtan`, nên bí danh không là đường vòng. Tag duyệt mới là `thanhtan/<task>/approved`; `seal.is_approved` vẫn tính tag `agentflow/<task>/approved`, và guard bảo vệ cả hai tiền tố (`APPROVAL_TAG_PREFIXES`).

### Lệnh của người cho việc ngoài workflow

- `taskexport.export` (`thanhtan task export`): `git commit-tree` cây của commit cuối nhánh task lên `git merge-base <nhánh gốc> <nhánh task>`, rồi `git branch` tên mới; không checkout, không push.
- `workspacesync` (`thanhtan workspace remote|save|load|status`): repo riêng tư của người được clone vào `~/.ThanhTan/store/`; mỗi dự án một thư mục. `save` chép `.ThanhTan/` (trừ `sync.json`) và một `git bundle` của nhánh task cùng tag duyệt, ghi `save.json` (máy, thời điểm, fingerprint sha256 của workspace), commit, push. `load` khôi phục ref không ghi đè ref khác commit, chép workspace về, trỏ `workflow.source_path` vào `workflow.yaml` của dev-core cài ở máy này (`~/.claude/plugins`, `~/.gemini/...`). Mỗi máy ghi fingerprint lần lưu/tải cuối vào `.ThanhTan/sync.json`: `save` từ chối khi fingerprint trong store khác (máy khác đã lưu), `load` từ chối khi workspace của máy này khác fingerprint đó (chưa lưu); mã 39 `WORKSPACE_SYNC`.
- `permissions.install` (`thanhtan permissions install`): gộp `data/claude-permissions.json` (test giữ nó trùng khối README Bước 4) vào settings của Claude Code, bỏ quy tắc chứa `agentflow` và quy tắc `allow` cho `task approve|cancel`.

Năm lệnh này nằm trong `_PERSON_ONLY` của guard.

### Nhánh gốc của task (`git.*`)

Nhánh một task tách ra là lựa chọn của dự án (`gitconfig.py`), không còn cố định là `develop`. Thứ tự chọn, mạnh nhất trước: `task new --base <nhánh>`, `git.base.<loại task>`, `git.base.default`, rồi mặc định `git.develop_branch` (hotfix: `git.main_branch`); hai tên này mặc định là `develop` và `main`. Cài đặt bằng `thanhtan config set` (việc của người, guard từ chối agent); `config set` chỉ nhận khóa `git.*` đã biết và tên nhánh hợp lệ, `config check` báo giá trị sai viết tay vào `config.yaml`. Nhánh gốc được ghi vào task (`base` trong `state.json`, schema `state.schema.json`) lúc tạo; đổi cài đặt sau đó không dời task. `seal.base_branch` đọc `task.base`, task cũ không có thì suy ra từ tiền tố nhánh như trước; từ đó `scope`, `review-map`, `scan` (phạm vi file đổi), `spec-delta.md` và `summary.md` so với đúng nhánh gốc. `task new` đòi nhánh gốc có trên máy và cảnh báo (không chặn) khi nó tụt so với `origin/<nhánh>`. Guard bảo vệ thêm các nhánh bạn đặt tên và nhánh gốc của task đang mở (`hook.protected_branches`, cũng dùng cho `thanhtan guard`); `main` và `develop` luôn được bảo vệ. Giới hạn: task cũ không có `base` vẫn suy ra `develop` hay `main` theo tên cố định, không theo `git.*`; và hash chống sửa ngoài của `config.yaml` chỉ bao `test_command`, `test_timeout_minutes`, còn `git.*` dựa vào việc hook chặn agent ghi vào `.ThanhTan/`.

### commit và guard

`thanhtan commit` chỉ chạy khi đang ở nhánh của task và có file staged. Gitleaks (image ghim phiên bản, chạy qua Docker, dự phòng Podman, mount chỉ đọc) quét phần staged; engine không chạy hoặc có secret thì báo lỗi và **không commit**.

`thanhtan guard` chặn: `git push` mọi dạng; mọi dạng `git commit` trong dự án đã có `.ThanhTan/` (chỉ cho commit qua `thanhtan commit`; repo không có `.ThanhTan/` thì không chặn); `merge`/`commit`/`rebase`/`cherry-pick`/`revert`/`am` khi đang ở `main` hoặc `develop`; `reset --hard`; `clean` có cả `-f` và `-d`; `branch -D` (và `-d -f`); xóa tag; tạo tag hoặc ref dưới `thanhtan/` (tag duyệt chỉ do `task approve` tạo); các lệnh của người (`decide`, `ext add`, `ext sync`, `config set`, `task seal`, `project confirm`, `roadmap set`, `replan done`, `replan skip`, `state accept`, `tests amend`, `knowledge init|pull|push`) khi agent tự chạy. Hiểu lệnh ghép (`&&`, `;`, `|`), `git -C`, `bash -c "..."` và việc `git switch` sang nhánh được bảo vệ ngay trong chuỗi lệnh. Với `task approve` và `task cancel` (trong dự án có workspace) guard không từ chối mà trả `ask`: Claude Code hiện câu hỏi (`permissionDecision: "ask"`), Antigravity buộc hỏi (`decision: "force_ask"`); một lệnh bị từ chối thắng một lệnh phải hỏi trong cùng dòng. Lệnh `thanhtan` được nhận ở mọi vị trí hợp lệ, không chỉ đầu dòng (xem "Bảo vệ workspace"). Đây là lưới an toàn cho agent, không phải sandbox: alias git, script hay biến môi trường vẫn có thể vượt qua.

### Bảo vệ workspace

Mọi ghi vào `.ThanhTan/` chỉ đi qua lệnh `thanhtan` (và tool MCP của nó). Hook `pre-tool` chặn hai đường khác:

- **Tool ghi file của CLI.** Claude Code: `Write`, `Edit`, `NotebookEdit` (và `MultiEdit` cho chắc); Antigravity: `write_to_file`, `replace_file_content`, `multi_replace_file_content`. Đường dẫn được đổi thành tuyệt đối, bỏ `.`/`..`/dấu phân cách thừa, theo symlink; trên Windows so tên không phân biệt hoa thường. Một thư mục `.ThanhTan` chỉ được bảo vệ khi trong nó có `config.yaml`, nên thư mục trùng tên (`.ThanhTan-notes`) không bị ảnh hưởng.
- **Lệnh shell ghi vào `.ThanhTan/`, mức cố gắng tốt nhất.** Chuyển hướng `>`, `>>`, `>|`, `&>`, `2>`; `tee`, `cp`/`copy` (chỉ đích), `mv`, `rm`, `touch`, `truncate`, `mkdir`, `sed -i`, `dd of=`; `Set-Content`, `Add-Content`, `Out-File`, `Clear-Content`, `New-Item`, `Remove-Item`, `Copy-Item`, `Move-Item` và bí danh PowerShell. Lệnh ghép, `cd` trước đó và `bash -c "..."` được hiểu. Thân heredoc được bỏ qua (đó là dữ liệu cho lệnh đọc nó), nên `thanhtan report ... <<'EOF'` có dấu `>` trong nội dung không bị chặn nhầm. Đọc `.ThanhTan/` luôn được phép.
- **Lệnh của người và lệnh phải hỏi, ở mọi dạng gọi.** Hook tìm `thanhtan` sau các lớp khởi chạy: `uv run thanhtan`, `uv run --project <dir> thanhtan`, `uv run --with ... thanhtan`, `uvx thanhtan`, `uv tool run`, `python -m thanhtan` (`python3`, `py -3`, `python.exe`, đường dẫn đầy đủ), wrapper `timeout`, `nohup`, `time`, `nice`, `command`, `env`, `xargs`, `sudo`, tiền tố biến môi trường (`FOO=1 thanhtan`), đường dẫn đầy đủ tới `thanhtan`, `bash -c`/`bash -lc`/`cmd /c`/`powershell -Command`, `eval`/`iex`, `Start-Process thanhtan -ArgumentList '...'`, và `python -c`/`node -e` có chứa `thanhtan` kèm các từ của lệnh. Lệnh chỉ nhắc chữ (`echo "thanhtan task approve"`, `grep`, commit message) không bị tính.
- **Heredoc, pipe và here-string.** Thân heredoc là dữ liệu cho `thanhtan report`, `cat`, `tee`, `python script.py` (không chạy nội dung), nên báo cáo nhắc "thanhtan task approve" không bị hỏi nhầm. Khi nội dung được đưa vào **trình thông dịch** chạy nó (`bash`, `sh`, `zsh`, `python`, `node`, `perl`, `ruby`, `pwsh`, `powershell`, `cmd`, `uv run python`...) qua heredoc, `|`, `<<<` hay `-c`, hook quét nó như lệnh: có lệnh của người thì từ chối, có `task approve`/`task cancel` thì hỏi. Nội dung không đọc được trước (`curl ... | sh`, `cat file | bash`, `bash < file`, `ls | bash`) thì hỏi, vì có thể chứa lệnh của người. Script đã nằm sẵn trong file (`bash run.sh`) hay do biến sinh ra không được đọc.

Đây là lưới an toàn, **không phải sandbox**. Không bị chặn: `python -c`/`node -e` và script (`bash run.sh`), alias, biến môi trường, hay một chương trình khác tự ghi file. Muốn chặn cứng cần sandbox của hệ điều hành hoặc quyền `deny` của CLI.

Hook không đọc được: biến (`& $exe task approve`, `thanhtan $args`), alias, script có sẵn trong file, chương trình khác tự gọi `thanhtan`, và mọi thứ chạy ngoài hook (một cửa sổ terminal khác). `python -c` hay script tự ghi file chỉ bị phát hiện qua việc `state.json` đổi. Sandbox của Claude Code chỉ có trên macOS, Linux và WSL2; trên Windows gốc không có sandbox, và sandbox cũng chỉ bao lệnh shell, không bao tool file, MCP hay hook. Chặn cứng chỉ có sandbox hoặc quyền hệ điều hành.

### Mô hình bảo vệ duyệt

Bước cần người duyệt có một checklist `.ThanhTan/tasks/<task>/approve-<bước>.md` (bước khai `approval_checklist` / `approval_items` trong `workflow.yaml`; thanhtan ghi lúc bước chuyển sang `awaiting_approval`). `thanhtan task approve` đọc nó: từ chối (mã 36) khi còn ô bắt buộc chưa tick hoặc khung (các dòng, đầu file) khác bản thanhtan đã ghi; từ chối (mã 37) khi `state.json` khác hash đã lưu hoặc nhật ký hook có lệnh có khả năng ghi vào checklist. Ghi chú của người vào `decisions/<task>-<bước>-approval.md`. Không lớp nào dưới đây đứng một mình; mỗi lớp có giới hạn:

| Lớp | Chặn gì | Giới hạn |
|---|---|---|
| Quy tắc `permissions` của README Bước 4 (`deny` ghi `state.json`, `ask` cho approve/cancel) | Tool file của Claude Code ghi `state.json`; hỏi trước approve/cancel | Quy tắc Bash không bóc `uv run`, đường dẫn đầy đủ, `sh -c`; Antigravity không có quy tắc `ask` |
| Hook `pre-tool` `deny` | Tool file và lệnh shell ghi vào `.ThanhTan/` (kể cả `approve-*.md`, `audit.jsonl`); lệnh của người (`state accept`, `project confirm`...) | Mức cố gắng: `python -c`/`node -e`, script, alias, biến, chương trình khác tự ghi file không bị thấy |
| Hook `ask` / `force_ask` | Luôn hỏi người trước `task approve`/`task cancel`, mọi dạng gọi hook đọc được | Không có tác dụng với `agy --dangerously-skip-permissions`; người dùng chế độ tự duyệt thì chỉ còn các lớp khác |
| Checklist `approve-*.md` + khung | Approve khi còn ô chưa tick; thêm, xóa, sửa dòng; sửa đầu file | Chỉ ngăn nhầm lẫn và sửa vụng: ai chạy được mã cùng quyền người dùng vẫn tick hộ được |
| Hash `state.json` trong `integrity.json` | Sửa tay `state.json` bị phát hiện trước `new`/`advance`/`approve`; hash khung của từng checklist | Agent viết mã Python có thể tính lại và ghi đè cả hai file: hash không chống được người cố ý |
| Nhật ký `audit.jsonl` | Ghi mọi lệnh/tool chạm tên `state.json`, `STATE.md`, `integrity.json`, `approve-*.md`, `locked-files.json`, `confirmations.json`, kèm quyết định; approve từ chối khi có dòng được cho qua mà có khả năng ghi | Chỉ thấy cái đi qua hook (Bash, PowerShell, tool ghi file): lệnh `python -c` chạy bên ngoài hook, tool đọc Read/Glob/Grep không ghi nhật ký, và chương trình tự ghi file không để lại dòng nào |
| `thanhtan commit` | Từ chối commit khi sai nhánh, có secret, hoặc đụng file không được phép | Chỉ cho commit đi qua thanhtan; `git commit` trực tiếp bị hook chặn nhưng không phải sandbox |
| `thanhtan state accept` | Người đọc thay đổi rồi mới tin lại file; ghi `decisions/` | Là lệnh của người: chỉ hiệu lực khi hook chặn agent tự chạy |
| Khóa test đã duyệt (`locked-files.json`, hook, `thanhtan commit`, cổng `locked-files-intact`) | Sửa, xóa, đổi tên test đã duyệt và file hạ tầng test; thêm file cấu hình test để bỏ qua test | Hook không đọc `python -c`, script, `patch`; chỉ cổng hash bắt ở bước sau; xem "Khóa test đã duyệt" |
| Sandbox của CLI | Chặn ghi file ở mức hệ điều hành | Sandbox của Claude Code chỉ có trên macOS, Linux, WSL2; trên Windows gốc không có sandbox, và nó chỉ bao lệnh shell, không bao tool file/MCP/hook |

Nhìn chung: các lớp trên làm cho việc duyệt hộ khó xảy ra do sơ suất và để lại dấu vết, **không** biến nó thành không thể. Chặn cứng cần quyền hệ điều hành hoặc sandbox. Một agent chạy được mã tùy ý có thể tính lại mọi hash và xóa dấu vết mà hook không thấy; vì vậy bạn nên đọc `decisions/` và `audit.jsonl` khi nghi ngờ, và không bật chế độ bỏ qua quyền (`permissions.disableBypassPermissionsMode`).

### Khóa test đã duyệt

Bước khai `lock_on_approval: true` trong `workflow.yaml` (với dev-core: `test-spec`) khóa file khi người `task approve` nó. Cơ chế chung của foundation (không biết "test" là gì ngoài tên file cấu hình thông dụng); dev-core khai bước nào khóa, gate nào kiểm, câu nào trong checklist.

**Danh sách khóa** (`tasks/<task>/locked-files.json`: `task`, `step`, `locked_at`, `files`, `windows`). Mỗi mục của `files` có `sha256`, `head_sha256` (blob ở HEAD), `kind` (`test` | `infra`), `scope` (`file` | `part`) và, với `part`, nhãn `part`. Nguồn: (1) file trong các dòng `- tests:` của báo cáo; (2) file ở mục `## Hạ tầng test` cuối báo cáo; (3) file cấu hình test có sẵn trong repo theo tên: `conftest.py` (mọi thư mục), `pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`, `vitest.workspace.*`, `.mocharc.*`, `karma.conf.*`, `phpunit.xml(.dist)` (khóa nguyên file, `scope: file`); `pyproject.toml`, `setup.cfg`, `package.json` khóa theo **phần cấu hình test** (`scope: part`): các bảng `[tool.pytest...]`, mục `tool:pytest*`, khóa `jest`/`vitest`/`mocha`/`ava` và `scripts.test|pretest|posttest`, hash của dữ liệu đã phân tích (khoảng trắng, chú thích, thứ tự và phần khác không đổi hash). File bị Git bỏ qua (ignored) không tính. Cổng `test-spec-valid` kiểm file khai phải có thật, trong dự án, đã commit và sạch, và ghi hash từng file ở `verify-red.json["files"]`; `task approve` từ chối nếu hash lúc duyệt khác hash lúc chạy đỏ. Khóa có hiệu lực tới khi task `done` hoặc `cancelled`.

**Các lớp.**

| Lớp | Chặn gì | Giới hạn |
|---|---|---|
| Hook `pre-tool` (chính sách đường dẫn đọc `locked-files.json` của task đang chạy; `state.json` hỏng thì coi khóa là còn hiệu lực) | Tool file và lệnh shell ghi, xóa, đổi tên, copy đè file `scope: file`; `git rm`, `git mv`, `git checkout|restore` lấy từ commit khác; tạo mới hay sửa mọi file cấu hình test chuyên dụng không có trong khóa; lý do nêu `thanhtan tests amend` | Không đọc `python -c`, `node -e`, `perl -pi`, `patch`, `git apply`, script, hard link; cố ý để mở file `scope: part` (hook không biết phần nào bị đổi) |
| `thanhtan commit` | Staged có file khóa (sửa, xóa, đổi tên: `diff --cached --no-renames`), file `scope: part` đổi phần cấu hình test, file cấu hình test mới | Chỉ chặn đường đi qua thanhtan |
| Cổng `locked-files-intact` (`implement`, `test`, `security`, `review`), cổng `tests-pass` (trước mọi lệnh), `thanhtan tests check` | So hash cây làm việc và HEAD; file mất, đổi tên, file cấu hình mới (kể cả file trở thành cấu hình pytest sau khóa) | Bắt sau khi việc đã xảy ra, ở bước kế tiếp |
| hash trong `integrity.json` (`locked_files_sha256`) | Sửa tay hay xóa `locked-files.json` (mã 37) | Agent chạy mã Python tính lại được cả hai file |
| hash `test_command`, `test_timeout_minutes` (`integrity.json`) và runner bỏ `PYTEST_ADDOPTS`, `PYTEST_PLUGINS` | Đổi lệnh test qua `config.yaml` hoặc qua biến môi trường (mã 37) | Chương trình khác chạy test không qua thanhtan |

**Đổi test đã duyệt.** `thanhtan tests amend <file>... --reason "..." [--accept-green]` (lệnh của người, guard từ chối agent mọi dạng gọi) mở `windows[<file>]` (`reason`, `opened_at`, `accept_green`, đường dẫn decision) và ghi `decisions/<thời điểm>-tests-amend.md` với hash cũ. Hook cho ghi đúng file đó. `thanhtan commit` file đó đóng cửa sổ: trước khi commit, `reverify` tạo checkout tạm (`git worktree`) của commit `verify-red.json["head"]`, chép nội dung staged vào, chạy lại lệnh của các mục dùng file (file hạ tầng hoặc `scope: part`: mọi mục có lệnh) bằng `thanhtan.testrun`. Mục `green` (thoát 0 trên mã cũ) làm commit bị từ chối trừ khi cửa sổ có `--accept-green`; `red`, quá giờ hay không tìm thấy lệnh thì qua (hai loại sau chỉ cảnh báo). Sau commit, khóa nhận hash mới, `verify-red.json["reverified"]` ghi `{Cn: command, exit_code, status, files, at, accepted}`, decision ghi hash mới, commit và kết quả. `results` của `verify-red.json` không bị ghi đè.

**Giới hạn trung thực.** Đây là lưới an toàn, không phải sandbox. Ghi bằng chương trình hook không đọc được chỉ bị cổng hash thấy ở bước sau; trên Windows gốc không có sandbox của Claude Code; `Makefile`, `package.json` (ngoài phần test), `tox.ini` và file helper test import chỉ khóa khi tester khai ở `## Hạ tầng test`; agent chạy mã tùy ý có thể tính lại hash. Cổng không biết một test đỏ vì đúng lý do hay không.

### Giới hạn trên Antigravity

Antigravity CLI không có quy tắc `ask` kiểu `permissions`; chỉ có chế độ phê duyệt lệnh của chính nó và hook. Hook `pre-tool` của dev-core trả `{"decision": "force_ask"}` cho `task approve`/`task cancel`: theo `hooks.md` của agy, `force_ask` bỏ qua bộ nhớ "Always Allow". Các lớp còn hiệu lực: hook `deny` (ghi vào `.ThanhTan/` bằng tool file hay lệnh shell, các lệnh của người), `thanhtan commit` từ chối (sai nhánh, quét ra secret). Không hiệu lực khi người dùng chế độ tự duyệt mọi lệnh (`--dangerously-skip-permissions`): đã thử, lệnh vẫn chạy, nên chỉ còn các hook deny và `thanhtan commit`. Đừng bật chế độ đó cho dự án dùng thanhtan.

### Thử thật hook `ask` (18/10/2026)

Cách thử: dự án tạm có `.ThanhTan/` (workflow dev-core) và hook `pre-tool` gọi `thanhtan` build từ `foundation/`; model được bảo chạy đúng một lệnh Bash rồi nói tool trả về gì. Claude Code: `claude -p --model haiku --output-format stream-json --verbose`, kèm quy tắc `permissions.allow: ["Bash(thanhtan *)"]` để lệnh không phải hỏi vì lý do khác. Antigravity: `agy -p --model "Gemini 3.8 Flash (Low)"` với `.agents/hooks.json`. Cột "chế độ quyền" là tham số thật của từng lệnh (và `permissionMode`/`permission_mode` trong init của CLI).

| CLI | Phiên bản | Ngày | Chế độ quyền (tham số lệnh) | Lệnh agent chạy | Kết quả |
|---|---|---|---|---|---|
| claude | 2.1.302 | 2026-10-18 | `--permission-mode default` | `thanhtan status .` | không hỏi: lệnh chạy (đối chứng, quy tắc allow có tác dụng) |
| claude | 2.1.302 | 2026-10-18 | `--permission-mode default` | `thanhtan task approve .` | hỏi: lệnh không chạy; `-p` không trả lời được nên tool báo "requested permissions ... haven't granted" |
| claude | 2.1.302 | 2026-10-18 | `--permission-mode acceptEdits` | `thanhtan task approve .` | hỏi: như trên |
| claude | 2.1.302 | 2026-10-18 | `--permission-mode bypassPermissions` | `thanhtan task approve .` | hỏi: hook `ask` vẫn hỏi trong bypassPermissions (lệnh không chạy) |
| claude | 2.1.302 | 2026-10-18 | `--permission-mode dontAsk` | `thanhtan task approve .` | chặn: dontAsk đổi câu hỏi thành từ chối, lệnh không chạy |
| agy | 1.4.0 | 2026-10-18 | không cờ (`request-review`) | `thanhtan task approve` | hỏi: "user denied permission" vì `-p` không trả lời được; đối chứng `git status` chạy không hỏi |
| agy | 1.4.0 | 2026-10-18 | `--dangerously-skip-permissions` (`always-proceed`) | `thanhtan task approve` | không hỏi: lệnh vẫn chạy; chưa tách được việc hook có chạy hay không |

Chưa thử: người thật bấm có/không ở giao diện tương tác (trong `-p` không ai trả lời được), chế độ `auto` và `plan` của Claude Code, `--mode accept-edits|auto` của agy, và `--dangerously-skip-permissions` với lệnh bị `deny` để biết hook có chạy trong chế độ đó.

### Cấp tool theo dự án

`config.yaml` có thêm `role_grants` (role → danh sách tên hoặc mẫu tool MCP), chỉ ghi qua `thanhtan role grant|revoke` (việc của người, guard từ chối khi agent chạy). `thanhtan` kiểm role có tồn tại (role của workflow hoặc extension), tên phải là `mcp__<server>`, `mcp__<server>__*` hoặc `mcp__<server>__<tool>`, và role trong `read_only_roles` chỉ nhận tool có tên chính xác bắt đầu bằng một động từ đọc (`ReadVerb`: get, list, read, search, query, find, describe, view, status).

Claude Code (theo tài liệu sub-agents và plugins-reference): `tools` của agent plugin là allowlist cố định, `mcpServers`/`hooks`/`permissionMode` bị bỏ qua với agent plugin, còn agent ở `.claude/agents/` của dự án được nạp. Nên với mỗi agent của role (`<role>` hoặc `<role>-fast`/`<role>-deep` nếu role nằm trong `tiered_roles`), thanhtan chép file agent của plugin (thư mục `agent_dirs.claude` cạnh file workflow hoặc cạnh `extension.yaml` đã đăng ký) thành `.claude/agents/project-<agent>.md`: đổi `name`, nối thêm tool vào `tools`, thêm dòng `Generated by thanhtan role sync from <file> (sha256 ...)`. `.claude/agents/project-*.md` nằm trong `.git/info/exclude`. File chỉ bị xóa khi có dòng đánh dấu đó. Hook `pre-tool` chặn tool ghi file và lệnh shell ghi vào các file này (khi dự án có `.ThanhTan/`). `plan assign --cli claude` dùng tên `project-…` nếu file tồn tại. Antigravity không cần bản sao vì mọi agent thấy mọi MCP đã cài; grant chỉ được ghi nhận.

### Tool MCP

`thanhtan mcp serve` (SDK `mcp` 2.x, stdio) cho agent mười tool, mỗi tool gọi `WorkspaceService` (`services.py`), cùng mã với CLI nên cùng luật; luật bị vi phạm trả về dưới dạng lỗi tool kèm thông báo rõ.

| Tool | Việc |
|---|---|
| `status`, `next_step` | Trạng thái task và việc tiếp theo |
| `plan_check` | Kiểm kế hoạch; plan sai là kết quả `{ok, problems}`, không phải lỗi tool |
| `report_write(step, content)` | Ghi báo cáo. **Chỉ cho bước hiện tại của task đang mở, khi bước còn `in_progress`**: từ chối bước khác và từ chối ghi đè báo cáo của bước đã qua/đang chờ duyệt (cả `thanhtan report`) |
| `project_write(section, content)` | Ghi `project/{profile,architecture,sources,conventions}.md`; từ chối khi còn task mở |
| `replan_write(content)` | Đề xuất replan của task xong gần nhất; chỉ khi không có task mở; chỉ đề xuất (`proposed`), người chạy `replan done` mới xong |
| `scan_summary` | Kết quả scan và phát hiện chặn còn lại |
| `conventions` | Quy ước đã gộp từ decisions, project, kho cá nhân; `enforced=false` là quy ước dự án chưa xác nhận |
| `knowledge_search`, `knowledge_read` | Chỉ đọc bản chép trong `.ThanhTan/knowledge/` |

Không có tool cho việc của người: duyệt, hủy, seal, `decide`, extension, `config set`, push kiến thức. Một test giữ danh sách tool là danh sách đóng.

Plugin khai báo server ở `.mcp.json` (Claude Code) và `mcp_config.json` (Antigravity), cùng lệnh `thanhtan mcp serve`. Điều đã thử thật nằm trong [mcp-notes.md](mcp-notes.md): tên tool ở Claude Code, tên tool của agent plugin, việc Antigravity chạy server ở thư mục plugin (nên server tìm dự án qua `cwd`, `THANHTAN_PROJECT_DIR`, `PWD`, rồi con trỏ `~/.ThanhTan/active-project.txt` mà hook Antigravity để lại), và việc Antigravity không cho giới hạn tool MCP theo role.

### Spec delta và replan

Khi seal một task (`TaskSealer`), thanhtan ghi `tasks/<task>/spec-delta.md` cạnh `summary.md`: mục `## Đề xuất của reviewer` (chép mục `## Đề xuất cập nhật hồ sơ` của báo cáo review, ở bước mang gate `drift-reviewed`, nếu workflow không có gate thì bước cuối), `## Thay đổi thật của task` (mục kế hoạch, commit, file đổi từ `git diff --name-status -z -M`, gom theo thư mục cấp đầu) và `## Liên kết` (mục roadmap; mission, profile, architecture là `missing|unconfirmed|confirmed`). Mọi thứ được tính trước khi ghi nên seal lỗi không để lại file dở.

Replan có bốn trạng thái do `replan_status` suy ra: `pending` (chưa có `replan.md`), `proposed` (có `replan.md`), `done` (task có `replanned_at` trong `state.json`, trường tùy chọn, vắng với task cũ), `skipped` (có `decisions/<task>-replan-skip.md`); task mở hoặc `blocked` thắng mọi trạng thái, và task xong chưa có tag là `not-sealed`. `replan write` / `replan_write` chỉ chuyển sang `proposed` (không ghi `replanned_at`, không xóa dòng `removed:`, không đổi trạng thái roadmap); bản `replan.md` cũ vào `project/history/replan-<task>-...`. Chỉ người chạy `replan done` mới chuyển sang `done`; lệnh này và `replan skip` nằm trong danh sách lệnh của người mà guard từ chối khi agent chạy.

Tham chiếu: ý tưởng này gần với luồng thay đổi theo đặc tả của [OpenSpec](https://github.com/Fission-AI/OpenSpec) (không phụ thuộc, *not a dependency*: không cài gì): `spec-delta.md` tương ứng *propose* (cái thay đổi so với đặc tả), task tương ứng *apply*, `thanhtan project confirm` là chấp nhận thay đổi vào hồ sơ, còn seal cùng tag duyệt tương ứng *archive*.

### Hồ sơ dự án và quy ước

Skill `setup` hỏi người đường dẫn tài liệu (không tự đi tìm), giao cho role `scout` (đọc, chạy lệnh; chỉ ghi qua `project_write`) đọc tài liệu và code rồi viết `.ThanhTan/project/{profile,architecture,sources,conventions}.md`. Chỉ ghi được khi không có task mở.

`conventions.md` có dạng `### PC-01 - tiêu đề` kèm `- check:` (`plan` | `semgrep` | `review`), `- rule:`, `- status:` (`unconfirmed` | `confirmed`), `- source:`, `- description:`, tùy chọn `- overrides:`; mục `## Câu hỏi mở` chứa `### S1 - ...` với `- docs:` và `- code:` cho chỗ tài liệu và code mâu thuẫn (scout không tự chọn).

Quyền xác nhận thuộc về người:
- Quy ước agent ghi luôn là `unconfirmed`. Ghi `confirmed` thì bị đưa về `unconfirmed` (tool báo trong `demoted`).
- Quy ước đã `confirmed` mà nội dung (tiêu đề, check, rule, source, description, overrides) bị đổi thì tự về `unconfirmed`; giữ nguyên thì vẫn `confirmed`.
- Xóa một quy ước đã `confirmed` bị từ chối; chỉ người làm (sửa tay file).
- `thanhtan project confirm <mã...>|--all` (chỉ người chạy, guard từ chối khi agent chạy) đánh dấu `confirmed` cho quy ước. `thanhtan task new` cảnh báo (không chặn) khi còn quy ước `unconfirmed`.

**Mission và roadmap.** `profile.md` có mục `## Mission` (`- why:`, `- for:`, `- scope:`, `- out-of-scope:`, `- source:`); scout lấy từ tài liệu người đưa và không suy từ code. `project_write profile` không từ chối mission thiếu, chỉ trả `warnings` (thiếu mục hoặc trường, trường rỗng, hai mục Mission, Mission chỉ nằm trong khối code). `project/roadmap.md` là danh sách mục `### R1 - tiêu đề` với `- status: todo|doing|done|dropped`, `- goal:`, `- docs:` (link, `file:dòng` hoặc `không có — lý do`); thứ tự file là thứ tự ưu tiên. Sai khuôn thì `project_write roadmap` bị từ chối (mã 35 `ROADMAP_INVALID`, file cũ giữ nguyên).

Hồ sơ nào cũng có thể được xác nhận bằng **hash**, không bằng cờ trong file: `project confirm mission|profile|architecture|R1` lưu sha256 (đã chuẩn hóa xuống dòng và khoảng trắng cuối dòng) vào `project/confirmations.json`, file chỉ thanhtan ghi. Tài liệu hay mục `confirmed` khi nội dung hiện tại còn khớp hash đã lưu; agent ghi lại khác đi thì tự `unconfirmed`, ghi lại đúng văn bản đã xác nhận thì lại `confirmed`. Hash của một mục roadmap không gồm dòng `status:`, nên đổi trạng thái không làm mất xác nhận. Quyền của agent với roadmap: mục mới luôn `todo`; trạng thái mục đã có luôn được giữ (agent ghi khác thì `warnings` nói); không bỏ được mục `doing`/`done`/`dropped` (mã 31); bỏ mục `todo` chưa xác nhận thì tự do, còn mục đã xác nhận thì vẫn bỏ được nhưng có warning, và `project status` ghi dòng `removed: R4 (confirmed)` để replan thấy (dòng này mất khi mục được thêm lại). Mỗi lần ghi đè một tài liệu dự án, bản cũ được lưu ở `project/history/<tài-liệu>-<thời-điểm>.md`.

`thanhtan task new --roadmap R3` gắn task với mục (trường `roadmap` trong `state.json`, `STATE.md`, `status`, `summary.md`) và chuyển mục sang `doing`; mục `done`/`dropped` bị từ chối. Task xong hay được duyệt **không** đổi mục sang `done` (một mục có thể cần nhiều task): người quyết, bằng `thanhtan roadmap set R3 done`. Hủy task trả mục `doing` về `todo` nếu không còn task nào khác (không bị hủy) dùng nó. `thanhtan status` gợi ý mục tiếp theo: mục `doing` chưa có task mở đầu tiên theo thứ tự file, rồi mục `todo` đầu tiên (kèm `(unconfirmed)` khi chưa xác nhận); tool MCP `status` trả thêm `next_roadmap`.

### Quy ước, kho kiến thức và bài học

**Ba nguồn quy ước**, ưu tiên từ cao xuống: `decisions/` (câu trả lời của người, `DC-NN`) > `project/conventions.md` (`PC-NN`) > `knowledge/conventions.md` (bản chép quy ước cá nhân, `KC-NN`). `thanhtan conventions` (và tool MCP `conventions`) gộp chúng; một quy ước thay quy ước khác khi ghi `overrides: <mã>` và nguồn của nó ưu tiên cao hơn. Quy ước của người (DC, KC) có hiệu lực ngay; quy ước của dự án chỉ được kiểm sau khi người `project confirm`.

**Ba cách kiểm** (`check:` là tập đóng):
- `plan`: hiện có hai luật, `item-order` và `layer-order`. `layer-order` đọc `layers: a, b, c` (thứ tự các lớp, ít nhất hai, không trùng) và tùy chọn `scope: glob, glob`: mặc định luật xét **toàn bộ kế hoạch**, mục lớp sau không được đứng trước mục lớp trước; có `scope` thì chỉ xét các mục có file khớp (và các mục phải ghi `files`). Mục trong phạm vi phải có `layer:` thuộc danh sách. `decide --answer ... --rule layer-order --layers "..." [--scope "..."]` tạo quy ước này. `item-order`: Mục kế hoạch có thêm `kind: interface|implement|other`; mục `interface` phải đứng trước mục `implement` đụng cùng file. Khi quy ước này đang hiệu lực, `kind` là bắt buộc, và mục interface/implement phải có `files`.
- `semgrep`: `rule: <file>.yaml` là rule do **người** viết, để trong `.ThanhTan/knowledge/semgrep/` (người chép từ kho cá nhân bằng `knowledge pull semgrep/<file>`). Chạy cùng scan ở bước `security` như một tool riêng `semgrep-conventions` (container riêng, mount chỉ đọc, không mạng); rule chỉ chặn khi `severity` là ERROR/HIGH/CRITICAL. Thiếu hoặc hỏng file rule là lỗi cứng, không bỏ qua im lặng. Không dùng rule của Semgrep Registry ở đây.
- `review`: gate `conventions-reviewed` đòi báo cáo review có `PC-01: đạt` hoặc `vi phạm PC-01 ở file:dòng` cho **từng** quy ước hiệu lực; có vi phạm thì không cho `pass` (phải `fail` để implementer sửa).

**Câu hỏi.** Planner không đoán: mục `## Chưa có quy ước` trong plan có `### Q1 - ...` (`- ask:`, `- options:`, `- needed-by:`). Gate `plan-valid` chặn tới khi người chạy `thanhtan decide --answer Q1 --text "..." --check <loại>`; câu trả lời thành quy ước `DC-NN` (`decisions/<task>-answer-Q1.md`). Câu hỏi `S1` của scout (tài liệu và code mâu thuẫn) trả lời cùng lệnh, file `decisions/project-answer-S1.md`.

**Kho cá nhân** nằm ngoài mọi repo: đường dẫn ở `~/.ThanhTan/user.yaml` (`knowledge_dir`, mặc định `~/knowledge`; `THANHTAN_HOME` đổi thư mục `~/.ThanhTan`). Khung gồm `index.md`, `conventions.md`, `sources.md`, `lessons/`, `patterns/`, `semgrep/`. Chỉ người chạy `knowledge init/pull/push` (guard từ chối khi agent chạy) và agent không bao giờ ghi vào kho; tool MCP `knowledge_*` chỉ đọc bản chép trong `.ThanhTan/knowledge/`.

**Bài học.** Cuối báo cáo review, reviewer có thể thêm `## Bài học đề xuất` (`### L1 - tiêu đề`). Khi seal, `thanhtan` tách thành `tasks/<task>/lessons/L<n>.md`, liệt kê trong `summary.md`; người chọn bài nào đưa về kho bằng `thanhtan knowledge push <file>`.

**Lệch hồ sơ (drift).** Khi thay đổi làm `profile`, `mission`, `architecture`, `conventions` hoặc `roadmap` sai, reviewer ghi mục `## Đề xuất cập nhật hồ sơ` trong báo cáo review: `không có`, hoặc mỗi tài liệu một dòng `- <tài liệu>: <đề xuất>`. Gate `drift-reviewed` (bước `review`) chỉ kiểm **hình thức**: mục có đúng một lần (heading cấp 2, ngoài khối code và chú thích HTML), không rỗng, mỗi dòng đúng khuôn với tên tài liệu hợp lệ, không vừa `không có` vừa liệt kê. Gate không kiểm đề xuất có đúng không và không sửa hồ sơ: tính đúng do người kiểm ở checklist Review, và reviewer không bao giờ ghi vào hồ sơ. Tiêu đề và tên tài liệu là hằng `DRIFT_HEADING`, `DriftDoc` trong `constants.py`; `tools/test_reviewer_drift.py` giữ prompt, schema và tài liệu khớp với chúng.

### Kế hoạch, gate và tag duyệt

- Mục kế hoạch còn có `tier:` (`fast` hoặc `deep`, thiếu là `deep`; `plan check` từ chối giá trị khác) và `layer:` (xem `layer-order`). Foundation chỉ biết hai trường này và giá trị hợp lệ của `tier`; việc role nào chia tier do `tiered_roles` của workflow quyết định.
- Mỗi mục kế hoạch là một khối `### C1 - tiêu đề` kèm `role:`, `files:`, `done-when:`, `docs:` (xem README). `plan check` đòi mã duy nhất, role thuộc bộ role hợp lệ (role của workflow cộng role extension đăng ký), `done-when` không rỗng, `docs` là link hoặc `không có — <lý do>`.
- **Test trước.** Gate `test-spec-valid` (bước `test-spec`) đọc báo cáo (mỗi mục kế hoạch một khối `tests`/`command`/`red: fail`/`reason`/`output`, hoặc `không có — <cách kiểm>`), kiểm file test có thật, trong dự án, đã commit; lệnh phải nhắc tới một file test của mục; rồi **tự chạy** từng lệnh (một lần cho mỗi lệnh khác nhau, từ gốc dự án, qua bộ chạy chung `thanhtan.testrun`) và đòi mã thoát khác 0 (không phải 126/127, không quá giờ). Kết quả ở `tasks/<task>/verify-red.json`. Gate `tests-pass` (bước `test`) chạy lệnh test của dự án (setting `test_command`, hoặc dòng `- test-command:` của `profile.md` đã xác nhận; timeout `test_timeout_minutes`, mặc định 15 phút) **và chạy lại** các lệnh của báo cáo `test-spec` đã duyệt, đối chiếu với `verify-red.json`; tất cả phải thoát 0. Kết quả ở `tasks/<task>/tests-pass.json` (lệnh dự án, và `spec_results` cho từng mục). Thiếu lệnh test thì chặn, trừ khi mọi mục kế hoạch là `kind: other` (cảnh báo, `skipped`). Giới hạn: máy chỉ biết lệnh đỏ hay xanh và có nhắc tới tên file test, không biết nó đỏ vì **lý do** đúng hay lệnh có thực sự chạy các test đó; lý do và lệnh do người đọc ở checklist. Dòng `exit` ở checklist là của thanhtan, `output` trong báo cáo là của tester.
- Gate `plan-valid` gắn vào bước `plan` trong `workflow.yaml`: `task advance --result pass` bị từ chối (mã `GATE_FAILED`) nếu báo cáo plan không qua kiểm tra. Gate chỉ áp dụng cho kết quả `pass`.
- Khi task chuyển sang `done` (duyệt bước cuối, hoặc bước cuối pass mà không cần duyệt), `thanhtan` ghi `tasks/<task>/summary.md` rồi tạo annotated tag `thanhtan/<task>/approved` ở commit cuối của nhánh task, **trước** khi lưu state: nếu việc đó lỗi thì task không bị đánh dấu xong. `task new` từ chối khi task `done` gần nhất thiếu tag.
### Scan

- Mỗi tool chạy trong container với image ghim phiên bản, repo mount **chỉ đọc**, kết quả lấy từ stdout và do `thanhtan` ghi vào `.ThanhTan/tasks/<task>/scans/` (`<tool>.json` và `summary.json` có sha commit đã quét). Engine container không chạy là lỗi cứng, không bao giờ tính là "sạch".
- **Semgrep** (`semgrep/semgrep:1.180.0`, `--network none`): chỉ quét các file task đã đổi so với nhánh gốc; chặn khi mức `ERROR`. Rule tải lúc chạy từ Semgrep Registry vào cache của người dùng (ngoài repo; xem `docs/scan-notes.md`) vì giấy phép không cho phân phối lại.
- **Trivy** (`aquasec/trivy:0.75.0`, `fs --scanners vuln`, volume cache `thanhtan-trivy-cache` cho DB): chặn khi `HIGH`/`CRITICAL` **đã có bản vá** (`FixedVersion`).
- **Gitleaks** (`v8.24.0`): quét các commit của task (`base..HEAD`); bất kỳ phát hiện nào cũng chặn.
- Gate `scans-clean` gắn vào bước `security`: `advance --result pass` bị từ chối nếu thiếu kết quả, kết quả cũ (HEAD đã đổi) hoặc còn phát hiện chặn chưa được bỏ qua.
- Báo nhầm chỉ được bỏ qua bằng file trong `decisions/` do `thanhtan decide --suppress` tạo; lệnh này chỉ người chạy được (hook từ chối khi agent tự chạy). Agent không có đường nào hạ mức. Hook chặn mọi tool ghi file vào `.ThanhTan/` (xem mục "Bảo vệ workspace"), nên agent không tự tạo được file trong `decisions/` bằng tool của CLI.
- Cấu hình bộ rule Semgrep bằng khóa `scan.semgrep.rulesets` (mặc định `p/default`).

- Hook Stop chỉ nhắc khi bước đang `in_progress` và đã có báo cáo của bước ghi sau lúc bước bắt đầu.

Mã lỗi nằm trong `ExitCode` (`foundation/src/thanhtan/constants.py`).
