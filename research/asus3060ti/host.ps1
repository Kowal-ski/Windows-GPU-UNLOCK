# GPL-2.0-only. Local host compilation/profile generation; no hardware writes.
param([Parameter(Mandatory)][string]$Clang,[Parameter(Mandatory)][string]$Python,
 [Parameter(Mandatory)][string]$Capture,[string]$VcVars)
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
. (Join-Path $repo 'research/profile/host.ps1')
Import-GuHostCompiler $VcVars $Clang
$locator=Build-GuFwsecLocate $repo $Clang
& $Python -I (Join-Path $repo 'research/profile/make-profile.py') $Capture $locator --experimental-asus3060ti
if($LASTEXITCODE -ne 0){throw 'Experimental profile refused; preserve the captures and resolve the reported mismatch.'}
