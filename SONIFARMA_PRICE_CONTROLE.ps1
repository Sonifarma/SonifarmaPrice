param(
    [ValidateSet('update','backup','verify')][string]$Acao='update',
    [string]$Destino,
    [string]$Origem,
    [string]$Arquivo
)
$ErrorActionPreference = 'Stop'
try {
    $Pasta = $PSScriptRoot
    $Python = Join-Path $Pasta '.venv\Scripts\python.exe'
    if (-not (Test-Path $Python)) { throw 'Execute instalar.bat primeiro.' }
    if ($Acao -ne 'verify') {
        $Listeners = @(Get-NetTCPConnection -LocalPort 8770 -State Listen -ErrorAction SilentlyContinue)
        if ($Listeners.Count -gt 0) { throw 'Pare iniciar.bat com Ctrl+C antes da manutencao. Porta 8770 ocupada.' }
    }
    $Parametros = @((Join-Path $Pasta 'manutencao.py'), $Acao)
    if ($Destino) { $Parametros += @('--destination', $Destino) }
    if ($Origem) { $Parametros += @('--source', $Origem) }
    if ($Arquivo) { $Parametros += @('--archive', $Arquivo) }
    & $Python @Parametros
    if ($LASTEXITCODE -ne 0) { throw 'Manutencao falhou. Confira a mensagem acima antes de iniciar o painel.' }
} catch {
    Write-Host "ERRO: $_" -ForegroundColor Red
    exit 1
}
