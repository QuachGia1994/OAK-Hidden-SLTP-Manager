Option Explicit

If WScript.Arguments.Count < 2 Then WScript.Quit 64

Dim shell, fso, nodePath, scriptPath, command, index, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
nodePath = WScript.Arguments(0)
scriptPath = WScript.Arguments(1)

If Not fso.FileExists(nodePath) Then WScript.Quit 65
If Not fso.FileExists(scriptPath) Then WScript.Quit 66

shell.CurrentDirectory = fso.GetParentFolderName(scriptPath)
command = QuoteArg(nodePath) & " " & QuoteArg(scriptPath)
For index = 2 To WScript.Arguments.Count - 1
  command = command & " " & QuoteArg(WScript.Arguments(index))
Next

exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode

Function QuoteArg(value)
  QuoteArg = Chr(34) & Replace(CStr(value), Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function
