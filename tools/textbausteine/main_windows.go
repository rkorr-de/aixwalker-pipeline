package main

// Textbausteine – kleiner Textbaustein-Helfer für Windows, ohne Installation.
// Eine einzige .exe; die Bausteine stehen in Textbausteine.txt daneben.

import (
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
	"unsafe"
)

const (
	appName  = "Textbausteine"
	fileName = "Textbausteine.txt"
	version  = "1.0"

	WM_TRAY     = WM_APP + 1
	WM_EXPAND   = WM_APP + 2
	WM_HOOKFAIL = WM_APP + 3

	hotkeyID = 1
	timerID  = 1
	runKey   = `Software\Microsoft\Windows\CurrentVersion\Run`
)

type App struct {
	hInst, hwnd, icon uintptr
	dpi               int
	exe, dir, file    string
	taskbarCreated    uint32
	hotkeyOK          bool

	mu      sync.RWMutex
	library *Library
	modTime time.Time
	size    int64

	paused atomic.Bool
}

var (
	app       App
	mainCb    = syscall.NewCallback(mainWndProc)
	classKeep []uintptr
)

func (a *App) lib() *Library {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.library
}

func main() {
	runtime.LockOSThread()
	call(pSetProcessDPIAware)

	// nur einmal starten
	if _, _, err := pCreateMutexW.Call(0, 0, wstr(`Local\Textbausteine-Einzelstart`)); err == syscall.ERROR_ALREADY_EXISTS {
		msgBox("Textbausteine läuft bereits.\n\nDas Symbol findest du unten rechts neben der Uhr (eventuell hinter dem kleinen Pfeil ^).", MB_ICONINFORMATION)
		return
	}

	exe, err := os.Executable()
	if err == nil {
		if r, e := filepath.EvalSymlinks(exe); e == nil {
			exe = r
		}
	}
	app.exe = exe
	app.dir = filepath.Dir(exe)
	app.file = filepath.Join(app.dir, fileName)

	if strings.Contains(strings.ToLower(app.dir), `\appdata\local\temp`) {
		msgBox("Bitte die ZIP-Datei zuerst entpacken!\n\n"+
			"Rechtsklick auf die ZIP-Datei → „Alle extrahieren …“ → z. B. in „Dokumente“.\n"+
			"Danach Textbausteine.exe im entpackten Ordner starten.\n\n"+
			"(Direkt aus der ZIP-Datei gestartet, gehen deine Textbausteine verloren.)", MB_ICONWARNING)
		return
	}
	if _, err := os.Stat(app.file); os.IsNotExist(err) {
		content := "\xEF\xBB\xBF" + strings.ReplaceAll(defaultFile, "\n", "\r\n")
		if err := os.WriteFile(app.file, []byte(content), 0o644); err != nil {
			msgBox("Ich kann die Datei mit den Textbausteinen nicht anlegen:\n"+app.file+"\n\n"+err.Error()+
				"\n\nBitte den Ordner mit Textbausteine.exe an einen Ort verschieben, an dem du speichern darfst (z. B. „Dokumente“).", MB_ICONERROR)
			return
		}
	}
	app.load()

	app.hInst = call(pGetModuleHandleW, 0)
	hdc := call(pGetDC, 0)
	app.dpi = int(call(pGetDeviceCaps, hdc, LOGPIXELSX))
	call(pReleaseDC, 0, hdc)
	if app.dpi < 96 {
		app.dpi = 96
	}
	app.icon = makeIcon()

	cls := registerClass("TextbausteineHaupt", mainCb, 0)
	app.hwnd = call(pCreateWindowExW, 0, cls, wstr(appName), 0, 0, 0, 0, 0, 0, 0, app.hInst, 0)
	app.taskbarCreated = uint32(call(pRegisterWindowMessageW, wstr("TaskbarCreated")))
	createSearchWindow()

	app.hotkeyOK = call(pRegisterHotKey, app.hwnd, hotkeyID, MOD_CONTROL|MOD_ALT|MOD_NOREPEAT, VK_SPACE) != 0
	app.trayAdd()
	app.updateAutostartPath()

	lib := app.lib()
	info := fmt.Sprintf("%d Bausteine geladen. Kürzel einfach tippen, z. B. ;mfg", lib.Count())
	if app.hotkeyOK {
		info += "\nSuche: Strg + Alt + Leertaste"
	} else {
		info += "\nStrg + Alt + Leertaste ist schon belegt – Suche per Klick auf das Symbol."
	}
	flags := uint32(NIIF_INFO)
	if len(lib.Warnings) > 0 {
		info += "\n" + strings.Join(lib.Warnings, "\n")
		flags = NIIF_WARNING
	}
	app.balloon("Textbausteine läuft", info, flags)

	call(pSetTimer, app.hwnd, timerID, 2000, 0)
	go hookThread()

	var m msgT
	for {
		r := call(pGetMessageW, uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if int32(r) <= 0 {
			break
		}
		call(pTranslateMessage, uintptr(unsafe.Pointer(&m)))
		call(pDispatchMessageW, uintptr(unsafe.Pointer(&m)))
	}
}

func registerClass(name string, proc uintptr, bg uintptr) uintptr {
	cls := wstr(name)
	classKeep = append(classKeep, cls)
	wc := wndClassExW{
		WndProc:    proc,
		Instance:   app.hInst,
		Icon:       app.icon,
		IconSm:     app.icon,
		Cursor:     call(pLoadCursorW, 0, IDC_ARROW),
		Background: bg,
		ClassName:  (*uint16)(unsafe.Pointer(cls)),
	}
	wc.Size = uint32(unsafe.Sizeof(wc))
	call(pRegisterClassExW, uintptr(unsafe.Pointer(&wc)))
	return cls
}

func (a *App) load() {
	data, err := os.ReadFile(a.file)
	if err != nil {
		return
	}
	lib := Parse(data)
	fi, _ := os.Stat(a.file)
	a.mu.Lock()
	a.library = lib
	if fi != nil {
		a.modTime, a.size = fi.ModTime(), fi.Size()
	}
	a.mu.Unlock()
}

func (a *App) checkReload() {
	fi, err := os.Stat(a.file)
	if err != nil {
		return
	}
	a.mu.RLock()
	same := fi.ModTime().Equal(a.modTime) && fi.Size() == a.size
	a.mu.RUnlock()
	if same {
		return
	}
	time.Sleep(150 * time.Millisecond) // Editor fertig speichern lassen
	a.load()
	lib := a.lib()
	text := fmt.Sprintf("%d Bausteine geladen.", lib.Count())
	flags := uint32(NIIF_INFO)
	if len(lib.Warnings) > 0 {
		text += "\n" + strings.Join(lib.Warnings, "\n")
		flags = NIIF_WARNING
	}
	a.balloon("Textbausteine aktualisiert", text, flags)
	a.trayTip()
	if call(pIsWindowVisible, search.hwnd) != 0 {
		refilter()
	}
}

// ---------- Symbol im Infobereich ----------

func (a *App) nid() *notifyIconData {
	n := &notifyIconData{HWnd: a.hwnd, UID: 1}
	n.CbSize = uint32(unsafe.Sizeof(*n))
	return n
}

func (a *App) tipText() string {
	t := fmt.Sprintf("Textbausteine – %d Bausteine", a.lib().Count())
	if a.paused.Load() {
		t += " (Pause)"
	}
	return t
}

func (a *App) trayAdd() {
	n := a.nid()
	n.UFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
	n.UCallbackMessage = WM_TRAY
	n.HIcon = a.icon
	copyUTF16(n.SzTip[:], a.tipText())
	call(pShellNotifyIconW, NIM_ADD, uintptr(unsafe.Pointer(n)))
}

func (a *App) trayTip() {
	n := a.nid()
	n.UFlags = NIF_TIP
	copyUTF16(n.SzTip[:], a.tipText())
	call(pShellNotifyIconW, NIM_MODIFY, uintptr(unsafe.Pointer(n)))
}

func (a *App) balloon(title, text string, flags uint32) {
	n := a.nid()
	n.UFlags = NIF_INFO
	copyUTF16(n.SzInfoTitle[:], title)
	copyUTF16(n.SzInfo[:], text)
	n.DwInfoFlags = flags
	call(pShellNotifyIconW, NIM_MODIFY, uintptr(unsafe.Pointer(n)))
}

const (
	cmdSearch = iota + 1
	cmdEdit
	cmdFolder
	cmdPause
	cmdAutostart
	cmdHelp
	cmdQuit
)

func (a *App) showMenu() {
	m := call(pCreatePopupMenu)
	add := func(id uintptr, text string, checked bool) {
		f := uintptr(MF_STRING)
		if checked {
			f |= MF_CHECKED
		}
		call(pAppendMenuW, m, f, id, wstr(text))
	}
	sep := func() { call(pAppendMenuW, m, MF_SEPARATOR, 0, 0) }
	add(cmdSearch, "Suchen …\tStrg+Alt+Leertaste", false)
	add(cmdEdit, "Textbausteine bearbeiten", false)
	add(cmdFolder, "Ordner öffnen", false)
	sep()
	add(cmdPause, "Pause (Kürzel aus)", a.paused.Load())
	add(cmdAutostart, "Mit Windows starten", autostartEnabled())
	sep()
	add(cmdHelp, "Hilfe", false)
	add(cmdQuit, "Beenden", false)
	call(pSetMenuDefaultItem, m, cmdSearch, 0)

	var pt point
	call(pGetCursorPos, uintptr(unsafe.Pointer(&pt)))
	call(pSetForegroundWindow, a.hwnd)
	cmd := call(pTrackPopupMenu, m, TPM_RIGHTBUTTON|TPM_RETURNCMD|TPM_NONOTIFY,
		uintptr(pt.X), uintptr(pt.Y), 0, a.hwnd, 0)
	call(pPostMessageW, a.hwnd, WM_NULL, 0, 0)
	call(pDestroyMenu, m)

	switch cmd {
	case cmdSearch:
		showSearch()
	case cmdEdit:
		call(pShellExecuteW, 0, wstr("open"), wstr("notepad.exe"), wstr(`"`+a.file+`"`), 0, SW_SHOWNORMAL)
	case cmdFolder:
		call(pShellExecuteW, 0, wstr("open"), wstr(a.dir), 0, 0, SW_SHOWNORMAL)
	case cmdPause:
		a.paused.Store(!a.paused.Load())
		a.trayTip()
	case cmdAutostart:
		if !setAutostart(!autostartEnabled()) {
			msgBox("Der Autostart konnte nicht geändert werden (eventuell von der Firma gesperrt).", MB_ICONWARNING)
		}
	case cmdHelp:
		msgBox(helpText(), MB_ICONINFORMATION)
	case cmdQuit:
		call(pDestroyWindow, a.hwnd)
	}
}

func helpText() string {
	return "Textbausteine " + version + "\n\n" +
		"• Kürzel tippen (z. B. ;mfg) → wird sofort durch den Text ersetzt.\n" +
		"• Strg + Alt + Leertaste → Suchfenster. Tippen, mit ↑ ↓ wählen, Enter fügt ein.\n" +
		"• Linksklick auf das Symbol → Suchfenster. Rechtsklick → dieses Menü.\n" +
		"• „Textbausteine bearbeiten“ öffnet die Liste im Editor. Speichern (Strg + S) – fertig.\n" +
		"• „Pause“ schaltet die Kürzel kurz aus.\n\n" +
		"Platzhalter: {datum} {datum+14} {zeit} {wochentag} {jahr} {zwischenablage} {cursor}\n\n" +
		"Hinweis: In Programmen, die als Administrator laufen, funktionieren die Kürzel nicht.\n\n" +
		"Datei: " + app.file
}

// ---------- Autostart (nur für den eigenen Benutzer, keine Adminrechte) ----------

func openRunKey(access uintptr) (uintptr, bool) {
	var hk uintptr
	r := call(pRegOpenKeyExW, HKEY_CURRENT_USER, wstr(runKey), 0, access, uintptr(unsafe.Pointer(&hk)))
	return hk, r == 0
}

func autostartEnabled() bool {
	hk, ok := openRunKey(KEY_QUERY_VALUE)
	if !ok {
		return false
	}
	defer call(pRegCloseKey, hk)
	return call(pRegQueryValueExW, hk, wstr(appName), 0, 0, 0, 0) == 0
}

func setAutostart(on bool) bool {
	hk, ok := openRunKey(KEY_SET_VALUE)
	if !ok {
		return false
	}
	defer call(pRegCloseKey, hk)
	if !on {
		return call(pRegDeleteValueW, hk, wstr(appName)) == 0
	}
	val := syscall.StringToUTF16(`"` + app.exe + `"`)
	return call(pRegSetValueExW, hk, wstr(appName), 0, REG_SZ,
		uintptr(unsafe.Pointer(&val[0])), uintptr(len(val)*2)) == 0
}

// Wurde der Ordner verschoben, zeigt der Autostart auf den neuen Ort.
func (a *App) updateAutostartPath() {
	if autostartEnabled() {
		setAutostart(true)
	}
}

// ---------- Nachrichten des unsichtbaren Hauptfensters ----------

func mainWndProc(hwnd, msg, wp, lp uintptr) uintptr {
	switch uint32(msg) {
	case WM_TRAY:
		switch uint32(lp & 0xFFFF) {
		case WM_LBUTTONUP:
			showSearch()
		case WM_RBUTTONUP, WM_CONTEXTMENU:
			app.showMenu()
		}
		return 0
	case WM_HOTKEY:
		showSearch()
		return 0
	case WM_EXPAND:
		pendingMu.Lock()
		p := pending
		pending = nil
		pendingMu.Unlock()
		if p != nil {
			insertText(p.snip.Text, p.backspaces)
		}
		return 0
	case WM_TIMER:
		app.checkReload()
		return 0
	case WM_HOOKFAIL:
		msgBox("Die Tastatur-Überwachung konnte nicht gestartet werden.\nKürzel funktionieren deshalb nicht – die Suche (Strg + Alt + Leertaste) schon.", MB_ICONWARNING)
		return 0
	case WM_DESTROY:
		n := app.nid()
		call(pShellNotifyIconW, NIM_DELETE, uintptr(unsafe.Pointer(n)))
		call(pPostQuitMessage, 0)
		return 0
	}
	if app.taskbarCreated != 0 && uint32(msg) == app.taskbarCreated {
		app.trayAdd() // Explorer wurde neu gestartet → Symbol wieder anzeigen
		return 0
	}
	return call(pDefWindowProcW, hwnd, msg, wp, lp)
}
