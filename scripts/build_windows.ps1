$ErrorActionPreference = "Stop"

uv sync --extra dev --extra ui
uv run pyinstaller --noconfirm --clean --windowed --onedir --name GridPilot `
  --exclude-module sklearn --exclude-module scipy --exclude-module pytest --exclude-module pygments `
  --add-data "assets/gridpilot.svg;assets" gridpilot.py

Write-Host "Built: dist\GridPilot\GridPilot.exe"
