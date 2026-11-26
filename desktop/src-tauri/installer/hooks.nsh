; NSIS hooks for the BluxTech Studio installer (bundle.windows.nsis.installerHooks).
; The app lays its workspace out on first run (Documents\BluxTech Studio) and keeps its settings and job database
; in %LOCALAPPDATA%\com.bluxtech.studio\engine, so the installer itself only has to place the files.

!macro NSIS_HOOK_PREINSTALL
  ; Stop a running engine so its files can be replaced (an upgrade over a running app).
  nsExec::ExecToLog 'taskkill /IM "BluxTech Studio.exe" /F /T'
  Pop $0
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Nothing to do: python, node, ffmpeg and HyperFrames ship under $INSTDIR\resources and need no registration.
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  nsExec::ExecToLog 'taskkill /IM "BluxTech Studio.exe" /F /T'
  Pop $0
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ; The user's workspace (projects, renders) and the engine database are left in place on purpose.
!macroend
