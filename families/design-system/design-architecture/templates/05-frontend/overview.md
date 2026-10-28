# Frontend: tổng quan

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Phần frontend chỉ có kiến trúc kỹ thuật; màu, font, bố cục, khoảng cách, hình dáng component, hiệu ứng, nội dung chữ và thứ tự màn hình thuộc designer, không được quyết ở đây (Q7). Điều kiến trúc cần designer làm thêm thì ghi câu hỏi vào `questions.md`, không tự quyết phần nhìn. Mỗi app một thư mục `{app}/` cạnh file này. File này chỉ nhắc ID, không đặt `FR-`, `D-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Danh sách app
<!-- required -->

| App | Loại | Người dùng | Yêu cầu (FR) | Thư mục |
| --- | --- | --- | --- | --- |
| <tên, trùng tên thư mục> | <web, admin, mobile> | <nhóm người dùng> | <FR-xx> | <[app](app/architecture.md)> |

## Chiến lược render
<!-- required -->

| App | Chiến lược | Lý do | Quyết định |
| --- | --- | --- | --- |
| <tên> | <CSR, SSR, SSG, kết hợp theo route> | <NFR-xx hoặc C-xx: ví dụ thời gian tải đầu, SEO, thiết bị yếu> | <D-xxx> |

## Dùng chung giữa các app
<!-- required -->

Thư viện, hợp đồng API, gói mã dùng chung và cách quản lý phiên bản; ghi "không có" nếu chỉ có một app.

| Thành phần dùng chung | Dùng bởi | Cách phát hành | Quy tắc đổi |
| --- | --- | --- | --- |
| <tên> | <app> | <monorepo, gói riêng> | <ai duyệt, tương thích ngược> |

## Nguồn từ designer
<!-- required -->

- Tài liệu màn hình: <đường dẫn tới `inputs/ui-design/` hoặc nơi designer giữ SCR-xx>
- Điều kiến trúc cần designer bổ sung: <CH-xxx trong questions.md, hoặc "không có">

## Rủi ro
<!-- required -->

Rủi ro frontend (thiết bị yếu, hiệu năng, phụ thuộc thư viện) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
