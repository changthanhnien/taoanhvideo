; Inno Setup Script for NAVTools
; Reference: https://jrsoftware.org/ishelp/

[Setup]
AppName=NAV TOOLS
AppVersion=2.0.0
AppPublisher=eKids
DefaultDirName={autopf}\NAVTools
DefaultGroupName=NAV TOOLS
AllowNoIcons=yes
OutputDir=d:\Downloads
OutputBaseFilename=NAVTools_Setup
SetupIconFile=d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\assets\navtools.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no
CloseApplications=force

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\dist\NAVTools\NAVTools.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\dist\NAVTools\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NAV TOOLS"; Filename: "{app}\NAVTools.exe"
Name: "{group}\{cm:UninstallProgram,NAV TOOLS}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\NAV TOOLS"; Filename: "{app}\NAVTools.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NAVTools.exe"; Description: "{cm:LaunchProgram,NAV TOOLS}"; Flags: nowait postinstall skipifsilent
