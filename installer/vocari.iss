; Inno Setup script for Vocari — see README "Сборка установщика".
;
; Installs per-user (no admin/UAC needed for Vocari itself) into
; %LOCALAPPDATA%\Programs\Vocari, matching how Discord/VS Code/etc. install —
; config.json/logs/silero_cache/assets keep living next to Vocari.exe (see
; vocari/paths.py), same as a plain unzipped dist/Vocari/ folder, no code
; changes needed for this to work.
;
; Also bundles and (only if missing) silently installs the Microsoft Visual
; C++ Redistributable (x64) — its absence is what causes the "Failed to load
; Python DLL ... LoadLibrary: The specified module could not be found" error
; some users hit with a bare dist/Vocari/ folder, since python312.dll itself
; depends on it. That one sub-step needs admin — Windows will show a single
; UAC prompt for it if the redist isn't already present; the rest of the
; install stays unelevated.
;
; Build: run "python installer\build_installer.py" (see README) — it fills
; in MyAppVersion from vocari/__version__.py and calls ISCC for you.
;
; Branding: SetupIconFile/WizardImageFile/WizardSmallImageFile below all
; come from the app's real icon (assets/branding/) — installer\branding\
; holds two PNG renders of it sized for Inno Setup's wizard image slots
; (portrait sidebar + small corner logo); the wide GitHub banner doesn't fit
; that shape without an ugly crop, so it isn't used here.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "Vocari"
#define MyAppExeName "Vocari.exe"
#define MyAppPublisher "Vocari"

[Setup]
AppId={{0CD8F917-C52D-4E4E-BB8E-4AF89AC20D6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
; No folder-picker page at all - always the same fixed per-user location,
; matching how Discord/Chrome/etc. install. Without this, Setup still
; remembered the last-used path via AppId (Inno's default UsePreviousAppDir
; behavior), but still made every run click through a page to confirm it -
; a real update should be double-click and done. A one-off custom location
; (e.g. for testing) is still possible via the command line: VocariSetup.exe
; /DIR="X:\some\path" works even with the page disabled.
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output
OutputBaseFilename=VocariSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\assets\branding\icon.ico
WizardStyle=modern
SetupIconFile=..\assets\branding\icon.ico
WizardImageFile=branding\wizard_image.png
WizardSmallImageFile=branding\wizard_small.png

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; A local smoke test may create user-specific runtime state inside dist.
; Never ship settings, tokens, logs, caches, or downloaded dependencies.
Source: "..\dist\Vocari\*"; DestDir: "{app}"; Excludes: "config.json,config.json.bak,.config.json.*.tmp,.config.json.bak.*.tmp,logs\*,silero_cache\*,runtime_deps\*,assets\branding\banner_github.png"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

[InstallDelete]
; Remove documentation artwork left by older installers during an in-place update.
Type: files; Name: "{app}\assets\branding\banner_github.png"

[Icons]
; IconFilename points at our own .ico explicitly rather than relying on
; Windows extracting one from the .exe's embedded resource — the exe's icon
; is set correctly (vocari.spec's EXE(icon=...)), but Explorer/the taskbar
; cache icons per file path and can keep showing a stale one (e.g. the old
; icon-less default) after an in-place upgrade until that cache clears; a
; shortcut with its own explicit IconFilename doesn't depend on that.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\branding\icon.ico"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\branding\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Устанавливаем Microsoft Visual C++ Redistributable…"; Check: VCRedistNeedsInstall; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
function VCRedistNeedsInstall: Boolean;
var
  Version: String;
begin
  // Present (any recent 2015-2022 redist installs/updates this same key) if
  // this registry value exists at all — absence means python312.dll won't load.
  Result := not RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64', 'Version', Version);
end;
