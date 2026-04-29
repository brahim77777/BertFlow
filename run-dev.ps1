if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
  Write-Error "Bun is not available on PATH. Install Bun, restart the terminal, then run: bun install; bun run dev"
  exit 1
}

bun run dev
