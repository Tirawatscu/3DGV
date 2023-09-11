from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class AdcData(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.String(120))  # or whatever length you think is appropriate
    num_channels = db.Column(db.Integer)
    duration = db.Column(db.Float)
    radius = db.Column(db.Float)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    location = db.Column(db.String(120))
    waveform_file = db.Column(db.String(120)) 