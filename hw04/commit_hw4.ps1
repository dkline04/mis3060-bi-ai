# commit_hw4.ps1 - makes the four HW4 commits in one go, then pushes.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File C:\MIS3060\mis3060-bi-ai\hw04\commit_hw4.ps1

Set-Location C:\MIS3060\mis3060-bi-ai

# 0. The report footer must have a real date before anything is committed
$footer = Get-Content hw04\reports\cleaning_report.md | Select-Object -Last 1
if ($footer -match "\[date\]") {
    Write-Host ""
    Write-Host "STOP: the last line of hw04\reports\cleaning_report.md still says [date]." -ForegroundColor Yellow
    Write-Host "Open the file, replace [date] with today's date, save, and run this script again." -ForegroundColor Yellow
    exit 1
}

# 1. Undo any HW4 commits that were made locally but never pushed (files are kept)
git fetch origin
git reset --soft origin/main
git restore --staged hw04

# 2. Commit 1 - Part A + B
git add hw04/HW04_Data_Cleaning.md hw04/.gitignore "hw04/*.csv" hw04/decision_log.md
git add hw04/scripts/wildcat_config.py hw04/scripts/01_profile.py
git add -f hw04/reports/profile_raw.csv hw04/reports/dq_summary_raw.csv
git commit -m "HW4 Part A+B: generic profiler with 4 check groups; decision log with 26 issues"

# 3. Commit 2 - Part C
git add hw04/scripts/02_clean.py
git add -f hw04/data
git commit -m "HW4 Part C: clean 8 tables - 225 rows quarantined, 198,389 cell changes logged, raw = clean + quarantined"

# 4. Commit 3 - Part D
git add hw04/scripts/03_validate.py
git add -f hw04/reports/profile_clean.csv hw04/reports/dq_summary_clean.csv hw04/reports/ri_results.csv hw04/reports/rule_results.csv hw04/reports/reconciliations.csv hw04/reports/outliers_iqr.csv hw04/reports/data_quality_scorecard.csv
git commit -m "HW4 Part D: reusable RI function on 13 relationships, rule checks, reconciliations, raw vs clean scorecard"

# 5. Commit 4 - Part E
git add hw04/README.md hw04/reports/cleaning_report.md
git commit -m "HW4 Part E: committee cleaning report and README with Claude Code review findings"

# 6. Show the result, then push
Write-Host ""
Write-Host "Commits:" -ForegroundColor Green
git log --oneline -5
Write-Host ""
Write-Host "Anything in hw04 not committed (should only be commit_hw4.ps1):" -ForegroundColor Green
git status --short hw04
git push
Write-Host ""
Write-Host "Done. Paste your hw04 folder link from GitHub into Brightspace." -ForegroundColor Green
