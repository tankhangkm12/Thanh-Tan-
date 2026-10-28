# CHANGELOG

> Template của design-architecture, chỉ để mô tả: `archive_release.py` ghi file này ở `architecture/CHANGELOG.md` khi phát hành (không phải Designer, không qua `drafts/`), nên template không có mục `<!-- required -->`. Đừng sửa tay. Mỗi lần phát hành thêm một mục `## vN` lên **đầu** file (trên các mục cũ), sau tiêu đề; phát hành lại số `vN` đã có bị từ chối. Đổi phiên bản công nghệ sau khi stack đã chốt đi qua chế độ nâng cấp và hiện ở mục của lần phát hành kế tiếp.

## Định dạng một mục

```text
## vN (YYYY-MM-DD)

- Mức áp dụng: <S, M, L hoặc XL>
- Phát hành khi người dùng duyệt: "<nguyên văn, ví dụ G10: duyệt>"
- Bản chụp: `archive/vN/`

### Quyết định đã chốt

- <D-xxx: phương án người dùng chọn>

### Rủi ro đã chấp nhận

- <R-xx: điểm, nguyên văn người dùng>

### So với bản trước (`inputs/previous-design/`)

- Thêm (số lượng): <danh sách file>
- Đổi (số lượng): <danh sách file>
- Xóa (số lượng): <danh sách file>
- Không đổi: <số lượng> file
```

Mục "So với bản trước" chỉ có khi workspace có `inputs/previous-design/`; so sánh theo hash từng file. Mục không có nội dung ghi "không có".
