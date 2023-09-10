import configparser
import paho.mqtt.client as mqtt
import time
import json
import numpy as np
import datetime  # Import the datetime library
import subprocess
import platform
import threading  # Import the threading library

# Read configuration from file
config = configparser.ConfigParser()
config.read('config.ini')

MQTT_IP = config['MQTT']['IP']
MQTT_PORT = int(config['MQTT']['Port'])
client_id = config['Device']['ID']

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe(f"{client_id}/command")

def get_real_rssi():
    try:
        os_platform = platform.system()
        command_output = ''
        if os_platform == 'Linux':
            command_output = subprocess.check_output(['iwconfig'], stderr=subprocess.STDOUT, text=True, universal_newlines=True)
            lines = command_output.split('\n')
            for line in lines:
                if 'Link Quality' in line:
                    rssi = line.split('=')[1].split('/')[0].strip()
                    return int(rssi)
        elif os_platform == 'Darwin':
            command_output = subprocess.check_output(
                ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True
            )
            lines = command_output.split('\n')
            for line in lines:
                if 'agrCtlRSSI' in line:
                    rssi = line.split(':')[1].strip()
                    return int(rssi)
        else:
            print(f'Unsupported platform: {os_platform}')
            return 0
    except Exception as e:
        print(f'An error occurred: {e}')
        return 0

def collect_data(client, userdata, msg):
    print(f"Received command on topic {msg.topic}: {msg.payload.decode()}")
    command = json.loads(msg.payload.decode())
    start_time = datetime.datetime.strptime(command['start_time'], '%Y-%m-%d %H:%M:%S')
    duration = int(command['duration'])
    freq = 1  # 1 Hz
    sampling_rate = 100  # 100 Hz
    values = []
    for t in np.arange(0, duration, 1 / sampling_rate):
        sine_wave = np.sin(2 * np.pi * freq * t)
        values.append(sine_wave)
        time.sleep(1 / sampling_rate)
    mqtt_client.publish(f"{client_id}/data", json.dumps(values))
    print(f"Sent data to the server")

def on_command(client, userdata, msg):
    data_thread = threading.Thread(target=collect_data, args=(client, userdata, msg))
    data_thread.start()

def publish_rssi():
    while True:
        rssi_value = get_real_rssi()
        if rssi_value is not None:
            print(f"Publishing RSSI value: {rssi_value}")
            mqtt_client.publish(f"{client_id}/rssi", rssi_value)
        time.sleep(5)

mqtt_client = mqtt.Client(client_id=client_id)
mqtt_client.on_connect = on_connect
mqtt_client.message_callback_add(f"{client_id}/command", on_command)

mqtt_client.connect(MQTT_IP, MQTT_PORT, 60)

mqtt_client.loop_start()

rssi_thread = threading.Thread(target=publish_rssi)
rssi_thread.start()
