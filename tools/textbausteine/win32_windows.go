package main

// Direkte Windows-API-Aufrufe (nur Standardbibliothek, keine Fremdpakete).

import (
	"syscall"
	"unicode/utf16"
	"unsafe"
)

var (
	user32   = syscall.NewLazyDLL("user32.dll")
	kernel32 = syscall.NewLazyDLL("kernel32.dll")
	shell32  = syscall.NewLazyDLL("shell32.dll")
	gdi32    = syscall.NewLazyDLL("gdi32.dll")
	advapi32 = syscall.NewLazyDLL("advapi32.dll")

	pSetWindowsHookExW        = user32.NewProc("SetWindowsHookExW")
	pCallNextHookEx           = user32.NewProc("CallNextHookEx")
	pGetMessageW              = user32.NewProc("GetMessageW")
	pTranslateMessage         = user32.NewProc("TranslateMessage")
	pDispatchMessageW         = user32.NewProc("DispatchMessageW")
	pPostMessageW             = user32.NewProc("PostMessageW")
	pSendMessageW             = user32.NewProc("SendMessageW")
	pPostQuitMessage          = user32.NewProc("PostQuitMessage")
	pDefWindowProcW           = user32.NewProc("DefWindowProcW")
	pRegisterClassExW         = user32.NewProc("RegisterClassExW")
	pCreateWindowExW          = user32.NewProc("CreateWindowExW")
	pDestroyWindow            = user32.NewProc("DestroyWindow")
	pShowWindow               = user32.NewProc("ShowWindow")
	pIsWindowVisible          = user32.NewProc("IsWindowVisible")
	pSetWindowPos             = user32.NewProc("SetWindowPos")
	pSetForegroundWindow      = user32.NewProc("SetForegroundWindow")
	pGetForegroundWindow      = user32.NewProc("GetForegroundWindow")
	pSetFocus                 = user32.NewProc("SetFocus")
	pGetClientRect            = user32.NewProc("GetClientRect")
	pSetWindowTextW           = user32.NewProc("SetWindowTextW")
	pGetWindowThreadProcessId = user32.NewProc("GetWindowThreadProcessId")
	pGetKeyboardLayout        = user32.NewProc("GetKeyboardLayout")
	pToUnicodeEx              = user32.NewProc("ToUnicodeEx")
	pGetAsyncKeyState         = user32.NewProc("GetAsyncKeyState")
	pGetKeyState              = user32.NewProc("GetKeyState")
	pMapVirtualKeyW           = user32.NewProc("MapVirtualKeyW")
	pSendInput                = user32.NewProc("SendInput")
	pOpenClipboard            = user32.NewProc("OpenClipboard")
	pCloseClipboard           = user32.NewProc("CloseClipboard")
	pEmptyClipboard           = user32.NewProc("EmptyClipboard")
	pGetClipboardData         = user32.NewProc("GetClipboardData")
	pSetClipboardData         = user32.NewProc("SetClipboardData")
	pCountClipboardFormats    = user32.NewProc("CountClipboardFormats")
	pRegisterClipboardFormatW = user32.NewProc("RegisterClipboardFormatW")
	pMessageBoxW              = user32.NewProc("MessageBoxW")
	pLoadCursorW              = user32.NewProc("LoadCursorW")
	pCreatePopupMenu          = user32.NewProc("CreatePopupMenu")
	pAppendMenuW              = user32.NewProc("AppendMenuW")
	pTrackPopupMenu           = user32.NewProc("TrackPopupMenu")
	pDestroyMenu              = user32.NewProc("DestroyMenu")
	pSetMenuDefaultItem       = user32.NewProc("SetMenuDefaultItem")
	pGetCursorPos             = user32.NewProc("GetCursorPos")
	pRegisterHotKey           = user32.NewProc("RegisterHotKey")
	pSetTimer                 = user32.NewProc("SetTimer")
	pRegisterWindowMessageW   = user32.NewProc("RegisterWindowMessageW")
	pSetWindowLongPtrW        = user32.NewProc("SetWindowLongPtrW")
	pCallWindowProcW          = user32.NewProc("CallWindowProcW")
	pMonitorFromWindow        = user32.NewProc("MonitorFromWindow")
	pGetMonitorInfoW          = user32.NewProc("GetMonitorInfoW")
	pGetDC                    = user32.NewProc("GetDC")
	pReleaseDC                = user32.NewProc("ReleaseDC")
	pCreateIconIndirect       = user32.NewProc("CreateIconIndirect")
	pInvalidateRect           = user32.NewProc("InvalidateRect")
	pSetProcessDPIAware       = user32.NewProc("SetProcessDPIAware")

	pGetModuleHandleW = kernel32.NewProc("GetModuleHandleW")
	pCreateMutexW     = kernel32.NewProc("CreateMutexW")
	pGlobalAlloc      = kernel32.NewProc("GlobalAlloc")
	pGlobalLock       = kernel32.NewProc("GlobalLock")
	pGlobalUnlock     = kernel32.NewProc("GlobalUnlock")
	pGlobalSize       = kernel32.NewProc("GlobalSize")
	pGlobalFree       = kernel32.NewProc("GlobalFree")

	pShellNotifyIconW = shell32.NewProc("Shell_NotifyIconW")
	pShellExecuteW    = shell32.NewProc("ShellExecuteW")

	pCreateFontW      = gdi32.NewProc("CreateFontW")
	pGetDeviceCaps    = gdi32.NewProc("GetDeviceCaps")
	pCreateDIBSection = gdi32.NewProc("CreateDIBSection")
	pCreateBitmap     = gdi32.NewProc("CreateBitmap")
	pSetBkColor       = gdi32.NewProc("SetBkColor")
	pSetTextColor     = gdi32.NewProc("SetTextColor")
	pGetStockObject   = gdi32.NewProc("GetStockObject")

	pRegOpenKeyExW    = advapi32.NewProc("RegOpenKeyExW")
	pRegSetValueExW   = advapi32.NewProc("RegSetValueExW")
	pRegQueryValueExW = advapi32.NewProc("RegQueryValueExW")
	pRegDeleteValueW  = advapi32.NewProc("RegDeleteValueW")
	pRegCloseKey      = advapi32.NewProc("RegCloseKey")
)

