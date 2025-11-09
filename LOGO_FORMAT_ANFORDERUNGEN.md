# Logo-Format-Anforderungen für HACS/Home Assistant

## Offizielle Anforderungen

### Dateiformat
- **Format**: PNG
- **Farbraum**: sRGB
- **Komprimierung**: Verlustfrei, optimiert für Web
- **Transparenz**: Bevorzugt (RGBA)

### Größen-Anforderungen

#### Für Icons (empfohlen für Custom Components):
- **Standard**: 256x256 Pixel
- **hDPI**: 512x512 Pixel (optional, als `icon@2x.png`)

#### Für Logos:
- **Kürzeste Seite**: Mindestens 128 Pixel, maximal 256 Pixel
- **Seitenverhältnis**: Entsprechend dem Markenlogo (bevorzugt Querformat)

### Weitere Anforderungen
- **Beschnitt**: Kein unnötiger Leerraum
- **Hintergrund**: Für helle Hintergründe optimiert
- **Dunkler Hintergrund**: Separate Dateien mit Präfix `dark_` möglich

## Aktuelles Logo

### Vorher (falsch):
- Größe: 100x100 Pixel ❌ (unter dem Minimum von 128 Pixel)

### Jetzt (korrekt):
- Größe: 256x256 Pixel ✅
- Format: PNG RGBA ✅
- Farbraum: sRGB ✅

## Wichtig für HACS

**Hinweis**: Auch wenn das Logo-Format korrekt ist, werden Logos für Custom Components in HACS nur angezeigt, wenn sie im **Home Assistant Brands-Repository** registriert sind.

### Optionen:

1. **Brands-Repository** (empfohlen):
   - Logo im Brands-Repository registrieren
   - Wird automatisch in HACS angezeigt
   - Dauer: Einige Tage (PR-Review)

2. **Lokale Verwendung**:
   - Logo lokal in Home Assistant ablegen
   - Wird nur lokal angezeigt, nicht in HACS

## Nächste Schritte

1. ✅ Logo auf 256x256 Pixel angepasst
2. ⏳ Logo im Brands-Repository registrieren (optional, für HACS-Anzeige)

