from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from twilio.rest import Client
from twilio.twiml import VoiceResponse
import openai
import os
import json
import asyncio
import websockets
from datetime import datetime
import logging
from translation_service import ChatGPTRealtimeTranslator

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize clients
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai.api_key = OPENAI_API_KEY

# Initialize translation service
translator = ChatGPTRealtimeTranslator(OPENAI_API_KEY)

# Store active calls and their translation settings
active_calls = {}

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Translation App</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
        <h1>Live Translation Service</h1>
        <p>Backend is running. Use the frontend to make calls.</p>
    </body>
    </html>
    ''')

@app.route('/start-call', methods=['POST'])
def start_call():
    """Initiate a call with translation capabilities"""
    try:
        data = request.json
        to_number = data.get('to_number')
        from_language = data.get('from_language', 'en')
        to_language = data.get('to_language', 'es')
        
        if not to_number:
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Create Twilio call
        call = twilio_client.calls.create(
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{request.url_root}voice",
            method='POST'
        )
        
        # Create translation session
        translation_session = await translator.create_translation_session(
            call.sid, from_language, to_language
        )
        
        # Store call information
        active_calls[call.sid] = {
            'from_language': from_language,
            'to_language': to_language,
            'status': 'initiated',
            'translation_session': translation_session,
            'created_at': datetime.now().isoformat()
        }
        
        logger.info(f"Call initiated: {call.sid} to {to_number}")
        
        return jsonify({
            'call_sid': call.sid,
            'status': 'initiated',
            'message': 'Call started successfully'
        })
        
    except Exception as e:
        logger.error(f"Error starting call: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/voice', methods=['POST'])
def handle_voice():
    """Handle incoming voice calls and set up translation"""
    response = VoiceResponse()
    
    # Get call SID from Twilio
    call_sid = request.form.get('CallSid')
    
    if call_sid in active_calls:
        call_info = active_calls[call_sid]
        from_lang = call_info['from_language']
        to_lang = call_info['to_language']
        
        # Create a greeting with translation context
        greeting = f"Hello! You are now connected to a live translation service. "
        greeting += f"I will translate between {from_lang} and {to_lang}. Please start speaking."
        
        response.say(greeting, voice='alice')
        
        # Set up real-time transcription and translation
        response.start().stream(
            url=f"wss://{request.host}/stream",
            track='both_tracks'
        )
        
        # Keep the call active
        response.pause(length=3600)  # 1 hour max
        
    else:
        response.say("Sorry, this call could not be processed.")
        response.hangup()
    
    return str(response)

@app.route('/stream')
async def handle_stream():
    """WebSocket endpoint for real-time audio streaming and translation"""
    websocket = request.environ.get('wsgi.websocket')
    if not websocket:
        return "WebSocket connection required", 400
    
    try:
        async for message in websocket:
            # Handle incoming audio data
            if message.startswith('audio:'):
                audio_data = message[6:]  # Remove 'audio:' prefix
                # Process audio with ChatGPT Realtime API
                await process_audio_with_translation(audio_data, websocket)
                
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")

async def process_audio_with_translation(audio_data, websocket, call_sid):
    """Process audio data and return translation using ChatGPT Realtime API"""
    try:
        if call_sid not in active_calls:
            logger.error(f"Call {call_sid} not found in active calls")
            return
        
        # Process audio with the translation service
        translation_result = await translator.process_audio(call_sid, audio_data)
        
        # Send translation back through WebSocket
        await websocket.send(json.dumps(translation_result))
        
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        error_response = {
            'error': str(e),
            'call_sid': call_sid
        }
        await websocket.send(json.dumps(error_response))

@app.route('/end-call/<call_sid>', methods=['POST'])
def end_call(call_sid):
    """End an active call"""
    try:
        if call_sid in active_calls:
            # End translation session
            await translator.end_session(call_sid)
            
            # Update call status
            active_calls[call_sid]['status'] = 'ended'
            active_calls[call_sid]['ended_at'] = datetime.now().isoformat()
            
            # Hang up the call
            call = twilio_client.calls(call_sid).update(status='completed')
            
            return jsonify({
                'call_sid': call_sid,
                'status': 'ended',
                'message': 'Call ended successfully'
            })
        else:
            return jsonify({'error': 'Call not found'}), 404
            
    except Exception as e:
        logger.error(f"Error ending call: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/call-status/<call_sid>')
def get_call_status(call_sid):
    """Get the status of a specific call"""
    if call_sid in active_calls:
        return jsonify(active_calls[call_sid])
    else:
        return jsonify({'error': 'Call not found'}), 404

@app.route('/active-calls')
def get_active_calls():
    """Get all active calls"""
    return jsonify(active_calls)

if __name__ == '__main__':
    # Check for required environment variables
    required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER', 'OPENAI_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these environment variables before running the app.")
    else:
        app.run(debug=True, host='0.0.0.0', port=5000)
