; Inno Setup script for TaxFlow Pro v3.10.0 Windows installer.
; Requires Inno Setup 6+ and the PyInstaller bundle at ..\dist\TaxFlowPro\.

#define MyAppName "TaxFlow Pro"
#define MyAppVersion "3.10.0"
#define MyAppPublisher "Fair Cash Investments, Inc."
#define MyAppURL "https://faircashinvestments.com"
#define MyAppExeName "TaxFlowPro.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=TaxFlowPro-{#MyAppVersion}-Setup
OutputDir=..\dist\installer
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
; Customize wizard page headers/titles to use the app name.
SelectLanguageTitle=TaxFlow Pro Installer
SelectLanguageSubtitle=Choose the language for the TaxFlow Pro installation.
SetupAppTitle=TaxFlow Pro Installer
SetupWindowTitle=TaxFlow Pro Installer
WelcomeLabel1=Welcome to the TaxFlow Pro Installer
WelcomeLabel2=This will install TaxFlow Pro %[Version] on your computer.%n%nIt is recommended that you close all other applications before continuing.
WizardLicense=License Agreement
LicenseLabel=License Agreement
LicenseLabel3=Please review the license terms before installing TaxFlow Pro.
WizardSelectDir=Select Destination Location
SelectDirLabel=Where should TaxFlow Pro be installed?
SelectDirDesc=Select the folder in which to install TaxFlow Pro.
WizardSelectComponents=Select Components
SelectComponentsLabel=Which components should be installed?
WizardSelectProgramGroup=Select Start Menu Folder
SelectStartMenuFolderLabel=Where should the program's shortcuts be placed?
WizardReady=Ready to Install
ReadyLabel1=The installer is now ready to begin installing TaxFlow Pro on your computer.
ReadyLabel2=Click Install to continue with the installation, or click Back if you want to review or change any settings.
WizardInstalling=Installing
InstallingLabel=Please wait while the installer installs TaxFlow Pro on your computer.
WizardFinished=Completing the TaxFlow Pro Installer
FinishedLabel=The installer has finished installing TaxFlow Pro on your computer.
FinishedLabelNoIcons=The installer has finished installing TaxFlow Pro on your computer.
UninstallAppFullTitle=Uninstall TaxFlow Pro
UninstallAppTitle=Uninstall TaxFlow Pro
ConfirmUninstall=Are you sure you want to completely remove TaxFlow Pro and all of its components?
UninstallStatusUninstalling=Uninstalling TaxFlow Pro, please wait...
UninstallStatusRemoved=Removed TaxFlow Pro
StatusUninstalling=Uninstalling TaxFlow Pro...
StatusCreatedUninstaller=Creating uninstaller: TaxFlow Pro...

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Recursively include the entire one-dir bundle.
Source: "..\dist\TaxFlowPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
