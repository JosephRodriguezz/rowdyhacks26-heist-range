<#
.SYNOPSIS
  Run the demo in REAL time in headless Edge and report what actually happens: the clock, scene and state every few
  seconds, screenshots at chosen moments, console errors, and (optionally) a pass over every control.

.DESCRIPTION
  snapshot.ps1 renders paused frames. This drives the real play loop through the DevTools protocol, so it catches
  problems snapshots cannot: playback that stalls, scene changes that fail, errors thrown mid-run, controls that break.
  Needs about -Seconds of wall-clock time. Use -Speed 2 to halve it.

.EXAMPLE
  .\realtime.ps1 -OutDir C:\temp\rt
.EXAMPLE
  .\realtime.ps1 -Speed 2 -ShotAt 5,15,30 -Interactions -OutDir C:\temp\rt
#>
param(
  [double]$Seconds = 0,                 # 0 = whole demo plus a little (from story.js)
  [double]$Speed = 1,
  [double[]]$ShotAt = @(),              # wall-clock seconds after pressing Play
  [string]$OutDir = (Join-Path $env:TEMP 'motion-realtime'),
  [int]$SampleEvery = 5,
  [switch]$Interactions,
  [switch]$Reduced
)
$ErrorActionPreference = 'Stop'
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") |
  Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'No Edge or Chrome found.' }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$url = 'file:///' + ($root -replace '\\', '/') + '/index.html' + $(if ($Reduced) { '?reduced=1' } else { '' })
if ($Seconds -le 0) {
  $m = [regex]::Match((Get-Content -Raw -Encoding UTF8 (Join-Path $root 'story.js')), '"total":\s*([0-9.]+)')
  $Seconds = [Math]::Ceiling(([double]$m.Groups[1].Value) / $Speed) + 2
}
New-Item -ItemType Directory -Force $OutDir | Out-Null
$userData = Join-Path $env:TEMP ('mp-rt-' + [guid]::NewGuid().ToString('N'))
$port = Get-Random -Minimum 9300 -Maximum 9900

$proc = Start-Process -FilePath $edge -PassThru -WindowStyle Hidden -ArgumentList @(
  '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1500,960',
  "--remote-debugging-port=$port", "--user-data-dir=$userData", '--no-first-run', 'about:blank')
