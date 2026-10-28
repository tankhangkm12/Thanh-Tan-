# Nhóm design-system

**Trạng thái:** Giai đoạn 6 xong và đã gộp vào `develop`; đã chạy thử trên một dự án mẫu ở G0–G2, các gate sau G2 chưa chạy thử trên dự án thật; bản Antigravity mới kiểm một phần.

Nhóm plugin thiết kế. `design-core` giữ chuẩn chung của nhóm (workflow, tiêu chí chất lượng, agent, template, script); các plugin con phụ thuộc vào `design-core` và chỉ thêm phần riêng. Kế hoạch đầy đủ, là nguồn sự thật duy nhất: [PLAN.md](PLAN.md). Cách cài và chạy: [hướng dẫn sử dụng](core/USAGE.md).

| Plugin | Phạm vi |
|---|---|
| `design-core` | Workflow G0–G10, 8 tiêu chí chất lượng, quyền ghi của agent, template workspace, script kiểm tra (chạy qua uv); có sẵn trong marketplace `thanh-tan-plugins` |
| `design-architecture` | Biến tài liệu BA thành bộ tài liệu kiến trúc giải pháp đầy đủ, có số liệu thật; chỉ chứa template, checklist và phần "dùng với core" |

Nhóm này không chạy bằng `thanhtan`: workspace là `.agent-workspace/` trong dự án và các gate do script Python kiểm.
