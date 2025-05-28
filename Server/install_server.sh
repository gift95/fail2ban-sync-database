#!/bin/bash

# Anpassbare Variablen:
INSTALL_DIR="/opt/fail2bansync"
SERVER_USER="fail2bansync"
SERVER_FILE="server.py"
SERVICE_NAME="fail2bansync-server"

echo "==== Fail2BanSync Server Installer ===="
echo "Installationsverzeichnis: $INSTALL_DIR"
echo "Systembenutzer: $SERVER_USER"
echo

# 1. Python und pip installieren
sudo apt update
sudo apt install -y python3 python3-pip

# 2. Benutzer anlegen (falls nicht vorhanden)
if ! id "$SERVER_USER" &>/dev/null; then
    sudo useradd -r -s /bin/false "$SERVER_USER"
fi

# 3. Zielordner anlegen
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR"

# 4. server.py aus aktuellem Verzeichnis kopieren
if [ ! -f "$SERVER_FILE" ]; then
    echo "Fehler: $SERVER_FILE nicht im aktuellen Verzeichnis gefunden!"
    exit 1
fi
sudo cp "$SERVER_FILE" "$INSTALL_DIR/$SERVER_FILE"
sudo chown "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR/$SERVER_FILE"

# 5. Beispiel-Konfig anlegen
if [ ! -f "$INSTALL_DIR/serverconfig.ini" ]; then
    sudo tee "$INSTALL_DIR/serverconfig.ini" >/dev/null <<EOF
[DEFAULT]
bantime = 10m
bantime.increment = true
bantime.factor = 3
bantime.maxtime = 5w
known_duration = 48h
allowed_duration = 2m

[api_tokens]
client1 = $(openssl rand -hex 32)
client2 = $(openssl rand -hex 32)
client3 = $(openssl rand -hex 32)
client4 = $(openssl rand -hex 32)
client5 = $(openssl rand -hex 32)
client6 = $(openssl rand -hex 32)
client7 = $(openssl rand -hex 32)
client8 = $(openssl rand -hex 32)
client9 = $(openssl rand -hex 32)
EOF
    sudo chown "$SERVER_USER":"$SERVER_USER" "$INSTALL_DIR/serverconfig.ini"
fi

# 6. Abhängigkeiten installieren
sudo pip3 install flask flask_httpauth

# 7. Systemd-Service anlegen
sudo tee /etc/systemd/system/${SERVICE_NAME}.service >/dev/null <<EOF
[Unit]
Description=Fail2BanSync API Server
After=network.target

[Service]
Type=simple
User=$SERVER_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/$SERVER_FILE
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 8. Systemd-Service aktivieren und starten
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo
echo "==== Fertig! ===="
echo "Der Fail2BanSync-Server läuft nun als Systemd-Service: $SERVICE_NAME"
echo "Prüfe den Status mit: sudo systemctl status $SERVICE_NAME"
echo
echo "Die Konfigdatei findest du unter: $INSTALL_DIR/serverconfig.ini"
echo
echo "Falls du Änderungen an server.py vornimmst, kopiere sie erneut ins Zielverzeichnis und starte den Service neu:"
echo "sudo cp server.py $INSTALL_DIR/server.py && sudo systemctl restart $SERVICE_NAME"
