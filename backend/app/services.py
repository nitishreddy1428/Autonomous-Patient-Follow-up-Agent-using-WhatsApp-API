"""
PatientAgent Services Layer
Handles Twilio WhatsApp messaging, AI analysis, and patient data processing.
"""

import os
from twilio.rest import Client
from .models import db, Alert, Patient, CheckInResponse
from .chatbot import start_checkin, process_patient_message


class TwilioService:
    """Real Twilio WhatsApp/SMS integration."""

    _client = None

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
            auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
            if account_sid and auth_token:
                cls._client = Client(account_sid, auth_token)
            else:
                print("⚠️  Twilio credentials not set. Running in MOCK mode.")
        return cls._client

    @classmethod
    def send_whatsapp(cls, to_phone, message):
        """
        Send a WhatsApp message via Twilio.
        Falls back to console logging if credentials are not set.
        """
        client = cls._get_client()
        from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

        # Aggressively clean phone number (remove all spaces, dashes, invisible chars)
        import re
        to_phone = re.sub(r'[^\d+]', '', to_phone)

        # Normalize phone number format
        if not to_phone.startswith('whatsapp:'):
            if not to_phone.startswith('+'):
                if len(to_phone) == 10:
                    to_phone = f'+91{to_phone}'
                else:
                    to_phone = f'+{to_phone}'
            to_phone = f'whatsapp:{to_phone}'

        print(f"DEBUG: Attempting to send to: '{to_phone}'")

        if client:
            try:
                msg = client.messages.create(
                    body=message,
                    from_=from_number,
                    to=to_phone
                )
                print(f"✅ WhatsApp sent to {to_phone} | SID: {msg.sid}")
                return {'success': True, 'sid': msg.sid}
            except Exception as e:
                print(f"❌ Twilio error: {e}")
                return {'success': False, 'error': str(e)}
        else:
            # Mock mode — log to console
            print(f"📱 [MOCK] WhatsApp to {to_phone}: {message[:80]}...")
            return {'success': True, 'sid': 'MOCK_SID', 'mock': True}

    @classmethod
    def send_sms(cls, to_phone, message):
        """Send an SMS via Twilio."""
        client = cls._get_client()
        from_number = os.environ.get('TWILIO_PHONE_NUMBER')

        if client and from_number:
            try:
                msg = client.messages.create(
                    body=message,
                    from_=from_number,
                    to=to_phone
                )
                return {'success': True, 'sid': msg.sid}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        else:
            print(f"📱 [MOCK] SMS to {to_phone}: {message[:80]}...")
            return {'success': True, 'sid': 'MOCK_SID', 'mock': True}


class AIService:
    """Symptom analysis engine."""

    @staticmethod
    def analyze_symptoms(pain_level, symptoms, sentiment=None):
        """
        Analyze patient symptoms and compute risk score.
        Uses rule-based logic (can be replaced with LLM).
        """
        risk_score = pain_level * 10

        symptoms_lower = symptoms.lower() if symptoms else ''

        # Critical symptom keywords
        critical_keywords = ['bleeding', 'infection', 'pus', 'unconscious', 'cant breathe']
        high_keywords = ['fever', 'swelling', 'vomiting', 'dizzy', 'redness', 'discharge']
        medium_keywords = ['pain', 'discomfort', 'nausea', 'headache', 'tired']

        for word in critical_keywords:
            if word in symptoms_lower:
                risk_score += 40
                break

        for word in high_keywords:
            if word in symptoms_lower:
                risk_score += 20
                break

        for word in medium_keywords:
            if word in symptoms_lower:
                risk_score += 10
                break

        # Sentiment modifier
        if sentiment == 'Negative':
            risk_score += 10
        elif sentiment == 'Positive':
            risk_score = max(0, risk_score - 10)

        # Cap at 100
        risk_score = min(100, risk_score)

        severity = "Low"
        if risk_score > 70:
            severity = "High"
        elif risk_score > 40:
            severity = "Medium"

        return risk_score, severity


