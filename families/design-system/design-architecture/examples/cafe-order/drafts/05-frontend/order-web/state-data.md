# State và lấy dữ liệu

## Phân loại state
<!-- required -->

| Loại state | Ví dụ | Giữ ở đâu | Vòng đời |
| --- | --- | --- | --- |
| dữ liệu từ máy chủ | đơn và trạng thái đơn | cache truy vấn trong lớp truy cập dữ liệu, dùng `fetch` có sẵn của trình duyệt | xóa khi nhân viên thoát |
| state giao diện cục bộ | giỏ chưa gửi | state của component | xóa khi rời `/orders/new` hoặc gửi xong |
| state dùng chung | khóa nhân viên | context của module session | xóa khi nhân viên thoát hoặc đóng tab |
| state trên URL | mã đơn | tham số route | theo URL |

## Lấy dữ liệu và cache
<!-- required -->

| Dữ liệu | API | Thời gian coi là mới (giây) | Khi nào làm mới | Cơ sở |
| --- | --- | --- | --- | --- |
| đơn ở SCR-order-status | API-get-order | 10 | hết thời gian mới khi màn hình còn mở, và sau khi nhân viên đổi trạng thái | NFR-003 |
| đơn ở SCR-staff-update | API-get-order | 0 | mỗi lần mở đơn và sau API-update-status | NFR-003 |

## Cập nhật lạc quan và xung đột
<!-- required -->

Không dùng cập nhật lạc quan.

| Thao tác | Cách xử lý | Khi máy chủ từ chối |
| --- | --- | --- |
| đặt đơn | chờ máy chủ trả mã đơn | báo lỗi theo error model, giữ giỏ |
| đổi trạng thái đơn | chờ máy chủ trả lời | báo lỗi theo error model, giữ trạng thái cũ |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| số request mỗi lần vào SCR-order-status | 1 | NFR-001 | log truy cập của order-service |
| bộ nhớ state tối đa ở thiết bị chuẩn | 5 MB | NFR-001 | công cụ hiệu năng của trình duyệt |
