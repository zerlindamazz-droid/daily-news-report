' 在后台静默启动每日调度器（无命令行窗口）
Dim shell
Set shell = CreateObject("WScript.Shell")
shell.Run "pythonw """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\scheduler.py""", 0, False
Set shell = Nothing
MsgBox "每日报告调度器已在后台启动！" & vbCrLf & vbCrLf & _
       "将在每天洛杉矶时间 07:30 自动生成并发送报告。" & vbCrLf & vbCrLf & _
       "日志文件: logs\scheduler.log", vbInformation, "每日要闻快报"
