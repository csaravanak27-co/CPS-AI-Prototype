; Inno Setup 6 installer for the validated Windows 10/11 desktop target.
; Compile only after packaging/cps.spec has produced dist\CPS\CPS.exe.
#define AppName "C.P.S."
#define AppPublisher "C.P.S. Team"
#define AppExeName "CPS.exe"
#define AppVersion GetFileVersion("..\dist\CPS\CPS.exe")

[Setup]
AppId={{B7BA1D1E-3E40-4F93-8A2E-AAD9D7B977A0}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\CPS
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=CPS-Setup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}
; User data is deliberately outside {app}; uninstall leaves user data intact.

[Files]
Source: "..\dist\CPS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Parameters: "--backend"
Name: "{userprograms}\{#AppName} (desktop only)"; Filename: "{app}\{#AppExeName}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Parameters: "--backend"

[Run]
Filename: "{app}\{#AppExeName}"; Parameters: "--backend"; Description: "Launch {#AppName} with local backend"; Flags: nowait postinstall skipifsilent
