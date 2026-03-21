; Inno Setup Script for XianyuAutoAgent
; Requires Inno Setup 6.x with ChineseSimplified.isl

#define MyAppName "XianyuAutoAgent"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "XianyuAutoAgent"
#define MyAppExeName "XianyuAutoAgent.exe"
#define SourceDir "..\build\electron-dist\win-unpacked"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\build\installer-output
OutputBaseFilename=XianyuAutoAgent-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
; Main application files
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Do not delete user data in %APPDATA%\XianyuAutoAgent (chat history and config)

[Code]
// Keep user data directory on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // Intentionally empty - user data in APPDATA is preserved
end;
