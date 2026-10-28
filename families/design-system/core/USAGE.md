# Hướng dẫn dùng design-core và design-architecture

Chỉ nói cách dùng. Quy trình, quyền agent và tiêu chí nằm ở [PLAN.md](../PLAN.md) và `workflow/`.

## Cần có trước

- `uv` (chạy mọi script), `git`, Claude Code.
- Docker hoặc Podman, đang chạy: để chạy spike (mức XL bắt buộc).
- `agy` (Antigravity CLI): tùy chọn, chỉ cần khi hội đồng gọi thành viên qua CLI ngoài.

## Cài đặt

Cài từ marketplace (một lần, dùng mọi dự án):

```text
claude plugin marketplace add tankhangkm12/Thanh-Tan-
claude plugin install design-core@thanh-tan-plugins
claude plugin install design-architecture@thanh-tan-plugins
```

Từ bản clone local thì thay dòng đầu bằng `claude plugin marketplace add "<repo>"`. Cập nhật: `claude plugin update design-core@thanh-tan-plugins` (và `design-architecture@...`). Đã kiểm: cả hai plugin cài được từ marketplace local ở trạng thái enabled.

Hoặc nạp thẳng từ thư mục repo, không cài. `--plugin-dir` lặp được (theo `claude --help`), mỗi plugin một cờ:

```text
claude --plugin-dir <repo>/families/design-system/core --plugin-dir <repo>/families/design-system/design-architecture
```

Chạy trong repo thiết kế của dự án (không phải repo plugin). `design-architecture` cần `design-core` cùng được nạp.

## Chạy

```text
claude --agent design-core:orchestrator
```

Phiên chính là Orchestrator. Lần đầu nó chạy `init_workspace.py` tạo `.agent-workspace/` (đã vào `.gitignore`); các phiên sau nó đọc `state.md` để biết đang ở đâu. Orchestrator tự gọi Planner, Researcher, Designer, Reviewer và hội đồng.

## Chạy không tương tác (`claude -p`)

Mỗi lượt là một lệnh `claude -p`; các lượt sau thêm `--continue` (hoặc `--resume <id>`) và chạy trong đúng thư mục repo thiết kế. Ở chế độ này không có ai bấm cho phép, nên tool nào chưa được cho phép sẽ bị từ chối. Cờ tối thiểu đã chạy được qua G0–G1 (không dùng `--dangerously-skip-permissions`):

```text
claude -p "<prompt>" --plugin-dir <repo>/families/design-system/core --plugin-dir <repo>/families/design-system/design-architecture --agent design-core:orchestrator --model sonnet --allowedTools Read Write Edit Glob Grep Agent "Bash(uv run:*)" < /dev/null
```

- `Bash(uv run:*)` chỉ cho chạy script `uv run` (mọi script kiểm của Orchestrator và Reviewer), không mở Bash nói chung.
- `cp`, `mv`, `rm` không nằm trong luật nên bị hỏi và, ở `-p`, bị từ chối. Đừng mở `Bash(cp:*)`: Orchestrator đã được dặn dùng Write để chép input vào `.agent-workspace/inputs/`. Thấy nó xin `cp` thì để nó dùng Write.
- Luật `Bash(uv run:*)` chỉ khớp lệnh `uv run <script> ...` đứng một mình. Lệnh ghép (`&&`, `;`, `|`, `cd ... &&`, gán biến đầu lệnh, heredoc) bị từ chối, nên Orchestrator và Reviewer được dặn mỗi lần Bash chỉ một lệnh `uv run`; thấy chúng xin lệnh ghép thì chúng sẽ tự viết lại thành lệnh đơn, tốn thêm lượt.
- Tự trả lời duyệt/chọn/chấp nhận vẫn là việc của bạn: mỗi lượt chuyển nguyên văn câu `Gn: duyệt`, `D-xxx: chọn …`, `CH-xxx: …` của bạn, không để script hay công cụ gửi thay.

## Chọn model cho Reviewer

Mặc định giữ nguyên: Orchestrator chọn Reviewer ở G0 (khác Designer) và bạn duyệt trong danh mục model. Đánh đổi khi bạn tự chọn:

