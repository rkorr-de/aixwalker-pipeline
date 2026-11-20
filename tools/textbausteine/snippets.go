package main

// Plattformunabhängiger Teil: Datei lesen, Bausteine finden, Platzhalter ersetzen.
// Wird auch unter Linux getestet (go test).

import (
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode"
	"unicode/utf16"
	"unicode/utf8"
)

// Snippet ist ein Textbaustein.
type Snippet struct {
	Trigger string // Kürzel, z. B. ";mfg" (leer = nur über die Suche)
	Desc    string // kurze Beschreibung (freiwillig)
	Text    string // Text mit "\n" als Zeilenumbruch
	key     []rune // Kürzel in Kleinbuchstaben
}

// Label ist die Beschreibung oder die erste Textzeile.
func (s *Snippet) Label() string {
	if s.Desc != "" {
		return s.Desc
	}
	line := s.Text
	if i := strings.IndexByte(line, '\n'); i >= 0 {
		line = line[:i]
	}
	if r := []rune(line); len(r) > 70 {
		line = string(r[:70]) + "…"
	}
	return line
}

// Library ist der Inhalt der Datei Textbausteine.txt.
type Library struct {
	Snippets []*Snippet
	byLen    []*Snippet // Bausteine mit Kürzel, längstes Kürzel zuerst
	Warnings []string
}

var headerRe = regexp.MustCompile(`^\[([^\]\s]*)\](.*)$`)

// Parse liest den Dateiinhalt.
//
// Format:
//
//	# Notizen (nur vor dem ersten Baustein)
//	[;kuerzel] Beschreibung
//	Text, beliebig viele Zeilen
//	[] Baustein ohne Kürzel (nur Suche)
//	Text
func Parse(data []byte) *Library {
	text := decodeText(data)
	text = strings.ReplaceAll(text, "\r\n", "\n")
	text = strings.ReplaceAll(text, "\r", "\n")

	lib := &Library{}
	var cur *Snippet
	var lines []string
	flush := func() {
		if cur == nil {
			return
		}
		for len(lines) > 0 && strings.TrimSpace(lines[0]) == "" {
			lines = lines[1:]
		}
		for len(lines) > 0 && strings.TrimSpace(lines[len(lines)-1]) == "" {
			lines = lines[:len(lines)-1]
		}
		cur.Text = strings.Join(lines, "\n")
		if cur.Text != "" || cur.Trigger != "" {
			lib.Snippets = append(lib.Snippets, cur)
		}
		cur, lines = nil, nil
	}
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimRight(line, " \t")
		if m := headerRe.FindStringSubmatch(line); m != nil {
			flush()
			cur = &Snippet{Trigger: m[1], Desc: strings.TrimSpace(m[2])}
			continue
		}
		if cur != nil {
			lines = append(lines, line)
		}
	}
	flush()
	lib.index()
	return lib
}

func (l *Library) index() {
	seen := map[string]bool{}
	for _, s := range l.Snippets {
		if s.Trigger == "" {
			continue
		}
		k := strings.ToLower(s.Trigger)
		if seen[k] {
			l.Warnings = append(l.Warnings, fmt.Sprintf("Kürzel %s kommt mehrfach vor – nur das erste gilt.", s.Trigger))
			continue
		}
		seen[k] = true
		s.key = []rune(k)
		l.byLen = append(l.byLen, s)
	}
	sort.SliceStable(l.byLen, func(i, j int) bool { return len(l.byLen[i].key) > len(l.byLen[j].key) })
	for _, short := range l.byLen {
		for _, long := range l.byLen {
			if len(short.key) < len(long.key) && strings.HasPrefix(string(long.key), string(short.key)) {
				l.Warnings = append(l.Warnings, fmt.Sprintf("Kürzel %s ist der Anfang von %s – %s kann so nie ausgelöst werden.", short.Trigger, long.Trigger, long.Trigger))
			}
		}
	}
}

// Count ist die Zahl der Bausteine.
func (l *Library) Count() int {
	if l == nil {
		return 0
	}
	return len(l.Snippets)
}

// Match prüft, ob die zuletzt getippten Zeichen auf ein Kürzel enden.
func (l *Library) Match(buf []rune) *Snippet {
	if l == nil {
		return nil
	}
	for _, s := range l.byLen {
		k := s.key
		if len(k) > len(buf) {
			continue
		}
		tail := buf[len(buf)-len(k):]
		ok := true
		for i := range k {
			if unicode.ToLower(tail[i]) != k[i] {
				ok = false
				break
			}
		}
		if ok {
			return s
		}
	}
	return nil
}

// Search liefert alle Bausteine, die alle Suchwörter enthalten.
// Treffer im Kürzel oder in der Beschreibung stehen vorne.
func (l *Library) Search(query string) []*Snippet {
	if l == nil {
		return nil
	}
	words := strings.Fields(strings.ToLower(query))
	type hit struct {
		s     *Snippet
		score int
	}
	var hits []hit
	for _, s := range l.Snippets {
		head := strings.ToLower(s.Trigger + " " + s.Desc)
		all := head + " " + strings.ToLower(s.Text)
		ok, score := true, 0
		for _, w := range words {
			if !strings.Contains(all, w) {
				ok = false
				break
			}
			if strings.Contains(head, w) {
				score++
			}
		}
		if ok {
			hits = append(hits, hit{s, score})
		}
	}
	sort.SliceStable(hits, func(i, j int) bool { return hits[i].score > hits[j].score })
	out := make([]*Snippet, len(hits))
	for i, h := range hits {
		out[i] = h.s
	}
	return out
}

