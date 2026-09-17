$ErrorActionPreference = "Stop"
$py = "C:\Users\Gebruiker\ableton-mcp\.venv\Scripts\python.exe"
$script = "C:\Users\Gebruiker\ableton-mcp\continue_v10.py"
& $py -u $script --smoke --seed 312
foreach ($s in 312, 313, 314, 315, 316, 317) {
  Write-Host "=== seed $s ==="
  & $py -u $script --seed $s --outdir "dry-next-v10\seed-$s"
}
Write-Host "ALLDONE"
