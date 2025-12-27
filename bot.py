#!/usr/bin/env python3
"""
Telegram PDF Utility Bot - Fixed for Render
"""

import os
import sys
import time
import tempfile
import logging
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MONGODB_URI = os.getenv('MONGODB_URI', '')
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Import Telegram bot
import telebot
from telebot import types

# Initialize bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Import local modules
try:
    from pdf_processor import PDFProcessor
    from session_manager import SessionManager
    from utils.validators import FileValidator
    from utils.file_cleaner import TempFileManager
except ImportError as e:
    logger.error(f"Import error: {e}")
    # Create fallback implementations
    class PDFProcessor:
        def merge_pdfs(self, *args, **kwargs):
            raise NotImplementedError("PDFProcessor not available")
    
    class SessionManager:
        def __init__(self, *args, **kwargs):
            self.sessions = {}
        
        def get_session(self, chat_id):
            return self.sessions.get(chat_id, {})
        
        def update_session(self, chat_id, **kwargs):
            if chat_id not in self.sessions:
                self.sessions[chat_id] = {}
            self.sessions[chat_id].update(kwargs)
    
    class FileValidator:
        def is_pdf_file(self, filename):
            return filename.lower().endswith('.pdf')
    
    class TempFileManager:
        def __init__(self):
            self.temp_dir = tempfile.mkdtemp()
    
    logger.warning("Using fallback implementations")

# Initialize components
pdf_processor = PDFProcessor()
file_validator = FileValidator(max_size=MAX_FILE_SIZE)
temp_manager = TempFileManager()

# Use MongoDB if URI is provided, otherwise use memory
if MONGODB_URI and MONGODB_URI != 'your_mongodb_uri_here':
    session_manager = SessionManager(MONGODB_URI)
else:
    # Use simple memory session manager
    session_manager = SessionManager('')

# Bot States
class BotState:
    WAITING = "waiting"
    UPLOADING_MERGE = "uploading_merge"
    UPLOADING_RENAME = "uploading_rename"
    UPLOADING_WATERMARK = "uploading_watermark"
    WAITING_FILENAME = "waiting_filename"
    WAITING_WATERMARK_TEXT = "waiting_watermark_text"
    WAITING_WATERMARK_POSITION = "waiting_watermark_position"
    WAITING_WATERMARK_OPACITY = "waiting_watermark_opacity"

# Flask app for webhook
from flask import Flask, request, jsonify
app = Flask(__name__)

# Helper Functions
def get_main_menu():
    """Create main menu keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("📄 Merge PDFs", callback_data='merge'),
        types.InlineKeyboardButton("✏️ Rename PDF", callback_data='rename'),
        types.InlineKeyboardButton("💧 Add Watermark", callback_data='watermark'),
        types.InlineKeyboardButton("❓ Help", callback_data='help'),
        types.InlineKeyboardButton("🗑️ Clear Session", callback_data='clear')
    ]
    markup.add(*buttons[:3])
    markup.add(*buttons[3:])
    return markup

def get_watermark_position_menu():
    """Create watermark position selection keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    positions = [
        ('Center', 'center'),
        ('Top', 'top'),
        ('Bottom', 'bottom'),
        ('Diagonal', 'diagonal')
    ]
    for text, data in positions:
        markup.add(types.InlineKeyboardButton(text, callback_data=f'pos_{data}'))
    return markup

def get_opacity_menu():
    """Create opacity selection keyboard"""
    markup = types.InlineKeyboardMarkup(row_width=4)
    opacities = ['0.3', '0.5', '0.7', '0.9']
    for op in opacities:
        markup.add(types.InlineKeyboardButton(f"{op}", callback_data=f"op_{op}"))
    return markup