- **haiku:** rẻ mỗi lượt, nhưng ở lần thử NoteNest nó bỏ sót lỗi ở vòng đầu rồi bắt thêm dần ở các vòng sau (G1 cần 4 báo cáo soát R-003 đến R-006; lỗi "bỏ `messaging.md` chưa có rủi ro" chỉ bị bắt ở vòng sau). Mỗi vòng thêm là một lượt Designer sửa và một lượt soát lại, nên tổng chi phí gate có thể không rẻ hơn.
- **sonnet:** đắt hơn mỗi lượt, kỳ vọng bắt đủ hơn ngay vòng đầu và cần ít vòng hơn. Chưa đo trong lần thử NoteNest (chỉ chạy Reviewer bằng haiku), nên đây là kỳ vọng, chưa phải số liệu.
- Gate nhiều nội dung hoặc nhiều con số (G1, G5, G10) nên dùng model mạnh hơn cho Reviewer; gate nhỏ và đã có script kiểm chặt thì haiku đủ. Lỗi mà script bắt được (liên kết, số thiếu nguồn, mục thiếu) không phụ thuộc model.

## Luồng G0–G10

| Gate | Việc | Bạn duyệt |
|---|---|---|
| G0 | Khởi tạo, hồ sơ dự án, mức S/M/L/XL, model | Mức, các phần áp dụng, danh mục model |
| G1 | Context | FR, NFR có số, ràng buộc, giả định |
| G2 | Tiêu chí lựa chọn TC | Tiêu chí và trọng số |
| G3 | Kiểu kiến trúc | Kiểu và giai đoạn scale |
| G4 | Stack và phiên bản | Từng lớp, ma trận phiên bản |
| G5 | Capacity sơ bộ | Tải, dung lượng, chi phí |
| G6 | Luồng chính | Luồng |
| G7 | Thiết kế chi tiết | Service, database, app frontend |
| G8 | Bảo mật, hạ tầng, quy trình | Từng phần |
| G9 | Rủi ro và roadmap | Sổ rủi ro |
| G10 | Kiểm tra chéo, phát hành | Phát hành vN |

Mỗi phiên làm trọn một giai đoạn và dừng ở gate. Không có gate nào tự qua: thiếu lời duyệt của bạn thì dừng.

## Khuôn yêu cầu task

Bốn prompt mẫu. Dòng "Chạy với" là ghi chú cho bạn; đổi model hoặc effort theo nhu cầu.

**1. Thiết kế mới**

```text
Chạy với: Claude Code · model Sonnet · effort high

Dùng plugin design-architecture, chế độ THIẾT KẾ MỚI.

Dự án: <tên> — <1–2 câu mô tả>
Repo thiết kế: <đường dẫn>
Stack bắt buộc (nếu có): <ví dụ: backend phải là NestJS> | không có
Ràng buộc đã biết: ngân sách <…>/tháng · team <n> người (<kỹ năng>) · hạn <ngày> · hạ tầng <…> · tuân thủ <…>
Thiết bị người dùng chính (nếu biết): <…>
Tài liệu UI của designer (nếu có): <đường dẫn danh sách SCR>

Tài liệu BA đã duyệt:
<dán nội dung, hoặc liệt kê đường dẫn từng file>

Yêu cầu:
- Lưu tài liệu BA vào .agent-workspace/inputs/ba/ và chỉ đọc từ đó.
- Dò các model gọi được, ghi .agent-workspace/models.md.
- Làm hết G0 rồi dừng: trình hồ sơ dự án, mức áp dụng và danh mục model để tôi duyệt.
- Chỗ nào chưa rõ thì ghi vào questions.md và hỏi tôi, không tự giả định.
```

**2. Nâng cấp từ thiết kế cũ**

```text
Chạy với: Claude Code · model Sonnet · effort high

Dùng plugin design-architecture, chế độ NÂNG CẤP.

Repo thiết kế: <đường dẫn> · phiên bản hiện có: v<N>
Bản thiết kế cũ: <đường dẫn architecture/ cũ>
Lý do nâng cấp: <…>
Giữ nguyên, không xét lại: <…> | không có

Tài liệu BA mới hoặc phần thay đổi:
<dán nội dung, hoặc liệt kê đường dẫn>

Yêu cầu:
- Đọc bản cũ và archive/ (nếu còn) trước khi đề xuất gì.
- Liệt kê phần giữ, phần đổi, phần thêm.
- Dừng ở G0 để tôi duyệt phạm vi nâng cấp.
```

**3. Tiếp tục ở session mới**

```text
Chạy với: Claude Code · model Sonnet · effort medium

Tiếp tục design-architecture ở repo này.
(Tuỳ chọn) Tôi đã trả lời trong questions.md các mục: CH-003, CH-005.
```

**4. Duyệt gate và quyết định**

