import time
from flask import Blueprint, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from .models import Patient, CheckInResponse, Alert, Doctor, db
from .services import PatientService, TwilioService
from .chatbot import get_conversation

api = Blueprint('api', __name__)

# ── Doctor Authentication ──────────────────────────────────────────

@api.route('/auth/signup', methods=['POST'])
def signup():
    data = request.json
    if Doctor.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    if Doctor.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    new_doctor = Doctor(username=data['username'], email=data['email'])
    new_doctor.set_password(data['password'])
    db.session.add(new_doctor)
    db.session.commit()
    return jsonify({'message': 'Doctor registered successfully', 'username': new_doctor.username}), 201

@api.route('/auth/login', methods=['POST'])
def login():
    data = request.json
    doctor = Doctor.query.filter_by(username=data['username']).first()
    if doctor and doctor.check_password(data['password']):
        return jsonify({
            'message': 'Login successful',
            'doctor': {
                'username': doctor.username,
                'email': doctor.email
            }
        }), 200
    return jsonify({'error': 'Invalid username or password'}), 401

# ── Twilio WhatsApp Webhook ─────────────────────────────────────────

@api.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """
    Twilio sends incoming WhatsApp messages here.
    Configure this URL in your Twilio Console:
    https://console.twilio.com → Messaging → Sandbox → "WHEN A MESSAGE COMES IN"
    URL: https://your-ngrok-url/api/webhook/whatsapp
    """
    from_phone = request.form.get('From', '')  # e.g. 'whatsapp:+919876543210'
    message_body = request.form.get('Body', '')
    
    print(f"📥 Incoming WhatsApp from {from_phone}: {message_body}")
    
    # Strip 'whatsapp:' prefix for internal lookup
    clean_phone = from_phone.replace('whatsapp:', '')
    
    # Process through the chatbot engine
    # (PatientService.handle_incoming_whatsapp already sends the reply internally)
    PatientService.handle_incoming_whatsapp(clean_phone, message_body)
    
    # Return empty TwiML to acknowledge receipt to Twilio
    return str(MessagingResponse()), 200, {'Content-Type': 'text/xml'}


@api.route('/send-checkin/<int:patient_id>', methods=['POST'])
def send_checkin(patient_id):
    """Doctor triggers a proactive check-in message to a patient."""
    result = PatientService.initiate_checkin(patient_id)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


@api.route('/send-checkin-all', methods=['POST'])
def send_checkin_all():
    """Send check-in messages to ALL recovering patients."""
    patients = Patient.query.filter(Patient.status.in_(['Recovering', 'Alert'])).all()
    results = []
    for p in patients:
        r = PatientService.initiate_checkin(p.id)
        results.append({'patient': p.name, 'result': r})
    return jsonify({'sent': len(results), 'details': results})


@api.route('/chat-status/<int:patient_id>', methods=['GET'])
def chat_status(patient_id):
    """Check if a patient has an active chat conversation."""
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({'active': False})
    
    conv = get_conversation(patient.phone)
    return jsonify({
        'active': conv['stage'] is not None,
        'stage': conv['stage'],
        'data_collected': conv.get('data', {})
    })

@api.route('/', methods=['GET'])
def root():
    return jsonify({
        'status': 'PatientAgent API is online',
        'endpoints': ['/patients', '/check-in', '/alerts', '/stats']
    })

@api.route('/patients', methods=['GET'])
def get_patients():
    patients = Patient.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'phone': p.phone,
        'surgery_type': p.surgery_type,
        'status': p.status,
        'risk_score': p.risk_score
    } for p in patients])

@api.route('/patients', methods=['POST'])
def add_patient():
    data = request.json
    new_patient = Patient(
        name=data['name'],
        phone=data['phone'],
        surgery_type=data.get('surgery_type', 'General'),
        emergency_phone=data.get('emergency_phone', None)
    )
    db.session.add(new_patient)
    db.session.commit()
    return jsonify({'message': 'Patient added', 'id': new_patient.id}), 201

@api.route('/check-in', methods=['POST'])
def check_in():
    data = request.json
    PatientService.process_response(
        data['patient_id'],
        data['pain_level'],
        data['temperature'],
        data['symptoms']
    )
    return jsonify({'message': 'Response recorded'})