# Command Handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handle /start command"""
    welcome_text = """
🤖 *Welcome to PDF Utility Bot!*

I can help you with:
• 📄 *Merge PDFs* - Combine multiple PDFs into one
• ✏️ *Rename PDF* - Change PDF filename
• 💧 *Add Watermark* - Add text watermark to PDF

*How to use:*
1. Choose an option below
2. Follow the step-by-step instructions
3. Download your processed file

⚠️ *Limits:* Max 20MB per file, PDF only
"""
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )
    
    # Initialize session
    session_manager.update_session(
        chat_id=message.chat.id,
        state=BotState.WAITING
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    """Handle /help command"""
    help_text = """
📚 *Available Commands:*
/start - Show main menu
/help - Show this help message
/cancel - Cancel current operation

🔧 *Features:*
1. *Merge PDFs*: Upload multiple PDFs, then confirm to merge
2. *Rename PDF*: Upload PDF and provide new filename
3. *Add Watermark*: Upload PDF, then specify text, position, and opacity

⚠️ *Important:*
• Only PDF files accepted
• Max file size: 20MB
• Files are deleted after processing
• One operation at a time
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['cancel'])
def cancel_operation(message):
    """Cancel current operation"""
    session_manager.update_session(
        message.chat.id,
        state=BotState.WAITING
    )
    
    bot.send_message(
        message.chat.id,
        "✅ Operation cancelled. What would you like to do next?",
        reply_markup=get_main_menu()
    )

# Callback Query Handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """Handle all callback queries"""
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    try:
        if call.data == 'merge':
            handle_merge_start(chat_id, message_id)
        elif call.data == 'rename':
            handle_rename_start(chat_id, message_id)
        elif call.data == 'watermark':
            handle_watermark_start(chat_id, message_id)
        elif call.data == 'help':
            bot.answer_callback_query(call.id)
            send_help(call.message)
        elif call.data == 'clear':
            handle_clear_session(chat_id, message_id, call.id)
        elif call.data == 'confirm_merge':
            handle_merge_confirm(chat_id, message_id, call.id)
        elif call.data.startswith('pos_'):
            handle_watermark_position(chat_id, call.data, call.id)
        elif call.data.startswith('op_'):
            handle_watermark_opacity(chat_id, call.data, call.id)
        else:
            bot.answer_callback_query(call.id, "Unknown command")
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(
            call.id,
            "❌ An error occurred. Please try again.",
            show_alert=True
        )

def handle_merge_start(chat_id, message_id):
    """Start merge operation"""
    session_manager.update_session(
        chat_id,
        state=BotState.UPLOADING_MERGE,
        data={'files': []}
    )
    
    instruction = """
📄 *Merge PDFs Mode*

*How to merge:*
1. Send me PDF files one by one
2. Files will be merged in the order you send them
3. Click ✅ Confirm Merge when done
4. Click ❌ Cancel to start over

⚠️ *Note:* Only PDF files accepted, max 20MB each

Send your first PDF file now...
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data='clear'))
    
    try:
        bot.edit_message_text(
            instruction,
            chat_id,
            message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except:
        bot.send_message(
            chat_id,
            instruction,
            parse_mode='Markdown',
            reply_markup=markup
        )

def handle_rename_start(chat_id, message_id):
    """Start rename operation"""
    session_manager.update_session(
        chat_id,
        state=BotState.UPLOADING_RENAME
    )
    
    instruction = """
✏️ *Rename PDF Mode*

Please send me the PDF file you want to rename.
I'll ask for the new filename afterwards.

⚠️ *Note:* Only PDF files accepted, max 20MB
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data='clear'))
    
    try:
        bot.edit_message_text(
            instruction,
            chat_id,
            message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except:
        bot.send_message(
            chat_id,
            instruction,
            parse_mode='Markdown',
            reply_markup=markup
        )

def handle_watermark_start(chat_id, message_id):
    """Start watermark operation"""
    session_manager.update_session(
        chat_id,
        state=BotState.UPLOADING_WATERMARK
    )
    
    instruction = """
💧 *Add Watermark Mode*

Please send me the PDF file you want to watermark.
Then I'll ask for:
1. Watermark text
2. Position (center, top, bottom, diagonal)
3. Opacity (transparency level)

⚠️ *Note:* Only PDF files accepted, max 20MB
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data='clear'))
    
    try:
        bot.edit_message_text(
            instruction,
            chat_id,
            message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )
    except:
        bot.send_message(
            chat_id,
            instruction,
            parse_mode='Markdown',
            reply_markup=markup
        )

