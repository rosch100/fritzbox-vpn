# Fritz!Box Tools vs. Fritzbox-VPN: SSDP/Discovery und mögliche Lösungen

Vergleich der **offiziellen** [FRITZ!Box Tools](https://github.com/home-assistant/core/tree/dev/homeassistant/components/fritz) (Core) mit **Fritzbox-VPN** (dieses Repo) für SSDP, unique_id und Repeater – als Grundlage für Fix-Vorschläge zu #165036 / #163330.

---

## 1. SSDP / Discovery

| Aspekt | Fritz!Box Tools (Core) | Fritzbox-VPN |
|--------|------------------------|--------------|
| **Manifest** | `"ssdp": [{"st": "urn:schemas-upnp-org:device:fritzbox:1"}]` | Kein `ssdp`-Eintrag → nutzt Default-Discovery |
| **Repeater** | Werden nicht gefiltert; Repeater können gleichen ST melden und erscheinen in der Discovery | Explizit ausgeschlossen: `_is_fritzbox_device()` liefert bei Repeater-Indikatoren `False` → `async_abort(reason="not_fritzbox")` |
| **unique_id (SSDP)** | Aus `discovery_info.upnp.get(ATTR_UPNP_UDN)` (UDN aus Device-Beschreibung), Präfix `uuid:` wird entfernt. **Falls kein UDN:** es wird **kein** `async_set_unique_id()` aufgerufen | Fallback-Kette: zuerst `host`, falls `ssdp_usn` mit `uuid:` vorhanden → `unique_id = usn.replace("uuid:", "")`; **immer** `async_set_unique_id(unique_id)` |
| **Abgleich bestehender Einträge** | 1) `async_set_unique_id(uuid)` + `_abort_if_unique_id_configured({CONF_HOST})` 2) `async_check_configured_entry()` vergleicht **aufgelösten Host** (IP); bei Treffer: Abort + optional `async_update_entry(unique_id=uuid)` **nur wenn** `not entry.unique_id` | 1) `async_set_unique_id(unique_id)` + `_abort_if_unique_id_configured()` 2) Kein zusätzlicher Abgleich per Host (weil nur eine Box sinnvoll; Repeater werden nicht angeboten) |

---

## 2. Warum Repeater bei Fritz!Box Tools „immer wieder neu“ erscheinen können

- **UDN fehlt in der Discovery:** Wenn bei Repeatern `discovery_info.upnp` keinen UDN liefert, setzt der Core-Flow **keinen** unique_id. Dann greift nur der Abgleich per Host (`async_check_configured_entry()`). Wenn der Host sich unterscheidet (z. B. IP vs. Hostname, oder anderer Responder), gibt es keinen Treffer → Flow läuft weiter → „Neues Gerät“.
- **Bestehender Eintrag hat unique_id = Host:** Einträge, die früher per User-Flow mit `unique_id=host` angelegt wurden, werden bei Discovery mit UDN nur dann aktualisiert, wenn `not entry.unique_id`. Alte Einträge mit `unique_id=host` bekommen also kein Update auf UDN; der neue Flow hat UDN als unique_id → kein Abort über `_abort_if_unique_id_configured`; ob `async_check_configured_entry()` greift, hängt von der Host-Übereinstimmung ab.
- **Kein Repeater-Filter:** Jedes Gerät, das den Fritzbox-ST meldet (inkl. Repeater), startet einen Flow. Es gibt keine Möglichkeit, Repeater gezielt zu ignorieren (wie in Fritzbox-VPN).

---

## 3. Übertragbare Ideen aus Fritzbox-VPN

### 3.1 Immer einen stabilen unique_id setzen (SSDP)

- **Bei Fritz!Box Tools:** Wenn `uuid` aus UDN fehlt, trotzdem einen unique_id setzen, z. B. `unique_id = host` oder aufgelöste IP, und `async_set_unique_id(unique_id)` aufrufen. So bleibt der Abgleich über unique_id auch bei Repeatern ohne UDN konsistent.
- **Referenz Fritzbox-VPN:** `config_flow.py` setzt immer einen unique_id (Host oder USN-UUID), nie „ohne unique_id“ in den Flow.

### 3.2 Host-basierten Abgleich robuster machen + unique_id nachziehen

