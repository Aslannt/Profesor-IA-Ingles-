; Inno Setup: instalador de la app de la laptop. Igual que el del Copiloto: se instala para el
; usuario (%LOCALAPPDATA%\Programs), sin pedir permisos de administrador.
;
;   ISCC.exe packaging\instalador.iss      (o mejor: packaging\construir_instalador_mama.ps1)

#define AppName "Profesora de Inglés"
#define AppVersion "0.2.0"
#define AppPublisher "Deivid"
#define AppExe "ProfesoraDeIngles.exe"
#define SourceDir "..\dist\ProfesoraDeIngles"

[Setup]
AppId={{3B7F1C62-9A4E-4D0B-8F21-PROFESORA001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ProfesoraDeIngles-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName} ahora"; Flags: nowait postinstall skipifsilent

; La configuración y los registros quedan en %LOCALAPPDATA%\ProfesoraDeIngles al desinstalar.
