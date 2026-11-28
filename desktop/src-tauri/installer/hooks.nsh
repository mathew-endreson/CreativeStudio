; NSIS hooks for the BluxTech Studio installer (bundle.windows.nsis.installerHooks).
; The app lays its workspace out on first run (Documents\BluxTech Studio) and keeps its settings and job database
; in %LOCALAPPDATA%\com.bluxtech.studio\engine, so the installer itself only has to place the files.
;
; Before files are replaced (an upgrade, or the in-app updater running this installer with /UPDATE), nothing from
; the install folder may still be running: the shell (bluxtech-studio.exe) and the engine it starts from
; resources\ (python.exe, and node / ffmpeg children). The in-app updater stops the engine before it hands over;
; these hooks are the safety net for an upgrade started by hand while the app is open.

!macro _BLUX_STOP_RUNNING
  nsExec::ExecToLog 'taskkill /IM "bluxtech-studio.exe" /F /T'
  Pop $0
  nsExec::ExecToLog 'taskkill /IM "BluxTech Studio.exe" /F /T'
  Pop $0
  ; anything still running from the install folder (the engine's python, node, ffmpeg, a headless chrome)
  nsExec::ExecToLog 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith(\"$INSTDIR\", [System.StringComparison]::OrdinalIgnoreCase) } | Stop-Process -Force -ErrorAction SilentlyContinue"'
  Pop $0
  Sleep 800
!macroend

!macro NSIS_HOOK_PREINSTALL
  !insertmacro _BLUX_STOP_RUNNING
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Nothing to do: python, node, ffmpeg and HyperFrames ship under $INSTDIR\resources and need no registration.
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  !insertmacro _BLUX_STOP_RUNNING
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ; The user's workspace (projects, renders) and the engine data are left in place on purpose.
!macroend
