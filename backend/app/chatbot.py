"""
PatientAgent AI Chatbot Engine
Handles conversational check-ins with patients via WhatsApp.
Uses rule-based NLP for the hackathon, structured to swap in an LLM later.
"""

import re
import os
import json
import requests
import time

# ── Conversation State Machine ──────────────────────────────────────
# Each patient goes through these check-in stages:
# 1. GREETING  → Bot sends initial check-in question
# 2. PAIN      → Bot asks about pain level
# 3. TEMP      → Bot asks about temperature
# 4. SYMPTOMS  → Bot asks about symptoms/concerns
# 5. COMPLETE  → Bot thanks patient, data is saved

CHECKIN_FLOW = {
    'GREETING': {
        'message': (
            "👋 Hello {name}! This is your PatientAgent check-in.\n\n"
            "I'd like to check on your recovery after your {surgery} surgery.\n"
            "Let's start — *How is your pain level today on a scale of 1-10?*\n"
            "(1 = no pain, 10 = worst pain)"
        ),
        'next': 'PAIN'
    },
    'PAIN': {
        'message': "📋 Got it. Now, *what is your current body temperature?* (e.g., 98.6°F or 37°C)\nIf you don't have a thermometer, just type 'skip'.",
        'next': 'TEMP'
    },
    'TEMP': {
        'message': "🩺 Almost done! *Are you experiencing any symptoms or concerns?*\n\nFor example: swelling, redness, fever, nausea, bleeding, dizziness, or just say 'feeling good'.",
        'next': 'SYMPTOMS'
    },
    'SYMPTOMS': {
        'message': "✅ Thank you for your update, {name}! Your recovery data has been recorded.\n\n{risk_summary}\n\nYour doctor has been notified. Take care! 💙",
        'next': 'COMPLETE'
    }
}

# In-memory conversation store (per phone number)
# In production, this would be Redis or a DB table
_conversations = {}


def get_conversation(phone):
    """Get or create a conversation state for a phone number."""
    if phone not in _conversations:
        _conversations[phone] = {
            'stage': None,
            'data': {},
            'last_updated': time.time(),
            'alerted': False
        }
    return _conversations[phone]


def clear_conversation(phone):
    """Reset conversation state after check-in completes."""
    if phone in _conversations:
        del _conversations[phone]


def start_checkin(patient):
    """Initialize a new check-in conversation for a patient."""
    phone = patient.phone
    _conversations[phone] = {
        'stage': 'GREETING',
        'patient_id': patient.id,
        'patient_name': patient.name,
        'surgery_type': patient.surgery_type or 'general',
        'emergency_phone': patient.emergency_phone,
        'data': {},
        'last_updated': time.time(),
        'alerted': False
    }
    msg = CHECKIN_FLOW['GREETING']['message'].format(
        name=patient.name,
        surgery=patient.surgery_type or 'general'
    )
    return msg


def process_patient_message(phone, message_body):
    """
    Process an incoming WhatsApp message from a patient.
    Returns (reply_text, is_complete, extracted_data).
    """
    conv = get_conversation(phone)
    message_body = message_body.strip()
    
    # Update last interaction timestamp
    conv['last_updated'] = time.time()
    
    # If no active conversation, treat as a new check-in request
    if conv['stage'] is None:
        # Try to find patient by phone
        return (
            "👋 Welcome to PatientAgent! It looks like you don't have an active check-in.\n"
            "Your doctor will send you a check-in request shortly. Stay well! 💙",
            False,
            None
        )

    stage = conv['stage']

    if stage == 'GREETING':
        # Patient just received the greeting, now we expect their pain level
        conv['stage'] = 'PAIN'
        # But this message IS their first reply, so parse it as pain
        return _handle_pain(conv, message_body)

    elif stage == 'PAIN':
        return _handle_pain(conv, message_body)

    elif stage == 'TEMP':
        return _handle_temp(conv, message_body)

    elif stage == 'SYMPTOMS':
        return _handle_symptoms(conv, phone, message_body)

    else:
        clear_conversation(phone)
        return ("Your check-in is already complete! Thank you. 💙", False, None)


def _handle_pain(conv, message_body):
    """Extract pain level from patient message."""
    pain = _extract_number(message_body, min_val=1, max_val=10)
    if pain is None:
        # Try Conversational AI if extraction fails
        ai_reply = get_conversational_reply(
            conv.get('patient_name'), 
            conv.get('surgery_type'), 
            message_body,
            "What is your pain level from 1 to 10?"
        )
        if ai_reply:
            return (ai_reply, False, None)

        return (
            "🤔 I didn't catch that. Please tell me your *pain level from 1 to 10*.\n"
            "(1 = no pain, 10 = worst pain imaginable)",
            False, None
        )
    conv['data']['pain_level'] = pain
    conv['stage'] = 'TEMP'
    reply = CHECKIN_FLOW['PAIN']['message']
    return (reply, False, None)


def _handle_temp(conv, message_body):
    """Extract temperature from patient message."""
    if 'skip' in message_body.lower():
        conv['data']['temperature'] = 37.0  # Default normal
    else:
        temp = _extract_temperature(message_body)
        if temp is None:
            # Try Conversational AI if extraction fails
            ai_reply = get_conversational_reply(
                conv.get('patient_name'), 
                conv.get('surgery_type'), 
                message_body,
                "What is your current body temperature?"
            )
            if ai_reply:
                return (ai_reply, False, None)

            return (
                "🤔 I didn't catch that. Please type your temperature like *98.6* or *37.2*.\n"
                "Or type 'skip' if you don't have a thermometer.",
                False, None
            )
        conv['data']['temperature'] = temp

    conv['stage'] = 'SYMPTOMS'
    reply = CHECKIN_FLOW['TEMP']['message']
    return (reply, False, None)


