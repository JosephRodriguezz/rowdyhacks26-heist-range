<#
.SYNOPSIS
  Find the four corners of a tilted screen in a scene image, so an overlay can be fitted onto it in perspective.

.DESCRIPTION
  Grows a region of similar colour outward from a seed point inside the glass (stopping at the bezel), then reports the
  corners of that region: top-left, top-right, bottom-right, bottom-left, in pixels of the original 1672x941 art, ready to
  paste into scene code as [[x,y],[x,y],[x,y],[x,y]].
  Probe the glass colour first with  measure.ps1 -Probe "x,y"  and pass it as -R -G -B.
  -Preview writes a copy of the image with the found quad drawn on it. LOOK at it before trusting the numbers.

.EXAMPLE
  .\corners.ps1 -Image ..\..\scenes-v2\11_blue_pursuit.png -R 25 -G 33 -B 52 -Tol 26 -SeedX 1250 -SeedY 700 -X0 860 -Y0 560 -X1 1660 -Y1 880 -Preview C:\temp\q11.png
#>
param(
  [Parameter(Mandatory)][string]$Image,
  [Parameter(Mandatory)][int]$R, [Parameter(Mandatory)][int]$G, [Parameter(Mandatory)][int]$B,
  [int]$Tol = 30,
  [Parameter(Mandatory)][int]$SeedX, [Parameter(Mandatory)][int]$SeedY,
  [int]$X0 = 0, [int]$Y0 = 0, [int]$X1 = -1, [int]$Y1 = -1,
  [int]$Step = 2,
  [string]$Preview = ''
)
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap ((Resolve-Path $Image).Path)
try {
  $W = $bmp.Width; $H = $bmp.Height
  if ($X1 -lt 0) { $X1 = $W }; if ($Y1 -lt 0) { $Y1 = $H }
  $X1 = [Math]::Min($X1, $W); $Y1 = [Math]::Min($Y1, $H)
  $gw = [int][Math]::Ceiling(($X1 - $X0) / $Step); $gh = [int][Math]::Ceiling(($Y1 - $Y0) / $Step)
  $hit = New-Object 'bool[]' ($gw * $gh)
  for ($gy = 0; $gy -lt $gh; $gy++) {
    $y = $Y0 + $gy * $Step
    for ($gx = 0; $gx -lt $gw; $gx++) {
      $c = $bmp.GetPixel($X0 + $gx * $Step, $y)
      $hit[$gy * $gw + $gx] = ([Math]::Abs($c.R - $R) -le $Tol -and [Math]::Abs($c.G - $G) -le $Tol -and [Math]::Abs($c.B - $B) -le $Tol)
    }
  }
  $sx0 = [int][Math]::Floor(($SeedX - $X0) / $Step); $sy0 = [int][Math]::Floor(($SeedY - $Y0) / $Step)
  if ($sx0 -lt 0 -or $sx0 -ge $gw -or $sy0 -lt 0 -or $sy0 -ge $gh) { 'seed is outside the searched region'; return }
  if (-not $hit[$sy0 * $gw + $sx0]) { 'seed pixel does not match the colour: probe it and adjust -R -G -B / -Tol'; return }
  $keep = New-Object 'bool[]' ($gw * $gh)
  $q = New-Object 'System.Collections.Generic.Queue[int]'
  $q.Enqueue($sy0 * $gw + $sx0); $keep[$sy0 * $gw + $sx0] = $true
  while ($q.Count -gt 0) {
    $i = $q.Dequeue(); $cx = $i % $gw; $cy = [int][Math]::Floor($i / $gw)
    foreach ($d in @(@(1, 0), @(-1, 0), @(0, 1), @(0, -1))) {
      $nx = $cx + $d[0]; $ny = $cy + $d[1]
      if ($nx -ge 0 -and $nx -lt $gw -and $ny -ge 0 -and $ny -lt $gh) {
        $j = $ny * $gw + $nx
        if ($hit[$j] -and -not $keep[$j]) { $keep[$j] = $true; $q.Enqueue($j) }
      }
    }
  }
  $tl = $null; $tr = $null; $br = $null; $bl = $null; $n = 0
  $bTL = 1e9; $bTR = -1e9; $bBR = -1e9; $bBL = 1e9
  for ($i = 0; $i -lt $keep.Length; $i++) {
    if (-not $keep[$i]) { continue }
    $x = $X0 + ($i % $gw) * $Step; $y = $Y0 + [int][Math]::Floor($i / $gw) * $Step; $n++
    $s = $x + $y; $d = $x - $y
    if ($s -lt $bTL) { $bTL = $s; $tl = @($x, $y) }
    if ($d -gt $bTR) { $bTR = $d; $tr = @($x, $y) }
    if ($s -gt $bBR) { $bBR = $s; $br = @($x, $y) }
    if ($d -lt $bBL) { $bBL = $d; $bl = @($x, $y) }
  }
  "region: $n samples"
  foreach ($p in @(@('top-left', $tl), @('top-right', $tr), @('bottom-right', $br), @('bottom-left', $bl))) {
    '{0,-13} px ({1,4},{2,4})   % ({3:N1}, {4:N1})' -f $p[0], $p[1][0], $p[1][1], (100 * $p[1][0] / $W), (100 * $p[1][1] / $H)
  }
  'JS: [[{0},{1}],[{2},{3}],[{4},{5}],[{6},{7}]]' -f $tl[0], $tl[1], $tr[0], $tr[1], $br[0], $br[1], $bl[0], $bl[1]
  if ($Preview) {
    $copy = New-Object System.Drawing.Bitmap $bmp
    $gfx = [System.Drawing.Graphics]::FromImage($copy)
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::Magenta), 3
    $pts = @((New-Object System.Drawing.Point $tl[0], $tl[1]), (New-Object System.Drawing.Point $tr[0], $tr[1]), (New-Object System.Drawing.Point $br[0], $br[1]), (New-Object System.Drawing.Point $bl[0], $bl[1]))
    $gfx.DrawPolygon($pen, [System.Drawing.Point[]]$pts)
    $dir = Split-Path $Preview -Parent; if ($dir) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $copy.Save($Preview, [System.Drawing.Imaging.ImageFormat]::Png)
    $gfx.Dispose(); $copy.Dispose()
    "preview written: $Preview"
  }
} finally { $bmp.Dispose() }
