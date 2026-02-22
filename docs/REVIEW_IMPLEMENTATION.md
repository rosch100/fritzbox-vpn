# Review: Vollständigkeit, Best Practice, SOLID, SSOT, CRAP

Stand nach sechster Prüfung: SSOT für SSDP-Indikatoren (FRITZBOX_SSDP_INDICATORS), Fritz-Integrations-Domains (FRITZ_INTEGRATION_DOMAINS), sensible Config-Keys und Log-Maskierung (SENSITIVE_CONFIG_KEYS, mask_config_for_log); NAME_FRITZBOX in allen Coordinator-Fehlermeldungen; CRAP durch zentrale Log-Maskierung reduziert.

---

## 1. Vollständigkeit

| Aspekt | Status | Anmerkung |
|--------|--------|-----------|
| Config Flow | ✅ | User-, SSDP-, Confirm-Schritte; Repeater-Filter (SSDP + bestehende Integration); Options Flow |
| Setup/Unload | ✅ | `async_setup_entry`, `async_unload_entry`, `async_reload_entry`; erste Aktualisierung; Geräteregistrierung |
| Coordinator | ✅ | Session, VPN-Abfrage, Toggle, Auth-Fehler-Erkennung, Benachrichtigung |
| Entitäten | ✅ | Switch, Binary Sensor, Sensor (Plattformen vorhanden) |
| Konstanten | ✅ | `const.py` mit Domain, Config-Keys, API-Pfaden, Status, Repeater- und Fehler-Indikatoren |
| Fehlerbehandlung | ✅ | CannotConnect/InvalidAuth; Validierung mit klarem Mapping; Auth-Notification mit Entfernen beim Reload |
| Repeater | ✅ | SSDP: Ablehnung über `_is_fritzbox_device`; bestehende Integration: nur Router-Einträge, bei nur Repeatern wird Domain übersprungen; `entry.title` null-sicher |

**Empfehlung:** Keine offensichtlichen Lücken. Optional: Integrationstests für Config Flow (User/SSDP/Options) und Coordinator.

---

## 2. Best Practice

| Aspekt | Status | Anmerkung |
|--------|--------|-----------|
| HA-Patterns | ✅ | Config Entry, DataUpdateCoordinator, Forward Entry Setups, Device Registry |
| Logging | ✅ | Debug/Info/Warning/Exception sinnvoll; Passwörter nicht geloggt; Fehlerschlüssel in Logs über ERROR_KEY_* (SSOT) |
| Async | ✅ | Durchgängig async/await; keine blockierenden Aufrufe |
| SID-Cache | ✅ | Session-Wiederverwendung, invalide SID → ein Retry, dann Fehler |
| Timeouts/Backoff | ✅ | `RETRY_AFTER_SECONDS` bei UpdateFailed; `VERIFICATION_DELAY` nach Toggle |
| Übersetzungen | ✅ | `en.json` / `de.json` für Fehlermeldungen |

**Empfehlung:** Beibehalten. Optional: Typ-Hints bei allen öffentlichen Funktionen prüfen (größtenteils bereits vorhanden).

---

## 3. SOLID

| Prinzip | Status | Anmerkung |
|---------|--------|-----------|
| **S**ingle Responsibility | ⚠️ | `ConfigFlow` und v. a. `_get_existing_fritz_config()` übernehmen viel: Domain-Durchlauf, Repeater-Filter, Credential-Extraktion, mehrere Integrationsformate. Eine Entlastung wäre: Hilfsmodul (z. B. `fritz_config_source.py`) mit reiner Funktion „bestehende Fritz-Konfiguration abrufen“. |
| **O**pen/Closed | ✅ | Erweiterung über Optionen/Plattformen ohne Änderung am Kern; neue Fehler-Indikatoren in `const.py` erweiterbar. |
| **L**iskov | ✅ | Subclasses von HA-Basisklassen (ConfigFlow, OptionsFlow, DataUpdateCoordinator) verhalten sich konsistent. |
| **I**nterface Segregation | ✅ | Kleine, klare Schnittstellen (validate_input, _is_fritzbox_device, _validation_error_to_error_key). |
| **D**ependency Inversion | ✅ | Coordinator nutzt Session-Interface; Config Flow hängt von `const` und Coordinator ab, nicht von konkreten Implementierungsdetails. |

