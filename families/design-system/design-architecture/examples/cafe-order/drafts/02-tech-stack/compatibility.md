# Tương thích giữa các lớp

## Ma trận tương thích
<!-- required -->

| Cặp (A ↔ B) | Phiên bản A | Phiên bản B | Kết quả | Bằng chứng |
| --- | --- | --- | --- | --- |
| backend ↔ data | Node.js 24.0 | PostgreSQL 16.4 | tương thích | https://example.com/compat/node-pg |
| infrastructure ↔ backend | Ubuntu Server 24.04 | Node.js 24.0 | tương thích | https://nodejs.org/en/about/previous-releases |
| infrastructure ↔ data | Ubuntu Server 24.04 | PostgreSQL 16.4 | tương thích | https://www.postgresql.org/download/linux/ubuntu/ |
| frontend ↔ backend | Vite 7.3 | Node.js 24.0 | tương thích (Vite chạy trên Node.js 20.19 trở lên) | https://vite.dev/guide/ |

## Xung đột và cách xử lý
<!-- required -->

Không có xung đột, kiểm tra ngày 2026-10-12.

| Xung đột | Cách xử lý | Rủi ro |
| --- | --- | --- |
| không có | không cần | không có |
