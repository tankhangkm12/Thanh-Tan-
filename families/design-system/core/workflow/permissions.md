# Quyền của agent

Mỗi việc giao cho một agent chạy trong ngữ cảnh riêng, chỉ được đọc đúng file Orchestrator truyền cho task đó và chỉ được ghi vào vùng của mình. Không agent nào được ghi trạng thái "Đã duyệt": chỉ người dùng duyệt. Nguồn: [PLAN.md](../../PLAN.md), mục "Các agent và quyền ghi". Các gate xem [stages.md](stages.md).

Đường dẫn tính từ `.agent-workspace/` trừ khi ghi `architecture/`.

## Bảng quyền

| Agent | Được đọc | Được ghi vào | Model / effort |
| --- | --- | --- | --- |
| Orchestrator (phiên chính) | `state.md`, `models.md`, `questions.md`, `plan/`, kết quả `checks/`; chỉ dùng để điều phối và chọn file truyền cho agent khác | `state.md`, `models.md`, `inputs/` (lưu input người dùng đưa), `questions.md` (chuyển câu trả lời), `decisions/decision-log.md`, phần "Quyết định của người dùng" trong `decision.md`, `risks/acceptance.md` (chỉ theo quy tắc 2), duy nhất dòng "Trạng thái" trong `plan/tasks/*.md` (không sửa nội dung khác của file task) | Model của phiên bạn mở / medium |
| Planner | `inputs/`, `state.md`, `models.md`, hồ sơ dự án đã duyệt | `plan/` (`plan.md`, `tasks/`), `questions.md`, bản nháp `drafts/00-context/project-profile.md` | Theo `models.md` / high |
| Researcher | Task được giao, tiêu chí TC đã duyệt, `~/knowledge/stacks/<stack>/`; không đọc `brief.md`, phiếu bầu hay `decision.md`, để giữ dữ kiện trung lập | `stack/` (trừ file kết quả spike `*.result.md`, chỉ `run_spike.py` ghi); `capacity/db-constants/<db>-<major>.yaml` (hằng số của DB đã chốt, từng hằng số kèm link nguồn đã tự xác minh; chép từ `~/knowledge/stacks/<db>/constants-<major>.yaml` ở G4) | Model có tìm web trong `models.md` / medium |
| Designer | Task được giao; input và context đã duyệt; `stack/`, `capacity/`, `drafts/` của giai đoạn; quyết định cuối của người dùng (không đọc phiếu từng người); `reviews/` của đúng phần đang sửa lỗi chặn, khi task truyền | `decisions/*/brief.md`, `drafts/` (trừ `drafts/00-context/assumptions.md` và `drafts/03-capacity/`, là file script sinh; trong `drafts/07-data/databases/<db>/tables.md` không sửa khối `BEGIN:calc`/`END:calc`), `capacity/` (trừ `capacity/db-constants/`, của Researcher), `questions.md` (chỉ thêm câu hỏi vào mục "Đang mở"), `stack/layers/<lớp>/spikes/S-xx-<tên>.md` (đề bài spike, theo template `spike.md`); chỉ loại file này trong `stack/`; `drafts/02-tech-stack/selection-criteria.md` (tiêu chí TC) không được nêu tên công nghệ hay ứng viên nào, và không bao giờ ghi `*.result.md` | Theo `models.md` / high |
| Hội đồng (3 hoặc 5 thành viên) | Chỉ `brief.md` và phần context được trích; vòng 2 thêm `r1-summary.md` ẩn danh | `decisions/*/votes/` (mỗi thành viên một file phiếu) | Mỗi thành viên một model khác nhau trong `models.md` |
| Reviewer | Bản nháp cần soát, template, checklist, nguồn gốc (BA, `capacity/assumptions.yaml`), kết quả script, và `decisions/decision-log.md` cùng `risks/acceptance.md` (chỉ để đối chiếu dòng duyệt và chấp nhận của người dùng cho Q5, Q6); không đọc brief, `votes/`, `decision.md` hay lý luận của Designer | `reviews/` (chỉ tạo file báo cáo mới) | Khác model với Designer / high |
| Script | Tùy script (xem bảng "Các script kiểm tra" trong PLAN.md) | `decisions/*/tally.md`, `decisions/*/votes/r1-summary.md` (do `tally_votes.py` sinh: gom nguyên văn phần "Lý do" của phiếu vòng 1, bỏ member/model/perspective, xáo thứ tự ngẫu nhiên; không tóm tắt bằng model), phần hội đồng trong `decision.md` (do `tally_votes.py` sinh), `drafts/03-capacity/` (do `calc_capacity.py` sinh), `drafts/00-context/assumptions.md` (sinh từ `capacity/assumptions.yaml`), khối bảng số có đánh dấu trong `drafts/07-data/databases/<db>/tables.md` (do `calc_capacity.py` sinh; phần còn lại của file là của Designer), `stack/layers/*/spikes/S-xx-*.result.md` (do `run_spike.py` sinh sau khi chạy spike trong container, chỉ khi `state.md` có dòng người dùng đồng ý đúng `S-xx: chạy` kèm sha256 của đề bài), `checks/`, `architecture/`, `archive/` | Không phải agent |
| Người dùng | Mọi thứ | Duyệt gate, quyết định, chấp nhận rủi ro | — |

