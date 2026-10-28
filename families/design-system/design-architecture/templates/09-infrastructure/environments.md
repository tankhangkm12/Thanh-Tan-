# Môi trường

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Chi phí môi trường ngoài production dẫn link [cost-model.md](../03-capacity/cost-model.md) nếu đã tính ở đó; khoản không có ở đó ghi kèm link nguồn giá và ngày tra cứu. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Danh sách môi trường
<!-- required -->

| Môi trường | Mục đích | Cỡ so với production (phần trăm) | Dữ liệu | Ai truy cập | Cơ sở |
| --- | --- | --- | --- | --- | --- |
| <dev, staging, production> | <phát triển, kiểm thử trước khi phát hành, chạy thật> | <số> | <giả lập, ẩn danh, thật> | <vai trò> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Quy tắc dữ liệu giữa môi trường
<!-- required -->

- Dữ liệu thật ở môi trường ngoài production: <không dùng, hoặc chỉ khi ẩn danh theo cách nào>
- Sao chép dữ liệu production về môi trường khác: <cấm, hoặc quy trình và người duyệt>

## Cấu hình và bí mật theo môi trường
<!-- required -->

| Mục | Cách quản lý |
| --- | --- |
| Cấu hình khác nhau giữa môi trường | <biến môi trường, tệp cấu hình theo môi trường> |
| Bí mật | <kho bí mật riêng mỗi môi trường, theo secrets-compliance.md> |
| Khác biệt với production được phép | <liệt kê, và rủi ro khi lệch> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian dựng một môi trường mới> | <số + đơn vị> | <NFR-xx> | <CI, nhật ký dựng> |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <dọn môi trường tạm, đồng bộ cấu hình với production> | <tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
