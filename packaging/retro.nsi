; Windows installer for EchoForge Retro Gaming. Per-user, so no administrator prompt.
; Silent: /S    Skip shortcuts (for tests): /NOSHORTCUTS    Folder: /D=<path> (last, unquoted)
; Favorites, history, settings and backups live in %LOCALAPPDATA%\EchoForge Retro Gaming and survive an uninstall.
Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!ifndef VERSION
  !error "Pass /DVERSION=x.y.z"
!endif
!define APP "EchoForge Retro Gaming"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\EchoForgeRetroGaming"

Name "${APP}"
OutFile "dist\EchoForge-Retro-Gaming-Setup-${VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!define MUI_ICON "..\icon.ico"
!define MUI_UNICON "..\icon.ico"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Open ${APP}"
!define MUI_FINISHPAGE_RUN_FUNCTION OpenApp
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function OpenApp
  Exec '"$INSTDIR\python\pythonw.exe" "$INSTDIR\app\jl_retro.pyw"'
FunctionEnd

; Stops this install's copy only; other Python programs on the PC keep running.
!macro StopApp
  nsExec::Exec `powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $$_.ExecutablePath -eq '$INSTDIR\python\pythonw.exe' } | Invoke-CimMethod -MethodName Terminate"`
  Sleep 500
!macroend

Section "Install"
  !insertmacro StopApp
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\app"
  SetOutPath "$INSTDIR"
  File /r "dist\stage\*.*"
  WriteUninstaller "$INSTDIR\Uninstall ${APP}.exe"

  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/NOSHORTCUTS" $1
  ${If} ${Errors}
    CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\app\jl_retro.pyw"' "$INSTDIR\app\icon.ico"
    CreateShortcut "$SMPROGRAMS\${APP}.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\app\jl_retro.pyw"' "$INSTDIR\app\icon.ico"
    WriteRegDWORD HKCU "${UNINST_KEY}" "MadeShortcuts" 1
  ${EndIf}

  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "EchoForge"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\app\icon.ico"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall ${APP}.exe"'
  WriteRegStr HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall ${APP}.exe" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  !insertmacro StopApp
  ReadRegDWORD $0 HKCU "${UNINST_KEY}" "MadeShortcuts"
  ${If} $0 == 1  ; only ones this installer made, never a same-named shortcut of the user's
    Delete "$DESKTOP\${APP}.lnk"
    Delete "$SMPROGRAMS\${APP}.lnk"
  ${EndIf}
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\app"
  Delete "$INSTDIR\Uninstall ${APP}.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
