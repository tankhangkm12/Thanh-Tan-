# Quyết định D-<xxx>: <câu hỏi>

- **Gate:** <G3 | G4 | G7>
- **Brief:** [brief.md](brief.md)
- **Phiếu:** [tally.md](tally.md)

> File có hai phần tách bạch bằng cặp dấu `BEGIN`/`END`. Mỗi bên chỉ được sửa phần của mình:
> - Phần **Hội đồng**: do `tally_votes.py` sinh từ `tally.md`. Không agent nào viết hay sửa tay; chạy lại script sẽ thay toàn bộ phần này.
> - Phần **Quyết định của người dùng**: do Orchestrator ghi, và chỉ khi người dùng nói rõ theo ID trong tin nhắn (ví dụ `D-007: chọn B`). Trích nguyên văn kèm ngày. "ok", "được", im lặng hay câu mơ hồ không phải quyết định: hỏi lại.

<!-- BEGIN:council (tally_votes.py sinh, không sửa tay) -->

## Hội đồng

- **Kết quả:** <đề xuất phương án X | chưa quá bán ở vòng 1: chờ vòng 2 | chưa đạt đồng thuận, hai phương án dẫn đầu: X và Y | "không phương án nào phù hợp": Designer làm lại brief>
- **Số vòng:** <1 | 2>
- **Quá bán cần:** <2/3 | 3/5>
- **Độ đa dạng model:** <đủ: mỗi thành viên một model khác nhau | giảm: dùng chung model <tên> cho <góc nhìn>>

### Tỉ lệ phiếu

| Phương án | Vòng 1 | Vòng 2 |
| --- | --- | --- |
| A | <n/tổng> | <n/tổng hoặc —> |
| none | <n/tổng> | <n/tổng hoặc —> |

### Ý kiến thiểu số

<!-- Luôn hiển thị: phiếu không theo phương án đề xuất, kèm góc nhìn, model, lý do (nguyên văn trích dẫn) và điểm. Không có phiếu thiểu số thì ghi "không có". -->

- <góc nhìn · model · chọn X · lý do>

### Rủi ro mới sinh ra

<!-- Gom từ mục "Rủi ro mới" của các phiếu. Designer khai vào sổ rủi ro sau khi người dùng quyết. -->

- <rủi ro · nêu bởi góc nhìn nào>

<!-- END:council -->

<!-- BEGIN:user (Orchestrator ghi, chỉ khi người dùng nói rõ theo ID) -->

## Quyết định của người dùng

- **Trạng thái:** <chờ người dùng | đã quyết | làm lại>
- **Người dùng nói (nguyên văn):** <"D-007: chọn B">
- **Ngày:** <YYYY-MM-DD>
- **Phương án được chọn:** <A | B | ... | làm lại brief>
- **Rủi ro đã khai vào sổ:** <R-xx, R-yy, hoặc: chưa>

<!-- END:user -->
