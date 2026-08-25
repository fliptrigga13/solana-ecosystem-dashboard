@echo off
rem Hourly Solana dashboard watch: collect -> detect -> generate -> commit+push.
rem Launched by Task Scheduler task "SolanaDashboardHourlyWatch" (hourly).
rem One refresh per trigger — Task Scheduler is the loop; do NOT use --loop here.
cd /d C:\Users\fyou1\solana-dashboard
set WATCH_AUTOCOMMIT=1
set GIT_AUTHOR_NAME=fliptrigga13
set GIT_AUTHOR_EMAIL=fliptrigga13@users.noreply.github.com
set GIT_COMMITTER_NAME=fliptrigga13
set GIT_COMMITTER_EMAIL=fliptrigga13@users.noreply.github.com
"C:\Users\fyou1\AppData\Local\Programs\Python\Python312\python.exe" autoupdate.py >> watch.log 2>&1
