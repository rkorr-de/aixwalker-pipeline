package main

// Suchfenster: Strg+Alt+Leertaste → tippen → Pfeiltasten → Enter fügt ein.

import (
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	idEdit    = 101
	idList    = 102
	idPreview = 103
)

type searchUI struct {
	hwnd, edit, list, preview, font uintptr
	prev                            uintptr // Fenster, in das eingefügt wird
	view                            []*Snippet
}

var (
	search     searchUI
	origProcs  = map[uintptr]uintptr{}
	searchCb   = syscall.NewCallback(searchWndProc)
	subclassCb = syscall.NewCallback(subclassProc)
	whiteBrush uintptr
)

func sc(v int) int { return v * app.dpi / 96 }

func createSearchWindow() {
	cls := registerClass("TextbausteineSuche", searchCb, COLOR_BTNFACE+1)
	w, h := sc(620), sc(480)
	search.hwnd = call(pCreateWindowExW, WS_EX_TOPMOST|WS_EX_TOOLWINDOW, cls,
		wstr("Textbaustein suchen   –   Enter = einfügen   ·   Esc = schließen"),
		WS_POPUP|WS_CAPTION|WS_SYSMENU, 0, 0, uintptr(w), uintptr(h), 0, 0, app.hInst, 0)

	var rc rect
	call(pGetClientRect, search.hwnd, uintptr(unsafe.Pointer(&rc)))
	cw, ch := int(rc.Right), int(rc.Bottom)
	m, eh, gap := sc(10), sc(30), sc(8)
	listTop := m + eh + gap
	listH := (ch - listTop - m - gap) * 58 / 100
	prevTop := listTop + listH + gap
	prevH := ch - prevTop - m

	search.edit = child("EDIT", WS_TABSTOP|ES_AUTOHSCROLL, m, m, cw-2*m, eh, idEdit)
	search.list = child("LISTBOX", WS_VSCROLL|LBS_NOTIFY|LBS_NOINTEGRALHEIGHT|LBS_USETABSTOPS, m, listTop, cw-2*m, listH, idList)
	search.preview = child("EDIT", WS_VSCROLL|ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL, m, prevTop, cw-2*m, prevH, idPreview)

	height := -int32(11 * app.dpi / 72)
	search.font = call(pCreateFontW, uintptr(height), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, wstr("Segoe UI"))
	for _, c := range []uintptr{search.edit, search.list, search.preview} {
		sendMessage(c, WM_SETFONT, search.font, 1)
	}
	margin := uintptr(sc(6))
	sendMessage(search.edit, EM_SETMARGINS, 3, margin|margin<<16)
	sendMessage(search.preview, EM_SETMARGINS, 3, margin|margin<<16)
	sendMessage(search.edit, EM_SETCUEBANNER, 1, wstr("Suchbegriff eingeben …"))
	tabs := []int32{80}
	sendMessage(search.list, LB_SETTABSTOPS, 1, uintptr(unsafe.Pointer(&tabs[0])))
	sendMessage(search.list, LB_SETITEMHEIGHT, 0, uintptr(sc(24)))
	whiteBrush = call(pGetStockObject, WHITE_BRUSH)

	for _, c := range []uintptr{search.edit, search.list} {
		origProcs[c] = call(pSetWindowLongPtrW, c, ^uintptr(3) /* GWLP_WNDPROC = -4 */, subclassCb)
	}
}

func child(class string, style uintptr, x, y, w, h int, id uintptr) uintptr {
	return call(pCreateWindowExW, WS_EX_CLIENTEDGE, wstr(class), 0, WS_CHILD|WS_VISIBLE|style,
		uintptr(x), uintptr(y), uintptr(w), uintptr(h), search.hwnd, id, app.hInst, 0)
}

func showSearch() {
	fg := call(pGetForegroundWindow)
	if fg != search.hwnd {
		search.prev = fg
	}
	setWindowText(search.edit, "")
	refilter()

	// mittig auf dem Bildschirm, auf dem gerade gearbeitet wird
	var mi monitorInfo
	mi.CbSize = uint32(unsafe.Sizeof(mi))
	mon := call(pMonitorFromWindow, search.prev, MONITOR_DEFAULTTONEAREST)
	x, y := 200, 200
	if mon != 0 && call(pGetMonitorInfoW, mon, uintptr(unsafe.Pointer(&mi))) != 0 {
		wa := mi.Work
		x = int(wa.Left) + (int(wa.Right-wa.Left)-sc(620))/2
		y = int(wa.Top) + (int(wa.Bottom-wa.Top)-sc(480))/3
	}
	call(pSetWindowPos, search.hwnd, ^uintptr(0) /* HWND_TOPMOST */, uintptr(x), uintptr(y), 0, 0, SWP_NOSIZE|SWP_SHOWWINDOW)
	call(pSetForegroundWindow, search.hwnd)
	call(pSetFocus, search.edit)
}

