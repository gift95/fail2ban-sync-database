
# Fail2BanSync – Zentrale IP-Synchronisation für Fail2Ban

Fail2Ban-Sync ermöglicht die zentrale Erfassung, Synchronisierung und Verwaltung gebannter und erlaubter IP-Adressen über mehrere Server mit Fail2Ban.  
Das System besteht aus einer serverseitigen REST-API mit Token-Authentifizierung und beliebig vielen synchronisierenden Clients.

---

## Features

- Zentrale REST-API (Flask-basiert) mit Token-Authentifizierung
- Automatische Erfassung & Verteilung gebannter/erlaubter IPs
- SQLite-Datenbank für IP-Management
- Konfigurierbare Logik für Bannzeiten, Block- und Freischaltzyklen
- Logging, Fehlerbehandlung und systemd-Integration
- Vollautomatische Installation (Server & Client)
- Authentifizierung per Bearer-Token

---

## Komponenten

### Server

- Bietet REST-API auf Port 5000 (Standard)
- Hält gebannte/erlaubte IPs in SQLite-Datenbank
- Authentifiziert Clients per Bearer-Token
- Wird als systemd-Service betrieben
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
- root-Rechte für Installation

---

### Server-Installation

1. Lege `server.py` und `install_server.sh` in ein Verzeichnis.
2. Führe das Installationsscript aus:
    ```bash
    chmod +x install_server.sh
    ./install_server.sh
    ```
3. Trage Tokens und Konfiguration nach Bedarf in `/opt/fail2bansync/serverconfig.ini` ein.

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
3. Trage die Server-IP und den Token in `/opt/fail2bansync-client/clientconfig.ini` ein.

4. Prüfe Cronjob und Log:
    ```bash
    crontab -l
    tail -f /opt/fail2bansync-client/client_cron.log
    tail -f /opt/fail2bansync-client/client.log
    ```

---

## Sicherheit & Produktion

- **Empfohlen:**  
  Betreibe die Server-API immer hinter NGINX/Apache mit HTTPS.
- Verwahre die Tokens sicher und lösche nicht mehr benötigte Tokens aus der Konfig.
- Backup der Datenbank regelmäßig durchführen (`ip_management.db`).

---

## Erweiterung & Anpassung

- Einfaches Hinzufügen weiterer Clients durch neue Tokens.

---

## Fehlerbehebung

- **Server-Logs:** `/opt/fail2bansync/server.log`
- **Client-Logs:** `/opt/fail2bansync-client/client.log`
- **Service-Status:** `sudo systemctl status fail2bansync-server`
- **Token falsch?** → HTTP 401 Fehler

---

## Upgrade

- Bei neuer Version entweder die Datei `server.py` ersetzen und das Service neu starten oder die Datei `client.py` ersetzen, wobei hier der Cronjob einfach weiter läuft.
- Neue Tokens können jederzeit in der Server-Konfiguration ergänzt werden.

---

## Kontakt

Bei Fragen wenden Sie sich an den Entwickler.

---

**Stand: Mai 2025**  
**Fail2BanSync – Zentrale IP-Synchronisation für moderne Serverlandschaften**