def get_conversational_reply(patient_name, surgery_type, user_msg, current_question):
    """Use AI to answer patient questions and guide them back to the check-in with Multi-lingual support."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key or len(user_msg) < 5: 
        return None

    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            f"You are a helpful medical assistant for PatientAgent. "
                            f"The patient, {patient_name}, is recovering from {surgery_type} surgery. "
                            "They are currently in a daily check-in. "
                            "INSTRUCTIONS: "
                            "1. Detect the language of the patient's message. "
                            "2. Reply professionally and reassuringly IN THE SAME LANGUAGE they used. "
                            "3. Do NOT provide medical prescriptions, just general care advice. "
                            f"4. Always end by re-asking the check-in question: '{current_question}' in their language."
                        )
                    },
                    {'role': 'user', 'content': user_msg}
                ],
                'temperature': 0.7,
                'max_tokens': 200
            },
            timeout=10
        )
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"LLM conversational reply failed: {e}")
        return None


def _handle_symptoms(conv, phone, message_body):
    """Extract symptoms and complete the check-in."""
    conv['data']['symptoms'] = message_body

    # Analyze sentiment / severity
    sentiment = _analyze_sentiment(message_body)
    conv['data']['sentiment'] = sentiment

    # Build risk summary for the patient
    pain = conv['data'].get('pain_level', 0)
    risk_summary = _build_risk_summary(pain, message_body)

    patient_name = conv.get('patient_name', 'Patient')
    reply = CHECKIN_FLOW['SYMPTOMS']['message'].format(
        name=patient_name,
        risk_summary=risk_summary
    )

    # Package extracted data
    extracted = {
        'patient_id': conv.get('patient_id'),
        'pain_level': conv['data']['pain_level'],
        'temperature': conv['data']['temperature'],
        'symptoms': conv['data']['symptoms'],
        'sentiment': sentiment
    }

    # Clear conversation
    clear_conversation(phone)

    return (reply, True, extracted)


# ── NLP Helpers ─────────────────────────────────────────────────────

def _extract_number(text, min_val=1, max_val=10):
    """Extract a number from text within a given range."""
    numbers = re.findall(r'\d+', text)
    for n in numbers:
        val = int(n)
        if min_val <= val <= max_val:
            return val
    # Try word-based numbers
    word_map = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    for word, val in word_map.items():
        if word in text.lower():
            return val
    return None


def _extract_temperature(text):
    """Extract temperature value from text, handle °F and °C."""
    # Match patterns like 98.6, 37.2, 98.6°F, 37°C, etc.
    matches = re.findall(r'(\d{2,3}\.?\d*)\s*°?\s*([fFcC])?', text)
    for match in matches:
        val = float(match[0])
        unit = match[1].upper() if match[1] else ''

        # Determine if Fahrenheit or Celsius
        if unit == 'F' or val > 45:
            # Convert F to C
            val = (val - 32) * 5.0 / 9.0

        # Sanity check for human body temp
        if 34.0 <= val <= 43.0:
            return round(val, 1)

    return None


def _analyze_sentiment(text):
    """Simple rule-based sentiment analysis on symptoms text."""
    text_lower = text.lower()
    negative_words = [
        'pain', 'fever', 'bleeding', 'swelling', 'nausea', 'vomit',
        'dizzy', 'dizziness', 'worse', 'bad', 'terrible', 'awful',
        'red', 'redness', 'infection', 'pus', 'discharge', 'hot',
        'throbbing', 'sharp', 'burning', 'can\'t sleep', 'worried'
    ]
    positive_words = [
        'good', 'great', 'fine', 'better', 'improving', 'no pain',
        'comfortable', 'healing', 'well', 'okay', 'ok', 'normal',
        'feeling good', 'much better', 'no issues', 'no problems'
    ]

    neg_count = sum(1 for w in negative_words if w in text_lower)
    pos_count = sum(1 for w in positive_words if w in text_lower)

    if neg_count > pos_count:
        return 'Negative'
    elif pos_count > neg_count:
        return 'Positive'
    return 'Neutral'


def _build_risk_summary(pain_level, symptoms):
    """Build a human-readable risk summary for the patient."""
    risk = pain_level * 10
    symptoms_lower = symptoms.lower()

    if any(w in symptoms_lower for w in ['fever', 'bleeding', 'infection', 'pus']):
        risk += 30
        return (
            "⚠️ *IMPORTANT*: Based on your symptoms, we've flagged this as a priority alert.\n"
            "Your doctor will review your case immediately."
        )
    elif risk > 40:
        return (
            "📊 Your recovery is being closely monitored.\n"
            "If symptoms worsen, please visit the hospital or message us again."
        )
    else:
        return (
            "🟢 Your recovery looks on track!\n"
            "Keep following your doctor's instructions and rest well."
        )


# ── LLM Integration (Optional Enhancement) ──────────────────────────

def analyze_with_llm(patient_name, surgery_type, message):
    """
    Optional: Use an LLM (OpenAI/Gemini) for more nuanced analysis.
    Can be swapped in to replace rule-based logic.
    """
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None  # Fall back to rule-based

    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            'You are a medical AI assistant analyzing post-surgery recovery messages. '
                            f'Patient: {patient_name}, Surgery: {surgery_type}. '
                            'Extract: pain_level (1-10), temperature (°C), symptoms, sentiment (Positive/Neutral/Negative). '
                            'Return JSON only: {"pain_level": int, "temperature": float, "symptoms": str, "sentiment": str}'
                        )
                    },
                    {'role': 'user', 'content': message}
                ],
                'temperature': 0.3
            },
            timeout=10
        )
        data = response.json()
        content = data['choices'][0]['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"LLM analysis failed: {e}")
        return None
