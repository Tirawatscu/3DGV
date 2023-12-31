from flask import Flask, render_template, json, request, jsonify
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import time
import os
from models import db, AdcData
import configparser
import numpy as np
from PyPOP import POP

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
    {'client_id': 'device1', 'status': 'disconnected', 'rssi': None, 'battery_voltage':None ,'battery_capacity':None ,'last_updated': None, 'index': 0},
    {'client_id': 'device2', 'status': 'disconnected', 'rssi': None, 'battery_voltage':None ,'battery_capacity':None ,'last_updated': None, 'index': 1},
    {'client_id': 'device3', 'status': 'disconnected', 'rssi': None, 'battery_voltage':None ,'battery_capacity':None ,'last_updated': None, 'index': 2},
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

def store_event_in_database(timestamp, num_channels, duration, radius, lat, lon, filepath, location, components=None):
    datetime_string = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    new_adc_data = AdcData(timestamp=datetime_string, num_channels=num_channels, duration=duration, radius=radius, latitude=lat, longitude=lon, location=location, waveform_file=filepath)
    db.session.add(new_adc_data)
    db.session.commit()

    print("Stored event in database")

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
                client['battery_voltage'] = None
                client['battery_capacity'] = None
        socketio.emit('update_clients', json.dumps(known_clients, default=custom_json))

def on_connect(mqtt_client, userdata, flags, rc):
    print(f'Connected with result code {rc}')
    for client in known_clients:
        #mqtt_client.subscribe(f"{client['client_id']}/rssi")
        mqtt_client.subscribe(f"{client['client_id']}/telemetry")
        mqtt_client.subscribe(f"{client['client_id']}/data")

def on_message(mqtt_client, userdata, msg):
    print(f'{msg.topic} {str(msg.payload.decode())}')
    client_id, data_type = msg.topic.split('/')
    data = msg.payload.decode()
    for client in known_clients:
        if client['client_id'] == client_id:
            if data_type == 'telemetry':
                parsed_data = json.loads(data)
                client['status'] = 'connected'
                client['rssi'] = parsed_data.get('rssi', None)
                client['battery_voltage'] = parsed_data.get('battery_voltage', None)
                client['battery_capacity'] = parsed_data.get('battery_capacity', None)
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
        
    store_event_in_database(start_time, 3, duration, data.get('radius', 0), data.get('latitude', 0), data.get('longitude', 0), f'{Storage_path}/{json_name}.json', data.get('location', ''))
            
            
@app.route('/')
def index():
    return render_template('index.html', clients=known_clients)

@app.route('/tables.html')
def adc_data():
    data = AdcData.query.with_entities(AdcData.id, AdcData.timestamp, AdcData.num_channels, AdcData.duration, AdcData.radius, AdcData.latitude, AdcData.longitude, AdcData.location).all()
    data_dicts = [row._asdict() for row in data]
    return render_template('tables.html', data=data_dicts)

@app.route('/get_waveform_data', methods=['GET'])
def get_waveform_data():
    event_id = request.args.get('id', type=int)

    if not event_id:
        return jsonify({'error': 'Event ID is required'}), 400

    # Fetch the waveform file path from the database
    adc_data = db.session.get(AdcData, event_id)
    if adc_data is None:
        return jsonify({'error': 'Event not found'}), 404
    waveform_data = fetch_waveform_data_from_file(adc_data.waveform_file)
    #print(waveform_data)
    return jsonify(waveform_data)

def fetch_waveform_data_from_file(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)
    
@app.route('/delete_event', methods=['POST'])
def delete_event():
    event_id = request.form['id']
    
    try:
        adc_data = db.session.get(AdcData, event_id)
        if adc_data:
            os.remove(adc_data.waveform_file)  # Delete the waveform file
            db.session.delete(adc_data)

        db.session.commit()
        
        return jsonify({'status': 'success'})
    except Exception as e:
        print(e)
        return jsonify({'status': 'error'})
    
@app.route('/update_event', methods=['POST'])
def update_event():
    # Retrieve the updated data from the request
    event_id = request.form.get('id')
    num_channels = request.form.get('num_channels')
    duration = request.form.get('duration')
    radius = request.form.get('radius')
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    location = request.form.get('location')

    try:
        # Update the data in the SQLite database
        event = db.session.get(AdcData, event_id)
        if event is None:
            return jsonify(status="error", message="No such event")

        event.num_channels = num_channels
        event.duration = duration
        event.radius = radius
        event.latitude = latitude
        event.longitude = longitude
        event.location = location

        db.session.commit()

        return jsonify(status="success")

    except Exception as e:
        print(e)
        return jsonify(status="error")    

@app.route('/plot_pop', methods=['GET'])
def plot_pop():
    event_id = request.args.get('id', type=int)
    segment_length = request.args.get('segment_length', type=int)
    
    if not event_id:
        return jsonify({'error': 'Event ID is required'}), 400
    
    # Fetch the waveform file path from the database
    adc_data = db.session.get(AdcData, event_id)
    #print(adc_data)
    
    with open(adc_data.waveform_file, 'r') as f:
        data = json.load(f)
    
    waveform_data = data['waveform_data']
    component_0 = waveform_data['0']
    component_1 = waveform_data['1']
    component_2 = waveform_data['2']

    vert = np.array([component_0, component_1, component_2]).T
    pop = POP(vert, [], [], adc_data.radius, 128, segment_length)
    F, C, C2 = pop.makepop()
    
    return jsonify({'frequency': F.tolist(), 'velocity': C.tolist()})

