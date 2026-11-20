package main

// Tastatur-Überwachung: merkt sich die zuletzt getippten Zeichen und meldet,
// wenn sie auf ein Kürzel enden. Läuft in einem eigenen Thread, damit das
// Einfügen (mit kurzen Pausen) die Tastatur nie bremst.

import (
	"runtime"
	"sync"
	"syscall"
	"unicode/utf16"
	"unsafe"
)

type expansion struct {
	snip       *Snippet
	backspaces int
}

var (
	hookBuf    []rune
	hookLastFg uintptr

	pendingMu sync.Mutex
	pending   *expansion

	keyboardCb = syscall.NewCallback(keyboardProc)
	mouseCb    = syscall.NewCallback(mouseProc)
)

func hookThread() {
	runtime.LockOSThread()
	hInst := call(pGetModuleHandleW, 0)
	kb := call(pSetWindowsHookExW, WH_KEYBOARD_LL, keyboardCb, hInst, 0)
	if kb == 0 {
		call(pPostMessageW, app.hwnd, WM_HOOKFAIL, 0, 0)
		return
	}
	call(pSetWindowsHookExW, WH_MOUSE_LL, mouseCb, hInst, 0)
	var m msgT
	for {
		r := call(pGetMessageW, uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if int32(r) <= 0 {
			return
		}
	}
}

func resetBuf() { hookBuf = hookBuf[:0] }

func keyboardProc(nCode, wParam, lParam uintptr) uintptr {
	if int32(nCode) == HC_ACTION && (wParam == WM_KEYDOWN || wParam == WM_SYSKEYDOWN) {
		kb := (*kbdllHookStruct)(unsafe.Pointer(lParam))
		if kb.Flags&LLKHF_INJECTED == 0 && !app.paused.Load() {
			if handleKey(kb) {
				return 1 // Taste schlucken: das letzte Zeichen des Kürzels erscheint gar nicht erst
			}
		}
	}
	return call(pCallNextHookEx, 0, nCode, wParam, lParam)
}

func mouseProc(nCode, wParam, lParam uintptr) uintptr {
	if int32(nCode) == HC_ACTION {
		switch wParam {
		case WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN:
			resetBuf() // Klick = Cursor woanders, also neu anfangen
		}
	}
	return call(pCallNextHookEx, 0, nCode, wParam, lParam)
}

func handleKey(kb *kbdllHookStruct) bool {
	fg := call(pGetForegroundWindow)
	if fg != hookLastFg {
		resetBuf()
		hookLastFg = fg
	}
	if fg == search.hwnd && fg != 0 {
		return false // im eigenen Suchfenster nichts ersetzen
	}

	vk := uintptr(kb.VkCode)
	switch {
	case vk == VK_BACK:
		if n := len(hookBuf); n > 0 {
			hookBuf = hookBuf[:n-1]
		}
		return false
	case vk == VK_SHIFT || vk == VK_CONTROL || vk == VK_MENU || (vk >= VK_LSHIFT && vk <= VK_RMENU),
		vk == VK_CAPITAL, vk == VK_NUMLOCK, vk == VK_SCROLL:
		return false
	case vk == VK_RETURN, vk == VK_TAB, vk == VK_ESCAPE, vk == VK_DELETE, vk == VK_INSERT,
		vk >= VK_PRIOR && vk <= VK_DOWN, vk == VK_LWIN, vk == VK_RWIN, vk == VK_APPS,
		vk >= VK_F1 && vk <= VK_F24:
		resetBuf()
		return false
	}

	ctrl, alt := keyDown(VK_CONTROL), keyDown(VK_MENU)
	if ctrl != alt || keyDown(VK_LWIN) || keyDown(VK_RWIN) {
		resetBuf() // Tastenkombination wie Strg+C, kein Text
		return false
	}

	var state [256]byte
	if keyDown(VK_SHIFT) {
		state[VK_SHIFT] = 0x80
	}
	if ctrl && alt { // AltGr (z. B. @ oder €)
		state[VK_CONTROL] = 0x80
		state[VK_MENU] = 0x80
	}
	if call(pGetKeyState, VK_CAPITAL)&1 != 0 {
		state[VK_CAPITAL] = 0x01
	}
	hkl := call(pGetKeyboardLayout, call(pGetWindowThreadProcessId, fg, 0))
	var buf [8]uint16
	// Flag 4: Tastaturzustand nicht verändern (sonst gehen Akzent-Tasten wie ^ und ´ kaputt)
	n := int32(call(pToUnicodeEx, vk, uintptr(kb.ScanCode), uintptr(unsafe.Pointer(&state[0])),
		uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)), 4, hkl))
	if n <= 0 {
		return false
	}
	for _, r := range utf16.Decode(buf[:n]) {
		if r < 0x20 {
			resetBuf()
			return false
		}
		hookBuf = append(hookBuf, r)
	}
	if len(hookBuf) > 64 {
		hookBuf = append(hookBuf[:0], hookBuf[len(hookBuf)-64:]...)
	}

	snip := app.lib().Match(hookBuf)
	if snip == nil {
		return false
	}
	resetBuf()
	pendingMu.Lock()
	pending = &expansion{snip: snip, backspaces: len(snip.key) - 1}
	pendingMu.Unlock()
	call(pPostMessageW, app.hwnd, WM_EXPAND, 0, 0)
	return true
}