```text
Chạy với: Claude Code · model Sonnet · effort medium

G4: duyệt.            (hoặc: G4: chưa duyệt — lý do: …)
D-007: chọn B. Ghi chú: …
R-04: chấp nhận rủi ro.
CH-006: <câu trả lời>
```

## Trả lời theo ID

Orchestrator chỉ ghi lời duyệt, quyết định và rủi ro chấp nhận khi bạn nói rõ theo ID, nguyên văn sẽ được lưu lại.

| Tiền tố | Nghĩa | Ví dụ |
|---|---|---|
| `G` | Gate | `G4: duyệt` |
| `D` | Quyết định (có phương án) | `D-007: chọn B` |
| `R` | Rủi ro | `R-04: chấp nhận rủi ro` |
| `CH` | Câu hỏi của agent | `CH-006: dùng giờ Việt Nam` |
| `S` | Spike (chạy thử trong container) | `S-02: chạy` |

## Nhắc khi kiểm tra

`check_profile.py` cần template: Orchestrator và Reviewer phải truyền `--templates` rõ ràng, trỏ tới `design-architecture/templates`. Không tìm thấy template là lỗi; `--no-templates` chỉ để thử, báo cáo ghi "Chưa kiểm mục bắt buộc" và không đủ để qua gate. Nếu thấy agent chạy `check_profile.py` mà không có `--templates`, nhắc nó.

## Bản Antigravity

Khuyến nghị dùng bản Claude Code cho dự án thật. Bản Antigravity (`core/agents/`, sinh từ bản Claude bằng `tools/gen_antigravity.py`) chạy được nhưng yếu hơn ở chỗ kiểm soát:

- **Không có chặn ghi theo thư mục bằng máy.** Hook của Antigravity không biết agent nào đang gọi tool, nên không làm lại được `guard_write.py`. Quy tắc ai được ghi đâu chỉ nằm trong prompt của từng agent, và Reviewer soát lại.
- **`commandExecutionPolicy: sandbox` không chặn ghi ra ngoài thư mục dự án** (đã thử: lệnh `echo` ghi được file ngoài thư mục làm việc). Đừng coi nó là lớp bảo vệ.
- Giới hạn tool theo vai trò vẫn có: chỉ Orchestrator và Reviewer có `run_command`; hội đồng chỉ có `view_file` và `write_to_file`.

Cài và chạy (chọn agent bằng tên trần, không có tiền tố plugin):

```text
agy plugin install <repo>/families/design-system/core
agy plugin install <repo>/families/design-system/design-architecture
agy --agent design-orchestrator
```

`design-architecture` cài được vì đã có `plugin.json` (đã thử: `agy plugin install` chép cả thư mục, gồm `templates/`, vào `~/.gemini/config/plugins/design-architecture`). Đường dẫn template cho `--templates` là trường `path` của plugin này trong `agy plugin list --json` cộng `/templates`; Orchestrator tự lấy và ghi vào lời giao cho agent con. Chưa thử chạy đủ một vòng G0–G2 trên Antigravity (xem 6B).

Ở chế độ không tương tác (`-p`), mọi tool cần quyền sẽ bị từ chối nếu không có luật cho phép; chế độ tương tác thì được hỏi từng lần. Luật nằm trong `~/.gemini/antigravity-cli/settings.json` và áp cho **mọi dự án**, nên giữ hẹp. Mẫu theo tài liệu Antigravity (cú pháp `command(...)` khớp từng từ; chưa thử hết từng dòng), thay `<DESIGN_CORE_DIR>` bằng trường `path` của `design-core` trong `agy plugin list --json`:

```json
{
  "permissions": {
    "allow": [
      "command(agy plugin list)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/init_workspace.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/detect_models.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/calc_capacity.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/check_links.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/check_profile.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/check_numbers.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/check_versions.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/check_trace.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/check_workspace.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/tally_votes.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/call_council_cli.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/run_spike.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/promote_drafts.py)",
      "command(uv run <DESIGN_CORE_DIR>/scripts/archive_release.py)",
      "write_file(.agent-workspace/)",
      "read_url(<tên miền nguồn chính thức, mỗi nguồn một dòng>)"
    ]
  }
}
```

Bỏ các dòng `promote_drafts` và `archive_release` nếu muốn duyệt từng lần hai bước phát hành (ghi vào `architecture/`). Luật `write_file(.agent-workspace/)` chỉ phủ phần workspace; mọi ghi ngoài đó Antigravity sẽ hỏi, hãy đọc kỹ từng lần.