var (
	placeholderRe = regexp.MustCompile(`(?i)\{(datum(?:[+-]\d{1,4})?|zeit|wochentag|jahr|zwischenablage|cursor)\}`)
	weekdays      = [...]string{"Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"}
)

const cursorMark = "\x00"

// Expand ersetzt die Platzhalter. back = wie oft danach "Pfeil links"
// gedrückt werden muss, damit der Cursor an {cursor} steht.
func Expand(text string, now time.Time, clipboard func() string) (out string, back int) {
	out = placeholderRe.ReplaceAllStringFunc(text, func(m string) string {
		name := strings.ToLower(m[1 : len(m)-1])
		switch {
		case name == "zeit":
			return now.Format("15:04")
		case name == "wochentag":
			return weekdays[now.Weekday()]
		case name == "jahr":
			return now.Format("2006")
		case name == "cursor":
			return cursorMark
		case name == "zwischenablage":
			c := clipboard()
			c = strings.ReplaceAll(c, "\r\n", "\n")
			return strings.ReplaceAll(c, "\x00", "")
		case strings.HasPrefix(name, "datum"):
			d := now
			if len(name) > len("datum") {
				n, _ := strconv.Atoi(name[len("datum"):])
				d = now.AddDate(0, 0, n)
			}
			return d.Format("02.01.2006")
		}
		return m
	})
	if i := strings.Index(out, cursorMark); i >= 0 {
		after := strings.ReplaceAll(out[i+1:], cursorMark, "")
		out = out[:i] + after
		back = utf8.RuneCountInString(after)
	}
	return out, back
}

// decodeText versteht UTF-8 (mit/ohne BOM), UTF-16 und Windows-1252 (ANSI).
func decodeText(b []byte) string {
	switch {
	case len(b) >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF:
		b = b[3:]
	case len(b) >= 2 && b[0] == 0xFF && b[1] == 0xFE:
		return decodeUTF16(b[2:], false)
	case len(b) >= 2 && b[0] == 0xFE && b[1] == 0xFF:
		return decodeUTF16(b[2:], true)
	}
	if utf8.Valid(b) {
		return string(b)
	}
	var sb strings.Builder
	for _, c := range b {
		if c >= 0x80 && c < 0xA0 {
			sb.WriteRune(cp1252[c-0x80])
		} else {
			sb.WriteRune(rune(c))
		}
	}
	return sb.String()
}

func decodeUTF16(b []byte, bigEndian bool) string {
	u := make([]uint16, len(b)/2)
	for i := range u {
		if bigEndian {
			u[i] = uint16(b[2*i])<<8 | uint16(b[2*i+1])
		} else {
			u[i] = uint16(b[2*i+1])<<8 | uint16(b[2*i])
		}
	}
	return string(utf16.Decode(u))
}

var cp1252 = [32]rune{
	0x20AC, 0x81, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021,
	0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0x8D, 0x017D, 0x8F,
	0x90, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014,
	0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0x9D, 0x017E, 0x0178,
}

// defaultFile wird beim ersten Start als Textbausteine.txt angelegt.
const defaultFile = `# =====================================================================
#  TEXTBAUSTEINE – deine Kürzel
# =====================================================================
#
#  So funktioniert es:
#   • Jeder Baustein beginnt mit einer Zeile in eckigen Klammern:
#         [;kürzel] kurze Beschreibung
#   • Darunter steht der Text – so viele Zeilen du willst – bis zum
#     nächsten Baustein.
#   • Tippst du irgendwo das Kürzel, wird es sofort durch den Text ersetzt.
#   • Bausteine ohne Kürzel schreibst du so:  [] Beschreibung
#     Die findest du dann nur über die Suche.
#   • Suche öffnen: Strg + Alt + Leertaste
#     (oder einmal auf das Symbol unten rechts neben der Uhr klicken).
#
#  Platzhalter, die du im Text benutzen kannst:
#     {datum}           heutiges Datum, z. B. 20.11.2026
#     {datum+14}        Datum in 14 Tagen (geht auch mit {datum-1} usw.)
#     {zeit}            aktuelle Uhrzeit, z. B. 14:35
#     {wochentag}       z. B. Freitag
#     {jahr}            z. B. 2026
#     {zwischenablage}  das, was du gerade kopiert hast
#     {cursor}          dort steht danach der Schreib-Cursor
#
#  Tipps:
#   • Kürzel am besten mit ; beginnen – das kommt in normalem Text kaum vor.
#   • Ein Kürzel darf nicht der Anfang eines anderen sein (z. B. ;m und ;mfg).
#   • Speichern mit Strg + S – die Änderung gilt sofort.
#   • Zeilen mit # ganz oben (vor dem ersten Baustein) sind nur Notizen.
#
# =====================================================================

[;mfg] Grußformel
Mit freundlichen Grüßen

[;gruss] Grüße mit Name
Viele Grüße
Rolf Korr

[;sig] Komplette Signatur
Mit freundlichen Grüßen

Rolf Korr
Firma GmbH
Telefon: 0000 000000

[;danke] Danke für die Nachricht
vielen Dank für Ihre Nachricht. Ich melde mich bis {datum+2} bei Ihnen.

[;anbei] Anhang ankündigen
anbei erhalten Sie {cursor}.

Bei Fragen melden Sie sich gerne.

[;datum] Heutiges Datum
{datum}

[;zeit] Aktuelle Uhrzeit
{zeit}

[] Abwesenheitsnotiz
Vielen Dank für Ihre Nachricht. Ich bin bis einschließlich {cursor} nicht im Büro
und habe keinen Zugriff auf meine E-Mails. Ab dem Folgetag bin ich wieder für Sie da.
`
