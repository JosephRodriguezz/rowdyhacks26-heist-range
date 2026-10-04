<#
.SYNOPSIS
  Find where something is in a scene image: the glass of a screen, a light, a coloured object. Reports its bounding box
  and centre in % of the image, which is what scene code needs (left/top/width/height and glow x/y).

.DESCRIPTION
  Coordinates are pixels of the original 1672x941 art. Accurate to about +-2 px at -Step 2.

  -Probe "x,y;x,y"   print the colour at points (and the mean of a small patch). Do this FIRST to learn the colour you are
                     looking for, e.g. the glass of a dead screen.
  -Mode color        pixels within -Tol of -R -G -B
  -Mode bright       luminance above -Threshold (lamps, light bars, headlights)
  -Mode dark         every channel below -Threshold. WARNING: this also matches dark bezels and shadows around a screen,
                     so its box is too big. For screens use -Mode color with -SeedX/-SeedY instead.
  -SeedX -SeedY      keep only the connected region that contains this point. This is how you get a screen's glass without
                     the bezel: probe the glass colour, then grow from a point inside it.

  Always confirm a result with snapshot.ps1 and crop.ps1 before trusting it.

.EXAMPLE
  .\measure.ps1 -Image ..\..\scenes-v2\04_large_straight_website-r4.png -Probe "1200,280;830,110"
  .\measure.ps1 -Image ..\..\scenes-v2\04_large_straight_website-r4.png -Mode color -R 20 -G 28 -B 52 -Tol 28 -SeedX 1200 -SeedY 280 -X0 780 -Y0 60 -X1 1640 -Y1 490
  .\measure.ps1 -Image ..\..\scenes-v2\08_bank_exit.png -X0 100 -Y0 450 -X1 330 -Y1 600 -Mode bright -Threshold 200
#>
param(
  [Parameter(Mandatory)][string]$Image,
  [string]$Probe = '',
  [int]$X0 = 0, [int]$Y0 = 0, [int]$X1 = -1, [int]$Y1 = -1,
  [ValidateSet('dark', 'bright', 'color')][string]$Mode = 'dark',
  [int]$Threshold = 40,
  [int]$R = 0, [int]$G = 0, [int]$B = 0, [int]$Tol = 40,
  [int]$SeedX = -1, [int]$SeedY = -1,
  [int]$Step = 2
)
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap ((Resolve-Path $Image).Path)
try {
  $W = $bmp.Width; $H = $bmp.Height
  "image ${W}x${H}"
  if ($Probe) {
    foreach ($pt in ($Probe -split ';')) {
      $xy = $pt.Trim() -split ','; $px = [int]$xy[0]; $py = [int]$xy[1]
      $sr = 0; $sg = 0; $sb = 0; $k = 0
      for ($dy = -3; $dy -le 3; $dy += 3) { for ($dx = -3; $dx -le 3; $dx += 3) {
        $c = $bmp.GetPixel([Math]::Min([Math]::Max($px + $dx, 0), $W - 1), [Math]::Min([Math]::Max($py + $dy, 0), $H - 1)); $sr += $c.R; $sg += $c.G; $sb += $c.B; $k++ } }
      'probe ({0},{1}): RGB {2},{3},{4}   (patch mean)' -f $px, $py, [int]($sr / $k), [int]($sg / $k), [int]($sb / $k)
    }
    return
  }
  if ($X1 -lt 0) { $X1 = $W }; if ($Y1 -lt 0) { $Y1 = $H }
  $X1 = [Math]::Min($X1, $W); $Y1 = [Math]::Min($Y1, $H)
  $gw = [int][Math]::Ceiling(($X1 - $X0) / $Step); $gh = [int][Math]::Ceiling(($Y1 - $Y0) / $Step)
  $hit = New-Object 'bool[]' ($gw * $gh)
  for ($gy = 0; $gy -lt $gh; $gy++) {
    $y = $Y0 + $gy * $Step
    for ($gx = 0; $gx -lt $gw; $gx++) {
      $c = $bmp.GetPixel($X0 + $gx * $Step, $y)
      switch ($Mode) {
        'dark'   { $m = ($c.R -lt $Threshold -and $c.G -lt $Threshold -and $c.B -lt $Threshold) }
        'bright' { $m = ((0.2126 * $c.R + 0.7152 * $c.G + 0.0722 * $c.B) -gt $Threshold) }
        'color'  { $m = ([Math]::Abs($c.R - $R) -le $Tol -and [Math]::Abs($c.G - $G) -le $Tol -and [Math]::Abs($c.B - $B) -le $Tol) }
      }
      $hit[$gy * $gw + $gx] = $m
    }
  }
  $keep = $hit
  if ($SeedX -ge 0) {
    $sx0 = [int][Math]::Floor(($SeedX - $X0) / $Step); $sy0 = [int][Math]::Floor(($SeedY - $Y0) / $Step)
    if ($sx0 -lt 0 -or $sx0 -ge $gw -or $sy0 -lt 0 -or $sy0 -ge $gh) { 'seed is outside the searched region'; return }
    if (-not $hit[$sy0 * $gw + $sx0]) { 'seed pixel does not match the rule: probe its colour and widen -Tol'; return }
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
  }
  $minx = 99999; $maxx = -1; $miny = 99999; $maxy = -1; $n = 0; $sx = 0L; $sy = 0L
  for ($i = 0; $i -lt $keep.Length; $i++) {
    if ($keep[$i]) {
      $x = $X0 + ($i % $gw) * $Step; $y = $Y0 + [int][Math]::Floor($i / $gw) * $Step
      $n++; $sx += $x; $sy += $y
      if ($x -lt $minx) { $minx = $x }; if ($x -gt $maxx) { $maxx = $x }
      if ($y -lt $miny) { $miny = $y }; if ($y -gt $maxy) { $maxy = $y }
    }
  }
  "mode $Mode, searched x $X0..$X1 y $Y0..$Y1" + $(if ($SeedX -ge 0) { ", connected to seed ($SeedX,$SeedY)" } else { '' })
  if ($n -eq 0) { 'no matching pixels'; return }
  'matches: {0} samples' -f $n
  'bounding box px : left {0}  top {1}  right {2}  bottom {3}' -f $minx, $miny, $maxx, $maxy
  'bounding box %  : left {0:N1}  top {1:N1}  width {2:N1}  height {3:N1}' -f (100 * $minx / $W), (100 * $miny / $H), (100 * ($maxx - $minx) / $W), (100 * ($maxy - $miny) / $H)
  'centre %        : x {0:N1}  y {1:N1}' -f (100 * ($sx / $n) / $W), (100 * ($sy / $n) / $H)
} finally { $bmp.Dispose() }
