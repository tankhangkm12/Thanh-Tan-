# Tiêu chí chất lượng Q1–Q8

Mọi file đầu ra phải qua 8 tiêu chí này. Chúng là nội dung checklist của Reviewer: Reviewer soát đủ Q1–Q8 ở mọi gate; các Q ghi theo từng gate trong [stages.md](stages.md) chỉ là trọng tâm, riêng Q6 và Q8 là trọng tâm ở mọi gate. Nguồn: [PLAN.md](../../PLAN.md), mục "8 tiêu chí chất lượng".

## Bảng tổng hợp

| ID | Tiêu chí | Kiểm bằng cách nào |
| --- | --- | --- |
| Q1 | Đúng FR / NFR / ràng buộc | Mọi thành phần truy về ít nhất một FR, NFR hoặc ràng buộc; script truy vết báo thiếu |
| Q2 | Tối ưu theo từng tầng: frontend, backend, lưu trữ, hạ tầng, quy trình | Mỗi phần có mục "Tối ưu" với chỉ số mục tiêu bằng số |
| Q3 | Sẵn sàng mở rộng, nâng cấp, bảo trì | Mỗi thành phần có đường scale, đường nâng cấp và gánh nặng bảo trì ước tính |
| Q4 | Số liệu thật | Mọi con số có công thức, giả định (link `assumptions.md`) và nguồn chính thức; script tính lại khớp |
| Q5 | Kiểu dữ liệu, kiến trúc, stack, phiên bản rõ từ đầu | Ma trận phiên bản và tính năng đã được người dùng duyệt ở gate stack (G4) |
| Q6 | Quản lý rủi ro | Mỗi quyết định sinh rủi ro vào sổ rủi ro; rủi ro điểm cao cần người dùng chấp nhận rõ ràng |
| Q7 | Frontend sâu về kiến trúc, tối ưu cho thiết bị thật; không đụng GUI | Có ma trận thiết bị và ngân sách hiệu năng; không có quyết định visual nào |
| Q8 | Phù hợp với dự án | Độ sâu tài liệu khớp hồ sơ dự án đã duyệt; không có phần thừa so với hồ sơ |

## Cách kiểm từng tiêu chí

Mỗi tiêu chí có hai lớp: script (máy kiểm được) chạy trước, rồi Reviewer đọc phần máy không kiểm được. Reviewer chạy lại script, không tin báo cáo của Designer. Kết quả script ở `.agent-workspace/checks/`, báo cáo soát ở `reviews/R-xxx-<phần>.md` với link file và dòng.

### Q1. Đúng FR / NFR / ràng buộc

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q1 -->
**Q1. Đúng FR / NFR / ràng buộc.** Mọi thành phần (`SVC`, `API`, `EVT`, `TBL`, `BKT`, `FL`) truy về ít nhất một FR, NFR hoặc ràng buộc; không có thành phần "tự thêm" ngoài yêu cầu.
<!-- END:council-q Q1 -->

- **Script:** `check_trace.py` (FR không có luồng; API frontend gọi mà backend không có; bảng, bucket, event nhắc trong luồng mà phần data không có), `check_links.py` (link gãy, ID trùng, ID mồ côi, thiếu liên kết ngược).
- **Reviewer:** mỗi thành phần (`SVC`, `API`, `EVT`, `TBL`, `BKT`, `FL`) truy về ít nhất một `FR`, `NFR` hoặc ràng buộc qua `00-context/requirements-trace.md`; không có thành phần "tự thêm" ngoài yêu cầu.
- **Lỗi chặn:** thành phần không truy được về yêu cầu nào; FR không có luồng.

### Q2. Tối ưu theo từng tầng

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q2 -->
**Q2. Tối ưu theo từng tầng** (frontend, backend, lưu trữ, hạ tầng, quy trình). Mỗi phần có mục "Tối ưu" với chỉ số mục tiêu bằng số và đơn vị; chỉ số truy được về NFR.
<!-- END:council-q Q2 -->

- **Script:** `check_profile.py` (mục bắt buộc theo template, đánh dấu `<!-- required -->`): mỗi phần có mục "Tối ưu" không trống. `check_numbers.py` (từ mơ hồ như "nhanh", "lớn", "đủ dùng", "scale tốt" không kèm số).
- **Reviewer:** mỗi phần thuộc frontend, backend, lưu trữ, hạ tầng, quy trình có mục "Tối ưu" với chỉ số mục tiêu bằng số và đơn vị; chỉ số truy được về NFR.
- **Lỗi chặn:** thiếu mục "Tối ưu"; chỉ số không có số; từ mơ hồ không kèm số.

