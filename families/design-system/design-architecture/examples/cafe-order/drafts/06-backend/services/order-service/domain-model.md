# Mô hình miền

## Thực thể
<!-- required -->

| Thực thể | Mô tả | Danh tính | Lưu ở bảng |
| --- | --- | --- | --- |
| Đơn | một lần đặt của khách | số tự tăng | TBL-orders |
| Dòng món | một món trong đơn | số tự tăng | TBL-order-items |

## Quy tắc bất biến
<!-- required -->

| Quy tắc | Áp dụng cho | Nguồn (FR / NFR / C) | Cách bảo đảm |
| --- | --- | --- | --- |
| Đơn có ít nhất một dòng món | Đơn | FR-001 | kiểm tra ở service trước khi ghi |
| Trạng thái chỉ đi tiến: mới, đang pha, sẵn sàng, đã giao | Đơn | FR-003 | kiểm tra ở service |

## Vòng đời trạng thái

mới → đang pha → sẵn sàng → đã giao.
