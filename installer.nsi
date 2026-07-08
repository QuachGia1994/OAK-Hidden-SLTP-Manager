
; NSIS Installer Script for OAK Manager
; Requires NSIS 3.0 or later
; Download: https://nsis.sourceforge.io/Download

!define APPNAME "OAK MANAGER"
!define COMPANY "QKP"
!define VERSION "3.15.0"

!define /date BUILDDATE "%Y-%m-%d"
!define DEFAULT_INSTALL_DIR "$PROGRAMFILES64\${APPNAME}"

Name "${APPNAME}"
OutFile "dist\${APPNAME}_${VERSION}_Installer.exe"
InstallDir "${DEFAULT_INSTALL_DIR}"
InstallDirRegKey HKLM "Software\${COMPANY}\${APPNAME}" "InstallDir"
RequestExecutionLevel admin
BrandingText "${APPNAME} v${VERSION}"

; MUI 2.0 Settings
!include "MUI2.nsh"

; Installer Pages
!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; LANGUAGE
!insertmacro MUI_LANGUAGE "English"

Section "Main Section" SecMain
  ; Set output path
  SetOutPath $INSTDIR

  ; Install the main executable
  File "dist\OAK MANAGER_v${VERSION}.exe"
  
  ; Install configuration examples
  File "profiles.example.json"
  File "settings.example.json"
  
  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\OAK MANAGER_v${VERSION}.exe"
  CreateShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\OAK MANAGER_v${VERSION}.exe"

  ; Write registry keys
  WriteRegStr HKLM "Software\${COMPANY}\${APPNAME}" "InstallDir" $INSTDIR
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANY}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSION}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoRepair" 1
  
  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; Uninstaller
Section "Uninstall"
  ; Remove main files
  Delete "$INSTDIR\OAK MANAGER_v${VERSION}.exe"
  Delete "$INSTDIR\uninstall.exe"
  Delete "$INSTDIR\profiles.example.json"
  Delete "$INSTDIR\settings.example.json"

  ; Remove shortcuts
  Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
  RMDir "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${APPNAME}.lnk"

  ; Remove registry keys
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
  DeleteRegKey HKLM "Software\${COMPANY}\${APPNAME}"

  ; Remove directory if empty
  RMDir "$INSTDIR"
SectionEnd
