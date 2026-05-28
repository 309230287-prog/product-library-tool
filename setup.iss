[Setup]
AppId={{B8F2A3D1-6E5C-4A7B-9C1D-2F8E3A5B7D9F}
AppName=商品库工具
AppVersion=2.1
AppPublisher=商品库整理项目
DefaultDirName={autopf}\商品库工具
DefaultGroupName=商品库工具
OutputDir=dist
OutputBaseFilename=商品库工具_v2.1_安装包
Compression=lzma2
SolidCompression=yes
UninstallDisplayName=商品库工具 v2.1
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
DisableDirPage=no
DirExistsWarning=yes

[Files]
Source: "dist\商品库工具.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "配置.xlsx"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\data"

[Icons]
Name: "{group}\商品库工具"; Filename: "{app}\商品库工具.exe"
Name: "{group}\卸载商品库工具"; Filename: "{uninstallexe}"
Name: "{commondesktop}\商品库工具"; Filename: "{app}\商品库工具.exe"

[Run]
Filename: "{app}\商品库工具.exe"; Description: "立即启动商品库工具"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
