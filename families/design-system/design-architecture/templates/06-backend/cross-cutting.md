# Các mối quan tâm xuyên suốt

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Quy tắc dùng chung cho mọi service để `api.md` của từng service chỉ cần dẫn link. Phân quyền chi tiết theo vai trò ở [authz-matrix.md](../08-security/authz-matrix.md) (có từ mức M); giám sát và cảnh báo ở [observability.md](../09-infrastructure/observability.md). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Xác thực và phân quyền
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Cách xác thực | <token, phiên, mTLS giữa service> | |
| Nơi kiểm quyền | <gateway kiểm vai trò, service kiểm quyền trên dữ liệu> | |
| Thời hạn token truy cập (giây) | <số, khớp auth-session.md của app> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Nguồn danh tính | <dịch vụ đăng nhập trong nhà, bên ngoài> | |

## Mô hình lỗi
<!-- required -->

Mọi API trả lỗi theo một dạng; `api.md` và frontend dẫn tới đây.

| Trường | Ý nghĩa | Ví dụ giá trị |
| --- | --- | --- |
| <mã lỗi máy đọc được> | <phân loại lỗi> | <ví dụ> |
| <thông điệp> | <nội dung an toàn để hiển thị, không lộ chi tiết nội bộ> | <ví dụ> |
| <mã tương quan (correlation id)> | <dò log theo request> | <ví dụ> |

| Nhóm lỗi | Mã HTTP hoặc tương đương | Client có nên thử lại không |
| --- | --- | --- |
| <dữ liệu sai, chưa xác thực, không có quyền, không tìm thấy, xung đột, quá tần suất, lỗi máy chủ> | <mã> | <có, không> |

## Idempotency
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Thao tác cần idempotency | <ghi tạo mới, thanh toán…> | |
| Cách gửi khóa | <header, trường> | |
| Thời gian giữ khóa (giây) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| Khi trùng khóa nhưng khác nội dung | <từ chối theo mô hình lỗi> | |

## Ghi log và truy vết
<!-- required -->

| Mục | Giá trị | Cơ sở |
| --- | --- | --- |
| Định dạng log | <có cấu trúc, trường bắt buộc> | |
| Dữ liệu không được ghi | <mật khẩu, token, dữ liệu cá nhân> | |
| Truyền mã tương quan | <header, qua cả event> | |
| Thời gian giữ log (ngày) | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Giới hạn tần suất
<!-- required -->

| Đối tượng | Giới hạn (số + đơn vị) | Hành vi khi vượt | Cơ sở |
| --- | --- | --- | --- |
| <mỗi người dùng, mỗi IP, mỗi API> | <ví dụ: request mỗi giây> | <trả lỗi theo mô hình lỗi> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian cộng thêm do xác thực mỗi request (p95)> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <xoay khóa ký token, rà quy tắc giới hạn tần suất> | <tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
