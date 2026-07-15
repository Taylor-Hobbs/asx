# PR-002 daily paper-trading job. Scheduled for 18:30 Sydney (after ASX close
# + settlement of the day's announcements), Mon-Fri.
#
# Register (run once, from an elevated or normal prompt):
#   schtasks /Create /TN "ASX-PaperTrading" /SC WEEKLY /D MON,TUE,WED,THU,FRI `
#     /ST 18:30 /TR "powershell -NoProfile -File C:\Users\taylo\asx\scripts\run_daily_paper.ps1"
#
# Dry mode by default. Once the IBKR paper gateway is running locally and
# you're ready to place paper orders, change $mode to '--execute'.
$mode = ''   # '' = dry run; '--execute' = place IBKR paper orders

Set-Location C:\Users\taylo\asx
$log = "trading_daily_$(Get-Date -Format yyyy-MM-dd).log"
& .venv\Scripts\python.exe -m asx_engine.trading.daily $mode *>> $log
