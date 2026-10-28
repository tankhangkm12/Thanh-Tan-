# Frontend: tổng quan

## Danh sách app
<!-- required -->

| App | Loại | Người dùng | Yêu cầu (FR) | Thư mục |
| --- | --- | --- | --- | --- |
| order-web | web | khách đặt món mang đi và nhân viên quán | FR-001, FR-002, FR-003 | [order-web](order-web/architecture.md) |

## Chiến lược render
<!-- required -->

| App | Chiến lược | Lý do | Quyết định |
| --- | --- | --- | --- |
| order-web | CSR (ứng dụng một trang, file tĩnh) | app chỉ phục vụ đặt và theo dõi đơn đã có mã, không cần SEO; không có máy chủ render để team 3 người (C-002) phải vận hành, và file tĩnh không thêm chi phí hạ tầng (C-001) | D-003 |

## Dùng chung giữa các app
<!-- required -->

Không có: dự án chỉ có một app.

## Nguồn từ designer
<!-- required -->

- Tài liệu màn hình: `inputs/ui-design/screens.md` (SCR-xx do designer giữ)
- Điều kiến trúc cần designer bổ sung: không có

## Rủi ro
<!-- required -->

Rủi ro hiệu năng trên thiết bị chuẩn của [device-matrix.md](device-matrix.md) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): R-001.
