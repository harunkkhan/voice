import openai
import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ChatGPTRealtimeTranslator:
    """Service for handling real-time translation using ChatGPT Realtime API"""
    
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.active_sessions = {}
    
    async def create_translation_session(self, session_id: str, from_language: str, to_language: str) -> Dict[str, Any]:
        """Create a new translation session"""
        try:
            # Create a ChatGPT Realtime API session
            session = self.client.beta.realtime.sessions.create(
                model="gpt-4o-realtime-preview-2024-10-01",
                voice="alloy",
                instructions=f"""
                You are a professional live translator. Your role is to:
                1. Listen to speech in {from_language}
                2. Translate it accurately to {to_language}
                3. Speak the translation clearly
                4. Maintain the original tone and context
                
                Always respond with the translation in {to_language}. Be natural and conversational.
                If you don't understand something, ask for clarification in {to_language}.
                """
            )
            
            self.active_sessions[session_id] = {
                'session': session,
                'from_language': from_language,
                'to_language': to_language,
                'status': 'active'
            }
            
            logger.info(f"Translation session created: {session_id}")
            return {
                'session_id': session_id,
                'status': 'active',
                'from_language': from_language,
                'to_language': to_language
            }
            
        except Exception as e:
            logger.error(f"Error creating translation session: {str(e)}")
            raise
    
    async def process_audio(self, session_id: str, audio_data: bytes) -> Dict[str, Any]:
        """Process audio data and return translation"""
        try:
            if session_id not in self.active_sessions:
                raise ValueError(f"Session {session_id} not found")
            
            session_info = self.active_sessions[session_id]
            session = session_info['session']
            
            # Send audio to ChatGPT Realtime API
            response = session.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=audio_data
            )
            
            # For now, we'll simulate the translation response
            # In a real implementation, you would process the actual response
            translation_result = {
                'session_id': session_id,
                'original_text': 'Simulated original text',
                'translated_text': 'Texto traducido simulado',
                'confidence': 0.95,
                'audio_response': response.audio if hasattr(response, 'audio') else None
            }
            
            return translation_result
            
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            raise
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """End a translation session"""
        try:
            if session_id in self.active_sessions:
                session_info = self.active_sessions[session_id]
                session = session_info['session']
                
                # Close the session
                session.close()
                
                # Remove from active sessions
                del self.active_sessions[session_id]
                
                logger.info(f"Translation session ended: {session_id}")
                return {
                    'session_id': session_id,
                    'status': 'ended'
                }
            else:
                raise ValueError(f"Session {session_id} not found")
                
        except Exception as e:
            logger.error(f"Error ending session: {str(e)}")
            raise
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a translation session"""
        if session_id in self.active_sessions:
            session_info = self.active_sessions[session_id]
            return {
                'session_id': session_id,
                'status': session_info['status'],
                'from_language': session_info['from_language'],
                'to_language': session_info['to_language']
            }
        return None
    
    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active translation sessions"""
        return {
            session_id: {
                'status': info['status'],
                'from_language': info['from_language'],
                'to_language': info['to_language']
            }
            for session_id, info in self.active_sessions.items()
        }