**Empfehlung:** Optionales Refactoring: `_get_existing_fritz_config` in eine separate Funktion/Klasse auslagern, um SRP zu stärken und Config Flow lesbarer zu machen.

---

## 4. SSOT (Single Source of Truth)

| Thema | Vorher | Nachher |
|-------|--------|---------|
| Repeater-Erkennung | Zwei Listen (SSDP + „repeater“ im Titel) | **Eine** Definition: `REPEATER_INDICATORS` in `const.py`; Nutzung in `_is_fritzbox_device` und Router-Filter in `_get_existing_fritz_config`. |
| Fehlermapping (Auth/Connect) | Mehrfach „Login failed“/„Invalid SID“/… in config_flow | **Eine** Quelle: `ERROR_INDICATOR_AUTH`, `ERROR_INDICATOR_CONNECT` in `const.py`; `_validation_error_to_error_key()`; alle Flows nutzen diese. |
| Auth-Indikatoren (Coordinator) | Eigene Liste in `_is_auth_error` | **Eine** Quelle: `AUTH_INDICATORS` in `const.py`. |
| Config-Keys (host/username/password) | Doppelt: `const.py` + homeassistant.const | **Nur** `homeassistant.const` für host/username/password; `const.py` nur noch `CONF_UPDATE_INTERVAL` (domain-spezifisch). Docstring in const erklärt SSOT. |
| Default-Host | Literal `"192.168.178.1"` mehrfach in config_flow | **Eine** Quelle: `DEFAULT_HOST` in `const.py`; überall verwendet. |
| Auth-Fehler-Notification-ID | `f"{DOMAIN}_auth_error_{host}"` in __init__ (2×) und coordinator (2×) | **Eine** Funktion: `auth_error_notification_id(host)` in `const.py`; __init__ und Coordinator nutzen sie. |
| Geräte-Labels (AVM, WireGuard VPN, Unknown) | Literale in switch/sensor/binary_sensor und coordinator | **Eine** Quelle: `MANUFACTURER_AVM`, `MODEL_WIREGUARD_VPN`, `DEFAULT_NAME_UNKNOWN` in `const.py`; alle Plattformen + Coordinator importieren sie. |
| Parent-Device (Fritz!Box) | Literale `"Fritz!Box"` in __init__ (name/model) | **Eine** Quelle: `NAME_FRITZBOX`, `MODEL_FRITZBOX` in `const.py`; __init__ nutzt sie. |
| Host-Fallback (intern) | Literal `"unknown"` in __init__, coordinator, auth_error_notification_id | **Eine** Quelle: `HOST_FALLBACK_UNKNOWN` in `const.py`; überall verwendet. |
| Config-Flow-Error-Keys | Literale `"unknown"`, `"cannot_connect"`, `"invalid_auth"`, `"config_entry_not_found"` in config_flow | **Eine** Quelle: `ERROR_KEY_*` in `const.py`; `_validation_error_to_error_key()` und alle Fehlerzuweisungen nutzen sie. |
| Entry-Titel (Integration) | Literal `"Fritz!Box VPN"` in config_flow | **Eine** Quelle: `INTEGRATION_TITLE` in `const.py`; Config Flow und Coordinator (Notification-Hinweis) nutzen sie. |
| Notification-Titel (Auth-Fehler) | Literal im Coordinator | **Eine** Quelle: `NOTIFICATION_TITLE_AUTH_ERROR` in `const.py`; Coordinator nutzt sie. |
| configuration_url (Device) | Host-Fallback `DEFAULT_NAME_UNKNOWN` → `"https://Unknown"` | **Korrektur:** `host_for_url` verwendet `HOST_FALLBACK_UNKNOWN`, damit URL-Platzhalter konsistent `"unknown"` ist; Log-Anzeige weiterhin `DEFAULT_NAME_UNKNOWN` wo sinnvoll. |
| Log-Meldungen (Error-Keys) | Literale `"cannot_connect"` / `"invalid_auth"` in _LOGGER.warning | **Eine** Quelle: Log-Ausgaben nutzen `ERROR_KEY_CANNOT_CONNECT` / `ERROR_KEY_INVALID_AUTH` als Platzhalter, damit sie mit dem tatsächlichen Fehlerschlüssel übereinstimmen. |
| ConfigEntryNotReady-Text | Literal „FritzBox“ in __init__ | **Eine** Quelle: `NAME_FRITZBOX` in der Fehlermeldung. |
| Link „Zur Konfiguration“ (Notification) | Literal `"/config/integrations"` im Coordinator | **Eine** Quelle: `CONFIG_URL_INTEGRATIONS` in `const.py`; Coordinator nutzt sie. |
| SSDP FritzBox-Erkennung | Lokale Liste `fritzbox_indicators` in _is_fritzbox_device | **Eine** Quelle: `FRITZBOX_SSDP_INDICATORS` in `const.py`; _is_fritzbox_device nutzt sie. |
| Fritz-Integrations-Domains | Literal-Liste `possible_domains` in _get_existing_fritz_config | **Eine** Quelle: `FRITZ_INTEGRATION_DOMAINS` in `const.py`. |
| Sensible Config-Keys (Log-Maskierung) | Literale `['password', 'pass']` mehrfach in config_flow | **Eine** Quelle: `SENSITIVE_CONFIG_KEYS` und `mask_config_for_log()` in `const.py`; alle Debug-Ausgaben nutzen sie. |
| Coordinator-Fehlermeldungen | Literale „FritzBox“/„Fritz!Box“ in Exception- und Log-Texten | **Eine** Quelle: `NAME_FRITZBOX` in allen nutzer-/log-sichtbaren Meldungen (Invalid SID, No response, HTTPS-Hinweis). |

