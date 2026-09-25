#!/usr/bin/python3

###################################################################################################
#################################             V1.2               ##################################
#############################  SofarCloud-Daten per MQTT versenden  ###############################
#################################   (C) 2025 Daniel Luginbühl    ##################################
###################################################################################################

####################################### WICHTIGE INFOS ############################################
################     Im Smarthome System ist ein MQTT Broker zu installieren      #################
################ ---------------------------------------------------------------- #################
################          Falls Raspberry: Alles als User PI ausführen!           #################
################ ---------------------------------------------------------------- #################
################ sofarcloud.py Script auf Rechte 754 setzen mit:                  #################
################ chmod 754 sofarcloud.py                                          #################
################ Dieses Script per Cronjob alle 5 Minuten ausführen:              #################
################ crontab -e                                                       #################
################ */5 * * * * /home/pi/sofarcloud.py       # Pfad ggf anpassen!    #################
################ ---------------------------------------------------------------- #################
################ Vorgängig zu installieren (auf Host, wo dieses Script läuft):    #################
################    pip3 install requests                                         #################
################    pip3 install paho-mqtt                                        #################
################    pip3 install typing-extensions                                #################
###################################################################################################

""" Deine Eintragungen ab hier:"""

###################################################################################################
################################### Hier Einträge anpassen! #######################################

USERNAME = "uuuuu@gmail.com"    # Deine Email Adresse bei SofarCloud
PASSWORD = "ppppppppp"          # Dein Passwort bei SofarCloud

BROKER_ADDRESS = "192.168.1.50" # MQTT Broker IP (da wo der MQTT Broker läuft)
MQTT_USER = "xxxxxx"            # MQTT User      (im MQTT Broker definiert)
MQTT_PASS = "yyyyyy"            # MQTT Passwort  (im MQTT Broker definiert)
MQTT_PORT = 1883                # MQTT Port      (default: 1883)

MQTT_ACTIVE = True              # Auf False, wenn nichts MQTT published werden soll

CREATE_JSON = True              # True = erstelle devData.json und forecast.json

JSON_PATH = ""                  # Pfad für die Json Datei.
                                # Standardpfad ist ein Unterverzeichnis "data" beim Script.
                                # Sonst zBsp.: JSON_PATH = "/home/pi/"

DEBUG = False                   # True = Debug Infos auf die Konsole.

###################################################################################################
###################################################################################################

#--------------------------------- Ab hier nichts mehr verändern! --------------------------------#

import time
import datetime
import json
import random
import requests
import hashlib
import paho.mqtt.client as mqtt
import urllib3
import base64
import os
from pathlib import Path

if CREATE_JSON:
    # Speicherort des aktuellen Skripts ermitteln
    script_dir = Path(__file__).resolve().parent

    # Falls JSON_PATH leer ist, nutze "Skript-Ordner + data/"
    if not JSON_PATH or JSON_PATH.strip() == "":
        target_dir = script_dir / "data"
    else:
        target_dir = Path(JSON_PATH)

    if DEBUG:
        print(f"Gewählter Zielpfad: {target_dir}")

    # Prüfen, ob der Pfad existiert. Falls nicht, versuchen zu erstellen.
    if not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            if DEBUG:
                print(f"Verzeichnis erfolgreich erstellt: {target_dir}")
            
        except PermissionError:
            print(f"Fehler: Keine Berechtigung (Permission Denied), um das Verzeichnis '{target_dir}' zu erstellen.")
            CREATE_JSON = False
            if DEBUG:
                exit(1)
            
        except FileNotFoundError:
            print(f"Fehler: Ein Teil des Pfades '{target_dir}' ist ungültig oder nicht erreichbar.")
            CREATE_JSON = False
            if DEBUG:
                exit(1)
            
        except Exception as e:
            print(f"Fehler: Verzeichnis '{target_dir}' konnte nicht erstellt werden. Grund: {e}")
            CREATE_JSON = False
            if DEBUG:
                exit(1)
    else:
        if DEBUG:
            print(f"Verzeichnis existiert bereits: {target_dir}")

    if CREATE_JSON:
        JSON_PATH = os.path.join(str(target_dir), "")

# Zufällige Zeitverzögerung 0 bis 117 Sekunden. Wichtig, damit der SofarCloud Server
# nicht immer zur gleichen Zeit bombardiert wird!!
verzoegerung = random.randint(0,117)
if DEBUG:
    verzoegerung = 0
print("Datenabfrage startet in", verzoegerung, "Sekunden")
time.sleep(verzoegerung)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://global.sofarcloud.com/api/"
appversion = "2.3.6"