## Quy tắc

1. **Chỉ script `promote_drafts.py` được ghi vào `architecture/`**, và chỉ chạy sau khi người dùng duyệt gate. Đầu ra nhờ vậy chỉ chứa nội dung đã chốt. Ngoại lệ duy nhất: `archive_release.py` thêm mục phát hành vào `architecture/CHANGELOG.md` sau khi người dùng duyệt G10 (không chép nội dung thiết kế).
2. **Chỉ người dùng duyệt; Orchestrator chỉ ghi lại.** Orchestrator chỉ ghi trạng thái duyệt (gate, quyết định, chấp nhận rủi ro) khi người dùng nói rõ theo ID trong tin nhắn, ví dụ `G4: duyệt`, `D-007: chọn B`, `R-04: chấp nhận`, `S-02: chạy` (cho chạy một spike). Orchestrator trích nguyên văn câu đó kèm ngày vào nơi ghi: phần "Quyết định của người dùng" trong `decision.md`, `decisions/decision-log.md`, `risks/acceptance.md`, `state.md` (gate; spike thì mục "Spike được duyệt chạy", kèm sha256 của đề bài để đề bài sửa sau đó phải xin lại). "ok", "được", im lặng hay câu mơ hồ **không phải** duyệt; khi đó Orchestrator phải hỏi lại. Quyết định nói trong chat được ghi trước khi làm tiếp.
3. **`decision.md` có hai phần.** Phần hội đồng (phương án đề xuất, tỉ lệ phiếu, ý kiến thiểu số) do `tally_votes.py` sinh từ `tally.md`, không agent nào viết tay. Phần "Quyết định của người dùng" do Orchestrator ghi theo quy tắc 2.
4. **Không ghi chéo vùng.** Reviewer không sửa bản nháp; Designer không sửa `reviews/` hay `votes/`; hội đồng chỉ ghi phiếu của chính mình; script không viết lý luận.
5. **Ngữ cảnh độc lập.** Agent không mang lịch sử trò chuyện hay suy luận của agent khác. Agent trao đổi với nhau chỉ qua file trong workspace, không truyền tin trực tiếp.
6. **Cô lập phiếu.** Vòng 1 thành viên hội đồng không thấy phiếu nào khác; vòng 2 chỉ thấy bản tóm tắt ẩn danh. Designer không thấy phiếu từng người, chỉ thấy quyết định cuối của người dùng.
7. **Reviewer soát như người ngoài.** Chỉ đọc bản nháp, template, checklist và nguồn gốc; luôn khác model với Designer của phần đang soát.
8. **Chọn model.** Orchestrator chọn model từ `models.md`. Hội đồng: mỗi thành viên một model khác nhau; không đủ model thì dùng chung model với góc nhìn khác nhau và `decision.md` ghi rõ độ đa dạng bị giảm. Model gọi lỗi bị đánh dấu không dùng được và thay bằng model khác.

