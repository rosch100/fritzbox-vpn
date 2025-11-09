# Logo-Export aus Affinity Designer/Photo

## Export-Einstellungen für Home Assistant/HACS Logo

### Schritt 1: Dokument-Größe prüfen

1. **Affinity Designer/Photo öffnen**
2. **Dokument-Größe prüfen**:
   - Sollte 256x256 Pixel sein (oder größer, dann beim Export skalieren)
   - Für hDPI-Version: 512x512 Pixel

### Schritt 2: Export-Einstellungen

1. **Datei → Exportieren** (oder `Cmd+Shift+Alt+E` / `Strg+Shift+Alt+E`)

2. **Format wählen**: **PNG**

3. **Export-Einstellungen**:

   #### Bereich
   - **Auswahl**: "Gesamtes Dokument" oder "Ausgewählte Objekte"
   - **Größe**: 256x256 Pixel (für Standard-Icon)
   - **Skalierung**: 1x (oder 2x für hDPI-Version = 512x512)

   #### Farbe
   - **Farbprofil**: **sRGB IEC61966-2.1** (wichtig!)
   - **Farbtiefe**: **8 Bit**
   - **Format**: **RGBA** (mit Alpha-Kanal für Transparenz)

   #### Komprimierung
   - **Komprimierung**: **PNG-24** oder **PNG-32** (mit Alpha)
   - **Interlacing**: **Aus** (nicht aktivieren)
   - **Optimierung**: **Für Web optimieren** (optional, aber empfohlen)

   #### Erweitert
   - **Dithering**: **Aus** (für Logos mit klaren Farben)
   - **Matte-Farbe**: **Keine** oder **Transparent** (wenn Transparenz gewünscht)

### Schritt 3: Speichern

1. **Dateiname**: `logo.png` (oder `icon.png` für Brands-Repository)
2. **Speicherort**: Wählen Sie den gewünschten Ordner
3. **Exportieren** klicken

## Empfohlene Export-Presets

### Preset 1: Standard-Icon (256x256)
```
Format: PNG
Größe: 256x256 Pixel
Farbprofil: sRGB IEC61966-2.1
Farbtiefe: 8 Bit
Format: RGBA
Komprimierung: PNG-32 (mit Alpha)
Interlacing: Aus
```

### Preset 2: hDPI-Icon (512x512)
```
Format: PNG
Größe: 512x512 Pixel
Farbprofil: sRGB IEC61966-2.1
Farbtiefe: 8 Bit
Format: RGBA
Komprimierung: PNG-32 (mit Alpha)
Interlacing: Aus
```

## Wichtige Hinweise

### ✅ Richtig:
- **sRGB Farbprofil** verwenden (nicht Adobe RGB oder ProPhoto RGB)
- **RGBA** für Transparenz
- **256x256 Pixel** für Standard-Icon
- **8 Bit Farbtiefe** (nicht 16 Bit)
- **PNG-32** für Transparenz-Unterstützung

### ❌ Falsch:
- ❌ Adobe RGB oder andere Farbprofile
- ❌ 16 Bit Farbtiefe (zu groß, nicht nötig)
- ❌ Interlacing aktiviert (nicht nötig für Icons)
- ❌ JPEG Format (keine Transparenz)
- ❌ Zu kleine Datei (unter 128x128 Pixel)

## Export für Brands-Repository

Wenn Sie das Logo für das Brands-Repository vorbereiten:

1. **Export 1**: `icon.png` (256x256 Pixel)
2. **Export 2**: `icon@2x.png` (512x512 Pixel)

Beide mit identischen Einstellungen, nur unterschiedliche Größe.

## Qualitätsprüfung nach dem Export

Nach dem Export können Sie prüfen:

```bash
# Datei-Informationen anzeigen
file logo.png

# Erwartete Ausgabe:
# logo.png: PNG image data, 256 x 256, 8-bit/color RGBA, non-interlaced
```

## Troubleshooting

### Problem: Logo sieht anders aus als im Designer
- **Lösung**: Stellen Sie sicher, dass Sie **sRGB** als Farbprofil verwenden

### Problem: Transparenz funktioniert nicht
- **Lösung**: Verwenden Sie **RGBA** Format und **PNG-32** Komprimierung

### Problem: Datei ist zu groß
- **Lösung**: 
  - Verwenden Sie 8 Bit statt 16 Bit
  - Optimieren Sie die Datei (Affinity hat eine "Für Web optimieren" Option)
  - Prüfen Sie, ob alle Ebenen notwendig sind

### Problem: Logo ist unscharf
- **Lösung**: 
  - Exportieren Sie in der vollen Auflösung (256x256 oder 512x512)
  - Skalieren Sie nicht nach dem Export
  - Verwenden Sie Vektorgrafiken im Designer, dann wird beim Export gerastert

## Beispiel-Export-Dialog

```
┌─────────────────────────────────────┐
│ Exportieren                         │
├─────────────────────────────────────┤
│ Format: PNG                         │
│                                     │
│ Bereich:                            │
│ ☑ Gesamtes Dokument                 │
│ Größe: 256 x 256 Pixel              │
│ Skalierung: 1x                      │
│                                     │
│ Farbe:                              │
│ Farbprofil: sRGB IEC61966-2.1       │
│ Farbtiefe: 8 Bit                    │
│ Format: RGBA                        │
│                                     │
│ Komprimierung:                      │
│ PNG-32 (mit Alpha)                  │
│ ☐ Interlacing                       │
│ ☑ Für Web optimieren                │
│                                     │
│ [Abbrechen]  [Exportieren]          │
└─────────────────────────────────────┘
```

## Nächste Schritte

1. ✅ Logo in Affinity Designer/Photo öffnen
2. ✅ Mit den obigen Einstellungen exportieren
3. ✅ Datei als `logo.png` speichern
4. ✅ In das Repository kopieren
5. ✅ Committen und pushen

