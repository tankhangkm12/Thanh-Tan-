# Hướng dẫn dùng nhóm software-dev

Tài liệu này nói về **quy trình và môi trường làm việc**: cài gì, chuẩn bị gì, viết yêu cầu task thế nào, duyệt ra sao, tiết kiệm token thế nào. Nó không nói về quy ước code, kiến trúc hay stack của dự án: những thứ đó nằm trong `.agentflow/project/` và do bạn xác nhận (xem [Chuẩn bị một lần cho mỗi dự án](#chuẩn-bị-một-lần-cho-mỗi-dự-án)).

Mục lục: [chọn plugin](#chọn-plugin-theo-loại-dự-án) · [chuẩn bị](#chuẩn-bị-một-lần-cho-mỗi-dự-án) · [khuôn yêu cầu task](#khuôn-yêu-cầu-task) · [chọn chế độ](#chọn-chế-độ) · [checklist khi duyệt](#checklist-khi-duyệt) · [lệnh của người](#lệnh-của-người) · [tiết kiệm token](#tiết-kiệm-token) · [xử lý tình huống](#xử-lý-tình-huống).

Cài đặt `agentflow` và plugin: xem [README gốc](../../README.md#cài-đặt-từng-bước). Mỗi plugin con có mục "Dùng cùng dev-core" trong README của nó, nói riêng dữ liệu cần thêm và ví dụ done-when cho gate của plugin đó; khuôn yêu cầu task chỉ có một, ở đây.

## Chọn plugin theo loại dự án

`dev-core` luôn có: nó giữ quy trình, hook an toàn và scan. Plugin con chỉ thêm nghiệp vụ riêng.

| Loại dự án | Cài | Ghi chú |
|---|---|---|
| Backend | `dev-core` + `dev-backend` | Dùng được. Xem [dev-backend](backend/README.md) |
| Mobile | `dev-core` + gói Google | **Chưa hỗ trợ Antigravity IDE**; đang chờ một mốc riêng. Chưa có hướng dẫn ở đây |
| Web | `dev-core` + `dev-frontend` | Khi plugin có nội dung. Hiện còn là khung |
| Hạ tầng | `dev-core` + `dev-infra` | Khi plugin có nội dung. Hiện còn là khung |

`dev-design` (thiết kế giao diện và hệ thống) cũng còn là khung.

## Chuẩn bị một lần cho mỗi dự án

Dự án phải là repo git có nhánh `main` và `develop`, cây làm việc sạch.

1. **Khởi tạo workspace.** Trong thư mục dự án:

   ```
   agentflow init --workflow "<repo>/families/software-dev/core/workflow.yaml"
   ```

2. **Đăng ký plugin con và đặt cài đặt (chỉ khi dùng dev-backend).** Đây là việc của bạn, agent không chạy được. Đặt các cài đặt `backend.*` **trước khi tạo task đầu tiên**; danh sách đầy đủ và ý nghĩa nằm trong [dev-backend](backend/README.md#dùng-với-một-dự-án).

   ```
   agentflow ext add "<repo>/families/software-dev/backend/extension.yaml"
   agentflow config set backend.test_command "<lệnh chạy test>"
   agentflow config check
   ```

3. **Hồ sơ hóa dự án.** Gõ `/dev-core:setup` (Antigravity: nhờ agent dùng skill `setup`). Skill hỏi bạn đường dẫn tài liệu rồi giao cho scout; scout chỉ đọc đúng các đường dẫn đó và code của dự án. Nên đưa cho scout:
   - tài liệu yêu cầu, tầm nhìn và phạm vi sản phẩm (scout lấy **mission** từ đây, không suy từ code);
   - backlog, TODO hoặc danh sách việc cần làm có sẵn (scout lấy **roadmap** từ đây và từ chú thích `TODO`/`FIXME` trong code);
   - ghi chú kiến trúc, ADR;
   - hướng dẫn đóng góp, hướng dẫn chạy build và test;
   - README, wiki export;
   - contract API hoặc thiết kế nếu có.

   Không có tài liệu nào thì nói "không có": scout làm việc từ code.

4. **Duyệt hồ sơ và xác nhận.** Mở các file `profile` (có mục `## Mission`), `architecture`, `sources`, `conventions` và `roadmap.md` trong `.agentflow/project/`. Mỗi câu hỏi mở `S1`, `S2`, ... (chỗ tài liệu và code mâu thuẫn) do bạn quyết, rồi xác nhận quy ước bạn đồng ý:

   ```
   agentflow decide --answer S1 --text "<quy ước, một dòng>" --check review
   agentflow project confirm PC-01 PC-02
   agentflow project confirm mission
   agentflow project confirm R1 R2 R3
   agentflow project status
   ```

   - **Mission** (vì sao, cho ai, phạm vi, ngoài phạm vi, nguồn) nằm ở mục `## Mission` của `profile.md`. Roadmap (`roadmap.md`) là danh sách mục `R1`, `R2`, ... theo thứ tự ưu tiên, mỗi mục có `goal`, `docs` và trạng thái `todo|doing|done|dropped`. Scout chỉ đề xuất; mission và từng mục chỉ có hiệu lực khi **bạn** `project confirm`. Scout (hay bất kỳ agent nào) ghi lại tài liệu đã xác nhận mà nội dung đổi thì nó về `unconfirmed`; ghi lại đúng văn bản đã xác nhận thì vẫn `confirmed`.
   - `agentflow project status` (chỉ đọc) cho biết `mission`, `profile`, `architecture`, `conventions`, `roadmap` đang `missing`, `unconfirmed` hay `confirmed`, và các dòng `removed: R4 (confirmed)` cho mục roadmap **đã xác nhận mà agent bỏ khỏi roadmap** (bản trước nằm trong `.agentflow/project/history/`). `--all` của `project confirm` chỉ xác nhận mọi quy ước, không đụng mission hay roadmap.
   - Trạng thái của mục roadmap là việc của bạn: `agentflow roadmap set R4 dropped`. Xem danh sách: `agentflow roadmap list`.

   Quy ước chưa xác nhận chỉ là gợi ý cho agent, chưa được kiểm. `agentflow task new` cảnh báo (không chặn) khi còn quy ước, mission hoặc mục roadmap chưa xác nhận, khi dự án chưa có roadmap, và khi task không gắn với mục nào.

5. **Khối permissions của Claude Code.** Bắt buộc, gồm cả quy tắc `ask` cho `task approve`, `task cancel`, `decide`. Nội dung ở [README gốc, Bước 4](../../README.md#bước-4-bắt-buộc-quy-tắc-permissions-của-claude-code); đừng chép lại vào chỗ khác để khỏi lệch.

6. **Kho kiến thức (tùy chọn).** Bài học và rule Semgrep của riêng bạn nằm ngoài mọi repo. Chép vào dự án file bạn chọn, agent chỉ đọc bản chép:

   ```
   agentflow knowledge init
   agentflow knowledge pull lessons/x.md semgrep/rule.yaml
   ```

## Khuôn yêu cầu task

Khuôn này là đầu vào của bước `confirm`. Gõ `/dev-core:start` (Antigravity: nhờ agent dùng skill `start`), rồi dán khuôn đã điền:

```
Loại: feature | bugfix | hotfix | refactor | chore        Cỡ: normal | small
Mục tiêu: <làm gì, cho ai, 1–2 câu>
Xong khi: <tiêu chí kiểm được>
Trong phạm vi: <phần được đụng>
Ngoài phạm vi: <không làm gì>
Tài liệu: <link spec / màn hình thiết kế / contract API, hoặc "không có">
Roadmap: <mục Rn trong `agentflow roadmap list`, hoặc "không có">
```

Dòng `Roadmap` được truyền cho `agentflow task new --roadmap Rn`: mục chuyển sang `doing`. Task xong **không tự** đóng mục roadmap (một mục có thể cần nhiều task): `done` do bạn quyết, hiện bằng `agentflow roadmap set Rn done`. Mục nào bỏ trống thì orchestrator hỏi lại ở bước `confirm`, trước khi bạn duyệt. Điền càng cụ thể, `done-when` của kế hoạch càng chặt.

### Không cần viết trong prompt

| Thông tin | Agent lấy ở đâu |
|---|---|
| Kiến trúc, stack, lệnh build và lệnh test | `.agentflow/project/` (do scout viết, bạn xác nhận) |
| Quy ước | `agentflow conventions` (gộp từ `decisions/`, hồ sơ dự án và kho cá nhân) |
| Bài học từ task trước | Kho kiến thức, bản đã `knowledge pull` vào `.agentflow/knowledge/` |
| Quy trình, các bước, việc agent không được làm | Skill và hook của `dev-core` |

### Ví dụ điền sẵn

Feature (cỡ normal):

```
Loại: feature        Cỡ: normal
Mục tiêu: Cho người dùng đã đăng nhập tải về lịch sử đơn hàng của chính mình.
Xong khi: `<lệnh test của dự án>` xanh; có test cho trường hợp lịch sử rỗng; người dùng khác không lấy được dữ liệu của mình.
Trong phạm vi: màn hình lịch sử đơn hàng và phần xử lý phía sau nó.
Ngoài phạm vi: đổi định dạng dữ liệu hiện có; các loại báo cáo khác.
Tài liệu: <link spec yêu cầu tải lịch sử đơn hàng>
Roadmap: <Rn của mục "người dùng xem lại đơn hàng">
```

Bugfix:

```
Loại: bugfix        Cỡ: normal
Mục tiêu: Danh sách đơn hàng bị lặp dòng khi lọc theo khoảng ngày.
Xong khi: có test tái hiện lỗi, đỏ trước khi sửa và xanh sau khi sửa; `<lệnh test của dự án>` xanh.
Trong phạm vi: phần lọc theo ngày của danh sách đơn hàng.
Ngoài phạm vi: giao diện danh sách; các bộ lọc khác.
Tài liệu: không có
Roadmap: không có
```

Task small:

```
Loại: bugfix        Cỡ: small
Mục tiêu: Sửa câu thông báo lỗi sai chính tả ở màn hình đăng nhập.
Xong khi: thông báo hiển thị đúng chính tả; `<lệnh test của dự án>` xanh.
Trong phạm vi: chỉ chuỗi thông báo đó.
Ngoài phạm vi: mọi thông báo khác.
Tài liệu: không có
Roadmap: không có
```

## Chọn chế độ

**Cỡ task: `small` hay `normal`.** Chọn `small` cho thay đổi nhỏ, rõ ràng, vừa trong tối đa 3 mục kế hoạch. Task `small` bỏ duyệt ở bước `plan` (`agentflow plan check` vẫn chạy và chặn), nhưng vẫn cần bạn duyệt ở `confirm` và `review`; bước `security` chỉ chạy Gitleaks và Semgrep, không chạy Trivy. Không chắc thì chọn `normal`. Kế hoạch dài hơn 3 mục thì bắt đầu lại bằng `normal`. Chi tiết: [README gốc](../../README.md#chế-độ-nhẹ-task-nhỏ).

**Tier của mục kế hoạch: `fast` hay `deep`.** Planner đề xuất tier cho từng mục; bạn sửa trực tiếp trong báo cáo plan khi duyệt, hoặc nhờ planner sửa. Mục thiếu `tier` được coi là `deep`.

| | fast | deep |
|---|---|---|
| Claude Code | `model: sonnet`, `effort: low` | `model: sonnet`, `effort: high` |
| Antigravity | `model: flash` | `model: pro` |

Trên Claude Code cả hai tier đều là Sonnet, khác nhau ở effort (`low` và `high`); role `db-engineer` của dev-backend cũng là Sonnet `high`. Muốn dùng Opus cho mục khó, đổi dòng `claude` của `deep` thành `claude: {model: opus, effort: medium}` theo [README gốc](../../README.md#tier-và-thứ-tự-lớp) (nguồn role `families/software-dev/core/src/roles/implementer.md`, khối `variants`), chạy `uv run tools/build.py`, rồi cài lại plugin; Opus tốn giới hạn sử dụng hơn. Antigravity không có trường effort.

**Model và effort của phiên Claude Code.** Đây là phiên của bạn (cho skill, orchestrator và các bước đọc), tách khỏi model cố định trong từng agent. Gợi ý: đặt Sonnet (`/model`) với effort `high` (`/effort high`) khi lập kế hoạch, rồi hạ xuống `/effort medium` khi chạy các bước còn lại. Trang [chi phí](https://code.claude.com/docs/en/costs) của Claude Code khuyên giữ Opus cho việc phức tạp và hạ effort cho việc đơn giản. Đổi effort giữa phiên có thể hiện cảnh báo về prompt cache.

**Claude Code hay Antigravity CLI.**

| | Claude Code | Antigravity CLI |
|---|---|---|
| Bắt đầu task | `/dev-core:start` | nhờ agent dùng skill `start` |
| Quy tắc permissions | khối `allow`/`ask` ở README gốc | dùng chế độ phê duyệt lệnh của chính CLI |
| Lệnh của người | tiền tố `!` | terminal riêng |
| Effort | có (`/effort`) | không có |
| Xem hạn mức | `/usage` | `/usage` |

Hai CLI cùng chạy một quy trình; hook, skill và agent của `dev-core` có ở cả hai.

## Checklist khi duyệt

Ba chỗ cần bạn duyệt: `confirm`, `plan`, `review`. Duyệt bằng `/dev-core:approve` hoặc `agentflow task approve`. Đọc báo cáo của bước ở `.agentflow/tasks/<task>/reports/<bước>.md` trước khi duyệt.

<!-- BEGIN:checklists -->

**Confirm — Xác nhận task** (`confirm`)
- [ ] Phần "Mục tiêu" được nhắc lại đúng ý bạn.
- [ ] Phạm vi và ngoài phạm vi khớp những gì bạn viết, không thêm, không bớt.
- [ ] Tiêu chí "Xong khi" kiểm được bằng lệnh hoặc quan sát cụ thể.
- [ ] Mọi câu hỏi mở đã được bạn trả lời, không để agent đoán.
- [ ] Mục `## Tài liệu` liệt kê đúng các tài liệu task làm theo (đường dẫn trong dự án hoặc link), hoặc `không có`.

**Plan — Vào workspace và lập kế hoạch** (`plan`)
- [ ] Mỗi mục có `done-when` là lệnh hoặc sự kiện kiểm được, không phải lời mô tả mơ hồ.
- [ ] Các mục đủ nhỏ để kiểm từng mục; không mục nào "làm hết".
- [ ] `tier` hợp lý: phần khó và nhạy cảm là `deep`, phần quen thuộc là `fast`.
- [ ] Mục `docs` có link tài liệu chính thức, hoặc `không có — <lý do>` mà bạn chấp nhận.
- [ ] Mục `files` không vượt phạm vi đã duyệt ở `confirm`.
- [ ] Mục `## Chưa có quy ước` (nếu có) đã được bạn trả lời bằng `agentflow decide --answer Q1 ...`.
- Thêm tự động: một ô `C<n>` cho mỗi mục của kế hoạch (`plan-items`).

**Test-spec — Viết test trước** (`test-spec`)
- [ ] Mỗi mục kế hoạch có test, hoặc `không có — <cách kiểm>` mà bạn chấp nhận (không ép viết test cho việc không test tự động được).
- [ ] Các test đo đúng `done-when` của mục, không phải thứ dễ qua hơn.
- [ ] Task feature, bugfix, hotfix: mỗi test đỏ vì đúng lý do (tính năng chưa có, không phải lỗi cú pháp, thiếu import hay môi trường). Task refactor, chore: mỗi test xanh trên code hiện tại và chốt đúng hành vi phải giữ. Đọc `reason` và `output` trong báo cáo.
- [ ] Lệnh của mỗi mục chạy đúng các test đã khai, không phải lệnh chạy cho có (như `false`); agentflow đã tự chạy lại và ghi `exit` ở dòng dưới.
- [ ] Các dòng L (danh sách file sẽ khóa) là đủ: file test, file hạ tầng test (conftest.py, cấu hình pytest/jest/vitest, script chạy test) và phần cấu hình test của pyproject.toml, setup.cfg, package.json. Sau khi bạn duyệt, không agent nào sửa được chúng; muốn đổi phải chạy `agentflow tests amend <file> --reason "..."`.
- Thêm tự động: một ô `C<n>` cho mỗi mục kế hoạch, kèm test, lệnh và kết quả agentflow tự chạy lại (`spec-items`).
- Thêm tự động: một ô `L<n>` cho mỗi file sẽ bị khóa khi bạn duyệt: file test, file hạ tầng test, cấu hình test (`locked-files`).

**Review — những gì bạn kiểm** (`review`)
- [ ] Mục "must fix" đã xử lý hoặc có lý do rõ ràng.
- [ ] Mục `## Đề xuất cập nhật hồ sơ` đúng và đủ, hoặc `không có` là đúng. Gate `drift-reviewed` chỉ kiểm hình thức, phần đúng sai do bạn kiểm; reviewer chỉ đề xuất, đề xuất nào bạn đồng ý thì bạn tự cập nhật hồ sơ (hoặc nhờ scout ghi lại rồi xác nhận).
- [ ] Thay đổi đúng kế hoạch đã duyệt, không có việc ngoài phạm vi.
- [ ] `summary.md` và kết quả scan (`.agentflow/tasks/<task>/scans/`) không còn phát hiện chặn nào chưa giải thích.
- [ ] "Bài học đề xuất" đáng giữ thì đưa về kho: `agentflow knowledge push .agentflow/tasks/<task>/lessons/L1.md`.
- Thêm tự động: một ô `Y<n>` cho mỗi yêu cầu của bước `confirm`, review phải ghi `Y<n>: đạt` hoặc `Y<n>: chưa đạt` (`review-requirements`).
- Thêm tự động: một ô `PC-xx` cho mỗi quy ước `check: review` đang hiệu lực (`review-conventions`).
- Thêm tự động: một ô `TL<n>` cho mỗi tài liệu ở mục `## Tài liệu` đã đổi từ lúc bạn duyệt `confirm` (`changed-docs`); không đổi thì không có ô.
- Thêm tự động: một ô `D<n>` cho mỗi đề xuất ở mục `## Đề xuất cập nhật hồ sơ` (`drift-proposals`).

<!-- END:checklists -->

### Cách tick

Khi một bước chuyển sang `awaiting_approval`, agentflow ghi file `.agentflow/tasks/<task>/approve-<bước>.md` và in đường dẫn của nó. Mở file, đọc báo cáo của bước, rồi ghi `x` vào từng ô bắt buộc (`- [x]`). Danh sách trên đây là các câu cố định (một nguồn duy nhất: `core/workflow.yaml`); agentflow thêm ô cho mục kế hoạch, quy ước và đề xuất cập nhật hồ sơ từ báo cáo.

- Đừng thêm, xóa hay sửa chữ của một dòng: `agentflow task approve` từ chối khi khung của file khác với bản agentflow đã ghi. Đầu file cũng không được sửa.
- Mục `## Ghi chú của bạn` (cuối file) để bạn viết điều cần nhớ; nếu có chữ, agentflow lưu nó cùng bản sao checklist vào `.agentflow/decisions/<task>-<bước>-approval.md` khi duyệt.
- Bước cuối của task có `--roadmap Rn` có thêm một ô tùy chọn ghi `(tùy chọn) roadmap: Mục Rn đã hoàn thành?`. Tick thì lúc duyệt mục chuyển sang `done`; để trống thì duyệt vẫn được và mục giữ `doing`.
- Bước bị đưa về làm lại rồi tới lượt duyệt lần nữa thì file cũ được giữ thành `approve-<bước>.<n>.md` và một file mới (mọi ô để trống) được ghi.
- Chỉ bạn tick. Agent không tick, không sửa file; hook chặn ghi vào `.agentflow/` và ghi nhật ký `audit.jsonl` các lệnh chạm tới file này (xem "Mô hình bảo vệ duyệt" ở `docs/architecture.md`).

## Test trước (test-spec)

Sau khi duyệt plan, bước `test-spec` do `tester` làm: viết test cho `done-when` của từng mục **trước khi có code**, commit chúng, và chứng minh chúng đỏ. Bước này luôn cần bạn duyệt, kể cả task `small`. Quy trình: `confirm → plan → test-spec → implement → test → security → review`.

Báo cáo `test-spec` có một khối cho mỗi mục kế hoạch:

```
### C1 - Tiêu đề mục
- tests: tests/test_greeting.py::test_says_hello, tests/test_greeting.py::test_says_name
- command: `uv run pytest tests/test_greeting.py`
- red: fail
- reason: greeting() chưa có nên mọi test đỏ vì thiếu hàm
- output: |
    FAILED tests/test_greeting.py::test_says_hello - ImportError: cannot import name 'greeting'
```

Việc không test tự động được (tài liệu, nối dây, kiểm tay) thì ghi `- tests: không có — <cách kiểm>`; lý do là bắt buộc, không ép viết test. Planner đặt `kind: other` và viết cách kiểm vào `done-when` cho mục kiểu đó.

**agentflow không tin báo cáo.** Lúc `task advance --result pass`, agentflow tự chạy lại lệnh của từng mục và chỉ cho qua khi nó đỏ (mã thoát khác 0; lệnh không tìm thấy hoặc quá giờ không tính là đỏ). `output` trong báo cáo chỉ để bạn đọc. Lệnh phải nhắc tới ít nhất một file test đã khai của chính mục đó (lệnh `false` hay `exit 1` bị từ chối); cổng chỉ biết được tới đó, nên bạn đọc lệnh ở checklist để chắc nó chạy đúng các test. File test phải có thật, nằm trong dự án và đã commit. Kết quả agentflow ghi ở `.agentflow/tasks/<task>/verify-red.json`; `agentflow tests verify-red` làm đúng việc đó theo yêu cầu (không đổi bước).

Checklist duyệt `test-spec` có một ô cho mỗi mục, kèm lệnh và `exit` agentflow đã thấy (khối checklist ở trên). Đọc lý do đỏ: máy chỉ biết lệnh đỏ, chỉ bạn biết nó đỏ vì đúng lý do.

**Cổng `tests-pass` ở bước `test`.** Khi `test` chuyển `pass`, agentflow tự chạy lệnh test của dự án **và** chạy lại đúng các lệnh của `verify-red.json` (đỏ trước, xanh sau); tất cả phải thoát 0, bất kể agent báo gì. Kết quả ghi ở `.agentflow/tasks/<task>/tests-pass.json` (lệnh dự án và `spec_results` cho từng mục).
- Lệnh test của dự án: setting `agentflow config set test_command "<lệnh>"` (người chạy, ưu tiên), hoặc dòng `- test-command: <lệnh>` trong `profile.md` **đã xác nhận** (`agentflow project confirm profile`; sửa profile sau đó thì phải xác nhận lại).
- Giới hạn thời gian: 15 phút, đổi bằng `agentflow config set test_timeout_minutes <số phút>`.
- Chưa có lệnh test: bước `test` bị chặn kèm hướng dẫn, trừ task mà mọi mục kế hoạch là `kind: other` (chỉ cảnh báo, ghi `skipped`).

## Khóa test đã duyệt

Khi bạn duyệt `test-spec`, agentflow **khóa** các file mà bài làm sau đó không được sửa, để agent không thể làm test xanh bằng cách đổi test. Nó ghi `.agentflow/tasks/<task>/locked-files.json` với sha256 của từng file; hash của chính file đó nằm trong `integrity.json` (`locked_files_sha256`), nên sửa tay hay xóa nó bị phát hiện (mã 37, như `state.json`).

**Khóa những file nào** (checklist `test-spec` liệt kê chúng thành các dòng `L1`, `L2`...; bạn tick như các ô khác):
- file test nêu trong các dòng `- tests:` của báo cáo (khóa nguyên file);
- file hạ tầng test tester khai ở mục `## Hạ tầng test` cuối báo cáo (`- <đường dẫn>` mỗi dòng, hoặc `không có`): fixture, helper test import, `Makefile` hay script mà lệnh test đi qua...;
- file cấu hình test có sẵn trong dự án theo tên: `conftest.py` ở mọi thư mục, `pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`, `.mocharc.*`... (khóa nguyên file);
- `pyproject.toml`, `setup.cfg`, `package.json` chỉ khóa **phần cấu hình test** của chúng: các bảng `[tool.pytest...]`, mục `[tool:pytest]`, khóa `jest`/`vitest`/`mocha` và `scripts.test` (hash theo phần, không theo chữ). Sửa phần khác (dependency, version, script build...) thì không cần amend.

Tester được tạo hay sửa cấu hình test ở chính bước `test-spec`, trước khi khóa; xong bước thì không ai tạo mới (tạo thêm `conftest.py`, `pytest.ini`... để bỏ qua test) hay sửa chúng nữa. Khóa áp cho **mọi role** và cả hai CLI, từ lúc duyệt tới khi task xong hoặc bị hủy (`blocked` vẫn giữ).

**Ba lớp.**
1. Hook `pre-tool` từ chối tool file và lệnh shell ghi, xóa, đổi tên, copy đè file khóa (`Write`, `Edit`, `sed -i`, `>`, `tee`, `cp`, `mv`, `rm`, `Set-Content`...), `git rm`/`git mv`, `git checkout|restore` lấy file từ commit khác, và tạo mới file cấu hình test. Lý do từ chối nêu `agentflow tests amend`.
2. `agentflow commit` từ chối commit đụng file khóa (sửa, xóa, đổi tên) hoặc thêm file cấu hình test mới; cả commit bị từ chối.
3. Cổng `locked-files-intact` ở các bước `implement`, `test`, `security`, `review`, và cổng `tests-pass` **trước khi chạy bất cứ lệnh nào**, so hash ở cả cây làm việc lẫn HEAD: file bị đổi, mất, đổi tên, hay file cấu hình test mới xuất hiện (kể cả `pyproject.toml` hoặc `setup.cfg` mới có thêm cấu hình pytest) đều làm bước fail, nêu từng file. `agentflow tests check` (chỉ đọc) làm đúng việc đó theo yêu cầu; tester chạy nó trước khi chạy test. Lớp 3 bắt cả những gì hook không thấy.

Ngoài ra `config.yaml` giữ lệnh test (`test_command`): sửa tay (không qua `agentflow config set`) bị báo mã 37, và agentflow bỏ `PYTEST_ADDOPTS`, `PYTEST_PLUGINS` khỏi môi trường khi tự chạy test. Duyệt `test-spec` cũng bị từ chối nếu một file đã đổi sau lúc agentflow chạy đỏ (`verify-red.json` giữ hash từng file).

### Đổi một test đã duyệt

Chỉ bạn làm được, và nó để lại dấu vết:
1. `agentflow tests amend <file>... --reason "<vì sao>"` mở một **cửa sổ** cho đúng những file đó (ghi vào `locked-files.json` và `decisions/<thời điểm>-tests-amend.md` kèm hash cũ). File cấu hình test chưa tồn tại cũng mở được bằng lệnh này. Hook cho phép sửa các file ấy, chỉ chúng.
2. Sửa file (bạn hoặc agent theo lời bạn), `git add`, rồi `agentflow commit "..."`. Commit file đó đóng cửa sổ: khóa nhận hash mới, `decisions/` ghi thêm hash mới và commit.
3. Trước khi commit, agentflow chạy lại lệnh của các mục dùng file đó (file hạ tầng hoặc phần cấu hình thì mọi mục có lệnh) trong một checkout tạm của commit lúc chạy đỏ, tức **mã cũ**, rồi ghi kết quả vào `verify-red.json` (`reverified`). Test đã sửa mà **xanh trên mã cũ** thì không còn chứng minh được gì: commit bị **chặn** (không có gì được commit, cửa sổ vẫn mở). Nếu đó đúng là ý bạn (ví dụ tính năng đã có sẵn), mở cửa sổ bằng `agentflow tests amend <file> --accept-green --reason "<lý do>"`: commit đi qua, lý do và kết quả xanh được ghi vào `decisions/`, và lệnh vẫn in cảnh báo.
Cửa sổ không bỏ qua việc hash khác: file sửa mà chưa commit thì `tests check` vẫn báo.

### Giới hạn của khóa test

Đây là lưới an toàn, **không phải sandbox**; nó không biến việc đổi test thành không thể.
- Hook chỉ đọc một danh sách lệnh cố định. `python -c`, `node -e`, `perl -pi`, `patch`, `git apply`, script agent tự viết, hard link... ghi được file mà hook không thấy; chúng chỉ bị cổng hash phát hiện (ở bước kế tiếp, không phải lúc ghi). Trên Windows gốc không có sandbox của Claude Code, nên không có lớp chặn cứng nào ở mức hệ điều hành.
- `Makefile`, `package.json` (ngoài phần test của nó), `tox.ini` mà lệnh test đi qua chỉ được khóa khi tester khai chúng ở `## Hạ tầng test`; file helper mà test import cũng vậy. Bạn đọc mục này ở checklist: máy không biết lệnh test đi qua file nào. Ngôn ngữ test agentflow không nhận ra (không phải py, js, ts...) cho cảnh báo nhắc tester khai đủ.
- Agent chạy được mã tùy ý cùng quyền người dùng vẫn có thể tính lại hash và sửa `locked-files.json`; hash là tripwire, không phải ổ khóa. Chặn cứng cần sandbox hay quyền hệ điều hành. Đọc `decisions/` và `audit.jsonl` khi nghi ngờ.
- `agentflow tests check` chạy được bất cứ lúc nào để thấy file nào đã lệch.

## Review khi task quay lại sửa

Mục tiêu: sau mỗi vòng sửa, reviewer và security chỉ đọc phần **đã đổi**, không đọc lại phần đã đúng.

- Khi một vòng `security` hoặc `review` kết thúc (đạt hay trả về), agentflow ghi commit nó đã xem vào `tasks/<task>/review-marks.json`. `agentflow scope` (chỉ đọc) cho biết vòng này đọc gì: `scope: whole task` ở vòng đầu, `scope: since <commit>` ở các vòng sau, kèm lệnh `git diff` cần chạy, các commit và số dòng từng file. Mốc không còn trong nhánh (rebase) thì quay về cả task và nói rõ.
- Prompt của `reviewer` và `security` bắt dùng `agentflow scope`. Ở vòng sau reviewer mở báo cáo bằng mục `## Phạm vi`, đóng từng must-fix cũ (`đã sửa ở <commit>` hoặc `còn`) và không nêu lỗi mới ở file ngoài phần đổi trừ khi thay đổi mới làm nó sai. Đây là quy định trong prompt, agentflow không kiểm bằng cổng.
- `agentflow scan` vẫn quét cả task mỗi vòng (chạy bằng máy, không tốn token).
- **Bản đồ review cho bạn:** khi `review` chờ duyệt, agentflow ghi `tasks/<task>/review-map.md` (cũng chạy được bằng `agentflow review-map`): với mỗi mục kế hoạch, các commit, file và số dòng, kết quả lệnh agentflow đã chạy gần nhất, file mục đã đổi mà dòng `files` của nó không liệt kê, commit không gắn mục nào. Dùng nó để biết nên đọc đâu trước. Nó tính từ git, không phải ý kiến của agent.
- `agentflow commit --item Cn` in cảnh báo (không từ chối) cho file đã stage mà dòng `files` của mục không liệt kê.

### Yêu cầu và độ lớn của mục kế hoạch

- Báo cáo `confirm` liệt kê yêu cầu thành các dòng `- Y1: ...` trong mục `## Yêu cầu`. Mỗi mục kế hoạch ghi `covers: Y1, Y2`. `agentflow plan check` (cổng `plan-valid`) từ chối khi có yêu cầu không mục nào phủ hoặc mục phủ mã không có. Báo cáo `confirm` không liệt kê `Y` thì không kiểm. Cổng chỉ kiểm phủ, không kiểm hiểu đúng: bạn vẫn đọc ở checklist.
- Mục kế hoạch tối đa 10 mục trong `files` (thư mục hay glob tính một): lớn hơn thì `plan check` yêu cầu chia nhỏ để diff của từng mục đủ nhỏ để review.
- **Review kết luận từng yêu cầu.** Cổng `requirements-reviewed` (bước `review`) đòi báo cáo review có một dòng cho **mỗi** `Y` của `confirm`: `Y1: đạt ở <file:dòng hoặc cách kiểm>`, hoặc `Y1: chưa đạt — <còn thiếu gì>`. Thiếu dòng thì bước không qua; có `chưa đạt` thì review phải `fail` để implementer làm tiếp. Checklist duyệt `review` có một ô `Y<n>` cho mỗi yêu cầu, kèm văn bản của nó, để bạn đối chiếu. Cổng chỉ kiểm có kết luận, không kiểm kết luận đúng.

### Tài liệu của task (ghim lúc duyệt confirm)

Báo cáo `confirm` có mục `## Tài liệu`: mỗi dòng một đường dẫn trong dự án (file hoặc thư mục) hoặc một link, hoặc `- không có`. Khi bạn duyệt `confirm`, agentflow ghi sha256 của từng đường dẫn vào `tasks/<task>/docs-pinned.json` (thư mục: mọi file bên trong, bỏ qua `.git`, `node_modules`...). Sau đó:

- `agentflow status` cảnh báo tài liệu nào đã đổi, mất, hoặc trước không có mà nay có;
- checklist duyệt `review` có thêm một ô `TL<n>` cho mỗi tài liệu đã đổi: bạn phải tick, tức là xác nhận công việc vẫn đúng với bản tài liệu bạn muốn. Không đổi thì không có ô nào.

Link (`https://...`) được ghi lại nhưng không so được. Muốn agentflow theo dõi thì để tài liệu trong repo (hoặc một thư mục trên máy, ghi đường dẫn tuyệt đối). Task mở trước khi nâng cấp không có bản ghim.

## Replan sau mỗi task

Vòng làm việc: `setup` (một lần) → mission + roadmap → `task new --roadmap Rn` → confirm → plan → test-spec → implement → test → security → review → **replan** → task kế. Replan là bước giữa hai task: cập nhật hồ sơ dự án cho đúng với cái task thật sự đã làm. Nó **chỉ đề xuất**; bạn đọc rồi quyết.

1. Khi task xong, agentflow ghi cạnh `summary.md` một file `spec-delta.md`: đề xuất của reviewer (mục `## Đề xuất cập nhật hồ sơ`), thay đổi thật của task (mục kế hoạch, commit, file đổi do git báo, gom theo thư mục) và liên kết (mục roadmap, mission/profile/architecture đã xác nhận hay chưa). File do agentflow sinh lúc seal nên agent làm việc không sửa được.
2. Gõ `/dev-core:replan` (Antigravity: nhờ agent dùng skill `replan`; cùng thư mục skill). Skill kiểm `agentflow replan status` rồi giao cho scout: scout đọc `summary.md` và `spec-delta.md`, ghi lại các tài liệu không còn đúng bằng `project_write` (chúng thành `unconfirmed`), rồi lưu `replan.md` bằng tool `replan_write` với hai mục `## Mục roadmap đã hoàn thành` (đề xuất `- Rn: <bằng chứng>` hoặc `không có`) và `## Đề xuất cải tiến quy trình` (hoặc `không có`). Lúc này trạng thái là `proposed`; ghi lại thì bản cũ vào `.agentflow/project/history/replan-<task>-<thời điểm>.md`.
3. Bạn đọc `replan.md`, `spec-delta.md` và các tài liệu scout vừa sửa (`agentflow project status` cho biết cái nào `unconfirmed` và dòng `removed:`). Rồi tự chạy: `agentflow project confirm profile architecture ...` cho cái bạn đồng ý, `agentflow roadmap set R1 done` cho mục đã xong (replan **không bao giờ** tự đóng mục), và cuối cùng `agentflow replan done`. Chỉ lúc này task mới được đánh dấu đã replan (`replanned_at` trong `state.json`, `Replan: done (ngày)` trong `summary.md`) và các dòng `removed:` biến mất.
4. Không muốn replan task này: `agentflow replan skip <task> --reason "..."` (ghi vào `decisions/`). Đề xuất về quy trình trong `replan.md` là để bạn xem xét; không có gì tự áp vào workflow.

`agentflow replan status` (chỉ đọc) in `replan: <trạng thái>`: `pending` (chưa có replan), `proposed` (scout đã ghi, chờ bạn), `done`, `skipped`, `task-open` (đang có task mở hoặc `blocked`), `not-sealed` (task xong chưa có tag: `agentflow task seal <id>`), `no-finished-task`. `agentflow task new` cảnh báo (không chặn) khi trạng thái là `pending` hoặc `proposed`.

## Task giữ hành vi (refactor, chore)

Dùng `refactor` khi đổi cấu trúc code mà không đổi việc code làm, `chore` cho việc bảo trì giữ nguyên hành vi (nâng dependency, đổi cấu hình build). Cả hai tạo nhánh từ `develop` (`refactor/T-00x-...`, `chore/T-00x-...`). Loại task được ghi vào `state.json` và hiện ở `agentflow status` (`type: refactor (keeps the behaviour...)`), `STATE.md`, `summary.md`, `agentflow stats`.

Bước `test-spec` làm ngược với task feature:

- tester chọn test đang có cho phần code sắp đổi, và viết thêm test chốt hành vi (characterization) cho chỗ chưa có test, ghi lại đúng việc code đang làm, kể cả chỗ trông lạ;
- mỗi khối ghi `- green: pass` thay cho `- red: fail`; `reason` nói test chốt hành vi gì;
- agentflow **tự chạy** từng lệnh trên code hiện tại và đòi **mã 0** (`verify-red.json` ghi `"mode": "green"`); lệnh đỏ thì bị từ chối;
- bạn duyệt thì các test đó bị **khóa** như mọi test đã duyệt;
- ở bước `test`, cổng `tests-pass` chạy lại đúng các lệnh đó: phải vẫn xanh, cộng lệnh test của dự án.

Đổi một test đã khóa (`agentflow tests amend`) trong task loại này: test sửa xong phải **vẫn xanh trên code cũ**; đỏ trên code cũ nghĩa là hành vi đổi, `agentflow commit` từ chối và bảo bạn làm việc đó bằng task `feature` hoặc `bugfix`. Planner chỉ lập mục đổi cấu trúc hay bảo trì, mỗi mục nhỏ và giữ test xanh; reviewer coi mọi thay đổi hành vi hay tính năng mới trộn vào là must-fix. Workflow khai việc này ở mục `types` (`refactor: {test_spec: green}`).

## Debug

Khi có lỗi mà **chưa rõ nguyên nhân**, đừng mở task bugfix ngay:

1. Gõ `/dev-core:debug` (Antigravity: nhờ agent dùng skill `debug`) và tả triệu chứng: làm gì, ra gì, mong gì, lỗi hay test nào.
2. Agent `debugger` (chỉ đọc và chạy lệnh, không sửa file) tái hiện lỗi, thu hẹp tới nguyên nhân gốc, và lưu một **chẩn đoán** với các mục `## Tái hiện`, `## Nguyên nhân` (kèm `file:dòng`), `## Phạm vi`, `## Hướng sửa`, `## Test tái hiện`. Ngoài task nó thành `D-001`, `D-002`...: xem bằng `agentflow diagnosis list` và `agentflow diagnosis show D-001`.
3. Skill đề nghị mở task `bugfix` từ chẩn đoán: orchestrator lấy nguyên nhân làm yêu cầu, tester viết đúng test tái hiện trước (đỏ), rồi mới sửa.

**Trong task.** Khi task bị `test`, `security` hoặc `review` trả về `implement` **từ vòng thứ 2** (`rework rounds: 2/3` trong `agentflow status`), skill `continue` gọi `debugger` đọc báo cáo fail gần nhất trước, lưu chẩn đoán vào `tasks/<task>/diagnoses/round-<n>.md`, rồi giao implementer sửa đúng nguyên nhân thay vì đoán tiếp. Vòng 1 bỏ qua debugger vì báo cáo fail thường đã đủ. Chẩn đoán không bao giờ đổi trạng thái task.

Lỗi nhỏ đã rõ nguyên nhân thì không cần debug: mở `bugfix --size small`, hoặc sửa thẳng ngoài workflow.

## Lệnh của người

Các lệnh dưới đây mang quyền quyết định của bạn. Hook của `dev-core` từ chối khi agent tự chạy (`agentflow guard` trả `deny`), nên bạn tự chạy.

| Lệnh | Việc |
|---|---|
| `agentflow decide --answer Q1 --text "..." --check review` | Trả lời câu hỏi "Chưa có quy ước" của plan (`Q1`) hoặc của setup (`S1`) |
| `agentflow decide --suppress <id> --reason "..."` | Bỏ qua một phát hiện scan mà bạn xác nhận là báo nhầm |
| `agentflow project confirm PC-01 PC-02` (hoặc `--all`) | Xác nhận quy ước trong hồ sơ dự án (`--all` chỉ gồm quy ước) |
| `agentflow project confirm mission` / `profile` / `architecture` / `R1 R2 ...` | Xác nhận mission, cả `profile`, cả `architecture` hoặc từng mục roadmap; sửa nội dung sau đó thì về `unconfirmed` |
| `agentflow roadmap set R4 done\|doing\|todo\|dropped` | Đổi trạng thái một mục roadmap. Mục **không tự** `done` khi task xong: bạn quyết |
| `agentflow knowledge init` / `pull <file...>` / `push <file>` | Tạo kho cá nhân; chép file vào dự án; đưa một bài học về kho |
| `agentflow ext add <extension.yaml>` / `ext sync` | Đăng ký, đồng bộ extension của plugin con |
| `agentflow config set <khóa> <giá trị>` | Đặt cài đặt dự án (ví dụ `backend.*`) |
| `agentflow task seal <id>` | Ghi `summary.md`, `spec-delta.md` và tag duyệt cho task đã xong mà chưa có |
| `agentflow replan done` | Sau khi đọc `replan.md`: replan của task xong gần nhất (đang `proposed`) là xong; đánh dấu task, cập nhật `summary.md`, xóa dòng `removed:` |
| `agentflow replan skip <task> --reason "..."` | Chủ động bỏ qua replan của task xong gần nhất (đang `pending` hoặc `proposed`) |
| `agentflow tests amend <file>... --reason "..." [--accept-green]` | Mở cửa sổ để đổi một test đã duyệt (hoặc thêm file cấu hình test); sửa xong commit bằng `agentflow commit`. `--accept-green` chỉ khi test sửa xong xanh trên mã cũ mà bạn chấp nhận (cần lý do). Xem "Khóa test đã duyệt" |
| `agentflow state accept --reason "..."` | Sau khi đọc một thay đổi `state.json` làm ngoài agentflow (hoặc các lệnh nhật ký `audit.jsonl` ghi lại): tin lại file, ghi `decisions/<thời điểm>-state-accept.md` kèm trạng thái đã chấp nhận |
| `agentflow role grant\|revoke\|sync` | Cấp, thu hồi, sinh lại tool MCP theo dự án cho role |

Hai lệnh sau không bị hook từ chối nhưng phải luôn hỏi bạn: hook `pre-tool` trả `ask` (Claude Code) hoặc `force_ask` (Antigravity) cho `agentflow task approve` (hoặc `/dev-core:approve`) và `agentflow task cancel`, kể cả khi agent gọi qua `uv run`, `python -m agentflow`, đường dẫn đầy đủ, `timeout`, tiền tố biến môi trường hay nội dung bash/python đọc từ heredoc. Quy tắc `ask` trong khối permissions của README (Bước 4) là lớp phụ.

**Cách chạy.**
- Claude Code: gõ với tiền tố `!` ở đầu dòng, ví dụ `! agentflow project confirm --all`. Lệnh chạy ngay trong phiên và kết quả đi vào cuộc trò chuyện.
- Antigravity CLI: tài liệu của nó không có tiền tố tương đương; mở một terminal riêng, vào thư mục dự án và chạy lệnh ở đó.

Merge và push là việc của bạn, không phải của agent: agent không bao giờ push, merge hay tạo PR.

### Giới hạn trên Antigravity CLI

Antigravity không có quy tắc `ask` kiểu `permissions`, nên câu hỏi duyệt đến từ hook: `force_ask` cho `task approve`/`task cancel`, bỏ qua "Always Allow". Chế độ mặc định (`request-review`) hỏi đúng; nếu bạn chạy chế độ tự duyệt mọi lệnh (`--dangerously-skip-permissions`) thì lệnh vẫn chạy mà không hỏi (đã thử với agy 1.4.0), và chỉ còn các lớp không phụ thuộc câu hỏi: hook từ chối ghi vào `.agentflow/` và lệnh của người, `agentflow commit` từ chối khi sai nhánh hoặc có secret. **KHÔNG dùng `agy --dangerously-skip-permissions` với plugin này**: mọi câu hỏi duyệt của plugin bị bỏ qua. Chi tiết và bảng thử thật: [docs/architecture.md](../../docs/architecture.md).

## Tiết kiệm token

Chi phí tăng theo kích thước ngữ cảnh: mỗi yêu cầu gửi lại cả cuộc trò chuyện (theo [trang chi phí](https://code.claude.com/docs/en/costs) của Claude Code).

- **Mỗi task một phiên.** Xong task (hoặc chuyển việc không liên quan) thì `/clear` để bắt đầu phiên mới. Trạng thái task không mất: nó nằm trong `.agentflow/`, phiên mới chạy `/dev-core:continue` hoặc `/dev-core:status` là biết đang ở đâu.
- **Xem ngữ cảnh đang chứa gì:** `/context`.
- **Xem mức dùng:** `/usage` (Claude Code), hiện cả mức dùng của phiên và phần nào do skill, subagent, plugin hay MCP server. Antigravity: `/usage` mở bảng hạn mức theo từng model.
- Phiên mở cả ngày vẫn tốn cho toàn bộ lịch sử ở mỗi lần hỏi; quay lại sau một khoảng nghỉ dài cũng làm cache hết hạn. `/clear` không tốn gì.
- Dùng Sonnet cho phiên, hạ effort khi chạy (xem [Chọn chế độ](#chọn-chế-độ)), và chọn `small` cho việc nhỏ.
- **Đo bằng `agentflow stats`** (chỉ đọc, `--task T-001` cho một task, `--json` để xử lý tiếp): mỗi task tốn bao lâu và bao nhiêu phần là chờ bạn duyệt, số lần duyệt, số vòng làm lại và ở bước nào, task có bị `blocked` không, cổng nào đã chặn `pass` bao nhiêu lần (đọc từ `tasks/<task>/gate-log.jsonl`, agentflow ghi mỗi lần cổng từ chối). Có nhiều task thì có dòng tổng. agentflow không biết số token: xem `/usage` của CLI và ghi kèm. Cổng chặn nhiều mà ít khi bắt lỗi thật là chỗ nên xem lại; task nhỏ mà tốn nhiều vòng thì nên chọn `small`.

## Xử lý tình huống

**Task `blocked`.** Một task fail quá 3 vòng ở `test`, `security` hoặc `review` thì chuyển `blocked`. Chạy `agentflow status`, đọc báo cáo mới nhất ở `.agentflow/tasks/<task>/reports/`, rồi chọn: cho làm tiếp bằng `agentflow task approve --reason "<lý do>"` (số vòng về 0, lý do được ghi vào `decisions/`), hoặc hủy bằng `agentflow task cancel`.

**Scan báo nhầm.** Chạy `agentflow scan` và đọc id của phát hiện. Chỉ khi bạn chắc là báo nhầm: `agentflow decide --suppress <id> --reason "<vì sao chấp nhận được>"`. Agent không có đường nào tự hạ mức.

**Câu hỏi "Chưa có quy ước".** Plan có mục `## Chưa có quy ước` bị chặn tới khi bạn trả lời từng câu: `agentflow decide --answer Q1 --text "<quy ước, một dòng>" --check plan|semgrep|review` (thêm `--global` để ghi cả vào kho cá nhân). Sau đó để agent chạy tiếp bằng `/dev-core:continue`.

**`task approve` bị từ chối (mã 36).** Còn ô chưa tick (thông báo nêu mã, ví dụ `K2 C3`): mở `.agentflow/tasks/<task>/approve-<bước>.md` và ghi `x`. Hoặc khung bị đổi (thêm, xóa, sửa chữ một dòng, hoặc sửa đầu file): đừng sửa tay, cho bước làm lại (`agentflow task advance --result fail`) để có file mới. File bị mất cũng bị từ chối.

**`task advance` hoặc `task approve` báo `state.json` bị đổi (mã 37).** `state.json` khác với hash agentflow giữ trong `.agentflow/integrity.json`, hoặc `audit.jsonl` ghi một lệnh được cho qua có thể đã ghi vào checklist hay `state.json` (thông báo trích dòng nhật ký). Đọc thay đổi (`git diff` không thấy vì `.agentflow/` nằm ngoài git; so với `STATE.md` và `decisions/`), nếu chấp nhận thì `agentflow state accept --reason "..."`. Lệnh chỉ đọc như `cat state.json` không bị tính, nhưng lệnh ghi (chuyển hướng `>`, `tee`, `sed -i`, `cp`, `Set-Content`, hoặc `python -c`/`node`/`bash -c` nhắc tới file) thì có. Thiếu `integrity.json` ở workspace cũ: agentflow tạo lại và cảnh báo một lần.

**`test-spec` bị từ chối khi `task advance --result pass`.** Thông báo nêu mã mục (`C2 ...`): thiếu khối, khối thừa, thiếu trường (`command`, `red: fail`, `reason`, `output`), file test chưa commit hay không tồn tại, lệnh không nhắc tới file test của mục, hoặc agentflow đã chạy lại lệnh và nó **không đỏ** (mã 0), không tìm thấy lệnh, hay quá giờ. Sửa test hoặc báo cáo rồi chạy lại; bước `test-spec` có thể quay về `plan` bằng `--result fail` nếu kế hoạch không test được.

**`tests-pass` chặn bước `test`.** Hoặc lệnh test của dự án thoát khác 0 (thông báo cho thấy đuôi output), hoặc lệnh của một mục vẫn đỏ sau khi code xong (`C3: its command still fails`), hoặc `verify-red.json` thiếu/khác báo cáo đã duyệt, hoặc chưa có lệnh test: chạy `agentflow config set test_command "<lệnh>"`, hoặc ghi `- test-command:` vào profile rồi `agentflow project confirm profile`.

**Bước báo `locked-files-intact` fail, hoặc `agentflow tests check` báo file lệch.** Thông báo nêu từng file khóa bị đổi, mất, đổi tên, hoặc file cấu hình test mới xuất hiện. Nếu là agent làm sai: nhờ nó trả lại file như cũ (`git restore <file>` lấy lại bản đã commit) rồi chạy lại bước. Nếu test đúng là cần đổi: `agentflow tests amend <file> --reason "..."`, sửa, `agentflow commit`. Không cần amend để thêm dependency hay đổi phần khác của `pyproject.toml`, `setup.cfg`, `package.json`. Một file mà bạn thấy cần khóa nhưng không bị khóa thường là file tester quên khai ở `## Hạ tầng test`: nhờ tester bổ sung rồi cho bước làm lại.

**Duyệt `test-spec` bị từ chối vì file đã đổi sau lúc chạy đỏ.** `verify-red.json` giữ hash lúc agentflow chạy đỏ; một file test hoặc hạ tầng khác hash đó thì không khóa được. Cho bước làm lại (`agentflow task advance --result fail`) để chạy đỏ lại trên bản hiện tại.

**`agentflow commit` từ chối vì file khóa, hoặc vì test sửa xong xanh trên mã cũ.** Thông báo nêu file và mục (`C1`). Đổi test đã duyệt phải qua `agentflow tests amend` (xem trên); test xanh trên mã cũ chỉ qua khi bạn mở cửa sổ với `--accept-green --reason "..."`.

**Báo `config.yaml` bị đổi ngoài agentflow (mã 37).** Lệnh test (`test_command`) hay `test_timeout_minutes` trong `.agentflow/config.yaml` khác với lần cuối agentflow ghi. Đặt bằng `agentflow config set test_command "<lệnh>"`; nếu bạn đã đọc thay đổi và chấp nhận, `agentflow state accept --reason "..."`.

**Workflow gốc đổi.** Khi file `workflow.yaml` gốc của plugin đổi (sau khi cập nhật plugin), `agentflow status` cảnh báo. Khi không có task đang chạy, đồng bộ bằng `agentflow workflow sync`; có task đang chạy thì lệnh bị từ chối, trừ khi bạn thêm `--force`. Tương tự, `agentflow ext sync` cho extension và `agentflow role sync` cho agent cấp theo dự án.

**Cảnh báo khi `task new`.** Cảnh báo không chặn, nhưng đáng đọc: *mission* hoặc *roadmap* chưa có hay chưa xác nhận (xác nhận bằng `agentflow project confirm mission` / `R1 ...`), task không gắn mục *roadmap* nào (thêm `--roadmap Rn`), hoặc mục gắn vào chưa xác nhận. `agentflow project status` cho cái nhìn tổng; dòng `removed: R4 (confirmed)` nghĩa là một agent đã bỏ khỏi roadmap một mục bạn từng xác nhận, bản trước ở `.agentflow/project/history/`; nếu không muốn, nhờ scout ghi lại mục đó (nó sẽ `unconfirmed`, bạn xác nhận lại).

**Mục roadmap bị từ chối.** `task new --roadmap Rn` từ chối mục đã `done` hoặc `dropped`: mở lại bằng `agentflow roadmap set Rn doing`. Agent ghi roadmap sai khuôn bị từ chối (mã 35) và không thể bỏ mục đã `doing`/`done`/`dropped` hay tự đổi trạng thái; mục đã `done` do **bạn** đặt.

**Cảnh báo chưa replan, hoặc replan chưa chạy được.** `agentflow task new` cảnh báo khi task xong gần nhất còn `pending` (chưa ai replan) hoặc `proposed` (scout đã đề xuất nhưng bạn chưa chạy `agentflow replan done`); cảnh báo không chặn. `/dev-core:replan` và `replan_write` bị từ chối khi đang có task mở, kể cả task `blocked` (nó vẫn là task mở): hoàn tất hoặc hủy task đó trước. Replan đã `done` thì không ghi lại được; muốn đổi, sửa tay tài liệu rồi xác nhận lại.

**Task xong nhưng thiếu tag duyệt.** `agentflow task new` từ chối khi task xong gần nhất chưa có tag `agentflow/<task>/approved`. Tạo bù bằng `agentflow task seal <id>`.
