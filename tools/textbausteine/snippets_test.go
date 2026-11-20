package main

import (
	"strings"
	"testing"
	"time"
)

func TestDefaultFileParses(t *testing.T) {
	lib := Parse([]byte(defaultFile))
	if lib.Count() != 8 {
		t.Fatalf("erwartet 8 Bausteine, bekommen %d", lib.Count())
	}
	if len(lib.Warnings) != 0 {
		t.Fatalf("unerwartete Warnungen: %v", lib.Warnings)
	}
	s := lib.Match([]rune("Hallo ;MFG"))
	if s == nil || s.Text != "Mit freundlichen Grüßen" {
		t.Fatalf("Match ;mfg fehlgeschlagen: %#v", s)
	}
	if lib.Match([]rune("Hallo ;mf")) != nil {
		t.Fatal("unvollständiges Kürzel darf nicht passen")
	}
	sig := lib.Match([]rune(";sig"))
	if sig == nil || !strings.HasPrefix(sig.Text, "Mit freundlichen Grüßen\n\nRolf Korr") {
		t.Fatalf("Signatur falsch: %q", sig.Text)
	}
}

func TestWarnings(t *testing.T) {
	lib := Parse([]byte("[;m]\na\n[;mfg]\nb\n[;m]\nc\n"))
	if len(lib.Warnings) != 2 {
		t.Fatalf("erwartet 2 Warnungen, bekommen %v", lib.Warnings)
	}
}

func TestExpand(t *testing.T) {
	now := time.Date(2026, 11, 20, 14, 5, 0, 0, time.Local)
	out, back := Expand("Am {wochentag}, {datum} um {zeit}, Frist {DATUM+14}: {cursor}.\nEnde {zwischenablage}", now, func() string { return "X\r\nY" })
	want := "Am Freitag, 20.11.2026 um 14:05, Frist 04.12.2026: .\nEnde X\nY"
	if out != want {
		t.Fatalf("\n got %q\nwant %q", out, want)
	}
	if back != len([]rune(".\nEnde X\nY")) {
		t.Fatalf("back = %d", back)
	}
}

func TestDecodeANSI(t *testing.T) {
	// "Grüße – €" in Windows-1252
	b := []byte{'G', 'r', 0xFC, 0xDF, 'e', ' ', 0x96, ' ', 0x80}
	if got := decodeText(b); got != "Grüße – €" {
		t.Fatalf("got %q", got)
	}
}

func TestSearch(t *testing.T) {
	lib := Parse([]byte(defaultFile))
	r := lib.Search("abwesen")
	if len(r) != 1 || r[0].Trigger != "" {
		t.Fatalf("Suche falsch: %v", r)
	}
	if len(lib.Search("")) != lib.Count() {
		t.Fatal("leere Suche muss alles zeigen")
	}
}
