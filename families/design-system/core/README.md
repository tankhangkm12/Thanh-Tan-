# design-core

Core của nhóm **design-system**. Giữ workflow G0–G10, 8 tiêu chí chất lượng, bảng quyền của agent, 5 agent và 5 góc nhìn hội đồng (`claude/agents/`, định dạng Claude Code), template workspace, script và dữ liệu cấu hình của script; các plugin `design-*` khác dùng lại.

- **Script** (`scripts/`, chạy bằng `uv run`, mỗi script có `test_<tên>.py`):
  - Giai đoạn 3A: `init_workspace`, `detect_models`, `guard_write` (+ `hooks/hooks.json`), `calc_capacity`, `check_links`, `check_profile`, `check_numbers`, `check_versions`.
  - Giai đoạn 3B: `tally_votes`, `call_council_cli`, `run_spike`, `check_trace`, `check_workspace`, `promote_drafts`, `archive_release`.
- **Module dùng chung** (không phải script chạy riêng): `idlist.py` (tiền tố ID), `checkreport.py` (khối hash cuối báo cáo `checks/`, khối `promoted`), `approvals.py` (đọc bảng `## Gate` của `state.md`).
- **Dữ liệu** (`data/`): `numbers.yaml`, `versions.yaml`, `council.yaml`, `ids.yaml`, `cli.yaml`, `spike.yaml`, `trace.yaml`, `workspace.yaml`, `gates.yaml`, `archive.yaml`.

Chạy test: `uv run --with pytest --with pyyaml pytest core/scripts`. Hiện xong Giai đoạn 1, 2 và 3 (3A, 3B); các giai đoạn sau chưa làm. Xem [PLAN.md](../PLAN.md).

## Cài đặt

```
/plugin install design-core --marketplace tankhangkm12/Thanh-Tan-
```

Cần cài cả `design-core` và `design-architecture`; xem [hướng dẫn sử dụng](USAGE.md).