const (
	WH_KEYBOARD_LL = 13
	WH_MOUSE_LL    = 14
	HC_ACTION      = 0
	LLKHF_INJECTED = 0x10

	WM_NULL           = 0x0000
	WM_DESTROY        = 0x0002
	WM_ACTIVATE       = 0x0006
	WM_SETTEXT        = 0x000C
	WM_GETTEXT        = 0x000D
	WM_GETTEXTLENGTH  = 0x000E
	WM_CLOSE          = 0x0010
	WM_SETREDRAW      = 0x000B
	WM_SETFONT        = 0x0030
	WM_CONTEXTMENU    = 0x007B
	WM_KEYDOWN        = 0x0100
	WM_CHAR           = 0x0102
	WM_SYSKEYDOWN     = 0x0104
	WM_COMMAND        = 0x0111
	WM_TIMER          = 0x0113
	WM_CTLCOLORSTATIC = 0x0138
	WM_LBUTTONDOWN    = 0x0201
	WM_LBUTTONUP      = 0x0202
	WM_RBUTTONDOWN    = 0x0204
	WM_RBUTTONUP      = 0x0205
	WM_MBUTTONDOWN    = 0x0207
	WM_HOTKEY         = 0x0312
	WM_APP            = 0x8000

	WA_INACTIVE = 0

	WS_POPUP         = 0x80000000
	WS_VISIBLE       = 0x10000000
	WS_CHILD         = 0x40000000
	WS_CAPTION       = 0x00C00000
	WS_SYSMENU       = 0x00080000
	WS_VSCROLL       = 0x00200000
	WS_TABSTOP       = 0x00010000
	WS_EX_TOPMOST    = 0x00000008
	WS_EX_TOOLWINDOW = 0x00000080
	WS_EX_CLIENTEDGE = 0x00000200

	ES_MULTILINE    = 0x0004
	ES_AUTOVSCROLL  = 0x0040
	ES_AUTOHSCROLL  = 0x0080
	ES_READONLY     = 0x0800
	EN_CHANGE       = 0x0300
	EM_SETSEL       = 0x00B1
	EM_SETMARGINS   = 0x00D3
	EM_SETCUEBANNER = 0x1501

	LBS_NOTIFY           = 0x0001
	LBS_USETABSTOPS      = 0x0080
	LBS_NOINTEGRALHEIGHT = 0x0100
	LBN_SELCHANGE        = 1
	LBN_DBLCLK           = 2
	LB_ADDSTRING         = 0x0180
	LB_RESETCONTENT      = 0x0184
	LB_SETCURSEL         = 0x0186
	LB_GETCURSEL         = 0x0188
	LB_GETCOUNT          = 0x018B
	LB_SETTABSTOPS       = 0x0192
	LB_SETITEMHEIGHT     = 0x01A0

	SW_HIDE       = 0
	SW_SHOWNORMAL = 1

	SWP_NOSIZE     = 0x0001
	SWP_SHOWWINDOW = 0x0040

	MB_ICONERROR       = 0x10
	MB_ICONWARNING     = 0x30
	MB_ICONINFORMATION = 0x40
	MB_SETFOREGROUND   = 0x10000

	MF_STRING       = 0x0000
	MF_CHECKED      = 0x0008
	MF_SEPARATOR    = 0x0800
	TPM_RIGHTBUTTON = 0x0002
	TPM_NONOTIFY    = 0x0080
	TPM_RETURNCMD   = 0x0100

	MOD_ALT      = 0x0001
	MOD_CONTROL  = 0x0002
	MOD_NOREPEAT = 0x4000

	NIM_ADD      = 0
	NIM_MODIFY   = 1
	NIM_DELETE   = 2
	NIF_MESSAGE  = 0x01
	NIF_ICON     = 0x02
	NIF_TIP      = 0x04
	NIF_INFO     = 0x10
	NIIF_INFO    = 0x01
	NIIF_WARNING = 0x02

	INPUT_KEYBOARD        = 1
	KEYEVENTF_EXTENDEDKEY = 0x0001
	KEYEVENTF_KEYUP       = 0x0002

	CF_UNICODETEXT = 13
	GMEM_MOVEABLE  = 0x0002
	GMEM_ZEROINIT  = 0x0040

	COLOR_BTNFACE            = 15
	WHITE_BRUSH              = 0
	IDC_ARROW                = 32512
	LOGPIXELSX               = 88
	MONITOR_DEFAULTTONEAREST = 2

	HKEY_CURRENT_USER = 0x80000001
	KEY_QUERY_VALUE   = 0x0001
	KEY_SET_VALUE     = 0x0002
	REG_SZ            = 1

	VK_BACK    = 0x08
	VK_TAB     = 0x09
	VK_RETURN  = 0x0D
	VK_SHIFT   = 0x10
	VK_CONTROL = 0x11
	VK_MENU    = 0x12
	VK_CAPITAL = 0x14
	VK_ESCAPE  = 0x1B
	VK_SPACE   = 0x20
	VK_PRIOR   = 0x21
	VK_NEXT    = 0x22
	VK_END     = 0x23
	VK_HOME    = 0x24
	VK_LEFT    = 0x25
	VK_UP      = 0x26
	VK_RIGHT   = 0x27
	VK_DOWN    = 0x28
	VK_INSERT  = 0x2D
	VK_DELETE  = 0x2E
	VK_LWIN    = 0x5B
	VK_RWIN    = 0x5C
	VK_APPS    = 0x5D
	VK_F1      = 0x70
	VK_F24     = 0x87
	VK_NUMLOCK = 0x90
	VK_SCROLL  = 0x91
	VK_LSHIFT  = 0xA0
	VK_RMENU   = 0xA5
)

