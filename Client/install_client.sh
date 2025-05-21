#!/bin/bash

# Zielverzeichnis für den Client
INSTALL_DIR="/opt/fail2bansync-client"
CLIENT_FILE="client.py"
CONFIG_FILE="clientconfig.txt"

echo "==== Fail2BanSync Client Installer ===="
echo "Installationsverzeichnis: $INSTALL_DIR"
echo

# 1. Python und pip installieren (falls nötig)
sudo apt update
sudo apt install -y python3 python3-pip

# 2. Zielordner anlegen
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER":"$USER" "$INSTALL_DIR"

# 3. client.py aus aktuellem Verzeichnis kopieren
if [ ! -f "$CLIENT_FILE" ]; then
    echo "Fehler: $CLIENT_FILE nicht im aktuellen Verzeichnis gefunden!"
    exit 1
fi
cp "$CLIENT_FILE" "$INSTALL_DIR/$CLIENT_FILE"
chown "$USER":"$USER" "$INSTALL_DIR/$CLIENT_FILE"

# 4. Beispiel-Konfig anlegen, falls nicht vorhanden
if [ ! -f "$INSTALL_DIR/$CONFIG_FILE" ]; then
    cat > "$INSTALL_DIR/$CONFIG_FILE" <<EOF
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
token = TOKEN_HIER_EINFUEGEN
EOF
    chown "$USER":"$USER" "$INSTALL_DIR/$CONFIG_FILE"
fi

# 5. Abhängigkeiten installieren
pip3 install --user requests

# 6. Cronjob anlegen
CRON_CMD="cd $INSTALL_DIR && /usr/bin/python3 $INSTALL_DIR/$CLIENT_FILE >> $INSTALL_DIR/client_cron.log 2>&1"
# Prüfe, ob der Cronjob bereits existiert
( crontab -l 2>/dev/null | grep -Fv "$CRON_CMD" ; echo "* * * * * $CRON_CMD" ) | crontab -

echo
echo "==== Fertig! ===="
echo "Client ist installiert in: $INSTALL_DIR"
echo "Bitte trage den passenden Token in [auth] token=... in $INSTALL_DIR/$CONFIG_FILE ein."
echo "Logs findest du in $INSTALL_DIR/client_cron.log"
echo
echo "Client läuft nun automatisch jede Minute als Cronjob."
echo "Cronjob prüfen: crontab -l"
