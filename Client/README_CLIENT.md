
# Fail2BanSync Client

Der Fail2BanSync-Client synchronisiert gebannte und erlaubte IPs automatisiert mit einem zentralen Fail2BanSync-Server.  
Er eignet sich zur einfachen Integration in bestehende Systeme.

---

## Features

- Regelmäßige Synchronisation (1x pro Minute via Cronjob)
- Automatischer Versand gebannter IPs an den Server
- Abruf und Anwendung zentral erlaubter/geblockter IPs
- Konfigurierbar über einfache INI-Datei

---

## Installation (Ubuntu, ab 20.04 empfohlen)

### 1. Dateien kopieren

Lege die Dateien `client.py` und `install_client.sh` auf dem Zielsystem ab.

### 2. Installationsscript ausführen

```bash
chmod +x install_client.sh
./install_client.sh
```

Das Script erledigt:
- Anlage von `/opt/fail2bansync-client`
- Kopieren von `client.py` und Anlegen einer Beispiel-Konfiguration `clientconfig.txt`
- Installation der Python-Abhängigkeit `requests`
- Einrichten eines Cronjobs für automatische Ausführung jede Minute

### 3. Konfiguration

Öffne `/opt/fail2bansync-client/clientconfig.txt`  
und **trage den zu deinem Client passenden Token** (ausgegeben vom Server-Admin) in den `[auth]`-Block ein.

**Beispiel:**
```ini
[server]
host = 192.168.0.3
port = 5000
protocol = http

[logging]
log_file = client.log
max_bytes = 1048576
backup_count = 3

[fail2ban]
jail = sshd

[auth]
token = DEIN_TOKEN_AUS_SERVER
```

---

## Betrieb & Logs

- **Automatische Ausführung:**  
  Der Client läuft jede Minute als Cronjob und schreibt sein Log nach:  
  `/opt/fail2bansync-client/client_cron.log`

- **Cronjob prüfen:**  
  ```bash
  crontab -l
  ```

- **Client manuell starten (z.B. zum Testen):**
  ```bash
  cd /opt/fail2bansync-client
  python3 client.py
  ```

---

## Sicherheitshinweise

- Bewahre den Token in `[auth]` geheim!  
- Achte darauf, dass die Logdatei keine sensitiven Daten enthält.
- Ändere den Token sofort, falls du einen Leak vermutest (Admin muss auch Server-Konfig anpassen).

---

## Fehlerbehebung

- Prüfe die Logdatei `/opt/fail2bansync-client/client_cron.log` bei Problemen.
- Kontrolliere, ob die Systemzeit korrekt läuft (Cronjobs sind zeitgesteuert).
- Token korrekt eingetragen? Falsche oder fehlende Tokens führen zu HTTP 401 Fehlern.

---

## Upgrade

- Bei neuer Version einfach die neue `client.py` nach `/opt/fail2bansync-client/` kopieren.
- Es ist kein Neustart nötig – der Cronjob übernimmt alles.

---

## Kontakt

Bei Problemen oder Fragen, wende dich an den zuständigen Administrator oder das IT-Team.

---

**Stand: Mai 2025**  
**Fail2BanSync – einfacher, sicherer Fail2Ban-Zentralsync**
