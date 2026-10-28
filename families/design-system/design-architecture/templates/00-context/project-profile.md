# Hồ sơ dự án

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc: `check_profile.py` báo lỗi nếu thiếu, để trống hoặc còn nguyên nội dung mẫu. Thay mọi `<…>`. File này quyết định phần nào của `architecture/` được phép vắng (Q8).

## Mức áp dụng
<!-- required -->

Mức: S|M|L|XL

Lý do chọn mức: <vì sao hồ sơ bên dưới ứng với mức này; dẫn số trong bảng "Hồ sơ">

Mốc tính số liệu của mức (S: ra mắt, 1 năm; M: thêm 3 năm; L: thêm 5 năm; XL: thêm đỉnh tải): <liệt kê mốc>

## Hồ sơ
<!-- required -->

| Mục | Giá trị (kèm đơn vị) | Nguồn |
| --- | --- | --- |
| Quy mô người dùng | <số người dùng ra mắt và 1 năm> | <BA hoặc A-xx> |
| Dữ liệu dự kiến | <dung lượng hoặc số dòng/ngày> | <BA hoặc A-xx> |
| Mức độ quan trọng | <mất dịch vụ thì thiệt hại gì, bao nhiêu mỗi giờ> | <BA> |
| Số người trong team | <số người> | <BA hoặc người dùng> |
| Ngân sách | <số tiền mỗi tháng> | <BA hoặc người dùng> |
| Thời hạn | <ngày ra mắt> | <BA hoặc người dùng> |
| Tuân thủ | <quy định áp dụng, hoặc "không có"> | <BA> |

## Phần áp dụng
<!-- required -->

Mỗi phần `00-context` … `12-roadmap` đúng một dòng; giá trị Áp dụng là `có`, `rút gọn` hoặc `bỏ`. Phần chỉ giữ một phần thì thêm dòng cấp file (ví dụ `01-system/containers.md`); dòng dài đường dẫn hơn thắng.

| Phần | Áp dụng | Lý do (Q8) |
| --- | --- | --- |
| 00-context | có | <lý do> |
| 01-system | có | <lý do> |
| 02-tech-stack | có | <lý do> |
| 03-capacity | có | <lý do> |
| 04-flows | có | <lý do> |
| 05-frontend | có | <lý do> |
| 06-backend | có | <lý do> |
| 07-data | có | <lý do> |
| 08-security | có | <lý do> |
| 09-infrastructure | có | <lý do> |
| 10-process | có | <lý do> |
| 11-risks | có | <lý do> |
| 12-roadmap | có | <lý do> |
