Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

' Neu thu muc .venv chua ton tai, chay bat o che do hien thi de nguoi dung theo doi qua trinh cai dat
If Not fso.FolderExists(currentDir & "\.venv") Then
    WshShell.Run chr(34) & currentDir & "\Start_NAVTools.bat" & Chr(34), 1, True
Else
    ' Neu da co .venv, chay an bat de mo ung dung em ru
    WshShell.Run chr(34) & currentDir & "\Start_NAVTools.bat" & Chr(34), 0
End If

Set WshShell = Nothing
Set fso = Nothing
