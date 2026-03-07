# Analyse: FritzBox-Repeater erscheinen nach Neustart wieder als „neu hinzuzufügen“

**Log:** `home-assistant_fritz_2026-03-07T07-41-31.118Z.log` (Downloads)  
**Betroffene Integration:** Offizielle Home-Assistant-Integration **FRITZ!Box Tools** (`homeassistant.components.fritz`), **nicht** die Custom-Integration Fritz!Box VPN aus diesem Repo.

---

## Befund aus dem Log

1. **Drei FRITZ!Box-Tools-Einträge werden geladen**
   - „Setting up FRITZ!Box Tools component“ erscheint dreimal (08:31:03):
     - Fritz!Box 7583 (Router) unter `192.168.253.1`
     - Zwei FRITZ!Repeater 1200 AX unter `192.168.253.227` und `192.168.253.230`

2. **Repeater sind nach dem Start erreichbar**
   - Repeater liefern `404` für `igddesc.xml`, antworten aber auf `tr64desc.xml` und werden per TR-064 angesprochen.
   - Coordinator-Logs zeigen erfolgreiche Datenabfragen für beide Repeater (z. B. „Finished fetching fritz-192.168.253.230-coordinator data … success: True“).

3. **Problem**
   - Nach jedem Neustart erscheinen die Repeater wieder als **neu zu entdeckende Geräte** („neu hinzuzufügen“), obwohl sie bereits konfiguriert sind.

---

## Ursache (offizielle Fritz-Integration)

Das Verhalten gehört zu bekannten Themen der **offiziellen** Fritz-Integration (FRITZ!Box Tools) in Home Assistant Core:

- **Discovery vs. Persistenz:** SSDP entdeckt die Repeater bei jedem Start erneut. Wenn der bei der Discovery verwendete **unique_id** nicht exakt mit dem der gespeicherten Config-Einträge übereinstimmt (z. B. UDN/UUID oder Host/IP), wird kein `already_configured` ausgelöst und die Integration zeigt die Repeater erneut als „neu hinzuzufügen“ an.
- **Ähnliche Meldungen:**  
  - [Issue #74179](https://github.com/home-assistant/core/issues/74179) (AVM FRITZ!SmartHome: Repeater immer wieder als neues Gerät entdeckt; **closed**, Lösung: ignorieren)  
  - [Issue #71822](https://github.com/home-assistant/core/issues/71822) (FRITZ!Box Tools: Rekonfiguration nach jedem Neustart bei Repeater; **closed**, Fix 2023.3 für unreachable)  
  - [Issue #134679](https://github.com/home-assistant/core/issues/134679) (Fritzconnection/Repeater nach 2025.1.0; **closed** not_planned; Repeater werden wieder als neues Gerät erkannt)  
  - [Issue #50159](https://github.com/home-assistant/core/issues/50159) (FRITZ!Box Tools Mesh: Auto-Discovery findet weiterhin neue Geräte; **closed**)  
  - [Issue #163330](https://github.com/home-assistant/core/issues/163330) (Platform fritz does not generate unique IDs; **open**, under investigation – gleiche Integration/unique_id-Thematik)

Die eigentliche Ursache liegt in der **Core-Integration** `homeassistant.components.fritz` (Config-Flow, SSDP, unique_id), nicht in der Custom-Integration **Fritz!Box VPN** aus diesem Repo.

---

## Abgrenzung zu Fritz!Box VPN (dieses Repo)

- **Fritz!Box VPN** (`fritzbox_vpn`) steuert nur **WireGuard-VPN-Verbindungen** auf der Fritz!Box.
- Repeater werden hier bewusst **nicht** als neue Integration angeboten: In `config_flow.py` filtert `_is_fritzbox_device()` Repeater per `REPEATER_INDICATORS` heraus, SSDP-Discovery für Repeater führt zu `async_abort(reason="not_fritzbox")`.
- Das Repeater-„neu hinzuzufügen“-Problem betrifft ausschließlich die **FRITZ!Box Tools**-Integration; in diesem Repo gibt es dafür keine umsetzbare Code-Änderung.

---

## Empfehlungen

1. **Discovery ignorieren**
   - Wenn die Meldung „Neues Gerät gefunden“ für die Repeater erscheint: Über das Drei-Punkte-Menü der Meldung **„Ignorieren“** wählen, damit diese Discovery dauerhaft unterdrückt wird (wird von HA persistiert).

2. **Home Assistant aktuell halten**
   - Mit neueren HA-Versionen wurden Verbesserungen an der Fritz-Integration (z. B. Fehlerbehandlung, Reconfig bei unreachable) umgesetzt. Prüfen, ob eine Aktualisierung auf die neueste stabile Version das Verhalten verbessert.

3. **Issue/PR im Core melden bzw. verfolgen**
   - **Angelegt:** [Issue #165036](https://github.com/home-assistant/core/issues/165036) (FRITZ!Box Tools: Repeaters shown as "new" after every restart). Verlinkt: #74179, #71822, #134679, #50159.
   - Optional: bei offenen Fritz-Issues in einem Kommentar auf #165036 verweisen.

4. **Diagnose (optional)**
   - Unter **Einstellungen → Geräte & Dienste → FRITZ!Box Tools** für die betroffenen Repeater-Einträge „Diagnose herunterladen“ und prüfen, welcher `unique_id` gespeichert ist. Bei einer Bugmeldung im Core-Repo können diese (bereinigt von Passwörtern) angehängt werden.

---

## Bug report template (home-assistant/core)

**Opened issue:** [#165036](https://github.com/home-assistant/core/issues/165036)

Summary: Repeaters appear as "new" again after each restart. SSDP/unique_id should match existing config entries. Related (closed): #74179, #71822, #134679, #50159. **Related (open):** [#163330](https://github.com/home-assistant/core/issues/163330) (Platform fritz does not generate unique IDs, under investigation). Workaround: Ignore discovery notification.

---

## Kurzfassung

- **Problem:** Repeater der **FRITZ!Box Tools**-Integration erscheinen nach jedem Neustart wieder als „neu hinzuzufügen“.
- **Ursache:** Verhalten der **offiziellen** Fritz-Integration (Discovery/Persistenz/unique_id), nicht der Custom-Integration Fritz!Box VPN.
- **Sofort-Mitigation:** Discovery für die Repeater über „Ignorieren“ unterdrücken.
- **Langfristig:** HA aktuell halten; Bug-Report [#165036](https://github.com/home-assistant/core/issues/165036) verfolgen.
