# Cấu trúc thư mục của service

## Cây thư mục
<!-- required -->

Mức tổ chức code của service này: B, theo [overview.md](../../overview.md).

```text
order-service/
├── src/domain/          # đơn, trạng thái đơn, quy tắc chuyển trạng thái
├── src/application/     # use case: đặt đơn, xem đơn, đổi trạng thái
├── src/infrastructure/  # truy cập order-db, phục vụ file tĩnh
└── src/presentation/    # xử lý request, xác thực, ánh xạ lỗi
```

## Quy ước
<!-- required -->

- Ranh giới module: phụ thuộc hướng vào domain; domain không import framework hay ORM, interface ở domain, hiện thực ở infrastructure
- Đặt tên: kebab-case cho file
- Chỗ đặt: API ở `presentation`, truy cập dữ liệu ở `infrastructure`, test cạnh file được test
