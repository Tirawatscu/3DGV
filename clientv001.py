import configparser
import paho.mqtt.client as mqtt
import time
import json
import numpy as np
import datetime  # Import the datetime library
import subprocess
import platform
import threading  # Import the threading library
import random

def collect_adc_data(duration):
    global ADC
    channelList = [0]
    start_time = time.perf_counter()
    ADC_Value_List = []

    next_sample_time = start_time + interval
    no_sample = duration * sampling_rate

    current_time = start_time

    while len(ADC_Value_List) < no_sample:
        current_time = time.perf_counter()
        if current_time >= next_sample_time:
            ADC_Value = ADC.ADS1263_GetAll(channelList)
            ADC_Value_List.append(ADC_Value)
            next_sample_time += interval

    actual_sampling_rate = len(ADC_Value_List) / (current_time - start_time)

    converted_data = {channel: [] for channel in channelList}
    for data in ADC_Value_List:
        for channel, value in enumerate(data):
            if value >> 31 == 1:
                converted_data[channel].append(-(REF * 2 - value * REF / 0x80000000))
            else:
                converted_data[channel].append(value * REF / 0x7fffffff)
    print(f"actual_sampling_rate = {actual_sampling_rate}")
    return converted_data, actual_sampling_rate

def simulate_adc_data(duration):
    channelList = [0, 1, 2]
    sample_count = int(duration * sampling_rate)
    simulated_data = {channel: [] for channel in channelList}
    time_per_sample = duration / sample_count

    for _ in range(sample_count):
        for channel in channelList:
            simulated_data[channel].append(round(random.uniform(-0.2, 0.2), 2))
        time.sleep(time_per_sample)

    actual_sampling_rate = sampling_rate
    return simulated_data, actual_sampling_rate

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
    start_time = command['start_time']
    duration = int(command['duration'])
    freq = 1  # 1 Hz

    
    # Wait until the start time
    while time.time() < start_time:
        pass
    
    # Then, start data collection
    if use_simulated_data or not ads1263_available:
        adc_data, actual_sampling_rate = simulate_adc_data(duration)
    else:
        adc_data, actual_sampling_rate = collect_adc_data(duration)

    mqtt_client.publish(f"{client_id}/data", json.dumps(adc_data))
    
    
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

if __name__ == '__main__':

    # Read configuration from file
    config = configparser.ConfigParser()
    config.read('config.ini')

    MQTT_IP = config['MQTT']['IP']
    MQTT_PORT = int(config['MQTT']['Port'])
    client_id = config['Device']['ID']
    use_simulated_data = config['Device'].getboolean('Sim')

    try:
        if platform.system() == "Linux":
            import ADS1263
            import RPi.GPIO as GPIO

            REF = 5.08
            ADC = ADS1263.ADS1263()
            if (ADC.ADS1263_init_ADC1('ADS1263_7200SPS') == -1):
                ADC.ADS1263_Exit()
                print("Failed to initialize ADC1")
                exit()
            ADC.ADS1263_SetMode(1)
            ads1263_available = True
    except ImportError:
        ads1263_available = False
        print("ADS1263 library not available, using simulated data")

    sampling_rate = config['Device'].getfloat('SampleRate')
    interval = 1 / sampling_rate
    mqtt_client = mqtt.Client(client_id=client_id)
    mqtt_client.on_connect = on_connect
    mqtt_client.message_callback_add(f"{client_id}/command", on_command)
    mqtt_client.connect(MQTT_IP, MQTT_PORT, 60)
    mqtt_client.loop_start()

    rssi_thread = threading.Thread(target=publish_rssi)
    rssi_thread.start()
