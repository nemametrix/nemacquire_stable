#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
#Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.
F12::pause,toggle

F10::
while 1 < 2
{
    SetControlDelay -1
    ControlClick, pushButtonRecord, NemAcquire,,,,NA
    Sleep, 3000
    ControlClick, pushButtonRecord, NemAcquire,,,,NA
    Sleep, 1000
    ControlSend,, {Enter}, Enter Experiment Notes
}
Return
