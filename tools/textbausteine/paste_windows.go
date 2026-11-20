package main

// Text einfügen: Kürzel löschen, Text über die Zwischenablage einfügen (Strg+V),
// danach die alte Zwischenablage zurückholen.

import (
	"strings"
	"syscall"
	"time"
	"unicode/utf16"
	"unsafe"
)

var (
	cfExclude   = call(pRegisterClipboardFormatW, wstr("ExcludeClipboardContentFromMonitorProcessing"))
	cfNoHistory = call(pRegisterClipboardFormatW, wstr("CanIncludeInClipboardHistory"))
	cfNoCloud   = call(pRegisterClipboardFormatW, wstr("CanUploadToCloudClipboard"))
)

func insertText(text string, backspaces int) {
	waitForModifiers()
	if backspaces > 0 {
		tap(VK_BACK, backspaces)
		time.Sleep(20 * time.Millisecond)
	}
	old, hadText, empty := readClipboardText()
	out, back := Expand(text, time.Now(), func() string { return old })
	if out == "" {
		return
	}
	if !setClipboardText(strings.ReplaceAll(out, "\n", "\r\n")) {
		msgBox("Die Zwischenablage ist gerade blockiert. Bitte noch einmal versuchen.", MB_ICONWARNING)
		return
	}
	time.Sleep(40 * time.Millisecond)
	send([]keyInput{key(VK_CONTROL, false), key('V', false), key('V', true), key(VK_CONTROL, true)})
	if back > 0 {
		time.Sleep(150 * time.Millisecond)
		tap(VK_LEFT, back)
	}
	time.Sleep(700 * time.Millisecond) // dem Programm Zeit lassen, die Zwischenablage zu lesen
	if hadText {
		setClipboardText(old)
	} else if empty {
		clearClipboard()
	}
}

// waitForModifiers wartet, bis Umschalt/Strg/Alt/Windows losgelassen sind.
func waitForModifiers() {
	for i := 0; i < 100; i++ {
		if !keyDown(VK_SHIFT) && !keyDown(VK_CONTROL) && !keyDown(VK_MENU) && !keyDown(VK_LWIN) && !keyDown(VK_RWIN) {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
}

func key(vk uint16, up bool) keyInput {
	k := keyInput{Type: INPUT_KEYBOARD, Vk: vk, Scan: uint16(call(pMapVirtualKeyW, uintptr(vk), 0))}
	if up {
		k.Flags |= KEYEVENTF_KEYUP
	}
	switch vk {
	case VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN, VK_HOME, VK_END, VK_PRIOR, VK_NEXT, VK_INSERT, VK_DELETE:
		k.Flags |= KEYEVENTF_EXTENDEDKEY
	}
	return k
}

func tap(vk uint16, n int) {
	in := make([]keyInput, 0, 2*n)
	for i := 0; i < n; i++ {
		in = append(in, key(vk, false), key(vk, true))
	}
	send(in)
}

func send(in []keyInput) {
	if len(in) == 0 {
		return
	}
	call(pSendInput, uintptr(len(in)), uintptr(unsafe.Pointer(&in[0])), unsafe.Sizeof(in[0]))
}

func openClipboard() bool {
	for i := 0; i < 20; i++ {
		if call(pOpenClipboard, app.hwnd) != 0 {
			return true
		}
		time.Sleep(25 * time.Millisecond)
	}
	return false
}

// readClipboardText liefert den Text der Zwischenablage.
// hasText: es war Text drin; empty: die Zwischenablage war ganz leer.
func readClipboardText() (text string, hasText, empty bool) {
	if !openClipboard() {
		return "", false, false
	}
	defer call(pCloseClipboard)
	if call(pCountClipboardFormats) == 0 {
		return "", false, true
	}
	h := call(pGetClipboardData, CF_UNICODETEXT)
	if h == 0 {
		return "", false, false
	}
	p := call(pGlobalLock, h)
	if p == 0 {
		return "", false, false
	}
	defer call(pGlobalUnlock, h)
	n := call(pGlobalSize, h) / 2
	if n == 0 {
		return "", true, false
	}
	s := unsafe.Slice((*uint16)(unsafe.Pointer(p)), n)
	return syscall.UTF16ToString(s), true, false
}

func globalBytes(u []uint16) uintptr {
	h := call(pGlobalAlloc, GMEM_MOVEABLE, uintptr(len(u)*2))
	if h == 0 {
		return 0
	}
	p := call(pGlobalLock, h)
	if p == 0 {
		call(pGlobalFree, h)
		return 0
	}
	copy(unsafe.Slice((*uint16)(unsafe.Pointer(p)), len(u)), u)
	call(pGlobalUnlock, h)
	return h
}

func setClipboardText(s string) bool {
	h := globalBytes(append(utf16.Encode([]rune(s)), 0))
	if h == 0 {
		return false
	}
	if !openClipboard() {
		call(pGlobalFree, h)
		return false
	}
	defer call(pCloseClipboard)
	call(pEmptyClipboard)
	if call(pSetClipboardData, CF_UNICODETEXT, h) == 0 {
		call(pGlobalFree, h)
		return false
	}
	// Nicht im Zwischenablage-Verlauf (Windows+V) und nicht in der Cloud speichern.
	for _, f := range []uintptr{cfExclude, cfNoHistory, cfNoCloud} {
		if f == 0 {
			continue
		}
		hh := call(pGlobalAlloc, GMEM_MOVEABLE|GMEM_ZEROINIT, 4)
		if hh != 0 && call(pSetClipboardData, f, hh) == 0 {
			call(pGlobalFree, hh)
		}
	}
	return true
}

func clearClipboard() {
	if openClipboard() {
		call(pEmptyClipboard)
		call(pCloseClipboard)
	}
}
