; Inno Setup script: MapleLens-Setup-X.Y.Z.exe, a per-user install with no admin prompt.
; Run through scripts/build_installer.py, which passes the version and the frozen app folder:
;   ISCC /DAppVersion=X.Y.Z /DSourceDir=<repo>\dist\MapleLens /O<repo>\dist maplelens.iss

#ifndef AppVersion
  #error Pass /DAppVersion=X.Y.Z (scripts/build_installer.py does)
#endif
#ifndef SourceDir
  #error Pass /DSourceDir=<the frozen app folder> (scripts/build_installer.py does)
#endif

[Setup]
; Never change AppId: it is how a newer setup finds and replaces an installed MapleLens.
AppId={{F09F003D-9781-4B3F-91DC-C1A6806FCB91}
AppName=MapleLens
AppVersion={#AppVersion}
AppVerName=MapleLens {#AppVersion}
AppPublisher=or-keren
AppPublisherURL=https://github.com/or-keren/maplelens
AppSupportURL=https://github.com/or-keren/maplelens/issues
AppUpdatesURL=https://github.com/or-keren/maplelens/releases
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={userpf}\MapleLens
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputBaseFilename=MapleLens-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\MapleLens.exe
UninstallDisplayName=MapleLens
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; A running MapleLens holds its files: ask the player to close it, and don't restart it
; (the last page offers to launch the new version).
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Files a newer build no longer ships must not linger from the old one.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MapleLens"; Filename: "{app}\MapleLens.exe"
Name: "{autodesktop}\MapleLens"; Filename: "{app}\MapleLens.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MapleLens.exe"; Description: "{cm:LaunchProgram,MapleLens}"; Flags: nowait postinstall skipifsilent

; Settings, EXP history and the log live in %APPDATA%\MapleLens, outside {app}, so the
; uninstaller leaves them alone.
