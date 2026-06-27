; NSIS installer script for TaxFlow Pro 3.11.5
!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "TaxFlow Pro"
OutFile "C:\Users\James Clawd\.openclaw\workspace\projects\TaxFlow-Pro\TaxFlow-Pro-v3.9\dist\installers\TaxFlowPro-3.11.5-Setup.exe"
InstallDir "$LOCALAPPDATA\TaxFlowPro"
RequestExecutionLevel user

!define MUI_ICON "C:\Users\James Clawd\.openclaw\workspace\projects\TaxFlow-Pro\TaxFlow-Pro-v3.9\scripts\packaging\assets\icon.ico"
!define MUI_UNICON "C:\Users\James Clawd\.openclaw\workspace\projects\TaxFlow-Pro\TaxFlow-Pro-v3.9\scripts\packaging\assets\icon.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    File /r "C:\Users\James Clawd\.openclaw\workspace\projects\TaxFlow-Pro\TaxFlow-Pro-v3.9\dist\pyinstaller\TaxFlowPro\*.*"

    ; Create user data directories outside install dir
    CreateDirectory "$LOCALAPPDATA\TaxFlowPro\db"
    CreateDirectory "$LOCALAPPDATA\TaxFlowPro\backups"
    CreateDirectory "$LOCALAPPDATA\TaxFlowPro\uploads"
    CreateDirectory "$LOCALAPPDATA\TaxFlowPro\ml"
    CreateDirectory "$LOCALAPPDATA\TaxFlowPro\logs"

    ; Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\TaxFlow Pro"
    CreateShortcut "$SMPROGRAMS\TaxFlow Pro\TaxFlow Pro.lnk" "$INSTDIR\TaxFlowPro.exe"
    CreateShortcut "$SMPROGRAMS\TaxFlow Pro\Uninstall TaxFlow Pro.lnk" "$INSTDIR\uninst.exe"

    ; Uninstaller
    WriteUninstaller "$INSTDIR\uninst.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TaxFlowPro" "DisplayName" "TaxFlow Pro"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TaxFlowPro" "UninstallString" "$\"$INSTDIR\uninst.exe$\""
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TaxFlowPro" "DisplayVersion" "3.11.5"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TaxFlowPro" "InstallLocation" "$INSTDIR"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\*.*"
    RMDir /r "$INSTDIR"
    Delete "$SMPROGRAMS\TaxFlow Pro\*.lnk"
    RMDir "$SMPROGRAMS\TaxFlow Pro"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TaxFlowPro"
SectionEnd

Function .onInit
    ; Silent install support
    IfSilent 0 +2
    SetSilent silent
FunctionEnd