- **Bei Fritz!Box Tools:** Wenn `async_check_configured_entry()` einen Eintrag mit gleichem Host findet, immer mit `already_configured` abbrechen und – sofern ein UDN aus der Discovery vorliegt – den bestehenden Eintrag auf diesen UDN als unique_id setzen:  
  `if uuid: self.hass.config_entries.async_update_entry(entry, unique_id=uuid)`  
  unabhängig von `entry.unique_id`. So werden auch ältere Einträge mit `unique_id=host` auf UDN umgestellt und spätere Discoveries führen zu Abort.
- **Fritzbox-VPN:** Macht keinen Host-Abgleich (nur eine Box, Repeater ausgeschlossen); die Idee „bestehenden Eintrag bei Treffer aktualisieren“ ist übertragbar.

### 3.3 Optional: Repeater in der Discovery erkennen

- **Bei Fritz!Box Tools:** Wenn gewünscht, Repeater in `async_step_ssdp` erkennen (z. B. über Friendly Name / Model wie in Fritzbox-VPN `REPEATER_INDICATORS`: `"repeater"`, `"wlan repeater"`, `"fritz!wlan repeater"`, `"fritz!wlanrepeater"`) und:
  - entweder mit einem eigenen Grund abbrechen (z. B. `repeater_not_supported` oder `ignore_repeater`), sodass sie nicht als „Neues Gerät“ angeboten werden, **oder**
  - Repeater weiter zulassen, aber mit derselben Logik wie oben (stabiler unique_id + Host-Abgleich + unique_id-Update), damit sie nicht bei jedem Neustart neu erscheinen.
- **Fritzbox-VPN:** `_is_fritzbox_device()` nutzt `FRITZBOX_SSDP_INDICATORS` und `REPEATER_INDICATORS` aus `const.py`; bei Repeater wird abgebrochen. Diese Konstanten/Logik könnten im Core als Inspiration dienen.

---

## 4. Konkrete Änderungsvorschläge für home-assistant/core (fritz)

1. **In `config_flow.py` `async_step_ssdp`:**
   - Wenn `discovery_info.upnp.get(ATTR_UPNP_UDN)` fehlt, einen Fallback-unique_id setzen (z. B. `host` oder aufgelöste IP) und trotzdem `async_set_unique_id(...)` aufrufen.
   - Nach `async_check_configured_entry()`: bei gefundenem Eintrag, wenn `uuid` aus Discovery vorhanden ist, immer `async_update_entry(entry, unique_id=uuid)` ausführen (nicht nur wenn `not entry.unique_id`), dann mit `already_configured` abbrechen.

2. **Optional – Repeater-Erkennung:**
   - In einem Hilfsfunktion prüfen, ob die Discovery ein Repeater ist (z. B. über Friendly Name / Model / vorhandene REPEATER_INDICATORS).
   - Entweder Repeater-Discovery mit eigenem Abort-Grund versehen oder (bei Beibehaltung der Repeater-Unterstützung) dieselbe unique_id- und Host-Logik wie für die Box anwenden.

3. **Zusammenhang mit #163330 (unique IDs):**
   - Die fehlende oder inkonsistente Vergabe von unique_id bei Entities („Platform fritz does not generate unique IDs“) kann dazu führen, dass Config-Entries und Entities auseinanderlaufen. Ein stabiler unique_id im Config-Flow (wie oben) verbessert die Zuordnung Config-Entry ↔ Gerät und kann die Probleme aus #165036 und #163330 gemeinsam entschärfen.

---

## 5. Kurzfassung

- **Fritzbox-VPN** vermeidet Repeater-Discovery durch explizite Filterung und setzt im SSDP-Flow immer einen unique_id (Host oder UUID).
- **Fritz!Box Tools** lässt Repeater zu, setzt bei fehlendem UDN aber keinen unique_id und aktualisiert bestehende Einträge nur bei fehlendem `entry.unique_id`.
- **Vorschlag für den Core:** (1) Immer einen Fallback-unique_id setzen, (2) bei Host-Match immer UDN in den Eintrag schreiben und (3) optional Repeater erkennen und entweder ignorieren oder mit derselben Logik stabil behandeln. Das kann als Kommentar/Lösungsvorschlag in #165036 und ggf. #163330 verlinkt werden.
