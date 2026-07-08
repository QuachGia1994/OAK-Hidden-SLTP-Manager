
# Cài đặt OAK Manager

## Phiên bản đã biên dịch (exe)

1. Tải bản mới nhất từ [Releases GitHub](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
2. Chạy file `.exe` để cài đặt
3. Sau khi cài, mở app từ shortcut trên Desktop hoặc Menu Start

## Build từ mã nguồn

Nếu bạn muốn tự build exe từ mã nguồn:

1. Cài đặt PyInstaller:

```bash
pip install pyinstaller
```

2. Chạy build script:

```bash
python build_exe.py
```

3. Sau khi build hoàn tất, file exe sẽ nằm trong thư mục `dist/`

## Lưu ý

- Nếu bạn dùng UPX để nén, hãy đặt folder `upx/` ở gốc repo (có thể tải từ [UPX Releases](https://github.com/upx/upx/releases))
- File exe sẽ có kích thước lớn (~100-200MB) vì đã đóng gói tất cả dependencies
