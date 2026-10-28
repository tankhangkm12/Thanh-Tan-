# Chỉ mục luồng

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mỗi luồng một file `FL-xxx-<tên>.md` cùng thư mục; `FL-xx` được định nghĩa ở **heading** của file luồng, bảng dưới đây chỉ là chỉ mục. `check_trace.py` chỉ tính file luồng, không tính file này, khi kiểm FR có luồng.

## Danh sách luồng
<!-- required -->

| Luồng | Tên | Tác nhân | Tần suất (số + đơn vị) | Dịch vụ tham gia |
| --- | --- | --- | --- | --- |
| [FL-xxx](FL-xxx-{tên}.md) | <tên luồng> | <người dùng, hệ thống ngoài> | <số lần/ngày, lấy từ A-xx> | <SVC-xxx, … hoặc "chưa thiết kế ở G6"> |

## Yêu cầu chưa có luồng
<!-- required -->

Mọi FR phải có ít nhất một luồng (Q1). Liệt kê FR chưa có luồng kèm lý do; không có thì ghi "không có FR nào thiếu luồng".

- <FR-xx: lý do, hoặc "không có FR nào thiếu luồng">
