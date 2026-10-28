# Cấu trúc repo backend

## Mô hình repo
<!-- required -->

- Mô hình: một repo chứa order-service, order-web và hợp đồng API (monorepo)
- Lý do: một team 3 người (C-002), một service; quyết định D-001

## Cây thư mục gốc
<!-- required -->

```
cafe-order/
├── order-service/   # service backend
├── order-web/       # app web, xem 05-frontend
├── contracts/       # hợp đồng API dùng chung
└── infra/           # mô tả hạ tầng
```

## Quy tắc phụ thuộc
<!-- required -->

| Quy tắc | Lý do | Cách bảo đảm |
| --- | --- | --- |
| order-web chỉ dùng API qua hợp đồng, không import mã của order-service | giữ ranh giới ở [overview.md](overview.md) | lint chặn import xuyên thư mục trong CI |

## Mã dùng chung và hợp đồng
<!-- required -->

| Thành phần | Nằm ở đâu | Ai được đổi | Cách phát hành |
| --- | --- | --- | --- |
| hợp đồng API | `contracts/` (chưa có file riêng, xem [contracts/README.md](contracts/README.md)) | cả team, một người duyệt | cùng tag của repo |

## Sở hữu mã
<!-- required -->

| Phần | Người hoặc nhóm duyệt |
| --- | --- |
| order-service | thành viên backend |
| order-web | thành viên frontend |
| infra | thành viên vận hành |
