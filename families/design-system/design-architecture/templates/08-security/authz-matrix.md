# Ma trận phân quyền

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Mức S bỏ cả phần 08-security. Cơ chế xác thực và nơi kiểm quyền ở [cross-cutting.md](../06-backend/cross-cutting.md); phiên đăng nhập phía client ở `auth-session.md` của từng app. File này chỉ nhắc ID (`API-xx`, `SCR-xx`, `FR-xx`), không định nghĩa: cột đầu là tên hành động, không phải ID. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Vai trò
<!-- required -->

| Vai trò | Ai giữ vai trò này | Yêu cầu (FR) |
| --- | --- | --- |
| <tên> | <nhóm người dùng, hệ thống> | <FR-xx> |

## Ma trận hành động
<!-- required -->

Mỗi hàng là một hành động nghiệp vụ; mỗi ô là `được`, `không`, hoặc `có điều kiện` (điều kiện ghi ở mục "Quy tắc theo dữ liệu"). Mọi API của dự án nằm trong ít nhất một hàng.

| Hành động | API | Màn hình (SCR) | <vai trò 1> | <vai trò 2> |
| --- | --- | --- | --- | --- |
| <hành động> | <API-xx> | <SCR-xx> | <được, không, có điều kiện> | <được, không, có điều kiện> |

## Quy tắc theo dữ liệu
<!-- required -->

Quyền phụ thuộc chủ sở hữu hoặc trạng thái của dữ liệu (ví dụ chỉ xem đơn của chính mình).

| Quy tắc | Áp dụng cho | Cách kiểm | Nguồn |
| --- | --- | --- | --- |
| <quy tắc> | <hành động, TBL-xx> | <điều kiện ở tầng service, ở truy vấn> | <FR-xx, NFR-xx hoặc C-xx> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <thời gian kiểm quyền mỗi request (p95)> | <số + đơn vị> | <NFR-xx> | <công cụ, vị trí đo> |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <rà quyền còn thừa, gỡ quyền người đã rời> | <tháng, quý> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
