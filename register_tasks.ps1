$pythonw = "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\pythonw.exe"
$dir = "C:\Users\Administrator\daily_report"

# Web 服务器任务
$a1 = New-ScheduledTaskAction -Execute $pythonw -Argument "$dir\web_server.py" -WorkingDirectory $dir
$t1 = New-ScheduledTaskTrigger -AtLogOn
$s1 = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName "DailyNewsWebServer" -Action $a1 -Trigger $t1 -Settings $s1 -RunLevel Highest -Force
Write-Host "DailyNewsWebServer 任务已注册"

Start-ScheduledTask -TaskName "DailyNewsWebServer"
Start-Sleep -Seconds 2
$state = (Get-ScheduledTask -TaskName "DailyNewsWebServer").State
Write-Host "DailyNewsWebServer 状态: $state"
