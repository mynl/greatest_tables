<#
.SYNOPSIS
    Render the greater_tables output-mode probe through Sphinx and Quarto and
    report which MIME type each consumer selected.

.DESCRIPTION
    Five renders, one shared fixture, one question: when a document toolchain
    is handed a GT object, which entry of GT._repr_mimebundle_ does it take?

        sphinx html     _build/html/index.html
        sphinx latex    _build/latex/probe.tex
        quarto html     quarto/probe.html
        quarto latex    quarto/probe.tex
        quarto gfm      quarto/probe.md

    The answer is read off the intermediate artifact, never off a PDF or a
    browser, so every check is a grep for a marker string:

        text    U+2501, the heavy rule of a text table
        html    data-gt-hash, emitted on the wrapper div by render_html
        tikz    \begin{tikzpicture}, emitted by render_tikz
        REPR    a hex memory address, meaning the object fell through to its
                default repr and no table was rendered at all
        DROPPED none of the above: the consumer emitted nothing

    Reported per block, not per file, because the interesting result is which
    of the five blocks produced which form. Each page carries one print block
    (A), two real GT displays (B, C) and two shim displays advertising a
    chosen mimebundle (D text/plain only, E text/html plus text/plain). The
    shims answer the question the real GT cannot, since its bundle carries no
    text/plain: would this consumer take a plain text entry if one existed?

    Markers are chosen to survive markup. Sphinx pygments-highlights the
    captured output and wraps every box drawing character individually as
    \PYG{err}{...}, so TEXT is detected on the bare presence of U+2501 rather
    than on a run of them.

.PARAMETER Clean
    Delete previous artifacts before rendering.

.NOTES
    Nothing here imports aggregate. The contract under test belongs to
    greater_tables. See dev/plan-display-bundle.md for the findings this
    probe produced and the changes they motivate.

    The result is toolchain-sensitive. The table recorded in that plan was
    measured with GT 6.0.0a8, Sphinx 8.2.3 and Quarto 1.6.36. This repo's
    .venv carries a different Sphinx, so re-running here may legitimately
    differ; record the versions printed at the top of every run.
#>
[CmdletBinding()]
param([switch]$Clean)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

# --- interpreter ------------------------------------------------------------
# The repo's own .venv, which carries greater_tables, sphinx and ipykernel
# together. Sync with `uv sync --all-extras` if any of the three is missing.
$Repo = (Resolve-Path (Join-Path $Root '..\..\..')).Path
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw "No interpreter at $Python" }

# Quarto picks whatever python is first on PATH unless told otherwise.
$env:QUARTO_PYTHON = $Python
# How both documents reach fixture.py, set here rather than with a sys.path
# line inside each document so neither has to hardcode a location.
$env:PYTHONPATH = $Root
# greater_tables draws box rules in unicode; a cp1252 stdout raises
# UnicodeEncodeError on the very first print.
$env:PYTHONIOENCODING = 'utf-8'
$env:MPLBACKEND = 'Agg'

Write-Host "python  : $Python"
Write-Host "gt      : $(& $Python -c 'import greater_tables; print(greater_tables.__version__)')"
Write-Host "sphinx  : $(& $Python -c 'import sphinx; print(sphinx.__version__)')"
Write-Host "quarto  : $(quarto --version)"
Write-Host ''

# --- clean ------------------------------------------------------------------
$artifacts = @(
    "$Root\sphinx\_build",
    "$Root\quarto\probe.html", "$Root\quarto\probe.tex", "$Root\quarto\probe.md",
    "$Root\quarto\probe_files", "$Root\quarto\.jupyter_cache"
)
if ($Clean) {
    foreach ($a in $artifacts) {
        if (Test-Path $a) { Remove-Item -Recurse -Force $a }
    }
    Write-Host 'cleaned' -ForegroundColor DarkGray
}

