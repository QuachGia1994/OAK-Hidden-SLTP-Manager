# Bộ khuyến nghị VN30 theo H=4 (Local EOD)

Module này quét thành phần VN30 hiện tại và đưa ra tối đa ba mã cho phiên chiều dựa trên dữ liệu EOD Local (không cần API Key). Đây chỉ là khuyến nghị mặc định. Module không có khả năng gửi lệnh, không nhận OTP hoặc private key giao dịch, và mọi giao dịch thật phải được User xác nhận riêng.

## Mô hình

- Signal: `Stock-DIRECTION` tại H=4; bản ghi cũ tự fallback về hướng XAUUSD cuối cùng.
- Điểm vào tham chiếu: Giá EOD / VWAP tham chiếu của phiên giao dịch.
- Kỳ nắm giữ: từ ngày signal tới phiên giao dịch kế tiếp.
- Cửa sổ active: 25 outcome đã hoàn tất trước ngày quyết định.
- Điều kiện mặc định: đủ ít nhất 8 mẫu cùng hướng, hit-rate toàn kỳ từ 72%, hit-rate cùng hướng từ 60%, beta dương và edge cùng hướng lớn hơn hurdle.
- Phân bổ: tối đa ba slot, mỗi slot bằng một phần ba vốn khả dụng. Slot không đạt chuẩn được giữ bằng tiền mặt.
- Gate phiên: chỉ tạo kết quả khi có dữ liệu phiên đúng ngày signal; ngày nghỉ sẽ dừng.
- `BUY`: mua hoặc tiếp tục giữ sau khi User xác nhận.
- `SELL`: bán nếu đang sở hữu hoặc đưa vào danh sách tránh mua sau khi User xác nhận. Không tạo vị thế bán khống.

## Quản lý dữ liệu Local EOD (`eod_collector`)

Hệ thống sử dụng bộ thu thập dữ liệu EOD nội bộ lưu trữ trong SQLite (`data/market.db`), hoàn toàn không yêu cầu SSI API Key hay tài khoản chứng khoán:

```powershell
# Cập nhật dữ liệu EOD cuối ngày
python -m eod_collector update

# Xem trạng thái dữ liệu lưu trữ
python -m eod_collector status

# Backfill dữ liệu lịch sử
python -m eod_collector backfill --days 30
```

## Khởi chạy Bộ lọc VN30

Chạy trực tiếp từ giao diện Desktop app (1-click) hoặc bằng dòng lệnh:

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
