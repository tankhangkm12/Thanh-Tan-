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
Loại: feature | bugfix | hotfix        Cỡ: normal | small
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

**Confirm — đúng ý, đúng phạm vi**
- [ ] Phần "Mục tiêu" được nhắc lại đúng ý bạn.
- [ ] Phạm vi và ngoài phạm vi khớp những gì bạn viết, không thêm, không bớt.
- [ ] Tiêu chí "Xong khi" kiểm được bằng lệnh hoặc quan sát cụ thể.
- [ ] Mọi câu hỏi mở đã được bạn trả lời, không để agent đoán.

**Plan — done-when đủ chặt, tier hợp lý, docs có link**
- [ ] Mỗi mục có `done-when` là lệnh hoặc sự kiện kiểm được, không phải lời mô tả mơ hồ.
- [ ] Các mục đủ nhỏ để kiểm từng mục; không mục nào "làm hết".
- [ ] `tier` hợp lý: phần khó và nhạy cảm là `deep`, phần quen thuộc là `fast`.
- [ ] Mục `docs` có link tài liệu chính thức, hoặc `không có — <lý do>` mà bạn chấp nhận.
- [ ] Mục `files` không vượt phạm vi đã duyệt ở `confirm`.
- [ ] Mục `## Chưa có quy ước` (nếu có) đã được bạn trả lời bằng `agentflow decide --answer Q1 ...`.

**Review — mỗi quy ước có dòng đánh giá**
- [ ] Mỗi quy ước `check: review` có đúng một dòng `PC-01: đạt` hoặc `vi phạm PC-01 ở file:dòng`.
- [ ] Mục "must fix" đã xử lý hoặc có lý do rõ ràng.
- [ ] Mục `## Đề xuất cập nhật hồ sơ` của báo cáo review: mỗi đề xuất (`profile`, `mission`, `architecture`, `conventions`, `roadmap`) là đúng và đủ, hoặc `không có` là đúng. Gate `drift-reviewed` chỉ kiểm hình thức (có mục, đúng khuôn), không kiểm đề xuất có đúng không: phần đó do bạn kiểm ở đây. Reviewer chỉ đề xuất, không sửa hồ sơ; đề xuất nào bạn đồng ý thì tự cập nhật hồ sơ (hoặc nhờ scout ghi lại rồi xác nhận).
- [ ] Thay đổi đúng kế hoạch đã duyệt, không có việc ngoài phạm vi.
- [ ] `summary.md` và kết quả scan (`.agentflow/tasks/<task>/scans/`) không còn phát hiện chặn nào chưa giải thích.
- [ ] "Bài học đề xuất" đáng giữ thì đưa về kho: `agentflow knowledge push .agentflow/tasks/<task>/lessons/L1.md`.

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
| `agentflow task seal <id>` | Ghi `summary.md` và tag duyệt cho task đã xong mà chưa có |
| `agentflow role grant\|revoke\|sync` | Cấp, thu hồi, sinh lại tool MCP theo dự án cho role |

Hai lệnh sau không bị hook từ chối nhưng phải luôn hỏi bạn nhờ quy tắc `ask` trong khối permissions: `agentflow task approve` (hoặc `/dev-core:approve`) và `agentflow task cancel`.

**Cách chạy.**
- Claude Code: gõ với tiền tố `!` ở đầu dòng, ví dụ `! agentflow project confirm --all`. Lệnh chạy ngay trong phiên và kết quả đi vào cuộc trò chuyện.
- Antigravity CLI: tài liệu của nó không có tiền tố tương đương; mở một terminal riêng, vào thư mục dự án và chạy lệnh ở đó.

Merge và push là việc của bạn, không phải của agent: agent không bao giờ push, merge hay tạo PR.

## Tiết kiệm token

