$ErrorActionPreference = "Stop"
$py = "C:\Users\Gebruiker\ableton-mcp\.venv\Scripts\python.exe"
$script = "C:\Users\Gebruiker\ableton-mcp\continue_v9.py"
foreach ($s in 306, 307, 308) {
  Write-Host "=== seed $s ==="
  & $py -u $script --seed $s --outdir "dry-next-v9\seed-$s"
}
Write-Host "ALL DONE"
