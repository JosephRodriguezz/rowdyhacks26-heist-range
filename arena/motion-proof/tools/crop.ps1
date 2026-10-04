<#
.SYNOPSIS
  Crop a region out of a screenshot and enlarge it, so small details (screens, light bars, glints) can be inspected.

.EXAMPLE
  .\crop.ps1 -In shot.png -X 700 -Y 120 -W 500 -H 300 -Scale 2 -Out zoom.png
#>
param(
  [Parameter(Mandatory)][string]$In,
  [Parameter(Mandatory)][int]$X, [Parameter(Mandatory)][int]$Y, [Parameter(Mandatory)][int]$W, [Parameter(Mandatory)][int]$H,
  [double]$Scale = 2,
  [Parameter(Mandatory)][string]$Out
)
Add-Type -AssemblyName System.Drawing
$src = [Drawing.Bitmap]::FromFile((Resolve-Path $In).Path)
try {
  $W = [Math]::Min($W, $src.Width - $X); $H = [Math]::Min($H, $src.Height - $Y)
  $dw = [int]($W * $Scale); $dh = [int]($H * $Scale)
  $dst = New-Object Drawing.Bitmap $dw, $dh
  $g = [Drawing.Graphics]::FromImage($dst)
  $g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.DrawImage($src, (New-Object Drawing.Rectangle 0, 0, $dw, $dh), (New-Object Drawing.Rectangle $X, $Y, $W, $H), [Drawing.GraphicsUnit]::Pixel)
  $dir = Split-Path $Out -Parent
  if ($dir) { New-Item -ItemType Directory -Force $dir | Out-Null }
  $dst.Save($Out, [Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $dst.Dispose()
  "wrote $Out ($dw x $dh)"
} finally { $src.Dispose() }
