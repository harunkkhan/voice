# Live Translation App

A real-time translation app that allows users to have phone conversations with live translation between different languages using Twilio Voice API and ChatGPT Realtime API.

## Features

- **Real-time Translation**: Live translation during phone calls
- **Multiple Languages**: Support for 12+ languages including English, Spanish, French, German, etc.
- **Twilio Integration**: Uses Twilio Voice API for phone call handling
- **AI-Powered**: Leverages ChatGPT Realtime API for accurate translations
- **Modern UI**: Clean, responsive React frontend
- **WebSocket Support**: Real-time communication between frontend and backend

## Architecture

```
Frontend (React) ←→ Backend (Flask) ←→ Twilio Voice API
                           ↓
                    ChatGPT Realtime API
```

## Prerequisites

Before running this application, you'll need:

1. **Twilio Account**: Sign up at [twilio.com](https://www.twilio.com)
   - Get your Account SID and Auth Token
   - Purchase a phone number for making calls

2. **OpenAI Account**: Sign up at [openai.com](https://www.openai.com)
   - Get your API key
   - Ensure you have access to ChatGPT Realtime API

3. **Python 3.8+**: For the backend
4. **Node.js 16+**: For the frontend

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` and add your actual API keys:
   ```
   TWILIO_ACCOUNT_SID=your_actual_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_actual_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_actual_twilio_phone_number
   OPENAI_API_KEY=your_actual_openai_api_key
   ```

5. Run the backend server:
   ```bash
   python app.py
   ```

   The backend will be available at `http://localhost:5000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:3000`

## Usage

1. **Start the Application**: Make sure both backend and frontend are running

2. **Make a Call**:
   - Enter the phone number you want to call
   - Select the source language (what the caller will speak)
   - Select the target language (what the recipient will hear)
   - Click "Start Translation Call"

3. **During the Call**:
   - The app will connect the call through Twilio
   - Speech will be transcribed and translated in real-time
   - Translations will appear in the UI
   - Both parties can speak naturally in their preferred languages

4. **End the Call**: Click "End Call" to terminate the conversation

## API Endpoints

### Backend API

- `POST /start-call` - Initiate a translation call
- `POST /voice` - Handle incoming Twilio voice calls
- `POST /end-call/<call_sid>` - End an active call
- `GET /call-status/<call_sid>` - Get call status
- `GET /active-calls` - Get all active calls

### Request/Response Examples

**Start Call:**
```json
POST /start-call
{
  "to_number": "+1234567890",
  "from_language": "en",
  "to_language": "es"
}
```

**Response:**
```json
{
  "call_sid": "CA1234567890abcdef",
  "status": "initiated",
  "message": "Call started successfully"
}
```

## Configuration

### Supported Languages

The app supports the following languages:
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Russian (ru)
- Japanese (ja)
- Korean (ko)
- Chinese (zh)
- Arabic (ar)
- Hindi (hi)

### Twilio Configuration

Make sure your Twilio phone number is configured to handle voice calls and can make outbound calls to the target numbers.

## Development

### Project Structure

```
live-translation/
├── backend/
│   ├── app.py                 # Main Flask application
│   ├── translation_service.py # ChatGPT Realtime API integration
│   ├── requirements.txt       # Python dependencies
│   └── env.example           # Environment variables template
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main React component
│   │   ├── main.jsx          # React entry point
│   │   └── index.css         # Styles
│   ├── package.json          # Node.js dependencies
│   └── vite.config.js        # Vite configuration
└── README.md                 # This file
```

### Adding New Languages

To add support for new languages:

1. Add the language to the `LANGUAGES` array in `frontend/src/App.jsx`
2. Update the translation instructions in `backend/translation_service.py`
3. Test with the new language pair

## Troubleshooting

### Common Issues

1. **"Missing required environment variables"**
   - Make sure all environment variables are set in your `.env` file
   - Check that the variable names match exactly

2. **"Call failed to start"**
   - Verify your Twilio credentials are correct
   - Ensure your Twilio phone number is active
   - Check that you have sufficient Twilio credits

3. **"Translation not working"**
   - Verify your OpenAI API key is valid
   - Check that you have access to ChatGPT Realtime API
   - Ensure you have sufficient OpenAI credits

4. **Frontend not connecting to backend**
   - Make sure the backend is running on port 5000
   - Check the proxy configuration in `vite.config.js`
   - Verify CORS is enabled in the backend

### Logs

Check the console output for both frontend and backend for detailed error messages and debugging information.

## Security Notes

- Never commit your `.env` file with real API keys
- Use environment variables for all sensitive configuration
- Consider using a secrets management service for production deployments
- Implement proper authentication and authorization for production use

## License

This project is for educational and demonstration purposes. Make sure to comply with Twilio's and OpenAI's terms of service when using their APIs.

## Contributing

Feel free to submit issues and enhancement requests!

## Support

For issues related to:
- **Twilio**: Check [Twilio's documentation](https://www.twilio.com/docs)
- **OpenAI**: Check [OpenAI's documentation](https://platform.openai.com/docs)
- **This App**: Open an issue in this repository
