# Bộ khuyến nghị VN30 theo H=4

Module này quét thành phần VN30 hiện tại và đưa ra tối đa ba mã cho phiên chiều. Đây chỉ là khuyến nghị mặc định. Module không có khả năng gửi lệnh, không nhận OTP hoặc private key giao dịch, và mọi giao dịch thật phải được User xác nhận riêng.

## Mô hình

- Signal: `Stock-DIRECTION` tại H=4; bản ghi cũ tự fallback về hướng XAUUSD cuối cùng.
- Điểm vào tham chiếu: VWAP nến SSI 5 phút bắt đầu lúc 13:05.
- Kỳ nắm giữ: từ 13:05 ngày signal tới 13:05 phiên giao dịch kế tiếp.
- Cửa sổ active: 25 outcome đã hoàn tất trước ngày quyết định.
- Điều kiện mặc định: đủ ít nhất 8 mẫu cùng hướng, hit-rate toàn kỳ từ 72%, hit-rate cùng hướng từ 60%, beta dương và edge cùng hướng lớn hơn hurdle.
- Phân bổ: tối đa ba slot, mỗi slot bằng một phần ba vốn khả dụng. Slot không đạt chuẩn được giữ bằng tiền mặt.
- Gate phiên: chỉ tạo kết quả khi SSI xác nhận VNINDEX có phiên đúng ngày signal; ngày nghỉ sẽ dừng.
- `BUY`: mua hoặc tiếp tục giữ sau khi User xác nhận.
- `SELL`: bán nếu đang sở hữu hoặc đưa vào danh sách tránh mua sau khi User xác nhận. Không tạo vị thế bán khống.

## Chuẩn bị

Đăng ký FastConnect và tạo API key chỉ dùng market data. Cài dependency:

```powershell
python -m pip install -r requirements.txt
```

Đặt credentials trong biến môi trường của tiến trình. Không ghi secret vào repository:

```powershell
$env:SSI_CLIENT_ID = "oak-stock-scanner"
$env:SSI_API_KEY = "<market-data-api-key>"
$env:SSI_API_SECRET = "<market-data-api-secret>"
```

## Backfill H=4 lần đầu

Đóng tiến trình signal bot đang ghi `signals_log.json` trước khi backfill để tránh hai tiến trình ghi cùng file:

```powershell
python vn_stock_advisor.py --backfill-h4 260 --capital 90000000 --output stock_recommendation.json
```

Những lần sau, chạy sau khi H=4 của ngày hiện tại đã được ghi:

```powershell
python vn_stock_advisor.py --capital 90000000 --hurdle-bps 0 --output stock_recommendation.json
```

`--hurdle-bps` phải được đặt theo tổng chi phí và biên an toàn thực tế của tài khoản. Giá trị `0` không khấu trừ chi phí.

## Đọc kết quả

Các trường an toàn luôn có trong JSON:

```json
{
  "advisory_only": true,
  "requires_user_confirmation": true,
  "orders_submitted": false
}
```

`READY` nghĩa là đủ ba mã, `PARTIAL` nghĩa là chỉ một hoặc hai mã đạt chuẩn, và `NO_TRADE` nghĩa là không mã nào vượt toàn bộ gate. Không được biến một trong các trạng thái này thành lệnh thật nếu chưa có xác nhận trực tiếp của User.

SSI giới hạn intraday trong một năm. Vì cần 25 phiên đầu làm training, một lần tải mới thường không thể tạo đủ 250 quyết định walk-forward. Báo cáo sẽ công khai số quyết định thực tế và không coi mục tiêu 250 là đã đạt nếu dữ liệu chưa đủ.
