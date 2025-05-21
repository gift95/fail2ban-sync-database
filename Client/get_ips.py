import requests
import configparser
import os

CONFIG_FILE = "clientconfig.txt"
DEFAULT_SERVER = {
    "host": "127.0.0.1",
    "port": "5000",
    "protocol": "http"
}

def load_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    server = DEFAULT_SERVER.copy()
    token = ""
    if config.has_option("server", "host"):
        server["host"] = config.get("server", "host")
    if config.has_option("server", "port"):
        server["port"] = config.get("server", "port")
    if config.has_option("server", "protocol"):
        server["protocol"] = config.get("server", "protocol")
    if config.has_option("auth", "token"):
        token = config.get("auth", "token")
    return server, token

def get_ips(url, token, label):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"Fehler beim Abrufen von {label}: {resp.status_code} - {resp.text}")
            return []
    except Exception as e:
        print(f"Fehler beim Verbinden zu {label}: {e}")
        return []

def main():
    server, token = load_config()
    if not token:
        print("Kein Token gefunden! Trage einen gültigen Token in [auth] token=... in clientconfig.txt ein.")
        return

    base_url = f"{server['protocol']}://{server['host']}:{server['port']}"
    endpoints = [
        ("/get_ips", "BLOCKED"),
        ("/get_allowed_ips", "ALLOWED"),
        ("/get_known_ips", "KNOWN"),
    ]

    for endpoint, label in endpoints:
        url = base_url + endpoint
        data = get_ips(url, token, label)
        print(f"\n===== {label} IPs ({len(data)}) =====")
        if data:
            for ip in data:
                print(f"ID: {ip['id']} | IP: {ip['ip_address']} | Status: {ip['status']} | Bis: {ip['blocked_until']} | Allowed seit: {ip['allowed_since']} | Block-Count: {ip['block_count']}")
        else:
            print("Keine Daten erhalten oder Fehler.")

if __name__ == "__main__":
    main()