# Cấu trúc thư mục của app

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Cấu trúc phải khớp [repo-structure.md](../../06-backend/repo-structure.md) (cách các repo hoặc package xếp cạnh nhau) và các module ở [architecture.md](architecture.md). Chỉ ranh giới mã; không có thư mục hay quy ước nào về giao diện nhìn thấy (Q7).

## Cây thư mục
<!-- required -->

```
<app>/
├── <thư mục>/    # <vai trò>
└── <thư mục>/    # <vai trò>
```

## Quy tắc ranh giới
<!-- required -->

| Quy tắc | Lý do | Cách bảo đảm |
| --- | --- | --- |
| <ví dụ: module không import trực tiếp nội bộ của module khác> | <giữ ranh giới ở architecture.md> | <lint, kiểm tra phụ thuộc trong CI> |

## Quy ước đặt tên
<!-- required -->

- Thư mục và file: <quy ước>
- Nơi đặt kiểu dữ liệu khai báo theo hợp đồng API: <đường dẫn, sinh từ `06-backend/contracts/` hay viết tay>
