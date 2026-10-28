# Lớp frontend

## Lựa chọn
<!-- required -->

| Công nghệ | Phiên bản | Vai trò trong dự án | Quyết định |
| --- | --- | --- | --- |
| React — thư viện dựng ứng dụng order-web | 19.2 | dựng order-web | D-003 |
| Vite — công cụ build order-web | 7.3 | build và chia gói mã order-web | D-003 |

## Truy vết tiêu chí
<!-- required -->

| Điều lớp phải đáp ứng | TC | Cách công nghệ đáp ứng | Nguồn |
| --- | --- | --- | --- |
| Còn hỗ trợ đến hết mốc 3y | TC-001 | xem [versions-features.md](../versions-features.md) | https://react.dev/versions |
| Team học được trước hạn | TC-002 | xem [team-readiness.md](../team-readiness.md) | https://react.dev/learn |
| Chi phí nằm trong ngân sách | TC-003 | giấy phép MIT, xem [cost-licensing.md](../cost-licensing.md) | https://github.com/facebook/react/blob/main/LICENSE |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| JS tải ban đầu | 170 KB nén | NFR-001 | báo cáo kích thước gói của Vite, xem [performance-budget.md](../../05-frontend/performance-budget.md) |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Công nghệ | Đơn vị scale | Giới hạn (số + đơn vị) | Ngưỡng lên giai đoạn sau | Đường nâng cấp | Bảo trì mỗi tháng (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- |
| React và Vite | file tĩnh phục vụ cùng order-service | theo [compute-sizing.md](../../03-capacity/compute-sizing.md) | file tĩnh chiếm trên 50% băng thông ra thì đổi sang CDN | bản chính kế tiếp, đọc danh sách thay đổi phá vỡ trước | 2 giờ | C-002 |

## Rủi ro
<!-- required -->

Rủi ro hiệu năng trên thiết bị yếu đã khai trong [sổ rủi ro](../../11-risks/risk-register.md): R-001.
