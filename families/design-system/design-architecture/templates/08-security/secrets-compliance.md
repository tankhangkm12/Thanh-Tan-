# Bí mật, mã hóa và tuân thủ

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Yêu cầu tuân thủ lấy từ ràng buộc `C-xx` ở `constraints.md`; không có quy định riêng thì ghi rõ "không có" kèm nguồn. Thời gian giữ dữ liệu khớp `partitioning-retention.md` và `object-storage.md`. File này chỉ nhắc ID, không đặt `C-`, `TBL-`… ở ô đầu dòng bảng. Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Quản lý bí mật
<!-- required -->

| Loại bí mật | Nơi lưu | Ai và gì được đọc | Chu kỳ xoay (ngày) | Cơ sở |
| --- | --- | --- | --- | --- |
| <khóa API, mật khẩu database, khóa ký token> | <kho bí mật, biến môi trường được mã hóa> | <service, người vận hành> | <số> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

Bí mật không nằm trong mã nguồn, log hay ảnh container: <cách bảo đảm, ví dụ quét bí mật trong CI>.

## Mã hóa
<!-- required -->

| Phạm vi | Cách mã hóa | Quản lý khóa | Cơ sở |
| --- | --- | --- | --- |
| <khi truyền> | <giao thức, phiên bản tối thiểu> | <ai giữ, xoay khi nào> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
| <khi lưu: database, object storage, sao lưu> | <thuật toán, mức lưu> | <ai giữ, xoay khi nào> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Dữ liệu cá nhân
<!-- required -->

Ghi "không lưu dữ liệu cá nhân" kèm nguồn nếu đúng như vậy.

| Loại dữ liệu | Nơi lưu | Thời gian giữ (ngày) | Cách xóa hoặc ẩn danh | Cơ sở |
| --- | --- | --- | --- | --- |
| <loại> | <TBL-xx, BKT-xx> | <số> | <khi hết hạn, khi người dùng yêu cầu> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tuân thủ
<!-- required -->

| Quy định hoặc chuẩn | Yêu cầu cụ thể | Biện pháp | Nguồn |
| --- | --- | --- | --- |
| <tên> | <điều khoản áp dụng cho dự án> | <nơi trong kiến trúc đáp ứng> | <C-xx và link văn bản chính thức> |

## Vá lỗi và nâng cấp bảo mật
<!-- required -->

| Mức nghiêm trọng của lỗ hổng | Hạn vá (ngày) | Cách phát hiện | Cơ sở |
| --- | --- | --- | --- |
| <nghiêm trọng, cao, trung bình> | <số> | <quét phụ thuộc, bản tin bảo mật của nhà cung cấp> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |

## Tối ưu
<!-- required -->

| Chỉ số | Mục tiêu (số + đơn vị) | NFR | Cách đo |
| --- | --- | --- | --- |
| <tỉ lệ bí mật xoay đúng hạn> | <phần trăm> | <NFR-xx> | <báo cáo kho bí mật> |
| <thời gian từ lúc có bản vá đến lúc triển khai (p95)> | <số + đơn vị> | <NFR-xx> | <CI, ghi nhận lỗ hổng> |

## Bảo trì
<!-- required -->

| Việc định kỳ | Tần suất | Giờ mỗi tháng | Cơ sở ước tính |
| --- | --- | --- | --- |
| <xoay bí mật, vá phụ thuộc, rà chứng chỉ hết hạn> | <tuần, tháng> | <giờ> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
