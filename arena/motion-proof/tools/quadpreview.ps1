<#
.SYNOPSIS
  Draw one or more quads on a scene image so you can check by eye that they sit on the screen glass.

.EXAMPLE
  .\quadpreview.ps1 -Image ..\..\scenes-v2\11_blue_pursuit.png -Quad "924,584;1598,604;1598,808;910,782" -Out C:\temp\check11.png
  .\quadpreview.ps1 -Image ... -Quad "..." -Quad2 "..." -Out ...     # compare two candidates (magenta, then cyan)
#>
param(
  [Parameter(Mandatory)][string]$Image,
  [Parameter(Mandatory)][string]$Quad,
  [string]$Quad2 = '',
  [Parameter(Mandatory)][string]$Out,
  [int]$CropX = 0, [int]$CropY = 0, [int]$CropW = 0, [int]$CropH = 0,
  [double]$Scale = 1
)
Add-Type -AssemblyName System.Drawing
function Pts($s) { ($s -split ';') | ForEach-Object { $xy = $_.Trim() -split ','; New-Object System.Drawing.Point ([int]$xy[0]), ([int]$xy[1]) } }
$bmp = New-Object System.Drawing.Bitmap ((Resolve-Path $Image).Path)
try {
  $copy = New-Object System.Drawing.Bitmap $bmp
  $gfx = [System.Drawing.Graphics]::FromImage($copy)
  $gfx.DrawPolygon((New-Object System.Drawing.Pen ([System.Drawing.Color]::Magenta), 2), [System.Drawing.Point[]](Pts $Quad))
  if ($Quad2) { $gfx.DrawPolygon((New-Object System.Drawing.Pen ([System.Drawing.Color]::Cyan), 2), [System.Drawing.Point[]](Pts $Quad2)) }
  $gfx.Dispose()
  $result = $copy
  if ($CropW -gt 0) {
    $dw = [int]($CropW * $Scale); $dh = [int]($CropH * $Scale)
    $result = New-Object System.Drawing.Bitmap $dw, $dh
    $g2 = [System.Drawing.Graphics]::FromImage($result)
    $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g2.DrawImage($copy, (New-Object System.Drawing.Rectangle 0, 0, $dw, $dh), (New-Object System.Drawing.Rectangle $CropX, $CropY, $CropW, $CropH), [System.Drawing.GraphicsUnit]::Pixel)
    $g2.Dispose()
  }
  $dir = Split-Path $Out -Parent; if ($dir) { New-Item -ItemType Directory -Force $dir | Out-Null }
  $result.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
  "wrote $Out"
} finally { $bmp.Dispose() }
