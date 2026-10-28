# Xong khi: README.md của architecture/

Gate: G10 (phát hành). Trọng tâm: Q1, Q8. `README.md` là mục lục; `promote_drafts.py --gate G10` từ chối khi thiếu `drafts/README.md`.

- [ ] Có đủ 5 mục bắt buộc: phiên bản và mức áp dụng, mục lục, cách đọc, quy ước ID, còn mở (`check_profile.py` báo `missing-required-section`).
- [ ] Mức áp dụng khớp `00-context/project-profile.md`; phiên bản khớp mục mới nhất của `CHANGELOG.md` sau khi `archive_release.py` chạy.
- [ ] Mục lục có đúng một dòng cho mỗi phần từ `00` đến `12`; phần có trong hồ sơ dự án đều link tới file thật; phần bỏ ghi "bỏ" kèm lý do (Q8) và không link.
- [ ] Mọi link relative trong README trỏ tới file có trong bản phát hành (`check_links.py` sạch).
- [ ] "Cách đọc" có ít nhất agent dev (trỏ `implementation-plan.md`), designer (khi có `05-frontend/`) và người vận hành (khi có `09-infrastructure/`).
- [ ] "Quy ước ID" khớp danh sách tiền tố ở `core/data/ids.yaml` và nơi định nghĩa thật.
- [ ] README không định nghĩa ID và không chứa con số thiết kế (nếu có số có đơn vị thì có ô cơ sở theo `check_numbers.py`).
- [ ] "Còn mở" liệt kê mọi câu hỏi `CH-xxx` chưa đóng, hoặc ghi "không có".
- [ ] Người dùng duyệt (`G10: duyệt`).
