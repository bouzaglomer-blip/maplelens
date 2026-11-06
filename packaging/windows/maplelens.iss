; Inno Setup script: MapleLens-Setup-X.Y.Z.exe, a per-user install with no admin prompt.
; Run through scripts/build_installer.py, which passes the version and the frozen app folder:
;   ISCC /DAppVersion=X.Y.Z /DSourceDir=<repo>\dist\MapleLens /O<repo>\dist maplelens.iss

#ifndef AppVersion
  #error Pass /DAppVersion=X.Y.Z (scripts/build_installer.py does)
#endif
#ifndef SourceDir
  #error Pass /DSourceDir=<the frozen app folder> (scripts/build_installer.py does)
#endif
; MapleLens holds this mutex while it runs (APP_MUTEX in src/maplelens/app.py).
#define AppMutexName "MapleLensRunning"

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
; A running MapleLens holds its files: Setup and the uninstaller close it ([Code] below).
; Restart Manager backs that up for Setup. Don't restart it: the last page offers to launch.
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

[Code]
function MapleLensRunning(): Boolean;
begin
  Result := CheckForMutexes('{#AppMutexName}');
end;

// Wait up to 3 s for MapleLens to exit.
function WaitForExit(): Boolean;
var
  Waited: Integer;
begin
  Waited := 0;
  while MapleLensRunning() and (Waited < 3000) do
  begin
    Sleep(250);
    Waited := Waited + 250;
  end;
  Result := not MapleLensRunning();
end;

// MapleLens has no window that answers a close request (its windows are overlays), so
// after asking the player, end it. Settings and each EXP segment are saved as they
// happen, so only the segment in progress is lost, as when the app crashes.
function CloseMapleLens(Next: String): Boolean;
var
  Code: Integer;
begin
  Result := True;
  if not MapleLensRunning() then
    Exit;
  if SuppressibleMsgBox('MapleLens is running. Close it and ' + Next + '?',
      mbConfirmation, MB_OKCANCEL, IDOK) <> IDOK then
  begin
    Result := False;
    Exit;
  end;
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM MapleLens.exe', '', SW_HIDE,
    ewWaitUntilTerminated, Code);
  Result := WaitForExit();
  if not Result then
    SuppressibleMsgBox('MapleLens is still running. Quit it from its right-click menu, ' +
      'then try again.', mbError, MB_OK, IDOK);
end;

function InitializeSetup(): Boolean;
begin
  Result := CloseMapleLens('continue');
end;

function InitializeUninstall(): Boolean;
begin
  Result := CloseMapleLens('uninstall it');
end;
