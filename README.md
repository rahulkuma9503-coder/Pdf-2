# Telegram PDF Utility Bot 🤖

A feature-rich Telegram bot for PDF manipulation hosted on Render.com.

## Features
- 📄 **Merge PDFs**: Combine multiple PDFs into one
- ✏️ **Rename PDF**: Change PDF filenames
- 💧 **Add Watermark**: Add text watermarks with custom positions and opacity
- 🗄️ **Session Management**: Track user workflows with MongoDB
- 🔒 **Security**: File validation, size limits, input sanitization
- 🧹 **Auto Cleanup**: Automatic temporary file cleanup

## Quick Deployment to Render

1. **Fork/Clone this repository**
2. **Get Telegram Bot Token** from [@BotFather](https://t.me/botfather)
3. **Optional**: Set up [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) for sessions
4. **Deploy to Render**:
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - Name: `pdf-telegram-bot`
     - Environment: `Python`
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `gunicorn bot:app --bind 0.0.0.0:$PORT`
   - Add Environment Variables:
     - `TELEGRAM_TOKEN`: Your bot token
     - `MONGODB_URI`: (Optional) MongoDB connection string
   - Click "Create Web Service"

5. **Set Webhook**:
   - Once deployed, visit: `https://your-app.onrender.com/setwebhook`
   - Or manually set: `https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://your-app.onrender.com/webhook`

## Local Development

1. **Clone and setup**:
```bash
git clone <your-repo>
cd pdf-telegram-bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
