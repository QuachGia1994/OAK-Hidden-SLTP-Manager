
# Cài đặt OAK Manager

## Phiên bản đã biên dịch

1. Tải bản mới nhất từ [Releases GitHub](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
2. Chọn một trong hai gói:
   - `window-unpack.zip`: bản portable giải nén và chạy trực tiếp
   - `Installer.exe`: bản cài đặt có shortcut Desktop/Start Menu
3. Sau khi cài hoặc giải nén, mở app và dùng tab `Tín Hiệu` để quản lý process nền

## Build từ mã nguồn

Nếu bạn muốn tự build gói Windows từ mã nguồn:

1. Cài đặt PyInstaller:

```bash
pip install pyinstaller
```

2. Chạy build script:

```bash
python build_exe.py
```

3. Sau khi build hoàn tất, bạn sẽ có:
   - `dist/window-unpack/<APP_VERSION>/`
   - `dist/<APP_VERSION>_window-unpack.zip`
   - `dist/<APP_VERSION>_Installer.exe` nếu máy có NSIS

## Lưu ý

- Nếu bạn dùng UPX để nén, hãy đặt folder `upx/` ở gốc repo (có thể tải từ [UPX Releases](https://github.com/upx/upx/releases))
- Nếu chưa cài NSIS, script vẫn build được `window-unpack` và file zip portable
