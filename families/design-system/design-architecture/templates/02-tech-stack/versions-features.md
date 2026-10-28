# Ma trận phiên bản và tính năng

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. `check_versions.py` đọc bảng có cột "Công nghệ": **chỉ giữ một bảng như vậy trong file này** (bảng phụ không được có cột tên "Công nghệ"). Mỗi công nghệ của [README.md](README.md) một dòng. Mọi dữ kiện kèm link nguồn chính thức; thiếu nguồn là lỗi chặn (Q4, Q5). Mỗi tham số thiết kế (số có đơn vị: thời gian chờ, giới hạn, ngưỡng, giờ bảo trì…) có ô "Cơ sở" hoặc "Cơ sở ước tính": ô đó chỉ tính là bằng chứng khi có ID (NFR, C, A, D, R, TC) hoặc link; chữ thuần ("kinh nghiệm team") thì `check_numbers.py` vẫn báo lỗi.

## Ma trận phiên bản
<!-- required -->

- Công nghệ: tên trước, vai trò sau " — " hoặc trong ngoặc.
- Phiên bản chốt: major.minor. Lớp third-party được thêm `YYYY-MM-DD` hoặc "SaaS, không phiên bản".
- Vòng đời: `ngày phát hành YYYY-MM-DD; hết hỗ trợ YYYY-MM-DD` kèm link trang vòng đời chính thức; hoặc "chưa công bố" kèm link; SaaS cần link changelog hoặc chính sách ngừng hỗ trợ.
- Rủi ro: link `[R-xx](../11-risks/risk-register.md#r-xx)`; bắt buộc khi hết hỗ trợ trong 12 tháng, ghi "không có" khi không.

| Công nghệ | Phiên bản chốt | Vòng đời (phát hành; hết hỗ trợ) | Tính năng dự án dựa vào (phiên bản tối thiểu) | Giới hạn và lỗi đã biết | Thay đổi phá vỡ ở bản lớn kế tiếp | Tương thích | Rủi ro |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <Tên — vai trò> | <major.minor; chính sách bản vá> | <YYYY-MM-DD; YYYY-MM-DD> [trang vòng đời](https://example.invalid/<đường dẫn>) | <tính năng (từ bản x.y)> | <giới hạn, link issue hoặc release note> | <ảnh hưởng khi nâng cấp> | <driver, SDK, lớp khác: bản tối thiểu> | [R-xx](../11-risks/risk-register.md#r-xx) |

## Chính sách bản vá
<!-- required -->

| Lớp | Cách nhận bản vá | Tần suất kiểm tra (ngày) | Người chịu trách nhiệm | Cơ sở |
| --- | --- | --- | --- | --- |
| <lớp> | <tự động / thủ công, kênh thông báo> | <số ngày> | <vai trò> | <NFR-xx, C-xx, A-xx, D-xxx, R-xx, TC-xx hoặc link> |