def get_local_timezone():
    try:
        # Python 3.9+
        return datetime.datetime.now().astimezone().tzinfo.key
    except AttributeError:
        # Fallback für ältere Python-Versionen
        tz_abbr = time.tzname[0]  # z. B. 'CET', 'CEST', 'UTC'
        # Mapping Tabelle: Abkürzung -> IANA Name
        tz_map = {
            "CET": "Europe/Zurich",   # Mitteleuropäische Zeit
            "CEST": "Europe/Zurich",  # Mitteleuropäische Sommerzeit
            "UTC": "UTC",
            "GMT": "Europe/London",
        }
        # Wenn Abkürzung nicht bekannt → Europe/Zurich als Standard
        return tz_map.get(tz_abbr, "Europe/Zurich")

def print_all_keys(d, prefix=""):
    if isinstance(d, dict):
        for k, v in d.items():
            print_all_keys(v, prefix + k + "/")
    elif isinstance(d, list):
        for i, item in enumerate(d):
            print_all_keys(item, prefix + str(i) + "/")
    else:
        print(f"{prefix}: {d}")

# Funktion zum senden per MQTT
def send_mqtt(client, topic, wert, station_id):
    """Send MQTT"""
    payload = "" if wert is None else str(wert)
    client.publish(f"SofarCloud/{station_id}/{topic}", payload, qos=0, retain=True)

def login():
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "okhttp/3.14.9"
    }

    payload = {
        "accountName": USERNAME,
        "expireTime": 2592000,  # 30 Tage
        "password": PASSWORD
    }

    try:
        LOGIN_URL = URL + "user/auth/he/login"
        response = requests.post(LOGIN_URL, headers=headers, json=payload, verify=True)
        if DEBUG:
            print("Status code:", response.status_code)
            print("Response:", response.text)

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "0" and "data" in data:
                token = data["data"].get("accessToken")
                if DEBUG:
                    print()
                    print("✅ Login erfolgreich. Token:", token)
                return token
            else:
                print("❌ Login fehlgeschlagen:", data.get("message"))
        else:
            print("❌ Serverfehler.")
    except Exception as e:
        print("🚫 Fehler beim Login:", str(e))

    return None

def get_sofar_station_data(token):

    timezone = get_local_timezone()
    url_list = URL + "device/stationInfo/selectStationListPages"
    headers = {
        "authorization": token,
        "app-version": appversion,
        "custom-origin": "sofar",
        "custom-device-type": "1",
        "request-from": "app",
        "scene": "eu",
        "bundlefrom": "2",
        "appfrom": "6",
        "timezone": timezone,
        "accept-language": "en",
        "user-agent": "okhttp/4.9.2",
        "content-type": "application/json"
    }

    if DEBUG:
        print()
        print("Timezone:", timezone)
        print("App Version:", appversion)

    data = {"pageNum": 1, "pageSize": 10}
    resp = requests.post(url_list, headers=headers, json=data)
    stations = resp.json()["data"]["rows"]

    # Für jede Station Details holen
    all_realtime = []
    for station in stations:
        station_id = station["id"]
        url_detail = f"{URL}device/stationInfo/selectStationDetail?stationId={station_id}"
        resp_detail = requests.post(url_detail, headers=headers)
        detail_data = resp_detail.json()
        all_realtime.append(detail_data["data"]["stationRealTimeVo"])
    return all_realtime

def main():
    """Hauptroutine"""

    if DEBUG:
        print()
    if MQTT_ACTIVE:
        try:
            client = mqtt.Client("SofarCloud")
            if DEBUG:
                print("paho-mqtt version < 2.0")
        except ValueError:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "SofarCloud")
            if DEBUG:
                print("paho-mqtt version >= 2.0")

    if DEBUG:
        print()

    if MQTT_ACTIVE:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        try:
            client.connect(BROKER_ADDRESS, port=MQTT_PORT)
        except OSError as error:
            print("Verbindung zum MQTT-Broker fehlgeschlagen")
            print("Connection to MQTT broker failed")
            print(error)

    token = login()

    if not token:
        print("No token. Abort")
        return

    daten = get_sofar_station_data(token)
    if not daten:
        print("Fehler. Keine Daten empfangen.")
        if MQTT_ACTIVE:
            client.disconnect()
        return

    if CREATE_JSON:
        with open(JSON_PATH + "sofar_realtime.json", "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, indent=2)


    if DEBUG:
        print()
        print("Received data:")
        print("=============")
        print()
        print_all_keys(daten)
        print()

    if MQTT_ACTIVE:
        for idx, station in enumerate(daten):
            station_id = station.get("id", f"station{idx}")
            for key, value in station.items():
                if not key.lower().endswith("unit"):
                    send_mqtt(client, key, value, station_id)

        time.sleep(0.5)
        client.disconnect()

if __name__ == "__main__":
    main()
