#define MyAppName "PCCOOLER-LCD Control"
#define MyAppVersion "3.0.0-beta1"
#define MyAppPublisher "Rodger"
#define MyAppExeName "PCCOOLER-LCD-Control.exe"

[Setup]
AppId={{B588D10C-904B-47E3-9822-1CFEC6283626}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PCCOOLER-LCD Control
DefaultGroupName=PCCOOLER-LCD Control
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=PCCOOLER-LCD-Control-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Start PCCOOLER-LCD Control when I sign in"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\PCCOOLER-LCD-Control\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PCCOOLER-LCD Control"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\PCCOOLER-LCD Control"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\PCCOOLER-LCD Control"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch PCCOOLER-LCD Control"; Flags: nowait postinstall skipifsilent
