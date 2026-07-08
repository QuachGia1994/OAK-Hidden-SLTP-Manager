
# Bắt đầu nhanh

## Yêu cầu hệ thống

- Windows 10/11
- Python 3.10 hoặc mới hơn
- MetaTrader 5 đã cài đặt và đăng nhập

## Cài đặt (phát triển)

1. Clone repo:

```bash
git clone https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager.git
cd OAK-Hidden-SLTP-Manager
```

2. Cài các gói phụ thuộc:

```bash
pip install -r requirements.txt
```

3. Đặt cấu hình:
   - Sao chép `profiles.example.json` → `profiles.json`
   - Sao chép `settings.example.json` → `settings.json`
   - Tạo `config.json` (xem phần Cấu hình)

4. Chạy app:

```bash
CHAY_ROBOT.bat
```

Hoặc nếu đang debug thủ công, chạy trực tiếp:

```bash
python OAK_Hidden_SLTP_Manager.py
```