**Weitere SSOT-Quellen:** `const.py` für Domain, API-Pfade, Status-Werte, Update-Intervalle – konsequent genutzt.

---

## 5. CRAP (Code Reuse, Avoid Duplication)

| Thema | Maßnahme |
|-------|----------|
| Fehlermapping in Config Flow | Drei Blöcke durch **eine** Funktion `_validation_error_to_error_key(error_msg)` ersetzt. |
| Repeater-Strings | **Ein** Tupel `REPEATER_INDICATORS` in `const.py` (SSDP + Entry-Titel). |
| Auth-Strings | **Ein** Tupel `AUTH_INDICATORS` in `const.py` im Coordinator. |
| Notification-ID für Auth-Fehler | **Eine** Funktion `auth_error_notification_id(host)` in `const.py`; __init__.py (2×) und coordinator (2×) nutzen sie. |
| Default-Host | **Eine** Konstante `DEFAULT_HOST`; alle Stellen in config_flow nutzen sie. |
| Geräte-Hersteller/Modell/Unknown | **Eine** Quelle `MANUFACTURER_AVM`, `MODEL_WIREGUARD_VPN`, `DEFAULT_NAME_UNKNOWN`; switch, sensor, binary_sensor, coordinator nutzen sie. |
| Error-Keys (Config Flow) | **Eine** Quelle `ERROR_KEY_UNKNOWN`, `ERROR_KEY_CANNOT_CONNECT`, `ERROR_KEY_INVALID_AUTH`, `ERROR_KEY_CONFIG_ENTRY_NOT_FOUND`; keine String-Literale mehr für Fehlerschlüssel. |
| Host-Fallback / Parent-Device | **Eine** Quelle `HOST_FALLBACK_UNKNOWN`, `NAME_FRITZBOX`, `MODEL_FRITZBOX`; __init__ und coordinator nutzen sie. |
| Entry-Titel / Notification-Titel | **Eine** Quelle `INTEGRATION_TITLE`, `NOTIFICATION_TITLE_AUTH_ERROR`; config_flow und coordinator nutzen sie; Auth-Message nutzt `NAME_FRITZBOX`. |
| _is_auth_error | Redundante isinstance-Checks (ValueError/ConnectionError), obwohl AUTH_INDICATORS bereits „invalid sid“/„login failed“ enthält | **Eine** Prüfung: `any(ind in str(error).lower() for ind in AUTH_INDICATORS)`. |
| Schema-Bau (Host/User/Pass) | Weiterhin mehrfach ähnliche Schemata; Kontext (Defaults, Optionen) unterschiedlich – akzeptabel. |
| Log-Maskierung (Config/Options) | Dict-Comprehension `{k: v if k not in ['password','pass'] else '***'}` mehrfach in config_flow | **Eine** Funktion: `mask_config_for_log(data)` in `const.py`; alle Debug-Logs nutzen sie. |

