# Cai dat OAK Manager

## Ban build san (v3.16.1)

1. Tai ban moi nhat tu [Releases GitHub](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
2. Chon goi phu hop:
   - `OAK.MANAGER_v3.16.1_window-unpack.zip` cho ban portable giai nen va chay ngay
   - `OAK.MANAGER_v3.16.1_Installer.exe` cho ban cai dat co shortcut Desktop/Start Menu
   - `OAK.Source.v3.16.1.zip` neu can source snapshot
3. Sau khi cai dat hoac giai nen, mo app va dung tab `Signals` de quan ly process nen
4. Moi profile chi nen Start 1 worker; app da co exact orphan cleanup theo `--profile`

## Build tu source

1. Cai dependency:

```bash
pip install -r requirements.txt
pip install pyinstaller
```

2. Build package Windows:

```bash
python build_exe.py
```

3. Tao source/profile backup:

```bash
python create_backup_final.py
```

4. Sau khi build xong, output nam o:
   - `dist/window-unpack/OAK MANAGER_v3.16.1/`
   - `dist/OAK MANAGER_v3.16.1_window-unpack.zip`
   - `dist/OAK MANAGER_v3.16.1_Installer.exe` neu may co NSIS
   - `OAK Source v3.16.1.zip`
   - `OAK_Profile_Backup.zip`

## Luu y

- Cuoi tuan, signal card desktop hien `Hien tai: Khong danh`; day la hanh vi dung, khong phai loi
- `create_backup_final.py` khong dua secrets/runtime state vao source zip
- Neu co UPX, dat folder `upx/` o goc repo de build script tu dung
- Neu chua cai NSIS, script van build duoc `window-unpack` va file zip portable