### Q3. Sẵn sàng mở rộng, nâng cấp, bảo trì

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q3 -->
**Q3. Sẵn sàng mở rộng, nâng cấp, bảo trì.** Mỗi thành phần có (a) đường scale: đơn vị scale, giới hạn, ngưỡng số để lên giai đoạn sau; (b) đường nâng cấp: phiên bản, ngày EOL; (c) gánh nặng bảo trì ước tính (người, giờ hoặc tần suất việc định kỳ).
<!-- END:council-q Q3 -->

- **Script:** `check_profile.py` (mục bắt buộc theo template, đánh dấu `<!-- required -->`): mỗi thành phần có mục scale, nâng cấp, bảo trì không trống. `check_links.py` kiểm link tới `scaling.md`, `upgrade-roadmap.md` nếu có. Việc ước tính có cơ sở vẫn do Reviewer.
- **Reviewer:** mỗi thành phần có (a) đường scale: đơn vị scale, giới hạn, ngưỡng số để lên giai đoạn sau; (b) đường nâng cấp: phiên bản, ngày EOL; (c) gánh nặng bảo trì ước tính (người, giờ hoặc tần suất việc định kỳ).
- **Lỗi chặn:** thành phần thiếu một trong ba mục. Mục "ước tính" không có cơ sở là góp ý.

### Q4. Số liệu thật

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q4 -->
**Q4. Số liệu thật.** Mỗi con số có đủ năm thành phần: giá trị và đơn vị, công thức, giả định, hằng số có nguồn, mốc thời gian. Nguồn là tài liệu chính thức đúng phiên bản đã chọn; đơn giá có ngày tra cứu. Số do model tính nhẩm thay vì tính bằng công thức là không đạt.
<!-- END:council-q Q4 -->

- **Script:** `calc_capacity.py` (đọc `capacity/*.yaml`, sinh bảng số; chặn khi thiếu nguồn cho hằng số hoặc giá), `check_numbers.py` (con số thiếu công thức, giả định hoặc nguồn; `assumptions.md` không lệch `capacity/assumptions.yaml`).
- **Reviewer:** chạy lại script và đối chiếu bảng số trong bản nháp; mỗi con số có đủ 5 thành phần (giá trị + đơn vị, công thức, giả định, hằng số có nguồn, mốc thời gian); nguồn là tài liệu chính thức đúng phiên bản đã chọn; đơn giá có ngày tra cứu.
- **Lỗi chặn:** con số không tính lại khớp; thiếu công thức, giả định hoặc nguồn; số do model tính nhẩm thay vì script.

### Q5. Kiểu dữ liệu, kiến trúc, stack, phiên bản rõ từ đầu

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q5 -->
**Q5. Kiểu dữ liệu, kiến trúc, stack, phiên bản rõ từ đầu.** Ma trận phiên bản và tính năng đã được người dùng duyệt ở gate stack; kiểu dữ liệu cột có số byte và lý do; không chi tiết nào dựa trên stack hay phiên bản chưa chốt; phiên bản đã hết hoặc sắp hết EOL phải có lý do.
<!-- END:council-q Q5 -->

- **Script:** `check_versions.py`: mọi công nghệ trong `02-tech-stack/README.md` có dòng trong `versions-features.md` với phiên bản chốt (major.minor; riêng lớp third-party được thêm phiên bản theo ngày YYYY-MM-DD hoặc "SaaS, không phiên bản"), ngày EOL và link nguồn; phiên bản **đã hết hỗ trợ** tại ngày chạy là lỗi chặn; phiên bản hết hỗ trợ **trong 12 tháng** là cảnh báo và dòng đó phải có link `R-xx` ở cột Rủi ro, thiếu thì lỗi chặn; dòng trùng (cùng công nghệ và phiên bản) là lỗi chặn. `check_links.py` (mỗi lớp stack truy về `TC`), `check_workspace.py` (quyết định chưa có quyết định của người dùng).
- **Reviewer:** ma trận phiên bản và tính năng đã được người dùng duyệt ở G4 (có dòng duyệt theo ID trong `decision.md`/`decision-log.md`); kiểu dữ liệu cột trong `tables.md` có số byte và lý do; không chi tiết nào dựa trên stack hay phiên bản chưa chốt.
- **Lỗi chặn:** thiết kế chi tiết (G7 trở đi) dùng lớp, phiên bản hoặc kiểu dữ liệu chưa được duyệt; phiên bản đã hết hỗ trợ (script báo); phiên bản sắp hết hỗ trợ trong 12 tháng mà dòng đó không có link `R-xx` ở cột Rủi ro (script báo).

