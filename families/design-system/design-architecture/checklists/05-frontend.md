# Xong khi: 05-frontend

Gate: G7. Trọng tâm: Q1, Q2, Q3, Q6, Q7, Q8. Mức S bỏ cả phần này. Phần có ba file chung (`overview`, `device-matrix`, `performance-budget`) và một thư mục mỗi app (`<app>/`: web, admin, mobile…) gồm 7 file.

## Giới hạn phạm vi (Q7)

- [ ] Không file nào có quyết định về giao diện nhìn thấy: màu, font, bố cục, khoảng cách, hình dáng component, icon, minh họa, hiệu ứng chuyển động, nội dung chữ, thứ tự và cách sắp xếp màn hình.
- [ ] Điều kiến trúc cần designer làm thêm đã ghi thành câu hỏi `CH-xxx` trong `questions.md`, không tự quyết.

## Chung (overview, device-matrix, performance-budget)

- [ ] Mỗi app có một dòng trong `overview.md` và một thư mục cùng tên; đủ 7 file trong thư mục (`check_profile.py` báo `instance-file-missing`).
- [ ] Chiến lược render từng app có lý do truy về NFR hoặc C và `D-xxx` (Q1).
- [ ] `device-matrix.md`: có OS, trình duyệt, RAM, mạng; tỉ lệ người dùng trỏ giả định `A-xx`; có thiết bị chuẩn là máy yếu nhất.
- [ ] `performance-budget.md`: ngân sách tài nguyên (KB, MB) và chỉ số trải nghiệm (LCP, INP, CLS, bộ nhớ) là số; mức sàn không lỏng hơn ngưỡng "tốt" của Core Web Vitals (LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1) (Q2, Q7).
- [ ] Có cách đo (lab và RUM) và bước CI chặn khi vượt ngân sách.
- [ ] `device-matrix.md` có "Tối ưu" và "Nâng cấp và bảo trì" (Q2, Q3).

## Mỗi app (thư mục `<app>/`)

- [ ] `architecture.md`: lớp có chiều phụ thuộc, module truy về FR và `SCR-xx`; có RUM và báo lỗi client.
- [ ] `routing-navigation.md`: mỗi route có `SCR-xx` (từ `inputs/ui-design/`, không định nghĩa ở đây), dữ liệu cần, `API-xx` gọi; không có đường dẫn API thô; mọi `API-xx` có định nghĩa ở `06-backend/` (`check_trace.py` báo `api-not-in-backend`).
- [ ] `state-data.md`: phân loại state, thời gian coi là mới của dữ liệu bằng giây kèm cơ sở, có "Tối ưu".
- [ ] `networking-offline.md`: thời gian chờ (ms), thử lại, khóa idempotency khớp `api.md`; mức offline truy về NFR hoặc ghi "không hỗ trợ"; có "Tối ưu".
- [ ] `auth-session.md`: nơi lưu token, thời hạn bằng số kèm cơ sở, phân quyền màn hình khớp `authz-matrix.md` khi có; quyền thật kiểm lại ở máy chủ.
- [ ] `build-delivery.md`: code splitting, CDN, cache asset, ảnh theo kích thước thiết bị, rollback; "Tối ưu"; "Scale, nâng cấp, bảo trì" với framework khớp `versions-features.md` (Q2, Q3).
- [ ] `folder-structure.md`: cây thư mục và quy tắc ranh giới, không mâu thuẫn `repo-structure.md`.

## Chung

- [ ] Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" với ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần không đạt (`check_numbers.py`).
- [ ] `check_trace.py --gate G7`, `check_links.py`, `check_numbers.py`, `check_versions.py`, `check_profile.py --gate G7 --templates …`, `check_workspace.py` sạch.
- [ ] Rủi ro mới (thiết bị yếu, thư viện nặng, phụ thuộc framework) đã khai vào sổ rủi ro (Q6).
- [ ] Người dùng duyệt từng app.
