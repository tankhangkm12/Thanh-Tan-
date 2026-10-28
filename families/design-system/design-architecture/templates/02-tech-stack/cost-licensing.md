# Chi phí và giấy phép

> Template của design-architecture. Mục có `<!-- required -->` là bắt buộc. **Không chép số chi phí hạ tầng vào file này**: chi phí hạ tầng theo mốc do `calc_capacity.py` tính ở [cost-model.md](../03-capacity/cost-model.md) (file sinh, không viết tay); ở đây chỉ dẫn link. Chỉ khoản ngoài hạ tầng (giấy phép, gói SaaS, hỗ trợ…) được ghi trực tiếp, mỗi dòng kèm link nguồn giá và ngày tra cứu (Q4).

## Giấy phép
<!-- required -->

| Công nghệ | Giấy phép | Giới hạn sử dụng thương mại | Nguồn |
| --- | --- | --- | --- |
| <Tên> | <tên giấy phép, phiên bản> | <điều kiện, hoặc "không có"> | <link giấy phép chính thức> |

## Chi phí ngoài hạ tầng
<!-- required -->

Không có khoản nào thì ghi "không có khoản ngoài hạ tầng". Chi phí máy chủ, lưu trữ, băng thông không ghi ở đây.

| Công nghệ | Hạng mục | Đơn giá (số + đơn vị) | Nguồn giá | Ngày tra cứu |
| --- | --- | --- | --- | --- |
| <Tên> | <gói SaaS, license, hỗ trợ> | <số tiền / đơn vị> | <link trang giá chính thức> | <YYYY-MM-DD> |

## So với ngân sách
<!-- required -->

Cột hạ tầng chỉ có link tới [cost-model.md](../03-capacity/cost-model.md), không chép số. Kết luận (đạt / vượt) dựa trên tổng hai khoản so với ràng buộc ngân sách.

| Mốc | Chi phí ngoài hạ tầng (số + đơn vị) | Chi phí hạ tầng | Ngân sách (ràng buộc) | Kết luận |
| --- | --- | --- | --- | --- |
| <ra mắt, 1 năm…> | <số tổng từ bảng trên> | [cost-model.md](../03-capacity/cost-model.md) | <C-xx> | <đạt / vượt, vì sao> |
