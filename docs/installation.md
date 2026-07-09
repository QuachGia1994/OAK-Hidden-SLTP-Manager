
# Cài đặt OAK Manager

## Phiên bản đã biên dịch (v3.15.2)

1. Tải bản mới nhất từ [Releases GitHub](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
2. Chọn gói:
   - `OAK MANAGER_v3.15.2_window-unpack.zip` — portable giải nén và chạy trực tiếp
   - `OAK MANAGER_v3.15.2_Installer.exe` — cài đặt có shortcut Desktop/Start Menu
   - (tuỳ chọn) `OAK Source v3.15.2.zip` — mã nguồn snapshot
3. Sau khi cài hoặc giải nén, mở app và dùng tab `Tín Hiệu` để quản lý process nền
4. Mỗi profile chỉ Start **1 worker** (app tự dọn orphan)

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
