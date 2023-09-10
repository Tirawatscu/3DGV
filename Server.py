from flask import Flask, render_template, json, request
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import time

app = Flask(__name__)
socketio = SocketIO(app)

known_clients = [
    {'client_id': 'device1', 'status': 'disconnected', 'rssi': None, 'last_updated': None},
    {'client_id': 'device2', 'status': 'disconnected', 'rssi': None, 'last_updated': None},
    {'client_id': 'device3', 'status': 'disconnected', 'rssi': None, 'last_updated': None},
]

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
        socketio.sleep(10)
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
                socketio.emit('update_data', json.dumps({'client_id': client_id, 'data': data["0"]}))

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect('192.168.1.112', 1883, 60)
mqtt_client.loop_start()

@socketio.on('start_collecting')
def handle_start_collecting(data):
    start_time = int(time.time()) + 3
    duration = data.get('duration', 30)
    for client in known_clients:
        if client['status'] == 'connected':
            command = {
                "start_time": start_time,
                "duration": duration
            }
            mqtt_client.publish(f"{client['client_id']}/command", json.dumps(command))

@app.route('/')
def index():
    return render_template('index.html', clients=known_clients)

if __name__ == '__main__':
    socketio.start_background_task(check_client_status)
    socketio.run(app, host='0.0.0.0', port=5000)
