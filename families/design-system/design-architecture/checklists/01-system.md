# Xong khi: 01-system

Gate: G3 (kiểu kiến trúc qua hội đồng). Trọng tâm: Q1, Q2, Q3, Q6, Q8. Mức S giữ `architecture-style.md` và `containers.md`, thêm `integrations.md` khi có hệ thống ngoài; `system-context.md` chỉ có từ mức M (`profiles.md`).

## system-context.md

- [ ] Mỗi tác nhân truy về ít nhất một FR; có phạm vi trong và ngoài (Q1).
- [ ] Mọi hệ thống ngoài nêu ở đây có dòng trong `integrations.md`, và ngược lại.
- [ ] Có sơ đồ; không có quyết định về giao diện nhìn thấy (Q7).

## containers.md

- [ ] Mỗi service, database, app, queue, cache, object storage của dự án có đúng một dòng; tên khớp thư mục trong `06-backend/`, `07-data/`, `05-frontend/` và khóa trong `capacity/`.
- [ ] Mỗi container dẫn link tới `scaling.md` hoặc `layers/{layer}.md` cho scale, nâng cấp, bảo trì; không chép lại (Q3).
- [ ] Công nghệ khớp `02-tech-stack/README.md`.
- [ ] Liên lạc giữa container có luồng `FL-xx` (Q1).

## architecture-style.md

- [ ] Kiểu kiến trúc có `D-xxx` đã qua hội đồng và người dùng quyết ở G3.
- [ ] Mỗi lý do truy về NFR, C hoặc TC; phương án đã loại có lý do (Q1).
- [ ] Mỗi giai đoạn scale có ngưỡng bằng số kèm cơ sở; khớp `scaling-stages.md` khi có (Q3).
- [ ] "Gánh nặng vận hành" có giờ mỗi tháng kèm cơ sở ước tính (Q3).

## integrations.md

- [ ] Mỗi hệ thống ngoài có dịch vụ gọi `SVC-xx`, FR, link tài liệu chính thức.
- [ ] "Lỗi và fallback": thời gian chờ (ms), số lần thử lại và hành vi khi hỏng cho từng hệ thống.
- [ ] "Giới hạn và chi phí": giới hạn nhà cung cấp là số; chi phí hạ tầng dẫn link `cost-model.md`, khoản ngoài có nguồn giá và ngày tra cứu (Q4).
- [ ] "Tối ưu": chỉ số bằng số, đơn vị, NFR, cách đo (Q2).
- [ ] "Nâng cấp và bảo trì": nhà cung cấp báo thay đổi qua đâu, việc định kỳ và giờ mỗi tháng (Q3).

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_links.py`, `check_numbers.py`, `check_profile.py --gate G3 --templates …`, `check_workspace.py` sạch.
- [ ] Quyết định và rủi ro mới (phụ thuộc ngoài, điểm hỏng đơn) đã khai vào sổ rủi ro (Q6).
- [ ] Người dùng duyệt kiểu kiến trúc (`G3: duyệt`).
