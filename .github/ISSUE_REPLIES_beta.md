# Antworten für offene Issues (Beta 0.9.0b1)

Kopiere den jeweiligen Abschnitt als Kommentar in das passende Issue.

---

## Issue #7 – Error fetching fritzbox_vpn data / Cannot connect to host 192.168.178.1:443

**Link:** https://github.com/rosch100/fritzbox-vpn/issues/7

### Kommentar (Englisch):

A fix for this is included in **Beta 0.9.0b1**. The integration now:

- **Connection errors to port 443:** If the Fritz!Box is not reachable via HTTPS, it automatically falls back to HTTP (with a one-time warning in the logs).
- **HTML instead of JSON:** If the Fritz!Box returns a login page (e.g. after session expiry) instead of JSON, the integration treats it as an invalid session, renews the session, and retries once.

You can test the beta in HACS:

1. Open the **Fritz!Box VPN** integration card in HACS.
2. Click the **⋮** menu → **Redownload**.
3. Enable **Show beta versions**, wait for the list to refresh.
4. Select **0.9.0b1** and confirm.
5. Restart Home Assistant.

**Beta release:** https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.9.0b1

If you still see errors after updating, please share the latest log lines (and whether the Fritz!Box is reachable via HTTP on port 80 in your network).

---

### Kommentar (Deutsch):

Dafür ist in **Beta 0.9.0b1** ein Fix enthalten. Die Integration macht jetzt:

- **Verbindungsfehler zu Port 443:** Wenn die Fritz!Box per HTTPS nicht erreichbar ist, wird automatisch auf HTTP umgestellt (mit einmaliger Warnung im Log).
- **HTML statt JSON:** Wenn die Fritz!Box eine Login-Seite (z. B. nach abgelaufener Sitzung) statt JSON zurückgibt, wertet die Integration das als ungültige Sitzung, erneuert die Sitzung und versucht es einmal erneut.

Zum Testen der Beta in HACS:

1. In HACS die Karte der Integration **Fritz!Box VPN** öffnen.
2. **⋮** Menü → **Erneut herunterladen**.
3. **Beta-Versionen anzeigen** aktivieren, kurz warten.
4. Version **0.9.0b1** wählen und bestätigen.
5. Home Assistant neu starten.

**Beta-Release:** https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.9.0b1

Wenn danach noch Fehler auftreten, bitte die neuesten Log-Zeilen schicken (und ob die Fritz!Box bei euch im Netz per HTTP auf Port 80 erreichbar ist).

---

## Issue #4 – New login for each poll

**Link:** https://github.com/rosch100/fritzbox-vpn/issues/4

### Kommentar (Englisch):

Session caching is already in place (one login per integration load, not per poll). In **Beta 0.9.0b1** the error handling was improved: when the Fritz!Box sometimes returns HTML instead of JSON (e.g. session expired), the integration now renews the session and retries once instead of failing repeatedly. That can reduce unnecessary re-logins in those edge cases.

If you still see a new login on every poll, please try the beta and share your update interval and a short description of what you see (e.g. router notification on every poll, or log messages). Then we can narrow it down.

**Beta release:** https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.9.0b1

How to install the beta in HACS: open the integration card → ⋮ → Redownload → enable **Show beta versions** → select **0.9.0b1** → restart Home Assistant.

---

### Kommentar (Deutsch):

Session-Caching ist bereits aktiv (ein Login pro Integrations-Load, nicht pro Abfrage). In **Beta 0.9.0b1** wurde die Fehlerbehandlung verbessert: Wenn die Fritz!Box gelegentlich HTML statt JSON zurückgibt (z. B. abgelaufene Sitzung), erneuert die Integration die Sitzung und versucht es einmal erneut statt dauerhaft zu scheitern. Das kann in solchen Fällen unnötige Neu-Logins reduzieren.

Wenn bei dir weiterhin bei jeder Abfrage ein neuer Login passiert, bitte die Beta testen und dein Update-Intervall sowie eine kurze Beschreibung schicken (z. B. Router-Benachrichtigung bei jeder Abfrage oder Log-Meldungen). Dann können wir gezielt nachsehen.

**Beta-Release:** https://github.com/rosch100/fritzbox-vpn/releases/tag/v0.9.0b1

Beta in HACS installieren: Integrations-Karte öffnen → ⋮ → Erneut herunterladen → **Beta-Versionen anzeigen** aktivieren → **0.9.0b1** wählen → Home Assistant neu starten.