**Ergebnis:** Weniger Duplikation bei Fehlermapping, Repeater/Auth, Notification-ID, Default-Host, Geräte-Labels, Error-Keys, Host-Fallback, Entry-/Notification-Titel, Log-Maskierung; _is_auth_error ohne Redundanz; CRAP verbessert.

---

## 6. Kurzfassung

- **Vollständigkeit:** Gut; alle Flows, Setup, Coordinator und Repeater-Logik abgedeckt.
- **Best Practice:** HA-konform; Logging, Async, Fehlerbehandlung und i18n stimmig.
- **SOLID:** Überwiegend gut; einziger Punkt: Config Flow / `_get_existing_fritz_config` könnte für bessere SRP ausgelagert werden.
- **SSOT:** Repeater-, Fehler- und Auth-Indikatoren, Config-Keys (nur homeassistant.const), Default-Host, Host-Fallback, Error-Keys, Parent-Device-Name/Modell, Notification-ID, Entry-Titel, Notification-Titel, configuration_url-Host, Log-Error-Keys, ConfigEntryNotReady-Text, Konfig-URL, **SSDP-Indikatoren (FRITZBOX_SSDP_INDICATORS), Fritz-Domains (FRITZ_INTEGRATION_DOMAINS), sensible Keys und Log-Maskierung (SENSITIVE_CONFIG_KEYS, mask_config_for_log)**, sowie NAME_FRITZBOX in Coordinator-Exception-/Log-Texten sind in `const.py` bzw. zentralen Hilfsfunktionen gebündelt.
- **CRAP:** Fehlermapping, Repeater/Auth, Error-Keys, Host-Fallback, Geräte-Labels, Entry-/Notification-Titel, Konfig-URL und **Log-Maskierung** entdoppelt; `_is_auth_error` ohne Redundanz; weniger Duplikation, bessere Wartbarkeit.

Die vorgenommenen Änderungen (u. a. Konstanten, `_validation_error_to_error_key`, ERROR_KEY_*, HOST_FALLBACK_UNKNOWN, NAME_FRITZBOX, MODEL_FRITZBOX, INTEGRATION_TITLE, NOTIFICATION_TITLE_AUTH_ERROR, CONFIG_URL_INTEGRATIONS, FRITZBOX_SSDP_INDICATORS, FRITZ_INTEGRATION_DOMAINS, SENSITIVE_CONFIG_KEYS, mask_config_for_log, NAME_FRITZBOX in Coordinator-Meldungen, Log mit ERROR_KEY_*, ConfigEntryNotReady mit NAME_FRITZBOX, host_for_url, vereinfachtes _is_auth_error, CONF_HOST/CONF_PASSWORD, Repeater-/Auth-SSOT) verbessern Wartbarkeit und Konsistenz ohne Verhalten zu ändern.