def handle_clear_session(chat_id, message_id, callback_id=None):
    """Clear user session"""
    session_manager.update_session(
        chat_id,
        state=BotState.WAITING,
        data={}
    )
    
    if callback_id:
        bot.answer_callback_query(callback_id, "✅ Session cleared")
    
    bot.send_message(
        chat_id,
        "✅ Session cleared. What would you like to do?",
        reply_markup=get_main_menu()
    )

def handle_merge_confirm(chat_id, message_id, callback_id):
    """Confirm and process merge"""
    session = session_manager.get_session(chat_id)
    if not session or 'files' not in session.get('data', {}):
        bot.answer_callback_query(callback_id, "❌ No files to merge")
        return
    
    files = session['data']['files']
    if len(files) < 2:
        bot.answer_callback_query(
            callback_id,
            "❌ Need at least 2 PDFs to merge",
            show_alert=True
        )
        return
    
    # Process merge
    bot.answer_callback_query(callback_id, "🔄 Merging PDFs...")
    bot.send_message(chat_id, "🔄 Merging your PDFs... This may take a moment.")
    
    try:
        # Create temp output file
        with tempfile.NamedTemporaryFile(suffix='_merged.pdf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Merge PDFs
        pdf_processor.merge_pdfs(files, output_path)
        
        # Send merged file
        with open(output_path, 'rb') as file:
            bot.send_document(
                chat_id,
                file,
                caption="✅ PDFs merged successfully!",
                visible_file_name="merged_document.pdf"
            )
        
        # Cleanup
        try:
            os.unlink(output_path)
            for file_path in files:
                if os.path.exists(file_path):
                    os.unlink(file_path)
        except:
            pass
        
        # Clear session
        session_manager.update_session(chat_id, state=BotState.WAITING, data={})
        
        # Show main menu
        bot.send_message(
            chat_id,
            "What would you like to do next?",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Merge error: {e}")
        bot.send_message(
            chat_id,
            f"❌ Error merging PDFs: {str(e)[:200]}"
        )

def handle_watermark_position(chat_id, callback_data, callback_id):
    """Handle watermark position selection"""
    position = callback_data.replace('pos_', '')
    
    session = session_manager.get_session(chat_id)
    if session:
        data = session.get('data', {})
        data['position'] = position
        session_manager.update_session(chat_id, data=data)
    
    bot.answer_callback_query(callback_id, f"✅ Position: {position}")
    
    # Ask for opacity
    bot.send_message(
        chat_id,
        f"📍 Position set to: *{position}*\n\n"
        "Now choose opacity (transparency level):",
        parse_mode='Markdown',
        reply_markup=get_opacity_menu()
    )

def handle_watermark_opacity(chat_id, callback_data, callback_id):
    """Handle watermark opacity selection"""
    opacity = float(callback_data.replace('op_', ''))
    bot.answer_callback_query(callback_id, f"✅ Opacity: {opacity}")
    
    # Process watermark
    process_watermark(chat_id, opacity)

# Message Handlers
@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Handle uploaded PDF files"""
    chat_id = message.chat.id
    
    # Get file info
    file_info = bot.get_file(message.document.file_id)
    file_name = message.document.file_name or 'document.pdf'
    
    # Validate file
    if not file_validator.is_pdf_file(file_name):
        bot.reply_to(
            message,
            "❌ Please send a PDF file only. Other formats are not supported."
        )
        return
    
    # Check file size
    if message.document.file_size and message.document.file_size > MAX_FILE_SIZE:
        bot.reply_to(
            message,
            f"❌ File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
        return
    
    # Download file
    bot.send_chat_action(chat_id, 'upload_document')
    
    try:
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(
            suffix='.pdf',
            delete=False,
            dir=temp_manager.temp_dir
        )
        temp_file.write(downloaded_file)
        temp_file.close()
        file_path = temp_file.name
        
        # Handle based on current state
        session = session_manager.get_session(chat_id)
        state = session.get('state', BotState.WAITING) if session else BotState.WAITING
        
        if state == BotState.UPLOADING_MERGE:
            handle_merge_file(chat_id, file_path, file_name)
        elif state == BotState.UPLOADING_RENAME:
            handle_rename_file(chat_id, file_path)
        elif state == BotState.UPLOADING_WATERMARK:
            handle_watermark_file(chat_id, file_path)
        else:
            bot.reply_to(
                message,
                "Please select an option from the menu first.",
                reply_markup=get_main_menu()
            )
            os.unlink(file_path)
            
    except Exception as e:
        logger.error(f"File handling error: {e}")
        bot.reply_to(message, f"❌ Error processing file: {str(e)[:200]}")

def handle_merge_file(chat_id, file_path, file_name):
    """Handle file upload for merge"""
    session = session_manager.get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Session expired. Please start again.")
        return
    
    # Add file to session
    data = session.get('data', {})
    if 'files' not in data:
        data['files'] = []
    
    data['files'].append(file_path)
    session_manager.update_session(chat_id, data=data)
    
    # Show confirmation options
    file_count = len(data['files'])
    markup = types.InlineKeyboardMarkup()
    if file_count >= 2:
        markup.add(types.InlineKeyboardButton(
            f"✅ Confirm Merge ({file_count} files)", 
            callback_data='confirm_merge'
        ))
    markup.add(types.InlineKeyboardButton("➕ Add More PDFs", callback_data='merge'))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data='clear'))
    
    bot.send_message(
        chat_id,
        f"📄 *{file_name}* added!\n\n"
        f"Total files: {file_count}\n\n"
        "Click 'Confirm Merge' when ready, or send more PDFs.",
        parse_mode='Markdown',
        reply_markup=markup
    )

def handle_rename_file(chat_id, file_path):
    """Handle file upload for rename"""
    # Update session
    session_manager.update_session(
        chat_id,
        state=BotState.WAITING_FILENAME,
        data={'file_path': file_path}
    )
    
    bot.send_message(
        chat_id,
        "✅ PDF received!\n\n"
        "Now please send me the *new filename* (without .pdf extension):\n"
        "Example: `my_document_v2`",
        parse_mode='Markdown'
    )

def handle_watermark_file(chat_id, file_path):
    """Handle file upload for watermark"""
    # Update session
    session_manager.update_session(
        chat_id,
        state=BotState.WAITING_WATERMARK_TEXT,
        data={'file_path': file_path}
    )
    
    bot.send_message(
        chat_id,
        "✅ PDF received!\n\n"
        "Now please send me the *watermark text* you want to add:",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Handle text messages for various states"""
    chat_id = message.chat.id
    text = message.text.strip()
    
    session = session_manager.get_session(chat_id)
    if not session:
        bot.reply_to(message, "❌ Session expired. Please use /start")
        return
    
    state = session.get('state', BotState.WAITING)
    
    if state == BotState.WAITING_FILENAME:
        handle_rename_filename(chat_id, text, session)
    elif state == BotState.WAITING_WATERMARK_TEXT:
        handle_watermark_text(chat_id, text, session)
    else:
        # Default response
        bot.reply_to(
            message,
            "Please select an option from the menu:",
            reply_markup=get_main_menu()
        )

def handle_rename_filename(chat_id, new_name, session):
    """Handle rename filename input"""
    file_path = session['data'].get('file_path')
    if not file_path or not os.path.exists(file_path):
        bot.send_message(chat_id, "❌ File not found. Please upload again.")
        return
    
    # Clean filename
    new_name = new_name.replace('.pdf', '').strip()
    if not new_name:
        bot.send_message(chat_id, "❌ Invalid filename. Please try again.")
        return
    
    # Process rename
    bot.send_chat_action(chat_id, 'upload_document')
    
    try:
        # Create renamed file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Copy file
        with open(file_path, 'rb') as src, open(output_path, 'wb') as dst:
            dst.write(src.read())
        
        # Send file
        with open(output_path, 'rb') as file:
            bot.send_document(
                chat_id,
                file,
                caption=f"✅ Renamed to: *{new_name}.pdf*",
                parse_mode='Markdown',
                visible_file_name=f"{new_name}.pdf"
            )
        
        # Cleanup
        try:
            os.unlink(file_path)
            os.unlink(output_path)
        except:
            pass
        
        # Clear session
        session_manager.update_session(chat_id, state=BotState.WAITING, data={})
        
        # Show menu
        bot.send_message(
            chat_id,
            "What would you like to do next?",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Rename error: {e}")
        bot.send_message(chat_id, f"❌ Error: {str(e)[:200]}")

def handle_watermark_text(chat_id, text, session):
    """Handle watermark text input"""
    if not text:
        bot.send_message(chat_id, "❌ Please provide watermark text.")
        return
    
    # Update session
    data = session.get('data', {})
    data['watermark_text'] = text[:100]  # Limit length
    session_manager.update_session(chat_id, data=data)
    
    # Ask for position
    bot.send_message(
        chat_id,
        f"✅ Watermark text: *{text[:50]}*\n\n"
        "Now choose position for the watermark:",
        parse_mode='Markdown',
        reply_markup=get_watermark_position_menu()
    )

def process_watermark(chat_id, opacity):
    """Process watermark with all parameters"""
    session = session_manager.get_session(chat_id)
    if not session:
        bot.send_message(chat_id, "❌ Session expired")
        return
    
    data = session.get('data', {})
    
    if not all(k in data for k in ['file_path', 'watermark_text', 'position']):
        bot.send_message(chat_id, "❌ Missing watermark parameters")
        return
    
    file_path = data['file_path']
    if not os.path.exists(file_path):
        bot.send_message(chat_id, "❌ File not found")
        return
    
    bot.send_chat_action(chat_id, 'upload_document')
    
    try:
        # Create output file
        with tempfile.NamedTemporaryFile(suffix='_watermarked.pdf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Add watermark
        pdf_processor.add_watermark(
            input_path=file_path,
            output_path=output_path,
            text=data['watermark_text'],
            position=data['position'],
            opacity=opacity
        )
        
        # Send file
        with open(output_path, 'rb') as file:
            bot.send_document(
                chat_id,
                file,
                caption="✅ Watermark added successfully!",
                visible_file_name="watermarked_document.pdf"
            )
        
        # Cleanup
        try:
            os.unlink(file_path)
            os.unlink(output_path)
        except:
            pass
        
        # Clear session
        session_manager.update_session(chat_id, state=BotState.WAITING, data={})
        
        # Show menu
        bot.send_message(
            chat_id,
            "What would you like to do next?",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Watermark error: {e}")
        bot.send_message(
            chat_id,
            f"❌ Error adding watermark: {str(e)[:200]}"
        )

# Flask Routes
@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'Telegram PDF Utility Bot',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

@app.route('/setwebhook', methods=['GET'])
def set_webhook():
    if RENDER_EXTERNAL_URL:
        try:
            bot.remove_webhook()
            time.sleep(1)
            webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
            bot.set_webhook(url=webhook_url)
            return f'Webhook set to: {webhook_url}'
        except Exception as e:
            return f'Error setting webhook: {str(e)}', 500
    return 'RENDER_EXTERNAL_URL not set', 400

# Main entry point
if __name__ == '__main__':
    # Get port from environment (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    # Set webhook if in production
    if RENDER_EXTERNAL_URL and 'localhost' not in RENDER_EXTERNAL_URL:
        logger.info(f"Starting in production mode on port {port}")
        logger.info(f"External URL: {RENDER_EXTERNAL_URL}")
        
        # Try to set webhook
        try:
            webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
            logger.info(f"Setting webhook to: {webhook_url}")
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=webhook_url)
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
        
        # Start Flask server
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Use polling for local development
        logger.info("Starting in development mode with polling...")
        bot.remove_webhook()
        bot.polling(none_stop=True, timeout=60)