type point struct{ X, Y int32 }

type rect struct{ Left, Top, Right, Bottom int32 }

type msgT struct {
	Hwnd    uintptr
	Message uint32
	WParam  uintptr
	LParam  uintptr
	Time    uint32
	Pt      point
	Private uint32
}

type wndClassExW struct {
	Size       uint32
	Style      uint32
	WndProc    uintptr
	ClsExtra   int32
	WndExtra   int32
	Instance   uintptr
	Icon       uintptr
	Cursor     uintptr
	Background uintptr
	MenuName   *uint16
	ClassName  *uint16
	IconSm     uintptr
}

type kbdllHookStruct struct {
	VkCode    uint32
	ScanCode  uint32
	Flags     uint32
	Time      uint32
	ExtraInfo uintptr
}

type notifyIconData struct {
	CbSize           uint32
	HWnd             uintptr
	UID              uint32
	UFlags           uint32
	UCallbackMessage uint32
	HIcon            uintptr
	SzTip            [128]uint16
	DwState          uint32
	DwStateMask      uint32
	SzInfo           [256]uint16
	UVersion         uint32
	SzInfoTitle      [64]uint16
	DwInfoFlags      uint32
	GuidItem         [16]byte
	HBalloonIcon     uintptr
}

// keyInput entspricht INPUT mit KEYBDINPUT (64 Bit: 40 Byte).
type keyInput struct {
	Type  uint32
	_     uint32
	Vk    uint16
	Scan  uint16
	Flags uint32
	Time  uint32
	_     uint32
	Extra uintptr
	_     [8]byte
}

