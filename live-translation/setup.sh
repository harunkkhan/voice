#!/bin/bash

echo "🚀 Setting up Live Translation App..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed. Please install Python 3.8+ and try again."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed. Please install Node.js 16+ and try again."
    exit 1
fi

echo "✅ Python and Node.js are installed"

# Setup backend
echo "📦 Setting up backend..."
cd backend

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp env.example .env
    echo "⚠️  Please edit backend/.env and add your actual API keys!"
fi

cd ..

# Setup frontend
echo "📦 Setting up frontend..."
cd frontend

# Install Node.js dependencies
echo "Installing Node.js dependencies..."
npm install

cd ..

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit backend/.env and add your API keys:"
echo "   - TWILIO_ACCOUNT_SID"
echo "   - TWILIO_AUTH_TOKEN" 
echo "   - TWILIO_PHONE_NUMBER"
echo "   - OPENAI_API_KEY"
echo ""
echo "2. Start the backend:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python app.py"
echo ""
echo "3. Start the frontend (in a new terminal):"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "4. Open http://localhost:3000 in your browser"
echo ""
echo "Happy translating! 🌍"
