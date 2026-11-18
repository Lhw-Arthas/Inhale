; Inhale Builder's installer (NSIS, made on Linux by packaging/windows/build.sh): the folder it staged, copied for this user
; alone into %LOCALAPPDATA%\Programs\Inhale, with no administrator rights; shortcuts in the Start menu and on the desktop; an
; uninstaller in "Apps & features". The game folders a player builds and their saves are elsewhere and are kept.
;
;   makensis -DSTAGE=<folder> -DVERSION=<name> -DVERNUM=<a.b.c.d> -DOUT=<setup.exe> packaging/windows/inhale.nsi
Unicode true
SetCompressor /SOLID lzma
SetCompressorDictSize 64
RequestExecutionLevel user
ManifestDPIAware true

!define NAME "Inhale Builder"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\InhaleBuilder"
Name "${NAME}"
OutFile "${OUT}"
InstallDir "$LOCALAPPDATA\Programs\Inhale"
InstallDirRegKey HKCU "${UNINST_KEY}" "InstallLocation"
BrandingText "Inhale ${VERSION}"
VIProductVersion "${VERNUM}"
VIAddVersionKey "ProductName" "${NAME}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "${NAME} setup"
VIAddVersionKey "LegalCopyright" "GPL-3.0-or-later"

!include "MUI2.nsh"
!define MUI_ICON "${STAGE}\gui\inhale.ico"
!define MUI_UNICON "${STAGE}\gui\inhale.ico"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Start ${NAME}"
!define MUI_FINISHPAGE_RUN_FUNCTION StartBuilder
!insertmacro MUI_PAGE_LICENSE "${STAGE}\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

; (what the stage holds at its top, and only that is removed: a folder chosen by hand may hold other files.
; tests/test_packaging_scripts.py checks each name is one build.sh stages)
!macro RemoveOurs
  RMDir /r "$INSTDIR\nx2"
  RMDir /r "$INSTDIR\host"
  RMDir /r "$INSTDIR\gpu"
  RMDir /r "$INSTDIR\scripts"
  RMDir /r "$INSTDIR\third_party"
  RMDir /r "$INSTDIR\third_party_objects"
  RMDir /r "$INSTDIR\llvm-mingw"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\cpm"
  RMDir /r "$INSTDIR\gui"
  RMDir /r "$INSTDIR\licenses"
  RMDir /r "$INSTDIR\work"
  Delete "$INSTDIR\VERSION"
  Delete "$INSTDIR\requirements.txt"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\CREDITS.md"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\PROVENANCE.md"
!macroend

Function StartBuilder
  Exec '"$INSTDIR\python\pythonw.exe" -I "$INSTDIR\gui\inhale_builder.py"'
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  ; (an update: the old version's files go first, so none it no longer has stays behind)
  !insertmacro RemoveOurs
  File /r "${STAGE}\*.*"
  WriteUninstaller "$INSTDIR\uninstall.exe"
  CreateShortcut "$SMPROGRAMS\${NAME}.lnk" "$INSTDIR\python\pythonw.exe" '-I "$INSTDIR\gui\inhale_builder.py"' \
      "$INSTDIR\gui\inhale.ico"
  CreateShortcut "$DESKTOP\${NAME}.lnk" "$INSTDIR\python\pythonw.exe" '-I "$INSTDIR\gui\inhale_builder.py"' \
      "$INSTDIR\gui\inhale.ico"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${NAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "Inhale"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\gui\inhale.ico"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  !insertmacro RemoveOurs
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\${NAME}.lnk"
  Delete "$DESKTOP\${NAME}.lnk"
  Delete "$APPDATA\Inhale\inhale-builder.json"
  RMDir "$APPDATA\Inhale"
  ; (the build's work folder: gigabytes of compiled files, kept for a quicker next build; the player chooses)
  IfFileExists "$LOCALAPPDATA\InhaleBuilder\*.*" 0 +3
    MessageBox MB_YESNO|MB_ICONQUESTION "Also delete the build's work folder ($LOCALAPPDATA\InhaleBuilder)? Your game folders and saves are kept either way." /SD IDNO IDNO +2
    RMDir /r "$LOCALAPPDATA\InhaleBuilder"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
