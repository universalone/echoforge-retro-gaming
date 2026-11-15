# Builds packaging\dist\EchoForge-Retro-Gaming-<version>-win64.zip from Python's official signed runtime plus Retro's own
# plain scripts. No program of our own at all: a PyInstaller wrapper (2.3) and then an NSIS installer (2.4, 2.5 tests) were
# both flagged by Windows Defender's machine learning as Trojan:Win32/Bearfoos.A!ml, a false alarm that hits unsigned
# programs that unpack and run Python. EchoForge installs the zip (or Retro updates itself from it); someone without
# EchoForge unzips it and starts it once, and Retro makes its own shortcuts and Apps entry (jl_retro.pyw self_register).
$root = Split-Path $PSScriptRoot -Parent
$PYTHON_VERSION = '3.12.10'
$stage = "$PSScriptRoot\dist\stage"
$version = [regex]::Match((Get-Content "$root\jl_retro.pyw" -Raw), 'APP_VERSION = "([^"]+)"').Groups[1].Value
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory "$stage\app\web", "$stage\python", "$PSScriptRoot\cache" -Force | Out-Null

$zip = "$PSScriptRoot\cache\python-$PYTHON_VERSION-embed-amd64.zip"
if (-not (Test-Path $zip)) {
  $ProgressPreference = 'SilentlyContinue'
  Invoke-WebRequest "https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-embed-amd64.zip" -OutFile $zip -UseBasicParsing
}
Expand-Archive $zip "$stage\python"
$sig = Get-AuthenticodeSignature "$stage\python\pythonw.exe"
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw "pythonw.exe isn't signed by Python: $($sig.Status)" }

python -m pip install --quiet --disable-pip-version-check --target "$stage\python\Lib\site-packages" --only-binary :all: --python-version 3.12 --platform win_amd64 pillow
if ($LASTEXITCODE) { throw 'pip failed' }
Add-Content "$stage\python\python312._pth" 'Lib\site-packages'

Copy-Item "$root\jl_retro.pyw", "$root\art_fetch.py", "$root\rom_inbox.py", "$root\save_backup.py", "$root\winutil.py", "$root\synopsis.py", "$root\padquit.py", "$root\selfupdate.py", "$root\padwatch.ps1", "$root\icon.ico" "$stage\app"
Copy-Item "$root\web\*" "$stage\app\web"
Set-Content "$stage\app\installed.txt" $version  # tells jl_retro.pyw to keep its data in the user's profile

# For someone who unzips it by hand: a way to start it, and what to do.
Set-Content "$stage\Start EchoForge Retro Gaming.cmd" "@echo off`r`nstart `"`" `"%~dp0python\pythonw.exe`" `"%~dp0app\jl_retro.pyw`"" -Encoding ascii
Set-Content "$stage\READ ME FIRST.txt" @"
EchoForge Retro Gaming $version

The easy way: install it from EchoForge (press RETRO FORGE at the top).

By hand:
1. Move this folder where you want it to stay, for example %LOCALAPPDATA%\Programs\EchoForge Retro Gaming.
2. Double-click "Start EchoForge Retro Gaming".
   The first time, it adds itself to the Start menu, the Desktop and Windows' list of apps (Settings > Apps),
   where you can uninstall it later. Your favorites, history and settings are kept in your user profile.

EchoForge Retro Gaming doesn't include or download games, firmware or BIOS files. Use games you own.
"@ -Encoding ascii

$zipOut = "$PSScriptRoot\dist\EchoForge-Retro-Gaming-$version-win64.zip"
if (Test-Path $zipOut) { Remove-Item $zipOut -Force }
python -I -c "import sys, zipfile, pathlib; s = pathlib.Path(sys.argv[1]); z = zipfile.ZipFile(sys.argv[2], 'w', zipfile.ZIP_DEFLATED, compresslevel=9); [z.write(p, p.relative_to(s).as_posix()) for p in sorted(s.rglob('*')) if p.is_file()]; z.close()" $stage $zipOut
if ($LASTEXITCODE) { throw 'zip failed' }
Get-Item $zipOut | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}, LastWriteTime