## Thực thi bằng hook

`hooks/hooks.json` của design-core gắn `scripts/guard_write.py` vào `PreToolUse` (matcher `Write|Edit|Bash|PowerShell`). Hook đọc `agent_type` (dạng `design-core:<agent>`, cả khi chạy `claude --agent design-core:orchestrator`) và chặn bằng exit 2 khi:

- Agent ghi ngoài vùng của mình trong bảng trên, hoặc ngoài `.agent-workspace/` (`architecture/` đóng với mọi agent).
- Orchestrator sửa file task ngoài dòng "Trạng thái", hoặc sửa `decision.md` ngoài khối `BEGIN:user`/`END:user`.
- Designer sửa khối `BEGIN:calc`/`END:calc` đã có nội dung trong `tables.md` (chỉ được thêm hoặc bỏ cặp dấu mà bên trong chỉ có "chờ script"), ghi `drafts/03-capacity/`, `drafts/00-context/assumptions.md`, hoặc `capacity/db-constants/`.
- Researcher hoặc Designer ghi file kết quả spike `stack/layers/<lớp>/spikes/*.result.md` (chỉ `run_spike.py` ghi); Designer ghi vào `stack/` ngoài đề bài spike `S-*.md`.
- Reviewer ghi đè hay sửa file có sẵn (chỉ tạo `reviews/R-<số>-<phần>.md` mới).
- Thành viên hội đồng ghi file không phải phiếu của chính mình (`votes/r<1|2>-<góc-nhìn>-<model>.md`).
- Shell (tool `Bash`; không agent nào có `PowerShell`, nhưng hook vẫn gắn cho cả hai làm lớp phòng thủ dự phòng, vì nếu một agent được thêm PowerShell sau này mà matcher chỉ có `Bash` thì lệnh lọt qua). Cùng một luật cho hai tool, phân tích lệnh theo cú pháp từng shell, theo danh sách cho phép (lệnh ngoài danh sách bị chặn):
  - Reviewer: `uv run` script kiểm tra của design-core (`check_links`, `check_trace`, `check_numbers`, `check_profile`, `check_versions`, `check_workspace`, và `calc_capacity` chỉ kèm `--check`) hoặc lệnh chỉ đọc.
  - Orchestrator: `uv run` mọi script của design-core (kể cả `promote_drafts.py`, `archive_release.py`, `tally_votes.py`, `run_spike.py`: script tự kiểm điều kiện), lệnh lấy ngày (`date` chỉ in, không đặt giờ; `Get-Date`), lệnh chỉ đọc, và chép file vào `.agent-workspace/inputs/` (`cp` / `Copy-Item` với đích nằm trong `inputs/` của workspace của dự án).
  - Planner, Researcher, Designer, hội đồng: không có shell; nếu gọi thì bị chặn.
  - Mọi shell: chặn chuyển hướng `>`/`<`, thay thế lệnh, chạy nền, biến và khối lệnh của PowerShell (`$`, `&`, `{}`, `()`, backtick), ghép lệnh có phần không hợp lệ (`;`, `&&`, `||`, `|`, xuống dòng đều tách lệnh và kiểm từng phần).
  - Lệnh chỉ đọc: `cat head tail wc ls dir type grep rg pwd diff stat echo cd find`, `git` (`status log diff show ls-files rev-parse`), và cmdlet PowerShell đọc (`Get-Content`, `Get-ChildItem`, `Select-String`, `Test-Path`...).

Phiên và agent không phải của design-core (không có `agent_type` của design-core) không bị hook chạm tới.
