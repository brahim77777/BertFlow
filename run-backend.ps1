param(
  [string]$Python = "python",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8765
)

& $Python -m backend --host $HostName --port $Port