func hideSearch() {
	call(pShowWindow, search.hwnd, SW_HIDE)
}

func refilter() {
	search.view = app.lib().Search(windowText(search.edit))
	sendMessage(search.list, WM_SETREDRAW, 0, 0)
	sendMessage(search.list, LB_RESETCONTENT, 0, 0)
	for _, s := range search.view {
		t := s.Trigger
		if t == "" {
			t = "(Suche)"
		}
		sendMessage(search.list, LB_ADDSTRING, 0, wstr(" "+t+"\t"+s.Label()))
	}
	sendMessage(search.list, WM_SETREDRAW, 1, 0)
	call(pInvalidateRect, search.list, 0, 1)
	if len(search.view) > 0 {
		sendMessage(search.list, LB_SETCURSEL, 0, 0)
	}
	updatePreview()
}

func selected() *Snippet {
	i := int(int32(sendMessage(search.list, LB_GETCURSEL, 0, 0)))
	if i < 0 || i >= len(search.view) {
		return nil
	}
	return search.view[i]
}

func updatePreview() {
	s := selected()
	if s == nil {
		setWindowText(search.preview, "")
		return
	}
	setWindowText(search.preview, strings.ReplaceAll(s.Text, "\n", "\r\n"))
}

func moveSel(delta int) {
	n := int(sendMessage(search.list, LB_GETCOUNT, 0, 0))
	if n <= 0 {
		return
	}
	i := int(int32(sendMessage(search.list, LB_GETCURSEL, 0, 0))) + delta
	if i < 0 {
		i = 0
	}
	if i >= n {
		i = n - 1
	}
	sendMessage(search.list, LB_SETCURSEL, uintptr(i), 0)
	updatePreview()
}

func chooseSelected() {
	s := selected()
	if s == nil {
		return
	}
	hideSearch()
	if search.prev != 0 {
		call(pSetForegroundWindow, search.prev)
	}
	time.Sleep(150 * time.Millisecond)
	insertText(s.Text, 0)
}

func subclassProc(hwnd, msg, wp, lp uintptr) uintptr {
	switch uint32(msg) {
	case WM_KEYDOWN:
		switch wp {
		case VK_RETURN:
			chooseSelected()
			return 0
		case VK_ESCAPE:
			hideSearch()
			return 0
		}
		if hwnd == search.edit {
			switch wp {
			case VK_DOWN:
				moveSel(1)
				return 0
			case VK_UP:
				moveSel(-1)
				return 0
			case VK_NEXT:
				moveSel(8)
				return 0
			case VK_PRIOR:
				moveSel(-8)
				return 0
			}
		}
	case WM_CHAR:
		switch wp {
		case 10, 13, 27: // Enter/Esc: kein Warnton
			return 0
		case 1: // Strg+A
			if hwnd == search.edit {
				sendMessage(search.edit, EM_SETSEL, 0, ^uintptr(0))
			}
			return 0
		case 127: // Strg+Rücktaste
			return 0
		}
	}
	return call(pCallWindowProcW, origProcs[hwnd], hwnd, msg, wp, lp)
}

func searchWndProc(hwnd, msg, wp, lp uintptr) uintptr {
	switch uint32(msg) {
	case WM_COMMAND:
		id, code := wp&0xFFFF, (wp>>16)&0xFFFF
		switch {
		case id == idEdit && code == EN_CHANGE:
			refilter()
		case id == idList && code == LBN_SELCHANGE:
			updatePreview()
		case id == idList && code == LBN_DBLCLK:
			chooseSelected()
		}
		return 0
	case WM_ACTIVATE:
		if wp&0xFFFF == WA_INACTIVE {
			hideSearch() // woanders hingeklickt → Fenster zu
		} else {
			call(pSetFocus, search.edit)
		}
		return 0
	case WM_CLOSE:
		hideSearch()
		return 0
	case WM_CTLCOLORSTATIC:
		if lp == search.preview {
			call(pSetBkColor, wp, 0xFFFFFF)
			call(pSetTextColor, wp, 0x303030)
			return whiteBrush
		}
	}
	return call(pDefWindowProcW, hwnd, msg, wp, lp)
}
