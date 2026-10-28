---
decision: D-<xxx>
gate: <G3 | G4 | G7>
council_size: <3 | 5>
criteria:
  - {id: <TC-01>, kind: <weighted | exclusion>, weight: <số nguyên dương; bỏ khi kind là exclusion>}
  - {id: <TC-05>, kind: exclusion}
options: [<A>, <B>]
---

# Brief D-<xxx>: <câu hỏi cần quyết>

> Phần giữa hai dấu `---` ở đầu file là dữ liệu cho `tally_votes.py`; nó phải khớp bảng "Tiêu chí chấm" và các mục "Phương án" bên dưới. `criteria` liệt kê đúng các TC dùng để chấm quyết định này, với trọng số đã duyệt ở G2; `options` liệt kê ID các phương án (không gồm "không phương án nào phù hợp", luôn có sẵn). Thành viên chấm điểm thô theo từng TC, script tính tổng có trọng số từ đây.
>
> Designer viết, đặt ở `decisions/D-xxx-<tên>/brief.md`. Hội đồng chỉ đọc file này (không đọc file nào khác), nên mọi dữ kiện cần để chấm phải nằm trong đây, kèm ID để truy ngược. **Trung lập:** không khuyến nghị, không dùng "nên", "tốt nhất", "phù hợp hơn", "khuyến nghị". Hai phương án phải được mô tả bằng cùng các trường và cùng độ chi tiết.

- **Quyết định:** D-<xxx>
- **Gate:** <G3 | G4 | G7>
- **Loại:** <kiểu kiến trúc | stack lớp ... | phiên bản chốt | loại database | ranh giới service | nhất quán dữ liệu | kiểu dữ liệu bảng ... >
- **Khó đảo ngược:** <có | không> (có: đổi sau khi có dữ liệu production thì phải migrate dữ liệu hoặc tách/gộp service)
- **Hội đồng:** <3 | 5> thành viên
- **Ngày viết:** <YYYY-MM-DD>

## Câu hỏi

<Một câu hỏi, phạm vi rõ ràng: quyết cái gì, cho phần nào của hệ thống.>

## Bối cảnh trích

<!-- Chỉ trích phần liên quan, mỗi dòng có ID và link tới file gốc trong workspace. Không diễn giải. -->

- **Hồ sơ dự án:** <mức S/M/L/XL; số người dùng; số người trong team; ngân sách; thời hạn; tuân thủ>
- **FR liên quan:** <FR-xx: nội dung ngắn>
- **NFR liên quan (có số):** <NFR-xx: chỉ số và ngưỡng>
- **Ràng buộc:** <C-xx: nội dung ngắn>
- **Số liệu capacity liên quan:** <giá trị + đơn vị, nguồn trong `03-capacity` hoặc `capacity/*.yaml`>
- **Rủi ro đã có:** <R-xx: mô tả ngắn, hoặc không có>
- **Quyết định trước liên quan:** <D-xxx: kết quả, hoặc không có>

## Tiêu chí chấm (TC đã duyệt ở G2)

<!-- Chép từ `02-tech-stack/selection-criteria.md`. Tiêu chí loại trừ ghi riêng. -->

| TC | Tiêu chí | Truy về | Trọng số | Loại trừ? |
| --- | --- | --- | --- | --- |
| TC-<01> | <...> | <FR/NFR/ràng buộc> | <số> | <có | không> |

## Phương án

<!-- Mỗi phương án dùng đúng các trường bên dưới. Dữ kiện kỹ thuật phải có link nguồn chính thức; không có nguồn thì không ghi. Chi phí và độ phức tạp ghi bằng số khi có. -->

### Phương án A: <tên>

- **Mô tả:** <điều phương án này là và làm>
- **Đáp ứng TC:** <TC-xx: đáp ứng thế nào, có số nếu có>
- **Chi phí:** <giá trị + đơn vị + kỳ; nguồn>
- **Độ phức tạp vận hành và đòi hỏi kỹ năng:** <số người, kỹ năng, giờ việc định kỳ>
- **Giới hạn đã biết:** <có link nguồn>
- **Đường scale và nâng cấp:** <ngưỡng số, phiên bản, ngày hết hỗ trợ>
- **Rủi ro đi kèm:** <R-xx đã có, hoặc rủi ro mới Designer thấy (chưa chấm điểm)>
- **Nguồn:** <link chính thức>

### Phương án B: <tên>

- **Mô tả:** <...>
- **Đáp ứng TC:** <...>
- **Chi phí:** <...>
- **Độ phức tạp vận hành và đòi hỏi kỹ năng:** <...>
- **Giới hạn đã biết:** <...>
- **Đường scale và nâng cấp:** <...>
- **Rủi ro đi kèm:** <...>
- **Nguồn:** <...>

### Không phương án nào phù hợp

Luôn có. Chọn mục này nghĩa là các phương án trên đều không đạt; Designer sẽ làm lại brief.

## Dữ kiện chưa có

<!-- Điều chưa biết hoặc chưa có nguồn. Hội đồng chỉ chấm trên dữ kiện đã có nguồn. -->

- <dữ kiện, hoặc: không có>
