# Ma trận thiết bị

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Ma trận là cơ sở của ngân sách hiệu năng: [performance-budget.md](performance-budget.md) đo trên máy yếu nhất ở đây. Tỉ lệ người dùng lấy từ giả định `A-xx` (hoặc số liệu thật nếu đã có), không đoán. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Thiết bị hỗ trợ
<!-- required -->

| Lớp thiết bị | OS và phiên bản tối thiểu | Trình duyệt tối thiểu | RAM (GB) | Màn hình (px rộng) | Tỉ lệ người dùng | Cơ sở |
| --- | --- | --- | --- | --- | --- | --- |
| <máy yếu nhất, tầm trung, máy mạnh, máy tính bàn> | <OS, bản> | <trình duyệt, bản> | <số> | <số> | <phần trăm> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Điều kiện mạng
<!-- required -->

| Lớp mạng | Băng thông tải xuống (Mbps) | Độ trễ khứ hồi (ms) | Tỉ lệ người dùng | Cơ sở |
| --- | --- | --- | --- | --- |
| <3G chậm, 4G, wifi> | <số> | <số> | <phần trăm> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Thiết bị chuẩn để đo
<!-- required -->

Máy yếu nhất và điều kiện mạng xấu nhất mà dự án cam kết đáp ứng; ngân sách hiệu năng đo trên cấu hình này.

- Thiết bị: <một dòng trong bảng trên>
- Mạng: <một dòng trong bảng mạng>

## Không hỗ trợ
<!-- required -->

| Thiết bị hoặc trình duyệt | Hành vi khi gặp | Cơ sở |
| --- | --- | --- |
| <ví dụ: trình duyệt cũ hơn bản tối thiểu> | <thông báo, bản rút gọn, chặn> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <tỉ lệ người dùng nằm trong ma trận> | <phần trăm> | <NFR-xx> | <analytics, RUM> |

## Nâng cấp và bảo trì
<!-- required -->

| Việc | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <rà lại ma trận theo số liệu thật, bỏ hỗ trợ OS hoặc trình duyệt hết vòng đời> | <tháng, quý> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
