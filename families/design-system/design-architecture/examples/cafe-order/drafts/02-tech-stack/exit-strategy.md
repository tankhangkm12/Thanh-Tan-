# Chiến lược thoát

## Đường thay thế
<!-- required -->

| Công nghệ | Mức khóa chặt | Phương án thay thế | Chi phí chuyển (người-ngày) | Dữ liệu cần chuyển |
| --- | --- | --- | --- | --- |
| Node.js | thấp: mã chuẩn, không dùng API riêng | Deno hoặc Bun | 10 | không có |
| React | vừa: mã giao diện viết theo hook | Vue | 25 | không có |
| Vite | thấp: cấu hình ngắn | webpack | 5 | không có |
| Ubuntu Server | thấp: gói và cấu hình chuẩn | Debian | 5 | không có |
| GitHub Actions | thấp: workflow là tệp YAML ngắn | GitLab CI | 5 | không có |
| PostgreSQL | vừa: dùng SQL chuẩn | MySQL | 20 | toàn bộ bảng, xem [data-sizing.md](../03-capacity/data-sizing.md) |

## Điều kiện kích hoạt
<!-- required -->

| Công nghệ | Điều kiện (số + đơn vị) | Cách phát hiện | Rủi ro | Cơ sở |
| --- | --- | --- | --- | --- |
| Node.js | hết hỗ trợ trong 6 tháng | lịch trong versions-features.md | không có | [versions-features.md](versions-features.md) |
| React và Vite | bản chốt không còn bản vá bảo mật trong 6 tháng | theo dõi trang chính sách trong versions-features.md | không có | [versions-features.md](versions-features.md) |
| Ubuntu Server | hết hỗ trợ trong 12 tháng | lịch trong versions-features.md | không có | [versions-features.md](versions-features.md) |
| GitHub Actions | số phút CI dùng trên 1.500 phút mỗi tháng | báo cáo sử dụng của GitHub | không có | [giới hạn dùng](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) |
| PostgreSQL | chi phí lưu trữ trên 100 USD mỗi tháng | cost-model.md | không có | C-001 |
