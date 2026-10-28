# Cấu trúc repo backend

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. Cấu trúc thư mục bên trong từng service ở `folder-structure.md` của service; file này chỉ nói repo nào chứa gì và quy tắc giữa chúng. Không được mâu thuẫn với `folder-structure.md` và `05-frontend/<app>/folder-structure.md`.

## Mô hình repo
<!-- required -->

- Mô hình: <monorepo, polyrepo, kết hợp>
- Lý do: <C-xx hoặc NFR-xx, quyết định D-xxx>

## Cây thư mục gốc
<!-- required -->

```
<repo>/
├── <thư mục>/    # <vai trò>
└── <thư mục>/    # <vai trò>
```

## Quy tắc phụ thuộc
<!-- required -->

| Quy tắc | Lý do | Cách bảo đảm |
| --- | --- | --- |
| <ví dụ: service không import mã nội bộ của service khác, chỉ dùng hợp đồng> | <giữ ranh giới ở overview.md> | <lint, kiểm tra phụ thuộc trong CI> |

## Mã dùng chung và hợp đồng
<!-- required -->

| Thành phần | Nằm ở đâu | Ai được đổi | Cách phát hành |
| --- | --- | --- | --- |
| <thư viện chung, hợp đồng API> | <thư mục hoặc repo> | <team, người duyệt> | <phiên bản, tag> |

## Sở hữu mã
<!-- required -->

| Phần | Người hoặc nhóm duyệt |
| --- | --- |
| <thư mục> | <vai trò> |
