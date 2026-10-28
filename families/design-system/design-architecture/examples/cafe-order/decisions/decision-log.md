# Nhật ký quyết định

| ID | Quyết định | Trạng thái |
| --- | --- | --- |
| D-001 | Kiểu kiến trúc: một service backend, một database | đã quyết |
| D-002 | Stack: Node.js cho backend, PostgreSQL cho dữ liệu | đã quyết |
| D-003 | Frontend: React và Vite, ứng dụng một trang (CSR), file tĩnh do order-service phục vụ | đã quyết |
| D-004 | Hạ tầng: hai máy ảo Ubuntu Server 24.04 LTS, mỗi máy chạy order-service; PostgreSQL primary và standby nằm cùng hai máy đó, vì tải đỉnh thấp (workload-model.md), ngân sách 300 USD (C-001) và team 3 người (C-002); năng lực mỗi máy được đo khi có PostgreSQL chạy cùng | đã quyết |
| D-005 | CI/CD: GitHub Actions | đã quyết |