class PatientService:
    """Core patient data processing."""

    @staticmethod
    def process_response(patient_id, pain_level, temperature, symptoms, sentiment=None):
        """Process a check-in response and update dashboard."""
        risk_score, severity = AIService.analyze_symptoms(pain_level, symptoms, sentiment)

        # Save response
        new_response = CheckInResponse(
            patient_id=patient_id,
            pain_level=pain_level,
            temperature=temperature,
            symptoms=symptoms,
            sentiment=sentiment
        )
        db.session.add(new_response)

        # Update patient state
        patient = Patient.query.get(patient_id)
        if not patient:
            db.session.rollback()
            return False

        patient.risk_score = risk_score

        if severity == "Low":
            patient.status = "Recovering"
        elif severity == "Medium":
            patient.status = "Alert"
        else:
            patient.status = "Critical"

        # Trigger Alert if needed
        if severity in ["Medium", "High"]:
            new_alert = Alert(
                patient_id=patient_id,
                severity=severity,
                message=f"Patient reports: {symptoms} (Pain: {pain_level}/10)"
            )
            db.session.add(new_alert)

            # Notify doctor via WhatsApp/SMS
            doctor_phone = os.environ.get('DOCTOR_PHONE', '+1234567890')
            TwilioService.send_whatsapp(
                doctor_phone,
                f"🚨 ALERT: Patient *{patient.name}* ({severity} severity)\n"
                f"Pain: {pain_level}/10 | Symptoms: {symptoms}\n"
                f"Dashboard: http://localhost:8080"
            )

            # Notify Emergency Contact if available
            if patient.emergency_phone:
                TwilioService.send_whatsapp(
                    patient.emergency_phone,
                    f"⚠️ URGENT PATIENT AGENT ALERT: We are checking in on *{patient.name}*.\n"
                    f"They have reported severe symptoms (Pain: {pain_level}/10) and might not be able to reply further.\n"
                    f"Please check on them immediately to ensure they are okay. A doctor has also been notified."
                )

        db.session.commit()
        return True

    @staticmethod
    def initiate_checkin(patient_id):
        """
        Doctor triggers a proactive check-in for a patient.
        Sends the initial WhatsApp message and sets up conversation state.
        """
        patient = Patient.query.get(patient_id)
        if not patient:
            return {'success': False, 'error': 'Patient not found'}

        # Generate the check-in greeting
        greeting_message = start_checkin(patient)

        # Send via Twilio
        result = TwilioService.send_whatsapp(patient.phone, greeting_message)

        return {
            'success': result.get('success', False),
            'message': f'Check-in initiated for {patient.name}',
            'twilio': result
        }

    @staticmethod
    def handle_incoming_whatsapp(from_phone, message_body):
        """
        Handle an incoming WhatsApp message from a patient.
        This is called by the Twilio webhook.
        """
        # Process through chatbot engine
        reply, is_complete, extracted_data = process_patient_message(from_phone, message_body)

        # If check-in is complete, save the data to the database
        if is_complete and extracted_data:
            PatientService.process_response(
                patient_id=extracted_data['patient_id'],
                pain_level=extracted_data['pain_level'],
                temperature=extracted_data['temperature'],
                symptoms=extracted_data['symptoms'],
                sentiment=extracted_data.get('sentiment')
            )

        # Send reply back to patient
        TwilioService.send_whatsapp(from_phone, reply)

        return {
            'reply': reply,
            'is_complete': is_complete,
            'data': extracted_data
        }

    @staticmethod
    def check_idle_conversations():
        from .chatbot import _conversations
        import time
        
        now = time.time()
        for phone, conv in list(_conversations.items()):
            if conv.get('stage') and not conv.get('alerted', False):
                # 600 seconds = 10 minutes
                if now - conv.get('last_updated', now) > 600:
                    conv['alerted'] = True
                    emergency_phone = conv.get('emergency_phone')
                    if emergency_phone:
                        TwilioService.send_whatsapp(
                            emergency_phone,
                            f"⚠️ EMERGENCY ALERT: Patient *{conv.get('patient_name', 'Patient')}* has "
                            "not responded to their AI check-in for over 10 minutes. "
                            "Please check on them immediately."
                        )
