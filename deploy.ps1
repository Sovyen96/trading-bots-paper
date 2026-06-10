# Despliegue a GitHub: crea el repo, sube el codigo, activa GitHub Pages
# (dashboard publico) y lanza la primera ejecucion del bot en la nube.
#
# Requisito previo (solo la primera vez):  gh auth login -w
# Uso:  .\deploy.ps1

$ErrorActionPreference = "Stop"
$repo = "trading-bots-paper"

# 1. Comprobar autenticacion
gh auth status
if (-not $?) { Write-Host "Ejecuta primero: gh auth login -w" -ForegroundColor Red; exit 1 }
$owner = gh api user --jq .login

# 2. Crear el repositorio publico y subir el codigo
#    (publico = GitHub Actions y Pages gratis e ilimitados; no hay nada sensible:
#     es paper trading sin claves API)
gh repo create $repo --public --source . --push --description "Sistema multi-agente de paper trading (dinero ficticio, datos reales de Binance)"

# 3. Activar GitHub Pages sirviendo /docs (el dashboard)
gh api "repos/$owner/$repo/pages" -X POST -f "source[branch]=main" -f "source[path]=/docs" 2>$null
if (-not $?) { Write-Host "(Pages ya estaba activo o se activara en el primer push)" }

# 4. Lanzar la primera ejecucion del bot en la nube
Start-Sleep -Seconds 5
gh workflow run paper-trading-tick

Write-Host ""
Write-Host "================= DESPLEGADO =================" -ForegroundColor Green
Write-Host "Repositorio:  https://github.com/$owner/$repo"
Write-Host "Ejecuciones:  https://github.com/$owner/$repo/actions"
Write-Host "Dashboard:    https://$owner.github.io/$repo/   (tarda ~2 min en publicarse)"
Write-Host ""
Write-Host "El bot se ejecuta solo cada hora (minuto 4). Tu PC ya no hace falta."
