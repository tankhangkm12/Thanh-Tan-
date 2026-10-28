# Kiến trúc của app

> Template của design-architecture, một thư mục mỗi app (`05-frontend/<app>/`: web, admin, mobile…). Mục có `<!-- required -->` là bắt buộc. Chỉ kiến trúc kỹ thuật: lớp, module, luồng dữ liệu; không quyết màu, bố cục, hình dáng component hay hiệu ứng (Q7). Màn hình nhắc bằng `SCR-xx` lấy từ designer. File này chỉ nhắc ID, không đặt `SCR-`, `API-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Lớp
<!-- required -->

| Lớp | Trách nhiệm | Được phụ thuộc vào | Không được phụ thuộc vào |
| --- | --- | --- | --- |
| <ví dụ: giao diện, ứng dụng, miền, hạ tầng> | <việc của lớp> | <lớp> | <lớp> |

## Module
<!-- required -->

| Module | Trách nhiệm | Màn hình (SCR) | Dữ liệu sở hữu | Yêu cầu (FR) |
| --- | --- | --- | --- | --- |
| <tên> | <việc> | <SCR-xx, …> | <loại state, cache key> | <FR-xx> |

## Luồng dữ liệu
<!-- required -->

```mermaid
flowchart LR
  screen[<màn hình>] --> module[<module>] --> data[<lớp dữ liệu>] --> api[<API-xx>]
```

## Đo thực tế và báo lỗi
<!-- required -->

Đo người dùng thật (RUM) và báo lỗi client; số liệu mục tiêu nằm ở [performance-budget.md](../performance-budget.md).

| Việc | Công cụ | Dữ liệu thu | Tần suất lấy mẫu (phần trăm) | Cơ sở |
| --- | --- | --- | --- | --- |
| <RUM, báo lỗi, ghi crash> | <công cụ> | <chỉ số, loại lỗi, không gồm dữ liệu cá nhân> | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Rủi ro
<!-- required -->

Rủi ro của app (phụ thuộc thư viện, thiết bị yếu) đã khai trong [sổ rủi ro](../../11-risks/risk-register.md): <R-xx, …>.
