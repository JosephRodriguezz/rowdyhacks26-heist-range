<#
.SYNOPSIS
  Compare two screenshots over a region (default: the stage in a 1500x960 snapshot) and report how different they are.

.EXAMPLE
  .\imgdiff.ps1 -A old.png -B new.png
  .\imgdiff.ps1 -A old.png -B new.png -X 0 -Y 0 -W 1500 -H 960   # whole page
#>
param(
  [Parameter(Mandatory)][string]$A,
  [Parameter(Mandatory)][string]$B,
  [int]$X = 140, [int]$Y = 72, [int]$W = 1220, [int]$H = 683,   # stage region inside a 1500x960 snapshot
  [int]$Step = 2
)
Add-Type -AssemblyName System.Drawing
$ba = [Drawing.Bitmap]::FromFile((Resolve-Path $A).Path)
$bb = [Drawing.Bitmap]::FromFile((Resolve-Path $B).Path)
try {
  if ($ba.Width -ne $bb.Width -or $ba.Height -ne $bb.Height) { "SIZE MISMATCH: $($ba.Width)x$($ba.Height) vs $($bb.Width)x$($bb.Height)"; return }
  $n = 0; $sum = 0L; $diff = 0; $max = 0
  for ($yy = $Y; $yy -lt [Math]::Min($Y + $H, $ba.Height); $yy += $Step) {
    for ($xx = $X; $xx -lt [Math]::Min($X + $W, $ba.Width); $xx += $Step) {
      $pa = $ba.GetPixel($xx, $yy); $pb = $bb.GetPixel($xx, $yy)
      $d = [Math]::Abs($pa.R - $pb.R) + [Math]::Abs($pa.G - $pb.G) + [Math]::Abs($pa.B - $pb.B)
      $sum += $d; $n++
      if ($d -gt 30) { $diff++ }
      if ($d -gt $max) { $max = $d }
    }
  }
  '{0}  vs  {1}' -f (Split-Path $A -Leaf), (Split-Path $B -Leaf)
  '  sampled {0} px | mean abs diff {1:N3} (of 765) | pixels differing >30: {2} ({3:N3}%) | worst pixel {4}' -f $n, ($sum / $n), $diff, (100 * $diff / $n), $max
} finally { $ba.Dispose(); $bb.Dispose() }