@app.route('/get_image_data', methods=['GET'])
def get_image_data():
    event_id = request.args.get('id', type=int)
    segment_length = request.args.get('segment_length', type=int)
    Fmin = request.args.get('Fmin', type=int)
    Fmax = request.args.get('Fmax', type=int)
    Vmin = request.args.get('Vmin', type=int)
    Vmax = request.args.get('Vmax', type=int)
    Res = request.args.get('Resolution', type=int)
    
    if not event_id:
        return jsonify({'error': 'Event ID is required'}), 400
    
    # Fetch the waveform file path from the database
    adc_data = db.session.get(AdcData, event_id)
    #print(adc_data)
    
    with open(adc_data.waveform_file, 'r') as f:
        data = json.load(f)
    
    waveform_data = data['waveform_data']
    component_0 = waveform_data['0']
    component_1 = waveform_data['1']
    component_2 = waveform_data['2']

    vert = np.array([component_0, component_1, component_2]).T
    pop = POP(vert, [], [], adc_data.radius, 128, segment_length)
    ds, f, vs, norm = pop.imagPop(Fmin=Fmin, Fmax=Fmax, vmin=Vmin, vmax=Vmax, resolustion=Res)
    
    return jsonify({'ds': ds.tolist(), 'f': f.tolist(), 'vs': vs.tolist()})


@app.route('/download_waveform_data', methods=['GET'])
def download_waveform_data():
    event_id = request.args.get('id', type=int)
    
    if not event_id:
        return jsonify({'error': 'Event ID is required'}), 400

    adc_data = db.session.get(AdcData, event_id)
    if adc_data is None:
        return jsonify({'error': 'Event not found'}), 404

    full_data = fetch_waveform_data_from_file(adc_data.waveform_file)
    
    if not full_data:
        return jsonify({'error': 'No data found'}), 404

    response = jsonify(full_data)
    response.headers.set('Content-Disposition', f'attachment; filename=waveform_data_{event_id}.json')
    response.headers.set('Content-Type', 'application/json')
    return response

@app.route('/store_uploaded_data', methods=['POST'])
def store_uploaded_data():
    data = request.json
    metadata = data['metadata']
    waveform_data = data['waveform_data']

    filepath = f'{Storage_path}/{metadata["location"]}.json'
    file_uploaded = {
        'metadata': {
            'timestamp': int(time.time()),
            'num_channels': len(waveform_data),
            'duration': metadata['duration'],
            'radius': metadata['radius'],
            'latitude': metadata['latitude'],
            'longitude': metadata['longitude'],
            'location': metadata['location'],
            },
        'waveform_data': waveform_data
    }
    with open(filepath, 'w') as jsonfile:
        json.dump(file_uploaded, jsonfile)

    adc_data = AdcData(
        timestamp=int(time.time()),
        num_channels=len(waveform_data),
        duration=metadata['duration'],
        radius=metadata['radius'],
        latitude=metadata['latitude'],
        longitude=metadata['longitude'],
        location=metadata['location'],
        waveform_file=filepath
    )
    db.session.add(adc_data)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Data stored successfully'})

@app.route('/merge_events', methods=['POST'])
def merge_events():
    try:
        event_ids = request.form.get('ids')
        event_ids = json.loads(event_ids)  # Convert the JSON string back to a list

        if not event_ids or len(event_ids) < 2:
            return jsonify({'status': 'error', 'message': 'At least two events must be selected for merging.'})

        merged_event_data, metadata = merge_waveforms(event_ids)

        # Create a new JSON file to store the merged event data
        timestamp = int(time.time())
        json_name = timestamp
        json_path = os.path.join(Storage_path, f"{json_name}.json")
        
        merged_event = {
            'metadata': metadata,
            'waveform_data': merged_event_data
        }

        with open(json_path, 'w') as f:
            json.dump(merged_event, f)

        # Store the merged event in the database
        store_event_in_database(
            timestamp=timestamp,
            num_channels=metadata['num_channels'],
            duration=metadata['duration'],  # Updated duration
            radius=metadata['radius'],
            lat=metadata['latitude'],
            lon=metadata['longitude'],
            filepath=json_path,
            location=metadata['location']  # Updated location with '_merged'
        )

        return jsonify({'status': 'success'})
    except Exception as e:
        print(e)
        return jsonify({'status': 'error'})
    
def merge_waveforms(event_ids):
    # Initialize empty lists to store waveforms for each channel
    waveforms = {'0': [], '1': [], '2': []}
    metadata = None
    total_duration = 0

    for event_id in event_ids:
        # Fetch the waveform file path from the database
        adc_data = db.session.get(AdcData, event_id)
        if adc_data is None:
            continue  # Skip if not found

        with open(adc_data.waveform_file, 'r') as f:
            data = json.load(f)
        
        if metadata is None:
            metadata = data['metadata']

        # Add the duration of this specific event to the total_duration
        event_metadata = data['metadata']
        total_duration += event_metadata['duration']

        for channel, waveform in data['waveform_data'].items():
            waveforms[channel].extend(waveform)
    
    metadata['duration'] = total_duration  # Update the metadata with the total duration
    metadata['location'] += "_merged"  # Add '_merged' suffix to the location

    return waveforms, metadata




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