$ws = $null
try {
  $targets = $null
  for ($i = 0; $i -lt 80 -and -not $targets; $i++) { try { $targets = Invoke-RestMethod "http://127.0.0.1:$port/json" } catch { Start-Sleep -Milliseconds 250 } }
  $page = $targets | Where-Object { $_.type -eq 'page' } | Select-Object -First 1
  $ws = New-Object System.Net.WebSockets.ClientWebSocket
  $ws.ConnectAsync([Uri]$page.webSocketDebuggerUrl, [Threading.CancellationToken]::None).Wait()
  $script:id = 0
  $script:problems = New-Object System.Collections.ArrayList

  function Send($method, $params) {
    if (-not $params) { $params = @{} }
    $script:id++
    $msg = @{ id = $script:id; method = $method; params = $params } | ConvertTo-Json -Depth 10 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($msg)
    $ws.SendAsync((New-Object ArraySegment[byte] -ArgumentList (, $bytes)), 'Text', $true, [Threading.CancellationToken]::None).Wait()
    while ($true) {
      $buf = New-Object byte[] 262144
      $sb = New-Object Text.StringBuilder
      do {
        $res = $ws.ReceiveAsync((New-Object ArraySegment[byte] -ArgumentList (, $buf)), [Threading.CancellationToken]::None).Result
        [void]$sb.Append([Text.Encoding]::UTF8.GetString($buf, 0, $res.Count))
      } until ($res.EndOfMessage)
      $o = $sb.ToString() | ConvertFrom-Json
      if ($o.method -eq 'Runtime.exceptionThrown') { [void]$script:problems.Add('EXCEPTION: ' + $o.params.exceptionDetails.text + ' ' + $o.params.exceptionDetails.exception.description) }
      elseif ($o.method -eq 'Runtime.consoleAPICalled' -and $o.params.type -eq 'error') { [void]$script:problems.Add('console.error: ' + (($o.params.args | ForEach-Object { $_.value }) -join ' ')) }
      if ($o.id -eq $script:id) { return $o }
    }
  }
  function Ev($expr) {
    $r = Send 'Runtime.evaluate' @{ expression = $expr; returnByValue = $true }
    if ($r.result.exceptionDetails) { return 'EVAL ERROR: ' + $r.result.exceptionDetails.text }
    return $r.result.result.value
  }
  function Shot($name) {
    $r = Send 'Page.captureScreenshot' @{ format = 'png' }
    $p = Join-Path $OutDir $name
    [IO.File]::WriteAllBytes($p, [Convert]::FromBase64String($r.result.data))
    return $p
  }
  $probe = "(function(){var q=function(i){return document.getElementById(i)};return q('time').textContent+' | '+q('play').textContent+' | '+q('hudScene').textContent+' | bank '+q('hudBank').textContent+' | alarm '+q('hudAlarm').textContent+' | blue '+q('hudBlue').textContent})()"

  [void](Send 'Runtime.enable' @{})
  [void](Send 'Page.enable' @{})
  [void](Send 'Page.navigate' @{ url = $url })
  Start-Sleep -Seconds 3
  'loaded    : ' + (Ev $probe)
  if ($Speed -ne 1) { [void](Ev "(function(){var s=document.getElementById('speed');var o=document.createElement('option');o.value='$Speed';o.textContent='$Speed';s.appendChild(o);s.value='$Speed';s.dispatchEvent(new Event('change',{bubbles:true}))})()") }
  [void](Ev "document.getElementById('poster').click()")
  $t0 = Get-Date
  $sceneSeen = @{}
  for ($s = 1; $s -le [int]$Seconds; $s++) {
    $wait = 1000 * $s - ((Get-Date) - $t0).TotalMilliseconds
    if ($wait -gt 0) { Start-Sleep -Milliseconds $wait }
    $state = Ev $probe
    $scene = ($state -split ' \| ')[2]
    if (-not $sceneSeen.ContainsKey($scene)) { $sceneSeen[$scene] = $s; 'scene seen : {0,3}s  {1}' -f $s, $state }
    elseif ($s % $SampleEvery -eq 0) { '{0,3}s real   : {1}' -f $s, $state }
    if ($ShotAt -contains $s) { 'shot       : ' + (Shot ("rt-{0:000}s.png" -f $s)) }
  }
  'final     : ' + (Ev $probe)
  [void](Shot 'rt-final.png')

  if ($Interactions) {
    '--- controls ---'
    [void](Ev "document.querySelector('#chips button:nth-child(5)').click()");  'chip 05      : ' + (Ev $probe)
    [void](Ev "document.querySelector('#chips button:nth-child(12)').click()"); 'chip 12      : ' + (Ev $probe)
    [void](Ev "document.getElementById('play').click()"); Start-Sleep -Milliseconds 1500; 'play 1.5 s   : ' + (Ev $probe)
    [void](Ev "document.getElementById('play').click()")
    $a = Ev "document.getElementById('time').textContent"; Start-Sleep -Milliseconds 800; $b = Ev "document.getElementById('time').textContent"
    'pause holds  : before=[{0}] after=[{1}]  {2}' -f $a, $b, $(if ($a -eq $b) { 'OK' } else { 'CLOCK MOVED WHILE PAUSED' })
    [void](Ev "document.dispatchEvent(new KeyboardEvent('keydown',{key:' ',bubbles:true}))"); Start-Sleep -Milliseconds 600; 'key Space    : ' + (Ev $probe)
    [void](Ev "document.dispatchEvent(new KeyboardEvent('keydown',{key:' ',bubbles:true}))")
    [void](Ev "document.dispatchEvent(new KeyboardEvent('keydown',{key:'3',bubbles:true}))");  'key 3        : ' + (Ev $probe)
    [void](Ev "document.dispatchEvent(new KeyboardEvent('keydown',{key:']',bubbles:true}))");  'key ]        : ' + (Ev $probe)
    [void](Ev "document.dispatchEvent(new KeyboardEvent('keydown',{key:'[',bubbles:true}))");  'key [        : ' + (Ev $probe)
    [void](Ev "document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}))"); 'key right    : ' + (Ev $probe)
    [void](Ev "var s=document.getElementById('scrub'); s.value='60'; s.dispatchEvent(new Event('input',{bubbles:true}))"); 'scrub to 60  : ' + (Ev $probe)
    [void](Ev "document.dispatchEvent(new KeyboardEvent('keydown',{key:'r',bubbles:true}))"); Start-Sleep -Milliseconds 700; 'key r        : ' + (Ev $probe)
  }
  ''
  if ($script:problems.Count) { "PAGE PROBLEMS ($($script:problems.Count)):"; $script:problems | Select-Object -First 12 | ForEach-Object { "  $_" } }
  else { 'PAGE PROBLEMS: none (no exceptions or console.error during the run)' }
} finally {
  if ($ws) { try { $ws.Dispose() } catch {} }
  if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
  Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*$userData*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 500
  Remove-Item $userData -Recurse -Force -ErrorAction SilentlyContinue
}