@api.route('/telehealth/<int:patient_id>', methods=['POST'])
def start_telehealth(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Generate a unique Jitsi Meet link
    room_id = f"PatientAgent_{patient_id}_{int(time.time())}"
    video_link = f"https://meet.jit.si/{room_id}"
    
    message = (
        f"🚨 *Urgent Video Consultation Requested*\n\n"
        f"Hi {patient.name}, your doctor at PatientAgent would like to jump on a quick video call to check on your recovery.\n\n"
        f"Please click the link below to join the secure video room:\n{video_link}"
    )
    
    success, error = TwilioService.send_whatsapp(patient.phone, message)
    
    if success:
        return jsonify({'success': True, 'link': video_link})
    else:
        return jsonify({'success': False, 'error': error}), 400


@api.route('/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    data = request.json
    
    patient.name = data.get('name', patient.name)
    patient.phone = data.get('phone', patient.phone)
    patient.surgery_type = data.get('surgery_type', patient.surgery_type)
    patient.emergency_phone = data.get('emergency_phone', patient.emergency_phone)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Patient updated successfully'})

@api.route('/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Clean up related records
    CheckInResponse.query.filter_by(patient_id=patient_id).delete()
    Alert.query.filter_by(patient_id=patient_id).delete()
    
    db.session.delete(patient)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Patient and related data deleted'})

@api.route('/alerts', methods=['GET'])
def get_alerts():
    alerts = Alert.query.filter_by(is_resolved=False).all()
    return jsonify([{
        'id': a.id,
        'patient_name': Patient.query.get(a.patient_id).name,
        'severity': a.severity,
        'message': a.message,
        'timestamp': a.timestamp.isoformat()
    } for a in alerts])

@api.route('/alerts/<int:alert_id>/resolve', methods=['PUT'])
def resolve_alert(alert_id):
    alert = Alert.query.get(alert_id)
    if alert:
        alert.is_resolved = True
        db.session.commit()
        return jsonify({'message': 'Alert resolved'})
    return jsonify({'error': 'Alert not found'}), 404

@api.route('/patients/<int:patient_id>/history', methods=['GET'])
def get_patient_history(patient_id):
    responses = CheckInResponse.query.filter_by(patient_id=patient_id).order_by(CheckInResponse.timestamp.asc()).all()
    return jsonify([{
        'timestamp': r.timestamp.isoformat(),
        'pain_level': r.pain_level,
        'temperature': r.temperature
    } for r in responses])

@api.route('/stats', methods=['GET'])
def get_stats():
    total_patients = Patient.query.count()
    active_alerts = Alert.query.filter_by(is_resolved=False).count()
    critical_cases = Patient.query.filter_by(status='Critical').count()
    recovering = Patient.query.filter_by(status='Recovering').count()
    total_responses = CheckInResponse.query.count()
    total_alerts = Alert.query.count()
    return jsonify({
        'total_patients': total_patients,
        'active_alerts': active_alerts,
        'critical_cases': critical_cases,
        'recovering': recovering,
        'total_responses': total_responses,
        'total_alerts': total_alerts
    })

# ── Database Viewer Endpoints ──────────────────────────────────────

@api.route('/db/patients', methods=['GET'])
def db_patients():
    patients = Patient.query.order_by(Patient.id.desc()).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'phone': p.phone,
        'surgery_type': p.surgery_type,
        'surgery_date': p.surgery_date.isoformat() if p.surgery_date else None,
        'status': p.status,
        'risk_score': p.risk_score
    } for p in patients])

@api.route('/db/responses', methods=['GET'])
def db_responses():
    responses = CheckInResponse.query.order_by(CheckInResponse.id.desc()).all()
    return jsonify([{
        'id': r.id,
        'patient_id': r.patient_id,
        'patient_name': Patient.query.get(r.patient_id).name if Patient.query.get(r.patient_id) else 'Unknown',
        'timestamp': r.timestamp.isoformat(),
        'pain_level': r.pain_level,
        'temperature': r.temperature,
        'symptoms': r.symptoms,
        'sentiment': r.sentiment
    } for r in responses])

@api.route('/db/alerts', methods=['GET'])
def db_alerts():
    alerts = Alert.query.order_by(Alert.id.desc()).all()
    return jsonify([{
        'id': a.id,
        'patient_id': a.patient_id,
        'patient_name': Patient.query.get(a.patient_id).name if Patient.query.get(a.patient_id) else 'Unknown',
        'timestamp': a.timestamp.isoformat(),
        'severity': a.severity,
        'message': a.message,
        'is_resolved': a.is_resolved
    } for a in alerts])
