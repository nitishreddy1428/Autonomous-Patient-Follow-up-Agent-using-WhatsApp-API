from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from .database import db

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    surgery_type = db.Column(db.String(100))
    surgery_date = db.Column(db.DateTime, default=datetime.utcnow)
    emergency_phone = db.Column(db.String(20), nullable=True) # Secondary contact
    status = db.Column(db.String(20), default='Recovering') # Recovering, Alert, Critical
    risk_score = db.Column(db.Integer, default=0) # 0-100

class CheckInResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    pain_level = db.Column(db.Integer) # 1-10
    temperature = db.Column(db.Float)
    symptoms = db.Column(db.Text)
    sentiment = db.Column(db.String(20)) # Positive, Neutral, Negative

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    severity = db.Column(db.String(20)) # Medium, High, Critical
    message = db.Column(db.Text)
    is_resolved = db.Column(db.Boolean, default=False)