### Q6. Quản lý rủi ro

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q6 -->
**Q6. Quản lý rủi ro.** Mỗi quyết định sinh rủi ro vào sổ rủi ro; điểm rủi ro = khả năng × tác động (mỗi thang 1-5, tối đa 25). Rủi ro 15-25 điểm cần giảm thiểu, và nếu vẫn giữ thì người dùng phải chấp nhận rõ ràng; rủi ro 8-14 điểm cần giảm thiểu và dấu hiệu sớm.
<!-- END:council-q Q6 -->

- **Script:** `check_workspace.py` (quyết định chưa có quyết định của người dùng; rủi ro ≥ 15 điểm chưa xử lý), `check_links.py` (rủi ro `R-xx` link tới thành phần liên quan), `check_versions.py` (phiên bản hết hỗ trợ trong 12 tháng phải link `R-xx` ở cột Rủi ro của `versions-features.md`; Reviewer đối chiếu `R-xx` đó có thật trong sổ rủi ro và đúng thành phần).
- **Reviewer:** ở mỗi gate, rủi ro mới từ giai đoạn vừa làm đã được khai vào sổ rủi ro chưa; mỗi brief quyết định, dòng phiên bản, bảng sizing và khoảng trống kỹ năng đều có rủi ro tương ứng; điểm (khả năng × tác động) có cần chấm lại không; rủi ro 15–25 điểm có giảm thiểu, và nếu vẫn giữ thì có dòng chấp nhận theo ID của người dùng ở `risks/acceptance.md`; rủi ro 8–14 có giảm thiểu và dấu hiệu sớm.
- **Lỗi chặn:** quyết định hoặc dòng phiên bản không sinh rủi ro (phiên bản sắp hết hỗ trợ không link `R-xx`: script báo); rủi ro ≥ 15 điểm chưa giảm thiểu hoặc chưa được chấp nhận.

### Q7. Frontend: kiến trúc sâu, tối ưu cho thiết bị thật, không đụng GUI

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q7 -->
**Q7. Frontend: kiến trúc sâu, tối ưu cho thiết bị thật, không đụng GUI.** Có ma trận thiết bị và ngân sách hiệu năng bằng số; mỗi app có kiến trúc, routing, state, networking, build-delivery; không có quyết định visual nào (màu, kiểu chữ, bố cục, component).
<!-- END:council-q Q7 -->

- **Script:** `check_profile.py` (chỉ chạy kiểm Q7 khi hồ sơ giữ `05-frontend`), `check_trace.py` (API frontend gọi mà backend không có).
- **Reviewer:** `05-frontend/device-matrix.md` (thiết bị, trình duyệt, OS, mạng hỗ trợ) và `performance-budget.md` (bundle KB, LCP/INP/CLS, bộ nhớ) có và có số; mỗi app có kiến trúc, routing, state, networking, build-delivery; không có quyết định visual nào (màu, kiểu chữ, bố cục, component).
- **Lỗi chặn:** thiếu ma trận thiết bị hoặc ngân sách hiệu năng; có quyết định visual trong tài liệu.
- **Ghi chú:** tiêu chí này không áp dụng khi hồ sơ dự án bỏ phần frontend (mức S).

### Q8. Phù hợp với dự án

- **Cho hội đồng:** đoạn giữa hai dấu dưới đây được chép nguyên văn vào các file hội đồng (`claude/agents/council/`); sửa ở đây thì sửa cả ở đó, test sẽ bắt lệch.
<!-- BEGIN:council-q Q8 -->
**Q8. Phù hợp với dự án.** Độ sâu và mức chi tiết khớp mức S/M/L/XL đã duyệt ở G0; không phần nào làm quá tay so với hồ sơ (phương án vượt xa nhu cầu mà thêm chi phí hoặc độ phức tạp bị trừ điểm).
<!-- END:council-q Q8 -->

- **Script:** `check_profile.py` (phần bắt buộc theo `project-profile.md` còn thiếu; phần đã bỏ lại xuất hiện).
- **Reviewer:** độ sâu và mức chi tiết khớp mức S/M/L/XL đã duyệt ở G0; không phần nào làm quá tay so với hồ sơ (phương án vượt xa nhu cầu mà thêm chi phí hoặc độ phức tạp bị trừ điểm); mốc tính số liệu đúng mức.
- **Lỗi chặn:** thiếu phần bắt buộc; phần đã bỏ vẫn xuất hiện. Làm quá tay mà không vi phạm hồ sơ là góp ý, trừ khi nó thêm chi phí hoặc độ phức tạp so với nhu cầu (khi đó là lỗi chặn).

## Mức độ lỗi trong báo cáo review

- **Lỗi chặn:** gate không qua cho tới khi sửa. Mọi lỗi liệt kê ở mục "Lỗi chặn" ở trên, và mọi lỗi do script báo.
- **Góp ý:** không chặn gate, Designer xem xét; người dùng quyết có sửa không.