type monitorInfo struct {
	CbSize  uint32
	Monitor rect
	Work    rect
	Flags   uint32
}

type bitmapInfoHeader struct {
	Size          uint32
	Width         int32
	Height        int32
	Planes        uint16
	BitCount      uint16
	Compression   uint32
	SizeImage     uint32
	XPelsPerMeter int32
	YPelsPerMeter int32
	ClrUsed       uint32
	ClrImportant  uint32
}

type iconInfo struct {
	FIcon    int32
	XHotspot uint32
	YHotspot uint32
	HbmMask  uintptr
	HbmColor uintptr
}

// call ruft eine Windows-Funktion auf und liefert den Rückgabewert.
//
//go:uintptrescapes
func call(p *syscall.LazyProc, a ...uintptr) uintptr {
	r, _, _ := p.Call(a...)
	return r
}

var keepStrings [][]uint16 // hält Zeichenketten am Leben, die Windows dauerhaft braucht

// wstr wandelt Text in einen Windows-Zeiger (UTF-16, mit 0 am Ende).
func wstr(s string) uintptr {
	u := append(utf16.Encode([]rune(s)), 0)
	keepStrings = append(keepStrings, u)
	if len(keepStrings) > 512 {
		keepStrings = keepStrings[len(keepStrings)-256:]
	}
	return uintptr(unsafe.Pointer(&u[0]))
}

func copyUTF16(dst []uint16, s string) {
	u := utf16.Encode([]rune(s))
	if len(u) > len(dst)-1 {
		u = u[:len(dst)-1]
	}
	copy(dst, u)
	dst[len(u)] = 0
}

func sendMessage(h uintptr, msg uint32, wp, lp uintptr) uintptr {
	return call(pSendMessageW, h, uintptr(msg), wp, lp)
}

func windowText(h uintptr) string {
	n := sendMessage(h, WM_GETTEXTLENGTH, 0, 0)
	buf := make([]uint16, n+1)
	sendMessage(h, WM_GETTEXT, n+1, uintptr(unsafe.Pointer(&buf[0])))
	return syscall.UTF16ToString(buf)
}

func setWindowText(h uintptr, s string) {
	call(pSetWindowTextW, h, wstr(s))
}

func keyDown(vk uintptr) bool {
	return call(pGetAsyncKeyState, vk)&0x8000 != 0
}

func msgBox(text string, flags uintptr) {
	call(pMessageBoxW, 0, wstr(text), wstr(appName), flags|MB_SETFOREGROUND)
}
