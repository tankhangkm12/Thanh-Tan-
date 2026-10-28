# Ngân sách hiệu năng

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Ngân sách là số. Dùng ngưỡng "tốt" của Core Web Vitals làm mức sàn (LCP ≤ 2,5 s, INP ≤ 200 ms, CLS ≤ 0,1) rồi siết thêm theo hồ sơ dự án và thiết bị chuẩn ở [device-matrix.md](device-matrix.md). Chỉ ghi giới hạn kỹ thuật (KB, ms, MB); không quyết gì về hình thức giao diện (Q7). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Ngân sách tài nguyên
<!-- required -->

| App | Tài nguyên | Giới hạn (số + đơn vị) | Cơ sở |
| --- | --- | --- | --- |
| <tên> | <JS tải ban đầu, JS mỗi route, ảnh, font, kích thước app mobile> | <ví dụ: KB nén> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

Chỉ số trải nghiệm mục tiêu, đo trên thiết bị chuẩn (Q2). Mức sàn là ngưỡng "tốt" của Core Web Vitals; mục tiêu dự án bằng hoặc chặt hơn.

| App | Chỉ số | Mức sàn | Mục tiêu dự án | NFR | Thiết bị chuẩn |
| --- | --- | --- | --- | --- | --- |
| <tên> | <LCP, INP, CLS, bộ nhớ tối đa, thời gian khởi động app mobile> | <số + đơn vị> | <số + đơn vị> | <NFR-xx> | <link device-matrix.md> |

## Cách đo
<!-- required -->

| Loại đo | Công cụ | Khi nào chạy | Ngưỡng lỗi |
| --- | --- | --- | --- |
| <đo trong phòng thí nghiệm, đo thực tế người dùng (RUM)> | <công cụ> | <mỗi lần build, liên tục> | <số làm hỏng build hoặc bật cảnh báo> |

## Thi hành
<!-- required -->

Ngân sách chỉ có nghĩa khi bị chặn tự động: bước CI nào so với bảng "Ngân sách tài nguyên" và hành vi khi vượt (chặn merge, cảnh báo). Chi tiết pipeline ở `build-delivery.md` của từng app và [ci-cd.md](../09-infrastructure/ci-cd.md).

- Bước CI: <tên bước>
- Khi vượt: <chặn, cảnh báo>

## Rủi ro
<!-- required -->

Rủi ro hiệu năng (thiết bị yếu, thư viện nặng) đã khai trong [sổ rủi ro](../11-risks/risk-register.md): <R-xx, …>.
