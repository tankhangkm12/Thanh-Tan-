# <tên dự án>: kiến trúc

> Template của design-architecture, mục lục của `architecture/`. Mục có `<!-- required -->` là bắt buộc. Designer viết file này ở `drafts/README.md`; G10 chép nó cùng mọi phần, thiếu `README.md` thì `promote_drafts.py` từ chối. File này chỉ liệt kê và link, không định nghĩa ID nào và không chứa số liệu thiết kế. Link tới phần nào thì file đó phải tồn tại ở bản phát hành; phần hồ sơ dự án đã bỏ chỉ ghi tên, không link.

## Phiên bản và mức áp dụng
<!-- required -->

- Phiên bản: <vN, khớp mục mới nhất của [CHANGELOG.md](CHANGELOG.md)>
- Ngày phát hành: <YYYY-MM-DD>
- Mức áp dụng: <S, M, L hoặc XL>, theo [project-profile.md](00-context/project-profile.md)
- Phát hành khi người dùng duyệt: <nguyên văn, ví dụ "G10: duyệt">

## Mục lục
<!-- required -->

Mỗi phần có đúng một dòng, đủ 13 phần từ `00` đến `12`. Phần bỏ theo hồ sơ dự án ghi "bỏ" và lý do (Q8), không link.

| Phần | Nội dung | Áp dụng |
| --- | --- | --- |
| <[00-context](00-context/project-profile.md)> | <hồ sơ dự án, truy vết yêu cầu, NFR, ràng buộc, giả định, thuật ngữ> | <có, rút gọn, bỏ: lý do> |
| <01-system> | <bối cảnh, containers, kiểu kiến trúc, hệ thống ngoài> | <có, rút gọn, bỏ: lý do> |

## Cách đọc
<!-- required -->

Người đọc đi vào từ đâu theo vai trò.

| Vai trò | Bắt đầu từ | Rồi đọc |
| --- | --- | --- |
| <agent dev> | <[implementation-plan.md](12-roadmap/implementation-plan.md), gói của mình> | <tài liệu đầu vào của gói> |
| <designer> | <routing-navigation.md của app> | <authz-matrix.md nếu có> |
| <người vận hành> | <topology.md, observability.md> | <operations.md, backup-recovery.md> |

## Quy ước ID
<!-- required -->

Mọi file liên kết hai chiều với nhau qua ID. Mỗi loại ID được định nghĩa ở đúng một nơi.

| Tiền tố | Nghĩa | Định nghĩa ở |
| --- | --- | --- |
| `FR`, `NFR` | yêu cầu chức năng, phi chức năng | `00-context/` |
| `C`, `A` | ràng buộc, giả định | `00-context/constraints.md`, `00-context/assumptions.md` |
| `TC` | tiêu chí chọn công nghệ | `02-tech-stack/selection-criteria.md` |
| `FL` | luồng | `04-flows/` |
| `SCR` | màn hình (của designer) | tài liệu của designer, không định nghĩa ở đây |
| `SVC`, `API` | service, API | `06-backend/` |
| `EVT`, `TBL`, `BKT` | event, bảng, bucket | `07-data/` |
| `R` | rủi ro | `11-risks/risk-register.md` |

## Còn mở
<!-- required -->

Việc chưa xong hoặc câu hỏi còn treo khi phát hành; ghi "không có" nếu hết.

- <câu hỏi hoặc việc, nơi theo dõi>
