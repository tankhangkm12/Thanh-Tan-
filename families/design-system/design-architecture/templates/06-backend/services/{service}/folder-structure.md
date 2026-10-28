# Cấu trúc thư mục của service

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Cây mã nguồn của service; quy ước chung cho cả repo ở [repo-structure.md](../../repo-structure.md). Cây phải khớp mức tổ chức code (A hoặc B) đã ghi cho service này ở [overview.md](../../overview.md): mức A chia thư mục theo loại thành phần của framework; mức B chia domain / application / infrastructure / presentation, domain không phụ thuộc framework hay ORM. Nâng A lên B thì cập nhật cả hai nơi.

## Cây thư mục
<!-- required -->

Mức tổ chức code của service này: <A | B>, theo overview.md.

```text
<service>/
├── <thư mục>/    # <vai trò>
└── <thư mục>/    # <vai trò>
```

## Quy ước
<!-- required -->

- Ranh giới module: <thư mục nào được phụ thuộc thư mục nào>
- Đặt tên: <quy ước tên file, tên package>
- Chỗ đặt: <nơi viết API, nơi viết truy cập dữ liệu, nơi viết test>
