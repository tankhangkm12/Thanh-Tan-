# Lộ trình nâng cấp theo ngày hết hỗ trợ

## Lộ trình
<!-- required -->

Sắp theo ngày hết hỗ trợ gần nhất trước. React, Vite và GitHub Actions chưa công bố ngày hết hỗ trợ nên không có hạn ở đây; chúng nhận bản vá theo [maintenance.md](../10-process/maintenance.md).

| Công nghệ | Dòng trong ma trận | Bản kế tiếp | Hạn bắt đầu (YYYY-MM-DD) | Hạn xong (YYYY-MM-DD) | Thay đổi phá vỡ cần xử lý | Công sức ước tính (giờ) | Cơ sở ước tính |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Node.js | [versions-features.md](../02-tech-stack/versions-features.md) | 26.0 | 2027-10-31 | 2028-03-31 | [ghi chú phát hành](https://nodejs.org/en/blog/release/v26.0.0) | 16 | C-002 |
| PostgreSQL | [versions-features.md](../02-tech-stack/versions-features.md) | 17.0 | 2028-05-09 | 2028-10-09 | [ghi chú phát hành](https://www.postgresql.org/docs/release/17.0/) | 24 | C-002 |
| Ubuntu Server | [versions-features.md](../02-tech-stack/versions-features.md) | 26.04 | 2028-11-01 | 2029-04-01 | [vòng đời](https://ubuntu.com/about/release-cycle) | 20 | C-002 |

## Phụ thuộc giữa các lần nâng cấp
<!-- required -->

| Nâng cấp | Phải làm sau | Lý do |
| --- | --- | --- |
| Node.js | không | chạy được trên Ubuntu Server hiện tại, theo [compatibility.md](../02-tech-stack/compatibility.md) |
| PostgreSQL | không | chạy được trên Ubuntu Server hiện tại, theo [compatibility.md](../02-tech-stack/compatibility.md) |
| Ubuntu Server | Node.js và PostgreSQL | hai thành phần phải được kiểm trên bản hệ điều hành mới, theo [compatibility.md](../02-tech-stack/compatibility.md) |

## Rủi ro
<!-- required -->

Không có rủi ro nâng cấp mới: không thành phần nào hết hỗ trợ trong 12 tháng tới (xem [versions-features.md](../02-tech-stack/versions-features.md)).
