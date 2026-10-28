# Các mối quan tâm xuyên suốt

## Xác thực và phân quyền
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cách xác thực | khách: mã tra cứu có chữ ký HMAC (id đơn kèm chữ ký, không lưu trong database); nhân viên: khóa nhân viên trong header mỗi request | [OWASP Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) |
| Nơi kiểm quyền | order-service kiểm trong từng API: API-create-order mở cho mọi người, API-get-order cần mã tra cứu hợp lệ hoặc khóa nhân viên, API-update-status cần khóa nhân viên | |
| Thời hạn token truy cập (giây) | không áp dụng, vì không có token truy cập; khớp [auth-session.md](../05-frontend/order-web/auth-session.md) | |
| Nguồn danh tính | không có tài khoản người dùng; khóa nhân viên do quán cấp, order-service chỉ giữ bản băm trong cấu hình bí mật, mỗi nhân viên một khóa | [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) |

## Mô hình lỗi
<!-- required -->

| Trường | Ý nghĩa | Ví dụ giá trị |
| --- | --- | --- |
| code | phân loại lỗi, máy đọc được | `ORDER_NOT_FOUND` |
| message | nội dung an toàn để hiển thị, không lộ chi tiết nội bộ | `Không tìm thấy đơn` |
| correlationId | dò log theo request | `7f3a9c1e` |

| Nhóm lỗi | Mã HTTP hoặc tương đương | Client có nên thử lại không |
| --- | --- | --- |
| dữ liệu sai | 400 | không |
| chưa xác thực | 401 | không |
| không có quyền | 403 | không |
| không tìm thấy | 404 | không |
| xung đột trạng thái | 409 | không |
| quá tần suất | 429 | có, sau thời gian chờ |
| lỗi máy chủ | 500 | có, với thao tác idempotent |

## Idempotency
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Thao tác cần idempotency | API-create-order | |
| Cách gửi khóa | header `Idempotency-Key`, giá trị do client sinh | |
| Thời gian giữ khóa (giây) | 86.400, khớp [api.md](services/order-service/api.md) | D-001 |
| Khi trùng khóa nhưng khác nội dung | từ chối 409 theo mô hình lỗi | |

## Ghi log và truy vết
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Định dạng log | JSON mỗi dòng: thời điểm, mức, correlationId, API, mã HTTP, thời gian xử lý | |
| Dữ liệu không được ghi | khóa nhân viên, chữ ký của mã tra cứu, ghi chú đơn | |
| Truyền mã tương quan | header `X-Correlation-Id`, sinh mới nếu client không gửi | |
| Thời gian giữ log (ngày) | 30 ngày | C-001 |

## Giới hạn tần suất
<!-- required -->

| Đối tượng | Giới hạn (số + đơn vị) | Hành vi khi vượt | Cơ sở |
| --- | --- | --- | --- |
| mỗi IP, API-create-order và API-get-order | 5 request/giây | trả 429 theo mô hình lỗi | NFR-003 |
| mỗi khóa nhân viên, API-update-status | 10 request/giây | trả 429 theo mô hình lỗi | NFR-003 |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| thời gian cộng thêm do kiểm xác thực mỗi request (p95) | 5 ms | NFR-001 | log truy cập của order-service |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| xoay khóa nhân viên mỗi 90 ngày, rà quy tắc giới hạn tần suất | mỗi tháng | 1 giờ | C-002 |
