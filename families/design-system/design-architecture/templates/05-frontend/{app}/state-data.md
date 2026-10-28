# State và lấy dữ liệu

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Chỉ quyết nơi giữ state và cách lấy dữ liệu; không quyết cách hiển thị (Q7). API nhắc bằng `API-xx`, không ghi đường dẫn thô; cột đầu của bảng không phải ID. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Phân loại state
<!-- required -->

| Loại state | Ví dụ | Giữ ở đâu | Vòng đời |
| --- | --- | --- | --- |
| <dữ liệu từ máy chủ, state giao diện cục bộ, state dùng chung, state trên URL> | <ví dụ> | <công cụ, vị trí> | <khi nào xóa> |

## Lấy dữ liệu và cache
<!-- required -->

| Dữ liệu | API | Thời gian coi là mới (giây) | Khi nào làm mới | Cơ sở |
| --- | --- | --- | --- | --- |
| <tên> | <API-xx> | <số> | <sau thao tác ghi nào, theo sự kiện nào> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Cập nhật lạc quan và xung đột
<!-- required -->

Thao tác nào cập nhật ngay trên client trước khi máy chủ trả lời, cách hoàn tác khi lỗi, cách xử lý hai nơi cùng sửa. Ghi "không dùng" nếu không có.

| Thao tác | Cách xử lý | Khi máy chủ từ chối |
| --- | --- | --- |
| <tên> | <ngay, chờ> | <hoàn tác, báo lỗi theo error model> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <số request mỗi lần vào màn hình> | <số> | <NFR-xx> | <công cụ, vị trí đo> |
| <bộ nhớ state tối đa (MB) ở thiết bị chuẩn> | <số> | <NFR-xx> | <công cụ, vị trí đo> |
