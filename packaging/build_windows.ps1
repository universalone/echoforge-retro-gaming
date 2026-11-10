# Builds packaging\dist\EchoForge-Retro-Gaming-Setup-<version>.exe from Python's official signed runtime plus Retro's own
# plain scripts. No wrapper .exe: PyInstaller's was flagged by Windows Defender (Trojan:Win32/Bearfoos.A!ml) in November 2026.
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

$nsis = Get-ChildItem "$env:LOCALAPPDATA\electron-builder\Cache\nsis-*\*\Bin\makensis.exe" | Select-Object -First 1
if (-not $nsis) { throw 'makensis not found' }
Set-Location $PSScriptRoot
& $nsis.FullName /V2 "/DVERSION=$version" retro.nsi
if ($LASTEXITCODE) { throw 'NSIS failed' }
Get-Item "dist\EchoForge-Retro-Gaming-Setup-$version.exe" | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}, LastWriteTime
