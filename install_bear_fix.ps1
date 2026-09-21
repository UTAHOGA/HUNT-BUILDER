Write-Host "Fixing bear.py pursuit classification..."

$bearPath = "engine\utah_draw_predictive\bear.py"
if (!(Test-Path $bearPath)) {
    Write-Host "ERROR: $bearPath not found. Run from repo root C:\Users\tyler\GitHub\HUNT-BUILDER"
    exit 1
}

# Ensure subpackage __init__.py exists
$init1 = "engine\__init__.py"
$init2 = "engine\utah_draw_predictive\__init__.py"
if (!(Test-Path $init1)) { New-Item -ItemType File -Path $init1 -Force | Out-Null; Write-Host "Created $init1" }
if (!(Test-Path $init2)) { New-Item -ItemType File -Path $init2 -Force | Out-Null; Write-Host "Created $init2" }

# Apply fixes using Python
python -c @"
import pathlib, re
p = pathlib.Path(r'engine\utah_draw_predictive\bear.py')
t = p.read_text(encoding='utf-8')

# Fix 1: before_source_correction function - restricted pursuit should be RESTRICTED not UNLIMITED
t = t.replace(
    '    if \"restricted pursuit\" in text or hunt_type == \"pursuit\" or hunt_type.startswith(\"pursuit\") or weapon == \"pursuit only\":\n        return UNLIMITED_PURSUIT_PERMIT',
    '    if \"restricted pursuit\" in text:\n        return RESTRICTED_BEAR_PURSUIT\n    if hunt_type == \"pursuit\" or hunt_type.startswith(\"pursuit\") or weapon == \"pursuit only\":\n        return UNLIMITED_PURSUIT_PERMIT'
)

# Fix 2: main classify function - UNKNOWN -> RESTRICTED
t = re.sub(
    r'if \"restricted pursuit\" in text:\s*\n\s*return UNKNOWN_BEAR_SUBTYPE',
    'if \"restricted pursuit\" in text:\n        return RESTRICTED_BEAR_PURSUIT',
    t
)

# Fix 3: UNLIMITED check should exclude official pursuit codes
t = t.replace(
    '    if hunt_code not in official_draw_codes and (hunt_type == \"pursuit\" or hunt_type.startswith(\"pursuit\") or weapon == \"pursuit only\"):',
    '    if hunt_code not in official_draw_codes and hunt_code not in official_pursuit_codes and (hunt_type == \"pursuit\" or hunt_type.startswith(\"pursuit\") or weapon == \"pursuit only\"):'
)

p.write_text(t, encoding='utf-8')
print('bear.py patched')
"@

if ($LASTEXITCODE -ne 0) { Write-Host "Python patch failed"; exit 1 }

Write-Host "Rebuilding bear report..."
$env:PYTHONPATH="."
python -m engine.utah_draw_predictive.bear

Write-Host "Checking report..."
python -c "import json; j=json.load(open('processed_data/bear_report.json')); print(j['bear_rows_by_algorithm_status']); print('LE', j['limited_entry_hunt_modeled_hunt_code_count'], 'Pursuit', j['restricted_pursuit_modeled_hunt_code_count'])"

Write-Host "Done. You should see Pursuit 9 not 0."
