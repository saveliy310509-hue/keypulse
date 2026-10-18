' KeyPulse — запуск бота без окна консоли (Windows)
' Используется планировщиком задач: wscript.exe start_hidden.vbs
'
' Логи пишутся в logs\bot.log, ошибки — в logs\bot.err.log

Option Explicit

Dim fso, shell, projectDir, py, cmd, logDir

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
shell.CurrentDirectory = projectDir

logDir = projectDir & "\logs"
If Not fso.FolderExists(logDir) Then fso.CreateFolder logDir

py = projectDir & "\.venv\Scripts\python.exe"
If Not fso.FileExists(py) Then py = "python"

cmd = "cmd /c """ & py & """ """ & projectDir & "\main.py"" >> """ & logDir & "\bot.log"" 2>> """ & logDir & "\bot.err.log"""

' 0 = скрытое окно, False = не ждать завершения
shell.Run cmd, 0, False
