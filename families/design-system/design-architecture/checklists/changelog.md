# Xong khi: CHANGELOG.md của architecture/

Gate: G10 (phát hành). Trọng tâm: Q5, Q6. `CHANGELOG.md` do `archive_release.py` ghi, không phải Designer; checklist này là cho Reviewer soát sau khi phát hành.

- [ ] File nằm ở `architecture/CHANGELOG.md`, có tiêu đề `# CHANGELOG` và các mục `## vN (YYYY-MM-DD)` với mục mới nhất ở đầu.
- [ ] Mục của lần phát hành có mức áp dụng, nguyên văn duyệt của người dùng (`G10: duyệt`) và đường dẫn bản chụp `archive/vN/` có thật.
- [ ] "Quyết định đã chốt" khớp các quyết định `đã quyết` trong `decisions/decision-log.md`.
- [ ] "Rủi ro đã chấp nhận" khớp các dòng trong `risks/acceptance.md` và sổ rủi ro (Q6).
- [ ] Nếu có `inputs/previous-design/`: có mục "So với bản trước" liệt kê file thêm, đổi, xóa; đổi phiên bản công nghệ so với bản trước (Q5) đều nằm trong danh sách file đổi.
- [ ] Không có mục nào sửa tay hay xóa; số `vN` không trùng.
