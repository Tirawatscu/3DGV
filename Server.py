from flask import Flask, render_template, json, request
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import time
import os
from models import db, AdcData
import configparser  

base_dir = os.path.abspath(os.path.dirname(__file__))
Storage_path = os.path.join(base_dir, 'storage')
db_path = os.path.join(base_dir, 'gvdb2023.db')

# Create 'Storages' directory if it doesn't exist
if not os.path.exists(Storage_path):
    os.makedirs(Storage_path)

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    db.init_app(app)
    return app

app = create_app()
    
socketio = SocketIO(app)

known_clients = [
    {'client_id': 'device1', 'status': 'disconnected', 'rssi': None, 'last_updated': None, 'index': 0},
    {'client_id': 'device2', 'status': 'disconnected', 'rssi': None, 'last_updated': None, 'index': 1},
    {'client_id': 'device3', 'status': 'disconnected', 'rssi': None, 'last_updated': None, 'index': 2},
]

file_data_placeholder = {
    'metadata': {
        'timestamp': '',
        'num_channels': 3,
        'duration': '',
        'radius': '',
        'latitude': '',
        'longitude': '',
        'location': '',
    },
    'waveform_data': {
        '0': [],
        '1': [],
        '2': [],
    },
}

json_name = ''

def custom_json(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    raise TypeError('Type not serializable')

@socketio.on('connect')
def handle_connect(auth=None):
    socketio.emit('update_clients', json.dumps(known_clients, default=custom_json))
    print(f"Emitting update at {datetime.now().strftime('%H:%M:%S')}")

def check_client_status():
    while True:
        socketio.sleep(5)
        for client in known_clients:
            if client['last_updated'] is None:
                continue
            if datetime.now() - client['last_updated'] > timedelta(seconds=20):
                client['status'] = 'disconnected'
                client['rssi'] = None
        socketio.emit('update_clients', json.dumps(known_clients, default=custom_json))

def on_connect(mqtt_client, userdata, flags, rc):
    print(f'Connected with result code {rc}')
    for client in known_clients:
        mqtt_client.subscribe(f"{client['client_id']}/rssi")
        mqtt_client.subscribe(f"{client['client_id']}/data")

def on_message(mqtt_client, userdata, msg):
    print(f'{msg.topic} {str(msg.payload.decode())}')
    client_id, data_type = msg.topic.split('/')
    data = msg.payload.decode()
    for client in known_clients:
        if client['client_id'] == client_id:
            if data_type == 'rssi':
                client['status'] = 'connected'
                client['rssi'] = data
                client['last_updated'] = datetime.now()
            elif data_type == 'data':
                parsed_data = json.loads(data)
                actual_data = parsed_data["0"]  # Since your data has a "0" key
                socketio.emit('update_data', json.dumps({'client_id': client_id, 'data': actual_data}))
                
                # read json file (json_name)
                with open(f'{Storage_path}/{json_name}.json') as f:
                    file_data = json.load(f)
                    
                # update json file
                file_data['waveform_data'][str(client['index'])] = actual_data
                
                # write json file
                with open(f'{Storage_path}/{json_name}.json', 'w') as f:
                    json.dump(file_data, f)    
                
                

@socketio.on('start_collecting')
def handle_start_collecting(data):
    global file_data_placeholder, json_name
    start_time = int(time.time()) + 3
    json_name = start_time
    duration = data.get('duration', 30)
    for client in known_clients:
        if client['status'] == 'connected':
            command = {
                "start_time": start_time,
                "duration": duration
            }
            mqtt_client.publish(f"{client['client_id']}/command", json.dumps(command))
            file_data_placeholder['metadata']['timestamp'] = start_time
            file_data_placeholder['metadata']['duration'] = duration
            file_data_placeholder['metadata']['radius'] = data.get('radius', 0)
            file_data_placeholder['metadata']['latitude'] = data.get('latitude', 0)
            file_data_placeholder['metadata']['longitude'] = data.get('longitude', 0)
            file_data_placeholder['metadata']['location'] = data.get('location', '')

            # write json file
            with open(f'{Storage_path}/{json_name}.json', 'w') as f:
                json.dump(file_data_placeholder, f)
            

@app.route('/')
def index():
    return render_template('index.html', clients=known_clients)

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(config['MQTT']['IP'], int(config['MQTT']['Port']), 60)
    mqtt_client.loop_start()
    
    socketio.start_background_task(check_client_status)
    socketio.run(app, host='0.0.0.0', port=1111)
