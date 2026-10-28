# Backend: tổng quan

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. File này là bản đồ: chi tiết từng service nằm ở `services/<service>/`, không chép lại. File này chỉ nhắc service bằng tên và link, không định nghĩa `SVC-xx` (chỉ `responsibility.md` của service định nghĩa) và không đặt ID ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Bản đồ service
<!-- required -->

Mọi service hoặc module của dự án có đúng một dòng; tên khớp thư mục `services/<service>/` và khóa trong `capacity/compute.yaml`.

**Mức tổ chức code (A/B)** là cách tổ chức code bên trong service, không liên quan số file tài liệu.

- **Mức A (đơn giản):** thư mục chia theo loại thành phần của framework (controller, service, repository, dto, entity…). Dùng khi service chủ yếu CRUD, logic mỏng.
- **Mức B (phân lớp):** domain / application / infrastructure / presentation; phụ thuộc hướng vào domain, domain không phụ thuộc framework hay ORM; interface ở domain hoặc application, hiện thực ở infrastructure. Dùng khi có quy tắc nghiệp vụ, trạng thái, tính toán; có tích hợp dịch vụ ngoài; hoặc sắp tách thành microservice.
- Nâng từ A lên B làm riêng từng service khi nó phình ra. `folder-structure.md` của service phải khớp mức đã chọn ở đây.

| Service | Đơn vị triển khai | Mức tổ chức code (A/B) | Cơ sở | Trách nhiệm | Database sở hữu | Chi tiết |
| --- | --- | --- | --- | --- | --- | --- |
| <tên> | <service riêng, module trong monolith> | <A hoặc B, định nghĩa ở trên> | <FR-xx, NFR-xx, D-xxx hoặc link: vì sao chọn mức này> | <một câu> | <db> | <[responsibility.md](services/service/responsibility.md)> |

## Ranh giới
<!-- required -->

Quy tắc giữ ranh giới giữa các service và quyết định đã chốt chúng.

| Quy tắc | Lý do | Quyết định |
| --- | --- | --- |
| <ví dụ: chỉ service sở hữu mới ghi vào bảng của nó> | <NFR-xx, C-xx hoặc vấn đề cần tránh> | <D-xxx> |

## Phụ thuộc giữa service
<!-- required -->

Không có vòng phụ thuộc đồng bộ. Cách gọi, thời gian chờ và thử lại ở [communication.md](communication.md).

| Service gọi | Service được gọi | Kiểu | Luồng |
| --- | --- | --- | --- |
| <tên> | <tên> | <đồng bộ, bất đồng bộ> | <FL-xx> |

## Tối ưu
<!-- required -->

Chỉ số của cả backend (Q2); chỉ số từng API nằm ở `api.md` của service.

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <p95 độ trễ đầu cuối của luồng chính> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |

## Scale, nâng cấp, bảo trì
<!-- required -->

Tổng hợp bằng link tới `scaling.md` của từng service, không chép lại (Q3).

| Service | Scale, nâng cấp, bảo trì |
| --- | --- |
| <tên> | <[scaling.md](services/service/scaling.md)> |

## Rủi ro
<!-- required -->

Rủi ro của cách chia service đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
