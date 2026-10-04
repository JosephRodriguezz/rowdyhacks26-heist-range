<#
.SYNOPSIS
  Tile several screenshots into one labelled contact sheet, so a whole scene (or the whole demo) can be reviewed in one image.

.DESCRIPTION
  Pairs naturally with snapshot.ps1: take frames, then tile them. By default each frame is cropped to the stage
  (the picture area of a 1500x960 snapshot) before it is scaled.

.EXAMPLE
  .\snapshot.ps1 -Scene 8 -Lt 0.2,1.2,2.2,3.2,4.2 -OutDir C:\temp\s8 -Prefix s8
  .\contact.ps1 -Files (Get-ChildItem C:\temp\s8\s8-*.png | Sort-Object Name).FullName -Cols 3 -Out C:\temp\s8\sheet.png
#>
param(
  [Parameter(Mandatory)][string[]]$Files,
  [int]$Cols = 4,
  [int]$Thumb = 480,                 # thumbnail width in pixels
  [string]$Out = (Join-Path $env:TEMP 'contact.png'),
  [switch]$Whole                      # keep the whole screenshot instead of cropping to the stage
)
Add-Type -AssemblyName System.Drawing
$cx = 140; $cy = 72; $cw = 1220; $ch = 683        # stage region inside a 1500x960 snapshot
$th = if ($Whole) { [int]($Thumb * 960 / 1500) } else { [int]($Thumb * $ch / $cw) }
$rows = [int][Math]::Ceiling($Files.Count / $Cols)
$label = 18; $gap = 6
$sheet = New-Object Drawing.Bitmap (($Thumb + $gap) * $Cols + $gap), (($th + $label + $gap) * $rows + $gap)
$g = [Drawing.Graphics]::FromImage($sheet)
$g.Clear([Drawing.Color]::FromArgb(11, 13, 18))
$g.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$font = New-Object Drawing.Font 'Segoe UI', 9
$brush = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(200, 205, 215))
for ($i = 0; $i -lt $Files.Count; $i++) {
  $x = $gap + ($i % $Cols) * ($Thumb + $gap); $y = $gap + [Math]::Floor($i / $Cols) * ($th + $label + $gap)
  $src = [Drawing.Bitmap]::FromFile((Resolve-Path $Files[$i]).Path)
  try {
    $srcRect = if ($Whole) { New-Object Drawing.Rectangle 0, 0, $src.Width, $src.Height } else { New-Object Drawing.Rectangle $cx, $cy, $cw, $ch }
    $g.DrawImage($src, (New-Object Drawing.Rectangle $x, ($y + $label), $Thumb, $th), $srcRect, [Drawing.GraphicsUnit]::Pixel)
  } finally { $src.Dispose() }
  $g.DrawString([IO.Path]::GetFileNameWithoutExtension($Files[$i]), $font, $brush, $x, $y)
}
$dir = Split-Path $Out -Parent
if ($dir) { New-Item -ItemType Directory -Force $dir | Out-Null }
$sheet.Save($Out, [Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $sheet.Dispose()
"wrote $Out  ($($Files.Count) frames, $Cols columns)"
