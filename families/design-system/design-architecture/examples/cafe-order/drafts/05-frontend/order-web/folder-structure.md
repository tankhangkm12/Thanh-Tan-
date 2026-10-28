# Cấu trúc thư mục của app

## Cây thư mục
<!-- required -->

```
order-web/
├── src/
│   ├── presentation/   # route và màn hình, nối module với route
│   ├── application/    # ordering, tracking, staff, session
│   └── data/           # API client, cache, ánh xạ lỗi
├── public/             # file tĩnh không qua build
└── tests/
```

## Quy tắc ranh giới
<!-- required -->

| Quy tắc | Lý do | Cách bảo đảm |
| --- | --- | --- |
| lớp `data` không import từ `presentation` hay `application` | giữ hướng phụ thuộc ở [architecture.md](architecture.md) | lint chặn import ngược trong CI |
| module không import nội bộ của module khác | giữ ranh giới module | lint chặn import xuyên module |

## Quy ước đặt tên
<!-- required -->

- Thư mục và file: chữ thường, nối bằng dấu gạch ngang
- Nơi đặt kiểu dữ liệu khai báo theo hợp đồng API: `src/data/types`, viết tay theo [api.md](../../06-backend/services/order-service/api.md)
