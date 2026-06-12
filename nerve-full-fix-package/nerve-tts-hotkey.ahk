; Labor of Love - AutoHotkey Quick Speak
; CapsLock+C: Copy selected text, paste into Labor of Love, then play
; CapsLock+X: Stop speaking
; Requires AutoHotkey v2

#Requires AutoHotkey v2.0
#SingleInstance Force
SetWorkingDir A_ScriptDir
SetTitleMatchMode 2

TTS_WINDOW_TITLE := "Labor of Love"
TTS_URL := "https://nerve-tts.pages.dev/index.html"

CapsLock & c::{
    savedClipboard := ClipboardAll()
    A_Clipboard := ""

    Send "^c"
    if !ClipWait(2) {
        ToolTip "No text selected"
        SetTimer ClearToolTip, -1500
        A_Clipboard := savedClipboard
        return
    }

    copiedText := A_Clipboard

    if WinExist(TTS_WINDOW_TITLE) {
        WinActivate
    } else if WinExist("Labor of Love") {
        WinActivate
    } else {
        Run TTS_URL
        if !WinWait("Labor of Love", , 5) {
            ToolTip "Could not open Labor of Love"
            SetTimer ClearToolTip, -2000
            A_Clipboard := savedClipboard
            return
        }
        WinActivate
        Sleep 1000
    }

    Sleep 200

    MouseGetPos &oldMouseX, &oldMouseY
    WinGetPos &appX, &appY, &appW, &appH, "A"
    Click appX + 48, appY + 124
    MouseMove oldMouseX, oldMouseY, 0
    Sleep 100

    Send "^a"
    Sleep 50

    A_Clipboard := copiedText
    Send "^v"
    Sleep 150

    Send "^{Enter}"

    Sleep 500
    A_Clipboard := savedClipboard

    ToolTip "Speaking..."
    SetTimer ClearToolTip, -1500
}

CapsLock & x::{
    if WinExist("Labor of Love") {
        WinActivate
        Sleep 100
        Send "{Escape}"
    }
}

CapsLock::return

ClearToolTip() {
    ToolTip
}
