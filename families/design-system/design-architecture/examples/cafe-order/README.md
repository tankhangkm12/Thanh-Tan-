# Bộ nháp mẫu: CafeOrder

Dữ liệu giả để chạy thử template và script của design-architecture (Giai đoạn 4 và 5B). Không dùng cho dự án thật; mọi link example.com và con số là giả.

- `drafts/`: bản nháp theo template, mức M, đủ 13 phần `00-context` … `12-roadmap` cộng `README.md` (một app web `order-web`, một service `order-service`, một database `order-db`; ba luồng FR-001..003). `CHANGELOG.md` không có vì do `archive_release.py` ghi khi phát hành.
- `capacity/`: đầu vào của `calc_capacity.py` (không có `storage.yaml`: dự án không có object storage); `drafts/03-capacity/`, `drafts/00-context/assumptions.md` và các khối calc trong `tables.md` do script sinh, không sửa tay.
- `decisions/decision-log.md`: nơi `D-xxx` được định nghĩa. `inputs/ui-design/screens.md`: nơi `SCR-xx` được định nghĩa (chỉ ID và mục đích, giả).
- Chạy ở G10: `calc_capacity.py` (+`--check`), `check_profile.py --gate G10 --templates`, `check_trace.py --gate G10`, `check_links.py`, `check_numbers.py`, `check_versions.py`, mỗi lệnh với `--workspace` trỏ tới bản sao của thư mục này (script ghi `checks/`, không đưa vào đây). `check_workspace.py`, `promote_drafts.py`, `archive_release.py` cần phê duyệt thật trong `state.md` nên chưa chạy trên bộ mẫu.