Chi phí tăng theo kích thước ngữ cảnh: mỗi yêu cầu gửi lại cả cuộc trò chuyện (theo [trang chi phí](https://code.claude.com/docs/en/costs) của Claude Code).

- **Mỗi task một phiên.** Xong task (hoặc chuyển việc không liên quan) thì `/clear` để bắt đầu phiên mới. Trạng thái task không mất: nó nằm trong `.agentflow/`, phiên mới chạy `/dev-core:continue` hoặc `/dev-core:status` là biết đang ở đâu.
- **Xem ngữ cảnh đang chứa gì:** `/context`.
- **Xem mức dùng:** `/usage` (Claude Code), hiện cả mức dùng của phiên và phần nào do skill, subagent, plugin hay MCP server. Antigravity: `/usage` mở bảng hạn mức theo từng model.
- Phiên mở cả ngày vẫn tốn cho toàn bộ lịch sử ở mỗi lần hỏi; quay lại sau một khoảng nghỉ dài cũng làm cache hết hạn. `/clear` không tốn gì.
- Dùng Sonnet cho phiên, hạ effort khi chạy (xem [Chọn chế độ](#chọn-chế-độ)), và chọn `small` cho việc nhỏ.

## Xử lý tình huống

**Task `blocked`.** Một task fail quá 3 vòng ở `test`, `security` hoặc `review` thì chuyển `blocked`. Chạy `agentflow status`, đọc báo cáo mới nhất ở `.agentflow/tasks/<task>/reports/`, rồi chọn: cho làm tiếp bằng `agentflow task approve --reason "<lý do>"` (số vòng về 0, lý do được ghi vào `decisions/`), hoặc hủy bằng `agentflow task cancel`.

**Scan báo nhầm.** Chạy `agentflow scan` và đọc id của phát hiện. Chỉ khi bạn chắc là báo nhầm: `agentflow decide --suppress <id> --reason "<vì sao chấp nhận được>"`. Agent không có đường nào tự hạ mức.

**Câu hỏi "Chưa có quy ước".** Plan có mục `## Chưa có quy ước` bị chặn tới khi bạn trả lời từng câu: `agentflow decide --answer Q1 --text "<quy ước, một dòng>" --check plan|semgrep|review` (thêm `--global` để ghi cả vào kho cá nhân). Sau đó để agent chạy tiếp bằng `/dev-core:continue`.

**Workflow gốc đổi.** Khi file `workflow.yaml` gốc của plugin đổi (sau khi cập nhật plugin), `agentflow status` cảnh báo. Khi không có task đang chạy, đồng bộ bằng `agentflow workflow sync`; có task đang chạy thì lệnh bị từ chối, trừ khi bạn thêm `--force`. Tương tự, `agentflow ext sync` cho extension và `agentflow role sync` cho agent cấp theo dự án.

**Cảnh báo khi `task new`.** Cảnh báo không chặn, nhưng đáng đọc: *mission* hoặc *roadmap* chưa có hay chưa xác nhận (xác nhận bằng `agentflow project confirm mission` / `R1 ...`), task không gắn mục *roadmap* nào (thêm `--roadmap Rn`), hoặc mục gắn vào chưa xác nhận. `agentflow project status` cho cái nhìn tổng; dòng `removed: R4 (confirmed)` nghĩa là một agent đã bỏ khỏi roadmap một mục bạn từng xác nhận, bản trước ở `.agentflow/project/history/`; nếu không muốn, nhờ scout ghi lại mục đó (nó sẽ `unconfirmed`, bạn xác nhận lại).

**Mục roadmap bị từ chối.** `task new --roadmap Rn` từ chối mục đã `done` hoặc `dropped`: mở lại bằng `agentflow roadmap set Rn doing`. Agent ghi roadmap sai khuôn bị từ chối (mã 35) và không thể bỏ mục đã `doing`/`done`/`dropped` hay tự đổi trạng thái; mục đã `done` do **bạn** đặt.

**Task xong nhưng thiếu tag duyệt.** `agentflow task new` từ chối khi task xong gần nhất chưa có tag `agentflow/<task>/approved`. Tạo bù bằng `agentflow task seal <id>`.
