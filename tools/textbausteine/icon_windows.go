package main

// Zeichnet das Symbol für den Infobereich (blaugrünes Quadrat mit drei Textzeilen).

import (
	"math"
	"unsafe"
)

// iconPixels liefert 32×32 Pixel im Format 0xAARRGGBB (vormultipliert).
func iconPixels() []uint32 {
	const s = 32
	px := make([]uint32, s*s)
	inRounded := func(x, y float64) float64 { // Deckung 0..1 für abgerundetes Quadrat
		const r, lo, hi = 7.0, 1.0, 31.0
		cx := x
		if cx < lo+r {
			cx = lo + r
		} else if cx > hi-r {
			cx = hi - r
		}
		cy := y
		if cy < lo+r {
			cy = lo + r
		} else if cy > hi-r {
			cy = hi - r
		}
		dx, dy := x-cx, y-cy
		d := dx*dx + dy*dy
		if d <= (r-0.5)*(r-0.5) {
			return 1
		}
		if d >= (r+0.5)*(r+0.5) {
			return 0
		}
		return r + 0.5 - math.Sqrt(d)
	}
	line := func(x, y int) bool {
		switch {
		case y >= 9 && y <= 11:
			return x >= 8 && x <= 23
		case y >= 15 && y <= 17:
			return x >= 8 && x <= 23
		case y >= 21 && y <= 23:
			return x >= 8 && x <= 17
		}
		return false
	}
	for y := 0; y < s; y++ {
		for x := 0; x < s; x++ {
			a := inRounded(float64(x)+0.5, float64(y)+0.5)
			if a <= 0 {
				continue
			}
			r, g, b := 0x0F, 0x76, 0x6E // Petrol
			if line(x, y) {
				r, g, b = 0xFF, 0xFF, 0xFF
			}
			A := uint32(a*255 + 0.5)
			px[y*s+x] = A<<24 | uint32(r)*A/255<<16 | uint32(g)*A/255<<8 | uint32(b)*A/255
		}
	}
	return px
}

func makeIcon() uintptr {
	const s = 32
	bi := bitmapInfoHeader{Width: s, Height: -s, Planes: 1, BitCount: 32}
	bi.Size = uint32(unsafe.Sizeof(bi))
	var bits uintptr
	hdc := call(pGetDC, 0)
	color := call(pCreateDIBSection, hdc, uintptr(unsafe.Pointer(&bi)), 0, uintptr(unsafe.Pointer(&bits)), 0, 0)
	call(pReleaseDC, 0, hdc)
	if color == 0 || bits == 0 {
		return 0
	}
	copy(unsafe.Slice((*uint32)(unsafe.Pointer(bits)), s*s), iconPixels())
	maskBits := make([]byte, s*s/8)
	mask := call(pCreateBitmap, s, s, 1, 1, uintptr(unsafe.Pointer(&maskBits[0])))
	ii := iconInfo{FIcon: 1, HbmMask: mask, HbmColor: color}
	return call(pCreateIconIndirect, uintptr(unsafe.Pointer(&ii)))
}
