
# Fail2BanSync – Zentrale IP-Synchronisation für Fail2Ban

Fail2BanSync ermöglicht die zentrale Erfassung, Synchronisierung und Verwaltung gebannter und erlaubter IP-Adressen über mehrere Server mit Fail2Ban.  
Das System besteht aus einer serverseitigen REST-API mit Token-Authentifizierung und beliebig vielen synchronisierenden Clients.

---

## Features

- Zentrale REST-API (Flask-basiert) mit Token-Authentifizierung
- Automatische Erfassung & Verteilung gebannter/erlaubter IPs
- SQLite-Datenbank (Upgrade auf PostgreSQL möglich)
- Konfigurierbare Logik für Bannzeiten, Block- und Freischaltzyklen
- Logging, Fehlerbehandlung und systemd-Integration
- Vollautomatische Installation (Server & Client)
- Sichere Kommunikation per Bearer-Token und Option für HTTPS

---

## Komponenten

### Server

- Bietet REST-API auf Port 5000 (Standard)
- Hält gebannte/erlaubte IPs in SQLite-Datenbank
- Authentifiziert Clients per Bearer-Token
- Kann als systemd-Service betrieben werden
- Beispielkonfig & automatische Token-Generierung für mehrere Clients

### Client

- Fragt gebannte IPs lokal ab (Fail2Ban)
- Sendet diese an den Server
- Holt zentrale Bann-/Erlaub-Listen ab und synchronisiert diese mit Fail2Ban lokal
- Läuft als Cronjob (1x pro Minute)

---

## Schnellstart

### Voraussetzungen

- Ubuntu Server (20.04 oder neuer empfohlen)
- Python 3.x
- (optional, aber empfohlen: root-Rechte für Installation)

---

### Server-Installation

1. Lege `server.py` und `install_server.sh` in ein Verzeichnis.
2. Führe das Installationsscript aus:
    ```bash
    chmod +x install_server.sh
    ./install_server.sh
    ```
3. Trage Tokens und Konfiguration nach Bedarf in `/opt/fail2bansync/serverconfig.txt` ein.

4. Prüfe den Status:
    ```bash
    sudo systemctl status fail2bansync-server
    ```
5. **Logs:**  
   `/opt/fail2bansync/server.log`

---

### Client-Installation

1. Lege `client.py` und `install_client.sh` auf dem Zielserver ab.
2. Führe das Script aus:
    ```bash
    chmod +x install_client.sh
    ./install_client.sh
    ```
3. Trage den für diesen Client bestimmten Token in `/opt/fail2bansync-client/clientconfig.txt` unter `[auth]` ein.

4. Prüfe Cronjob und Log:
    ```bash
    crontab -l
    tail -f /opt/fail2bansync-client/client_cron.log
    ```

---

## Sicherheit & Produktion

- **Empfohlen:**  
  Betreibe die Server-API immer hinter NGINX/Apache mit HTTPS.
- Verwahre die Tokens sicher und lösche nicht mehr benötigte Tokens aus der Konfig.
- Backup der Datenbank regelmäßig durchführen (`ip_management.db` bzw. PostgreSQL).

---

## Erweiterung & Anpassung

- Für hohe Last: Wechsel auf Gunicorn und PostgreSQL.
- Für eigene Authentifizierung/Rollen: Anpassung der Token-Logik im Server möglich.
- Einfaches Hinzufügen weiterer Clients durch neue Tokens.

---

## Fehlerbehebung

- **Server-Logs:** `/opt/fail2bansync/server.log`
- **Client-Logs:** `/opt/fail2bansync-client/client_cron.log`
- **Service-Status:** `sudo systemctl status fail2bansync-server`
- **Token falsch?** → HTTP 401 Fehler beim Client

---

## Upgrade

- Bei neuer Version einfach die jeweilige `server.py` bzw. `client.py` ersetzen und Service/Cronjob läuft weiter.
- Neue Tokens können jederzeit in der Server-Konfiguration ergänzt werden.

---

## Kontakt

Bei Fragen wenden Sie sich an den Entwickler.

---

**Stand: Mai 2025**  
**Fail2BanSync – Zentrale IP-Synchronisation für moderne Serverlandschaften**
