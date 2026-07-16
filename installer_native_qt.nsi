; NSIS Installer Script for OAK Manager NativeQt
; Requires NSIS 3.0 or later

!define APPNAME "OAK MANAGER NativeQt"
!define COMPANY "QKP"
!ifndef VERSION
!define VERSION "v3.16.3"
!endif

!ifndef PACKAGE_DIR_NAME
!define PACKAGE_DIR_NAME "${APPNAME}_${VERSION}"
!endif

!ifndef APP_EXE_NAME
!define APP_EXE_NAME "${PACKAGE_DIR_NAME}.exe"
!endif

!define DEFAULT_INSTALL_DIR "$PROGRAMFILES64\${APPNAME}"

Name "${APPNAME}"
OutFile "dist\${APPNAME}_${VERSION}_Installer.exe"
InstallDir "${DEFAULT_INSTALL_DIR}"
InstallDirRegKey HKLM "Software\${COMPANY}\${APPNAME}" "InstallDir"
RequestExecutionLevel admin
BrandingText "${APPNAME} ${VERSION}"

!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Main Section" SecMain
  SetOutPath $INSTDIR
  File /r "dist\native-qt\${PACKAGE_DIR_NAME}\*.*"

  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APP_EXE_NAME}"
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APP_EXE_NAME}"

  WriteRegStr HKLM "Software\${COMPANY}\${APPNAME}" "InstallDir" $INSTDIR
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayName" "${APPNAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "Publisher" "${COMPANY}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "DisplayIcon" "$INSTDIR\${APP_EXE_NAME}"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "NoRepair" 1

  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
  RMDir "$SMPROGRAMS\${APPNAME}"
  Delete "$DESKTOP\${APPNAME}.lnk"

  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
  DeleteRegKey HKLM "Software\${COMPANY}\${APPNAME}"
  RMDir /r "$INSTDIR"
SectionEnd
