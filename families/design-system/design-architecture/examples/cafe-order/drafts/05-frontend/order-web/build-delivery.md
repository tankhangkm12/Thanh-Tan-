# Build và phân phối

## Build
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Công cụ build | Vite 7.3 (xem [versions-features.md](../../02-tech-stack/versions-features.md)) | |
| Chia gói mã (code splitting) | theo route | |
| Loại bỏ mã thừa, nén | tree-shaking và minify khi build; nén Brotli khi phục vụ | |
| Kích thước gói tối đa mỗi route (KB) | 60 KB nén, khớp [performance-budget.md](../performance-budget.md) | NFR-001 |

## Phân phối
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Nơi phục vụ | file tĩnh trong thư mục build, do order-service phục vụ; không có CDN riêng | C-001 |
| Cache asset | tên file có hash, giữ 31.536.000 giây; trang vào (index) không cache | [MDN Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control) |
| Ảnh theo kích thước thiết bị | không có ảnh nội dung trong app này | |
| Cập nhật cho người dùng đang mở bản cũ | tải lại trang khi API báo phiên bản client lỗi thời | |
| Rollback | triển khai lại bản build trước cùng với order-service, trong 10 phút | NFR-002 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| tỉ lệ trúng cache của file tĩnh có hash | 90% | NFR-001 | log truy cập của order-service |
| thời gian build đầy đủ | 5 phút | NFR-002 | CI |

## Scale, nâng cấp, bảo trì
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Scale phân phối | file tĩnh đi cùng các instance order-service, theo [compute-sizing.md](../../03-capacity/compute-sizing.md); đổi sang CDN khi file tĩnh chiếm trên 50% băng thông ra | NFR-003 |
| Ngày hết hỗ trợ gần nhất của framework | chưa công bố, xem [versions-features.md](../../02-tech-stack/versions-features.md) | |
| Đường nâng cấp framework | theo bản chính kế tiếp của React và Vite, đọc danh sách thay đổi phá vỡ trước | |
| Cập nhật thư viện phụ thuộc | mỗi 30 ngày, kiểm lỗ hổng bằng công cụ audit của trình quản lý gói | C-002 |
| Bảo trì mỗi tháng (giờ) | 2 | C-002 |