# --- renders ----------------------------------------------------------------
# Failures are reported and skipped: a toolchain that cannot render this page
# is itself a result, and the other four renders still carry information.
function Invoke-Step {
    param([string]$Label, [scriptblock]$Body)
    Write-Host "render  : $Label" -ForegroundColor Cyan
    try { & $Body | Out-Null }
    catch { Write-Host "  FAILED: $_" -ForegroundColor Red }
}

Invoke-Step 'sphinx html' {
    & $Python -m sphinx -b html -q "$Root\sphinx" "$Root\sphinx\_build\html"
}
Invoke-Step 'sphinx latex' {
    & $Python -m sphinx -b latex -q "$Root\sphinx" "$Root\sphinx\_build\latex"
}

Push-Location "$Root\quarto"
try {
    foreach ($to in 'html', 'latex', 'gfm') {
        Invoke-Step "quarto $to" { quarto render probe.qmd --to $to }
    }
}
finally { Pop-Location }

# --- scan -------------------------------------------------------------------
# Per block, not per file: the interesting result is which of the five blocks
# produced which form, and a whole-file count cannot say that.
#
# TEXT is detected on the bare presence of U+2501 rather than on a run of
# them, because Sphinx's LaTeX writer wraps EVERY box drawing character
# individually as \PYG{err}{...}: Pygments lexes the captured output as
# ipython source and classifies the rule as an error token. That escaping is
# itself a finding, so the marker has to see through it.
$blockNames = 'A. print', 'B. display', 'C. display', 'D. shim', 'E. shim'
$blockCols = 'A_print', 'B_expr', 'C_display', 'D_plain', 'E_both'

function Get-Kind {
    param([string]$Segment)
    $kinds = @()
    if ($Segment.Contains([char]0x2501)) { $kinds += 'text' }
    if ($Segment -match 'data-gt-hash') { $kinds += 'html' }
    if ($Segment -match '\\begin\{tikzpicture\}') { $kinds += 'tikz' }
    if ($Segment -match '0x[0-9a-fA-F]{8,}') { $kinds += 'REPR' }
    if ($kinds.Count -eq 0) { return 'DROPPED' }
    $kinds -join '+'
}

function Get-Report {
    param([string]$Label, [string]$Path)
    $row = [ordered]@{ consumer = $Label }
    if (-not (Test-Path $Path)) {
        foreach ($c in $blockCols) { $row[$c] = 'no artifact' }
        return [pscustomobject]$row
    }
    $body = Get-Content -Raw -Encoding utf8 $Path
    $at = $blockNames | ForEach-Object { $body.IndexOf($_) }
    for ($i = 0; $i -lt $blockNames.Count; $i++) {
        if ($at[$i] -lt 0) { $row[$blockCols[$i]] = 'missing'; continue }
        $end = if ($i + 1 -lt $at.Count -and $at[$i + 1] -gt 0) { $at[$i + 1] }
               else { $body.Length }
        $row[$blockCols[$i]] = Get-Kind $body.Substring($at[$i], $end - $at[$i])
    }
    [pscustomobject]$row
}

Write-Host ''
Write-Host 'what each block produced' -ForegroundColor Yellow
Write-Host 'A print = stdout. B/C = real GT (bundle has no text/plain).' -ForegroundColor DarkGray
Write-Host 'D = shim advertising text/plain only. E = shim advertising html + plain.' -ForegroundColor DarkGray
Write-Host 'DROPPED = the consumer emitted nothing at all.' -ForegroundColor DarkGray
Write-Host 'The qmd carries a sixth block, F, dumping the QUARTO_* environment.' -ForegroundColor DarkGray
Write-Host 'It is Quarto only and read by eye, so it is not in the table.' -ForegroundColor DarkGray
@(
    Get-Report 'sphinx html'  "$Root\sphinx\_build\html\index.html"
    Get-Report 'sphinx latex' "$Root\sphinx\_build\latex\probe.tex"
    Get-Report 'quarto html'  "$Root\quarto\probe.html"
    Get-Report 'quarto latex' "$Root\quarto\probe.tex"
    Get-Report 'quarto gfm'   "$Root\quarto\probe.md"
) | Format-Table -AutoSize
