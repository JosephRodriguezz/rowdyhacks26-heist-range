<#
.SYNOPSIS
  Screenshot the motion demo at chosen moments with headless Edge on file://. No server, Node or Python needed.

.DESCRIPTION
  Each shot launches its own throwaway browser profile, so several agents can run this at the same time.
  Frames are exact: the page renders a paused snapshot from ?t= (global seconds) or ?scene=N&lt=SECONDS.
  Prints the PNG path per shot plus any page errors found in the browser console.

.EXAMPLE
  .\snapshot.ps1 -T 0.55,1.4,12.75 -OutDir C:\temp\shots
.EXAMPLE
  .\snapshot.ps1 -Scene 11 -Lt 1,6,11 -OutDir C:\temp\shots -Prefix pursuit
.EXAMPLE
  .\snapshot.ps1 -Scene 8 -Lt 2 -Reduced -OutDir C:\temp\shots   # reduced-motion frame
#>
param(
  [double[]]$T = @(),
  [int]$Scene = 0,
  [double[]]$Lt = @(),
  [switch]$Reduced,
  [string]$OutDir = (Join-Path $env:TEMP 'motion-shots'),
  [string]$Prefix = 'shot',
  [int]$Width = 1500,
  [int]$Height = 960,
  [switch]$Twice,  # take each frame twice and report whether the PNG bytes match (determinism check)
  [int]$Retries = 2  # a capture can land before the art has painted (a blank page is ~100-250 KB, a real frame ~1 MB); retry those
)
$ErrorActionPreference = 'Stop'
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") |
  Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'No Edge or Chrome found.' }
$page = (Resolve-Path (Join-Path $PSScriptRoot '..\index.html')).Path -replace '\\', '/'
$base = 'file:///' + $page
New-Item -ItemType Directory -Force $OutDir | Out-Null

$jobs = @()
foreach ($tv in $T) { $jobs += [pscustomobject]@{ q = "t=$tv"; label = ("t{0:0.00}" -f $tv) } }
foreach ($lv in $Lt) { if ($Scene -lt 1) { throw "-Lt needs -Scene." }; $jobs += [pscustomobject]@{ q = "scene=$Scene&lt=$lv"; label = ("s{0:00}-lt{1:0.00}" -f $Scene, $lv) } }
if (-not $jobs) { throw 'Give -T or -Scene with -Lt.' }

function Shoot($url, $out) {
  $userData = Join-Path $env:TEMP ('mp-snap-' + [guid]::NewGuid().ToString('N'))
  $err = "$out.err"
  Remove-Item $out, $err -Force -ErrorAction SilentlyContinue
  $edgeArgs = @('--headless=new', '--disable-gpu', '--hide-scrollbars', "--window-size=$Width,$Height", '--virtual-time-budget=2500',
            "--user-data-dir=$userData", '--no-first-run', '--no-default-browser-check', '--enable-logging=stderr', '--v=0', "--screenshot=$out", $url)
  Start-Process -FilePath $edge -ArgumentList $edgeArgs -Wait -WindowStyle Hidden -RedirectStandardError $err | Out-Null
  $bad = @()
  if (Test-Path $err) {
    $bad = @(Select-String -Path $err -Pattern 'Uncaught|SyntaxError|ReferenceError|TypeError|\[motion\]|net::ERR' |
      Where-Object { $_.Line -notmatch 'ProtocolLaunch' } | ForEach-Object { $_.Line.Trim() })
    Remove-Item $err -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $userData -Recurse -Force -ErrorAction SilentlyContinue
  return ,$bad
}

function PixelDiff($fa, $fb) {
  Add-Type -AssemblyName System.Drawing
  $ba = [System.Drawing.Bitmap]::FromFile($fa); $bb = [System.Drawing.Bitmap]::FromFile($fb)
  try {
    if ($ba.Width -ne $bb.Width -or $ba.Height -ne $bb.Height) { return [pscustomobject]@{ Max = 765; Mean = 765; Over = 999999 } }
    $n = 0; $sum = 0L; $mx = 0; $over = 0
    for ($yy = 0; $yy -lt $ba.Height; $yy += 3) {
      for ($xx = 0; $xx -lt $ba.Width; $xx += 3) {
        $pa = $ba.GetPixel($xx, $yy); $pb = $bb.GetPixel($xx, $yy)
        $m = [Math]::Max([Math]::Abs($pa.R - $pb.R), [Math]::Max([Math]::Abs($pa.G - $pb.G), [Math]::Abs($pa.B - $pb.B)))
        $sum += $m; $n++
        if ($m -gt $mx) { $mx = $m }
        if ($m -gt 30) { $over++ }
      }
    }
    return [pscustomobject]@{ Max = $mx; Mean = ($sum / $n); Over = $over }
  } finally { $ba.Dispose(); $bb.Dispose() }
}

foreach ($j in $jobs) {
  $url = "$base`?$($j.q)" + $(if ($Reduced) { '&reduced=1' } else { '' })
  $name = "$Prefix-$($j.label)" + $(if ($Reduced) { '-reduced' } else { '' }) + '.png'
  $out = Join-Path $OutDir $name
  $bad = Shoot $url $out
  $tries = 0
  while ($tries -lt $Retries -and (-not (Test-Path $out) -or (Get-Item $out).Length -lt 400000)) { $tries++; $bad = Shoot $url $out }
  $line = '{0,-40} png:{1,-5} page-errors:{2}' -f $name, (Test-Path $out), $bad.Count
  if ($tries) { $line += "  retried:$tries" }
  if ((Test-Path $out) -and (Get-Item $out).Length -lt 400000) { $line += '  WARNING:capture still looks blank (under 400 KB)' }
  if ($Twice -and (Test-Path $out)) {
    $out2 = Join-Path $OutDir ('twice-' + $name)
    [void](Shoot $url $out2)
    if (-not (Test-Path $out2)) { $line += '  deterministic:False (second capture failed)' }
    elseif ((Get-FileHash $out).Hash -eq (Get-FileHash $out2).Hash) { $line += '  deterministic:True' }
    else {
      # Bytes differ. Tilted (perspective) content can rasterise with a +-1 rounding change, so compare pixels.
      $pd = PixelDiff $out $out2
      if ($pd.Over -eq 0 -and $pd.Mean -lt 0.05) { $line += ('  deterministic:True (bytes differ by rounding only: worst pixel {0}, mean {1:N4})' -f $pd.Max, $pd.Mean) }
      else { $line += ('  deterministic:False (worst pixel {0}, mean {1:N3}, {2} px over 30). Re-run once before blaming the scene: heavy CPU load can shift a capture.' -f $pd.Max, $pd.Mean, $pd.Over) }
    }
    Remove-Item $out2 -Force -ErrorAction SilentlyContinue
  }
  $line
  $bad | Select-Object -First 4 | ForEach-Object { "    $_" }
}
