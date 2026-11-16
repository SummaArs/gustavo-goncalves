<#
prova.ps1 — invariante + busca adversarial em PowerShell.
Zero instalação: PowerShell 5.1 já vem no Windows.

Primeiro comando a rodar (prova que o arnês funciona ANTES de você confiar nele):
    powershell -ExecutionPolicy Bypass -File .\prova.ps1 -Autoteste

Esperado: o caso INGENUO FALHA em poucas tentativas, o CORRIGIDO passa 20.000.
Arnês que nunca falha não está testando nada.

Uso na sua ferramenta:
    . .\prova.ps1
    $ger = { param($rnd,$escala) [pscustomobject]@{ total = [math]::Round($rnd.NextDouble()*1000*$escala + 0.01, 2); n = $rnd.Next(1, [int](1 + 59*$escala) + 1) } }
    $inv = { param($c) $p = Get-Parcelas $c.total $c.n; (Cent (($p | Measure-Object -Sum).Sum)) -eq (Cent $c.total) }
    Invoke-Prova -Nome "soma das parcelas == total" -Gerador $ger -Invariante $inv -Tentativas 20000
#>

param([switch]$Autoteste)

function Cent {
    # Dinheiro é centavo inteiro. AwayFromZero porque .NET arredonda "banqueiro"
    # por padrão (2,5 -> 2) e o Excel NÃO — sem isso a conciliação nunca fecha.
    param([double]$Valor)
    return [int][math]::Round($Valor * 100, [System.MidpointRounding]::AwayFromZero)
}

function Invoke-Prova {
    param(
        [Parameter(Mandatory=$true)][string]$Nome,
        [Parameter(Mandatory=$true)][scriptblock]$Gerador,    # param($rnd,$escala) -> caso
        [Parameter(Mandatory=$true)][scriptblock]$Invariante, # param($caso) -> $true/$false
        [int]$Tentativas = 10000,
        [int]$Semente = 0
    )

    $t0 = Get-Date
    $falha = $null
    $feitas = 0
    $escalaFalha = 1.0

    for ($i = 0; $i -lt $Tentativas; $i++) {
        $feitas = $i + 1
        $rnd = New-Object System.Random([int](($Semente * 7919 + $i) % 2147483647))
        $escala = ((($i % 100) + 1) / 100.0)
        $caso = & $Gerador $rnd $escala
        $motivo = Test-Invariante $Invariante $caso
        if ($motivo) {
            $falha = @{ Caso = $caso; Motivo = $motivo; Indice = $i }
            $escalaFalha = $escala
            break
        }
    }

    # Encolher: contraexemplo pequeno é o que vira teste de regressão legível.
    if ($falha) {
        $menor = (ConvertTo-Json $falha.Caso -Compress -Depth 6).Length
        for ($k = 0; $k -lt 300; $k++) {
            $esc = $escalaFalha / [math]::Pow(2, [math]::Floor($k / 50) + 1)
            if ($esc -lt 0.005) { break }
            $rnd = New-Object System.Random([int]((57721 + $k) % 2147483647))
            $c = & $Gerador $rnd $esc
            $m = Test-Invariante $Invariante $c
            if ($m) {
                $tam = (ConvertTo-Json $c -Compress -Depth 6).Length
                if ($tam -le $menor) { $falha.Caso = $c; $falha.Motivo = $m; $menor = $tam }
            }
        }
    }

    $seg = [math]::Max(((Get-Date) - $t0).TotalSeconds, 0.001)
    if ($falha) {
        Write-Host ("[FALHA] {0}: {1} tentativas, 1 violacao, {2:N2}s" -f $Nome, $feitas, $seg) -ForegroundColor Red
        Write-Host ("        motivo: " + $falha.Motivo)
        Write-Host ("        caso minimo: " + (ConvertTo-Json $falha.Caso -Compress -Depth 6))
        Write-Host ("        reproduza: semente=$Semente indice=" + $falha.Indice)
        return $false
    }
    Write-Host ("[OK   ] {0}: {1} tentativas, 0 violacoes, {2:N2}s" -f $Nome, $feitas, $seg) -ForegroundColor Green
    return $true
}

function Test-Invariante {
    param([scriptblock]$Invariante, $Caso)
    try {
        $r = & $Invariante $Caso
        if ($r -is [array]) { $r = $r[-1] }   # scriptblock pode devolver saída extra
        if (-not $r) { return "invariante devolveu falso" }
        return $null
    } catch {
        return "excecao: " + $_.Exception.Message
    }
}

# ------------------------------------------------------------------ autoteste
if ($Autoteste) {

    function Get-ParcelasIngenuo {
        param([double]$Total, [int]$N)
        $p = [math]::Round($Total / $N, 2)
        return @(1..$N | ForEach-Object { $p })
    }

    function Get-Parcelas {
        param([double]$Total, [int]$N)
        $c = Cent $Total
        $base = [math]::Floor($c / $N)
        $resto = $c - ($base * $N)
        return @(0..($N - 1) | ForEach-Object {
            if ($_ -lt $resto) { ($base + 1) / 100 } else { $base / 100 }
        })
    }

    $ger = {
        param($rnd, $escala)
        [pscustomobject]@{
            total = [math]::Round($rnd.NextDouble() * 100000 * $escala + 0.01, 2)
            n     = $rnd.Next(1, [int](1 + 59 * $escala) + 1)
        }
    }
    $invIngenuo   = { param($c) (Cent ((Get-ParcelasIngenuo $c.total $c.n | Measure-Object -Sum).Sum)) -eq (Cent $c.total) }
    $invCorrigido = { param($c) (Cent ((Get-Parcelas        $c.total $c.n | Measure-Object -Sum).Sum)) -eq (Cent $c.total) }

    Write-Host "`n>>> 1. O arnes precisa ACHAR o bug da versao ingenua:"
    $a = Invoke-Prova -Nome "INGENUO: soma das parcelas == total" -Gerador $ger -Invariante $invIngenuo -Tentativas 20000

    Write-Host "`n>>> 2. A versao corrigida precisa sobreviver:"
    $b = Invoke-Prova -Nome "soma das parcelas == total" -Gerador $ger -Invariante $invCorrigido -Tentativas 20000

    Write-Host ""
    if ((-not $a) -and $b) {
        Write-Host "ARNES VALIDO: achou o bug plantado e aprovou o codigo correto." -ForegroundColor Green
        exit 0
    }
    Write-Host "ARNES INVALIDO — conserte o arnes antes de confiar em qualquer '0 violacoes'." -ForegroundColor Red
    exit 1
}
