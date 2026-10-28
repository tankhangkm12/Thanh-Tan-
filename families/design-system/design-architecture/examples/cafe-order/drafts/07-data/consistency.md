# Nhất quán dữ liệu

## Mức nhất quán theo nghiệp vụ
<!-- required -->

| Nghiệp vụ hoặc dữ liệu | Mức | Cơ chế | Cửa sổ bất nhất tối đa (giây) | Cơ sở |
| --- | --- | --- | --- | --- |
| đặt đơn (FR-001) | mạnh | một giao dịch ghi đơn và các món | 0 | NFR-001 |
| xem trạng thái đơn (FR-002) | mạnh | đọc từ primary | 0 | NFR-001 |
| đổi trạng thái đơn (FR-003) | mạnh | câu cập nhật có điều kiện trên trạng thái hiện tại | 0 | NFR-001 |

## Giao dịch xuyên service hoặc xuyên kho
<!-- required -->

Không có: mọi thay đổi nằm gọn trong một database.

## Xung đột và thứ tự
<!-- required -->

| Tình huống | Cách xử lý |
| --- | --- |
| hai nhân viên cùng đổi trạng thái một đơn | câu cập nhật chỉ thành công khi trạng thái hiện tại còn như lúc đọc; bên chậm hơn nhận 409 theo mô hình lỗi |
| client gửi lại đơn khi mất phản hồi | khóa idempotency, xem [cross-cutting.md](../06-backend/cross-cutting.md) |

## Đối soát
<!-- required -->

Không có: chỉ một nguồn sự thật, bản standby được PostgreSQL nhân bản liên tục nên không có kho thứ hai để so sánh.

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| độ trễ nhân bản tới standby (p95) | 5 giây | NFR-002 | thống kê nhân bản của PostgreSQL |

## Rủi ro
<!-- required -->

Không có rủi ro nhất quán mới: một database, giao dịch trong một kho.
