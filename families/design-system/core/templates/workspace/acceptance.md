# Rủi ro đã được người dùng chấp nhận

> Orchestrator ghi, và chỉ khi người dùng nói rõ theo ID trong tin nhắn (ví dụ `R-04: chấp nhận`). Chép nguyên văn câu của người dùng kèm ngày; điểm lấy từ sổ rủi ro `11-risks/risk-register.md` (khả năng × tác động). Áp cho rủi ro từ 15 điểm trở lên còn giữ sau giảm thiểu. "ok", "được", im lặng hay câu mơ hồ không phải chấp nhận.
>
> `check_workspace.py` đối chiếu hai chiều: rủi ro ≥ 15 điểm có trạng thái "đã chấp nhận" trong sổ rủi ro phải có dòng ở đây, và mỗi dòng ở đây phải có rủi ro tương ứng trong sổ.

| ID | Điểm | Người dùng nói (nguyên văn) | Ngày |
| --- | --- | --- | --- |
| R-<xx> | <15–25> | <"R-04: chấp nhận"> | <YYYY-MM-DD> |
