# Ma trận phân quyền

## Vai trò
<!-- required -->

| Vai trò | Ai giữ vai trò này | Yêu cầu (FR) |
| --- | --- | --- |
| khách | bất kỳ ai đặt hoặc xem đơn, không có tài khoản; chủ đơn là người giữ mã tra cứu | FR-001, FR-002 |
| nhân viên | nhân viên quán, mỗi người một khóa nhân viên | FR-003 |

## Ma trận hành động
<!-- required -->

| Hành động | API | Màn hình (SCR) | khách | nhân viên |
| --- | --- | --- | --- | --- |
| đặt đơn | API-create-order | SCR-order-form | được | được |
| xem đơn bằng mã tra cứu | API-get-order | SCR-order-status | có điều kiện | được |
| mở đơn bất kỳ theo mã đơn thường | API-get-order | SCR-staff-update | không | được |
| đổi trạng thái đơn | API-update-status | SCR-staff-update | không | được |

## Quy tắc theo dữ liệu
<!-- required -->

| Quy tắc | Áp dụng cho | Cách kiểm | Nguồn |
| --- | --- | --- | --- |
| khách chỉ xem đơn khi mã tra cứu có chữ ký hợp lệ; mã sai trả lỗi không tìm thấy, không phân biệt với đơn không tồn tại | xem đơn bằng mã tra cứu | order-service tính lại chữ ký HMAC và so sánh, xem [cross-cutting.md](../06-backend/cross-cutting.md) | FR-002 |
| chỉ khóa nhân viên đổi được trạng thái, và chỉ đi tiến | đổi trạng thái đơn | kiểm khóa ở presentation, kiểm thứ tự trạng thái ở domain | FR-003 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian kiểm quyền mỗi request (p95) | 5 ms | NFR-001 | log truy cập của order-service |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| rà danh sách khóa nhân viên, gỡ khóa người đã rời | mỗi tháng | 1 giờ | C-002 |
