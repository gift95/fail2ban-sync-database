
# Fail2BanSync Server

Fail2BanSync ist eine zentrale API zur Verwaltung gebannter und erlaubter IPs mehrerer Fail2Ban-Instanzen.  
Mit Token-Authentifizierung, systemd-Integration und einfacher Konfiguration.

---

## Features

- Zentrale REST-API für gebannte und erlaubte IP-Adressen
- Bearer-Token-Authentifizierung
- SQLite-Datenbank
- Logging & Rotationsunterstützung
- Automatischer Start/Restart per systemd

---

## Installation (Ubuntu)

### 1. Dateien vorbereiten

Kopiere `server.py` und `install_server.sh` in ein beliebiges Verzeichnis auf deinem Server.

### 2. Installationsscript ausführen

```bash
chmod +x install_server.sh
./install_server.sh
```

Das Script erledigt:
- Systembenutzer & Ordner anlegen (`/opt/fail2bansync`)
- `server.py` dorthin kopieren
- 9 Tokens erzeugen und in `serverconfig.txt` eintragen
- Abhängigkeiten installieren (`flask`, `flask_httpauth`)
- Service als `fail2bansync-server` aktivieren & starten

### 3. Status prüfen

```bash
sudo systemctl status fail2bansync-server
```

---

## Konfiguration

- Hauptkonfig: `/opt/fail2bansync/serverconfig.txt`
- Beispiel:
    ```ini
    [DEFAULT]
    bantime = 10m
    bantime.increment = true
    bantime.factor = 3
    bantime.maxtime = 5w
    known_duration = 48h
    allowed_duration = 2m

    [api_tokens]
    client1 = <TOKEN1>
    client2 = <TOKEN2>
    ...
    ```
- Jeder Client benötigt einen eigenen Token.

---

## Systemd-Service-Steuerung

| Befehl                                      | Zweck             |
|----------------------------------------------|-------------------|
| `sudo systemctl start fail2bansync-server`   | Server starten    |
| `sudo systemctl stop fail2bansync-server`    | Server stoppen    |
| `sudo systemctl restart fail2bansync-server` | Server neustarten |
| `sudo systemctl status fail2bansync-server`  | Status anzeigen   |

Nach jeder Änderung an `server.py` oder `serverconfig.txt` bitte den Service neustarten.

---

## Logfiles

- Das Server-Log liegt in:  
  `/opt/fail2bansync/server.log`

---

## Client-Anbindung

Am Ende der Installation gibt das Script 9 `[auth]`-Blöcke für `clientconfig.txt` aus – einer für jeden Client (1–9).

**Für jeden Client:**
```ini
[auth]
token = <EINZELNER_TOKEN_AUS_SERVERCONFIG.TXT>
```

---

## Sicherheit & Betrieb

- **API ist nur mit gültigem Bearer-Token erreichbar**
- Kompromittierte Tokens in `[api_tokens]` löschen, dann Service neustarten
- Regelmäßige Sicherung der Datenbank (`ip_management.db`) empfohlen

---

## Troubleshooting

- Logs prüfen: `/opt/fail2bansync/server.log`
- Status anzeigen: `sudo systemctl status fail2bansync-server`

---

## FAQ

- **Weitere Clients hinzufügen?**  
  → Token generieren (z. B. mit `openssl rand -hex 32`), zu `[api_tokens]` hinzufügen, Service neustarten.
- **Logs zu groß?**  
  → Logrotation per `logrotate` oder manuell einrichten.

---

## Kontakt

Bei Fragen wenden Sie sich an den Entwickler.

---

**Stand: Mai 2025**  
**Fail2BanSync – zentrale, sichere IP-Synchronisation für Fail2Ban**
