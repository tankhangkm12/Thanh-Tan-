# Mức áp dụng S / M / L / XL

Bảng này là nguồn để điền bảng `| Phần | Áp dụng |` trong `00-context/project-profile.md` (template: [templates/00-context/project-profile.md](templates/00-context/project-profile.md)). Nó khớp bảng "Phần của architecture/ theo mức áp dụng" trong `core/workflow/stages.md` và bảng mức trong PLAN.md; khi hai nơi đó đổi thì sửa ở đây. `check_profile.py` đọc hồ sơ đã duyệt, không đọc file này.

Giá trị trong bảng: `có` = đủ nội dung của phần; `rút gọn` = giữ phần nhưng bớt như ghi ở cột "Rút gọn nghĩa là"; `bỏ` = phần không làm và không được xuất hiện.

## Dòng cấp phần

| Phần | S | M | L | XL | Rút gọn nghĩa là |
| --- | --- | --- | --- | --- | --- |
| 00-context | có | có | có | có | |
| 01-system | rút gọn | có | có | có | S: `architecture-style.md` và `containers.md`, thêm `integrations.md` khi có hệ thống ngoài (xem dòng cấp file) |
| 02-tech-stack | có | có | có | có | |
| 03-capacity | rút gọn | có | có | có | S: ít mốc hơn, chỉ ra mắt và 1 năm; vẫn đủ 5 file |
| 04-flows | có | có | có | có | |
| 05-frontend | bỏ | có | có | có | |
| 06-backend | có | có | có | có | |
| 07-data | có | có | có | có | |
| 08-security | bỏ | có | có | có | |
| 09-infrastructure | bỏ | có | có | có | |
| 10-process | bỏ | có | có | có | |
| 11-risks | rút gọn | có | có | có | S: sổ rủi ro chỉ ghi rủi ro từ 8 điểm trở lên |
| 12-roadmap | rút gọn | có | có | có | S: chỉ `implementation-plan.md` (xem dòng cấp file) |

## Dòng cấp file

Chỉ ghi vào hồ sơ khi giá trị khác dòng cấp phần của phần chứa nó; dòng dài hơn thắng. Mức không ghi ở đây dùng dòng cấp phần.

| File | S | M | L | XL |
| --- | --- | --- | --- | --- |
| 01-system/system-context.md | bỏ | có | có | có |
| 01-system/integrations.md | có nếu dự án có hệ thống ngoài (thanh toán, mail, SMS…); bỏ chỉ khi không có hệ thống ngoài nào, lý do ở cột "Lý do (Q8)" | có | có | có |
| 12-roadmap/scaling-stages.md | bỏ | có | có | có |
| 12-roadmap/upgrade-roadmap.md | bỏ | có | có | có |

Ở mức S, ô `integrations.md` có hai giá trị tùy dự án; hồ sơ đã duyệt ghi `có` hoặc `bỏ` (không ghi cả câu). Ở mức S, `01-system/architecture-style.md`, `01-system/containers.md` và `12-roadmap/implementation-plan.md` giữ theo dòng cấp phần (`rút gọn`).

## Quy tắc khác theo mức

| Mục | S | M | L | XL |
| --- | --- | --- | --- | --- |
| Mốc tính số liệu (`milestones` trong `assumptions.yaml`) | `launch`, `1y` | `launch`, `1y`, `3y` | `launch`, `1y`, `3y`, `5y` | `launch`, `1y`, `3y`, `5y`, `peak` |
| Hội đồng (`stages.md`) | 3 phiếu, chỉ cho kiểu kiến trúc (G3) và stack từng lớp (G4) | 3 phiếu | 3 phiếu; 5 phiếu cho quyết định khó đảo ngược | 5 phiếu |
| Chi tiết service | — | — | chi tiết từng service | chi tiết từng service |
| Spike trong container (`run_spike.py`) | không bắt buộc | không bắt buộc | không bắt buộc | bắt buộc: data, messaging, backend, infrastructure, cộng lớp Planner thêm |
| DR | — | — | — | chi tiết |

## Chọn mức

Mức đề xuất từ hồ sơ dự án (quy mô người dùng và dữ liệu, mức độ quan trọng, số người, ngân sách, thời hạn, tuân thủ); người dùng duyệt ở G0.

| Mức | Ví dụ dự án |
| --- | --- |
| S | Công cụ nội bộ, MVP |
| M | Sản phẩm thật, một team |
| L | Nhiều team, nhiều client |
| XL | Phân tán, tải lớn, yêu cầu tuân thủ cao |

Danh sách phần áp dụng cuối cùng do người dùng duyệt ở G0 (`stages.md`); phần bỏ phải có lý do ở cột "Lý do (Q8)" của hồ sơ. Dấu "—" trong bảng nghĩa là PLAN không nêu khác biệt cho mức đó.
