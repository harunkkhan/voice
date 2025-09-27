import React, { useState, useEffect } from 'react'
import { Phone, PhoneOff, Globe, Mic, MicOff } from 'lucide-react'
import axios from 'axios'

const LANGUAGES = [
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ru', name: 'Russian' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ar', name: 'Arabic' },
  { code: 'hi', name: 'Hindi' }
]

const API_BASE_URL = 'http://localhost:5000'

function App() {
  const [phoneNumber, setPhoneNumber] = useState('')
  const [fromLanguage, setFromLanguage] = useState('en')
  const [toLanguage, setToLanguage] = useState('es')
  const [isCallActive, setIsCallActive] = useState(false)
  const [callSid, setCallSid] = useState(null)
  const [translations, setTranslations] = useState([])
  const [status, setStatus] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const startCall = async () => {
    if (!phoneNumber.trim()) {
      setError('Please enter a phone number')
      return
    }

    setIsLoading(true)
    setError('')
    setStatus('Initiating call...')

    try {
      const response = await axios.post(`${API_BASE_URL}/start-call`, {
        to_number: phoneNumber,
        from_language: fromLanguage,
        to_language: toLanguage
      })

      if (response.data.call_sid) {
        setCallSid(response.data.call_sid)
        setIsCallActive(true)
        setStatus('Call connected! Translation is active.')
        setTranslations([])
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to start call')
      setStatus('')
    } finally {
      setIsLoading(false)
    }
  }

  const endCall = async () => {
    if (!callSid) return

    setIsLoading(true)
    setStatus('Ending call...')

    try {
      await axios.post(`${API_BASE_URL}/end-call/${callSid}`)
      setIsCallActive(false)
      setCallSid(null)
      setStatus('Call ended successfully')
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to end call')
    } finally {
      setIsLoading(false)
    }
  }

  const getCallStatus = async () => {
    if (!callSid) return

    try {
      const response = await axios.get(`${API_BASE_URL}/call-status/${callSid}`)
      const callData = response.data
      
      if (callData.status === 'ended') {
        setIsCallActive(false)
        setCallSid(null)
        setStatus('Call ended')
      }
    } catch (err) {
      console.error('Error getting call status:', err)
    }
  }

  // Poll for call status when call is active
  useEffect(() => {
    let interval
    if (isCallActive && callSid) {
      interval = setInterval(getCallStatus, 5000) // Check every 5 seconds
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isCallActive, callSid])

  // Simulate receiving translations (in a real app, this would come from WebSocket)
  useEffect(() => {
    if (isCallActive) {
      const interval = setInterval(() => {
        // Simulate receiving a translation
        const sampleTranslations = [
          { original: 'Hello, how are you?', translated: 'Hola, ¿cómo estás?', confidence: 0.95 },
          { original: 'I am doing well, thank you', translated: 'Estoy bien, gracias', confidence: 0.92 },
          { original: 'What is your name?', translated: '¿Cuál es tu nombre?', confidence: 0.98 }
        ]
        
        const randomTranslation = sampleTranslations[Math.floor(Math.random() * sampleTranslations.length)]
        setTranslations(prev => [...prev, {
          id: Date.now(),
          ...randomTranslation,
          timestamp: new Date().toLocaleTimeString()
        }])
      }, 10000) // Add a new translation every 10 seconds

      return () => clearInterval(interval)
    }
  }, [isCallActive])

  return (
    <div className="container">
      <h1 className="title">
        <Globe size={32} style={{ marginRight: '0.5rem', verticalAlign: 'middle' }} />
        Live Translation
      </h1>

      {!isCallActive ? (
        <div>
          <div className="form-group">
            <label className="label" htmlFor="phone">
              Phone Number
            </label>
            <input
              id="phone"
              type="tel"
              className="input"
              placeholder="+1234567890"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
            />
          </div>

          <div className="language-selector">
            <div className="form-group">
              <label className="label" htmlFor="from-lang">
                From Language
              </label>
              <select
                id="from-lang"
                className="select"
                value={fromLanguage}
                onChange={(e) => setFromLanguage(e.target.value)}
              >
                {LANGUAGES.map(lang => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="label" htmlFor="to-lang">
                To Language
              </label>
              <select
                id="to-lang"
                className="select"
                value={toLanguage}
                onChange={(e) => setToLanguage(e.target.value)}
              >
                {LANGUAGES.map(lang => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            className="button"
            onClick={startCall}
            disabled={isLoading}
          >
            {isLoading ? (
              <div className="loading">
                <div className="spinner"></div>
                Starting Call...
              </div>
            ) : (
              <>
                <Phone size={20} style={{ marginRight: '0.5rem' }} />
                Start Translation Call
              </>
            )}
          </button>
        </div>
      ) : (
        <div>
          <div className="status success">
            <Mic size={20} style={{ marginRight: '0.5rem', verticalAlign: 'middle' }} />
            Call Active - Translation in Progress
          </div>

          <div className="translation-display">
            <h3 style={{ marginBottom: '1rem', color: '#333' }}>Live Translations</h3>
            {translations.length === 0 ? (
              <p style={{ color: '#666', textAlign: 'center', padding: '2rem' }}>
                Waiting for speech to translate...
              </p>
            ) : (
              translations.map(translation => (
                <div key={translation.id} className="translation-item">
                  <div className="translation-original">
                    <strong>{LANGUAGES.find(l => l.code === fromLanguage)?.name}:</strong> {translation.original}
                  </div>
                  <div className="translation-result">
                    <strong>{LANGUAGES.find(l => l.code === toLanguage)?.name}:</strong> {translation.translated}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '0.5rem' }}>
                    {translation.timestamp} • Confidence: {Math.round(translation.confidence * 100)}%
                  </div>
                </div>
              ))
            )}
          </div>

          <button
            className="button danger"
            onClick={endCall}
            disabled={isLoading}
          >
            {isLoading ? (
              <div className="loading">
                <div className="spinner"></div>
                Ending Call...
              </div>
            ) : (
              <>
                <PhoneOff size={20} style={{ marginRight: '0.5rem' }} />
                End Call
              </>
            )}
          </button>
        </div>
      )}

      {status && (
        <div className={`status ${error ? 'error' : 'info'}`}>
          {status}
        </div>
      )}

      {error && (
        <div className="status error">
          {error}
        </div>
      )}
    </div>
  )
}

export default App
