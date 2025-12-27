#!/usr/bin/env python3
"""
Telegram PDF Utility Bot - Working Version
Uses python-telegram-bot library (stable)
"""

import os
import sys
import tempfile
import logging
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import Telegram bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Import PDF processor
try:
    from pdf_processor import PDFProcessor
    pdf_processor = PDFProcessor()
except ImportError:
    # Fallback if PDF processor not available
    class PDFProcessor:
        def merge_pdfs(self, *args, **kwargs):
            raise Exception("PDF Processor not available")
    
    pdf_processor = PDFProcessor()

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# User session data (simple memory storage)
user_sessions = {}

# Bot states
class BotState:
    WAITING = "waiting"
    UPLOADING_MERGE = "uploading_merge"
    UPLOADING_RENAME = "uploading_rename"
    UPLOADING_WATERMARK = "uploading_watermark"
    WAITING_FILENAME = "waiting_filename"
    WAITING_WATERMARK_TEXT = "waiting_watermark_text"
    WAITING_WATERMARK_POSITION = "waiting_watermark_position"

def get_user_session(chat_id):
    """Get or create user session"""
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            'state': BotState.WAITING,
            'data': {}
        }
    return user_sessions[chat_id]

def update_user_session(chat_id, **kwargs):
    """Update user session"""
    session = get_user_session(chat_id)
    session.update(kwargs)
    user_sessions[chat_id] = session

def clear_user_session(chat_id):
    """Clear user session"""
    if chat_id in user_sessions:
        del user_sessions[chat_id]

def get_main_menu():
    """Create main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("📄 Merge PDFs", callback_data='merge'),
            InlineKeyboardButton("✏️ Rename PDF", callback_data='rename'),
        ],
        [
            InlineKeyboardButton("💧 Add Watermark", callback_data='watermark'),
            InlineKeyboardButton("❓ Help", callback_data='help'),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_watermark_position_menu():
    """Create watermark position selection keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("Center", callback_data='pos_center'),
            InlineKeyboardButton("Top", callback_data='pos_top'),
        ],
        [
            InlineKeyboardButton("Bottom", callback_data='pos_bottom'),
            InlineKeyboardButton("Diagonal", callback_data='pos_diagonal'),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )
    
    # Initialize session
    clear_user_session(update.effective_chat.id)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📚 *Available Commands:*
/start - Show main menu
/help - Show this help message
/cancel - Cancel current operation

🔧 *Features:*
1. *Merge PDFs*: Upload multiple PDFs, then confirm to merge
2. *Rename PDF*: Upload PDF and provide new filename
3. *Add Watermark*: Upload PDF, then specify text and position

⚠️ *Important:*
• Only PDF files accepted
• Max file size: 20MB
• Files are deleted after processing
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    clear_user_session(update.effective_chat.id)
    await update.message.reply_text(
        "✅ Operation cancelled. What would you like to do next?",
        reply_markup=get_main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    data = query.data
    
    if data == 'merge':
        await handle_merge_start(query, context)
    elif data == 'rename':
        await handle_rename_start(query, context)
    elif data == 'watermark':
        await handle_watermark_start(query, context)
    elif data == 'help':
        await help_command(update, context)
    elif data == 'confirm_merge':
        await handle_merge_confirm(query, context)
    elif data.startswith('pos_'):
        await handle_watermark_position(query, context)

async def handle_merge_start(query, context):
    """Start merge operation"""
    chat_id = query.message.chat_id
    
    update_user_session(
        chat_id,
        state=BotState.UPLOADING_MERGE,
        data={'files': []}
    )
    
    instruction = """
📄 *Merge PDFs Mode*

*How to merge:*
1. Send me PDF files one by one
2. Files will be merged in the order you send them
3. I'll automatically merge when you send multiple files

⚠️ *Note:* Only PDF files accepted, max 20MB each

Send your first PDF file now...
"""
    
    await query.edit_message_text(
        instruction,
        parse_mode='Markdown'
    )

async def handle_rename_start(query, context):
    """Start rename operation"""
    chat_id = query.message.chat_id
    
    update_user_session(
        chat_id,
        state=BotState.UPLOADING_RENAME
    )
    
    instruction = """
✏️ *Rename PDF Mode*

Please send me the PDF file you want to rename.
I'll ask for the new filename afterwards.

⚠️ *Note:* Only PDF files accepted, max 20MB
"""
    
    await query.edit_message_text(
        instruction,
        parse_mode='Markdown'
    )

async def handle_watermark_start(query, context):
    """Start watermark operation"""
    chat_id = query.message.chat_id
    
    update_user_session(
        chat_id,
        state=BotState.UPLOADING_WATERMARK
    )
    
    instruction = """
💧 *Add Watermark Mode*

Please send me the PDF file you want to watermark.
Then I'll ask for:
1. Watermark text
2. Position (center, top, bottom, diagonal)

⚠️ *Note:* Only PDF files accepted, max 20MB
"""
    
    await query.edit_message_text(
        instruction,
        parse_mode='Markdown'
    )

async def handle_merge_confirm(query, context):
    """Process merge confirmation"""
    chat_id = query.message.chat_id
    session = get_user_session(chat_id)
    
    if not session or 'files' not in session.get('data', {}):
        await query.message.reply_text("❌ No files to merge")
        return
    
    files = session['data']['files']
    if len(files) < 2:
        await query.message.reply_text("❌ Need at least 2 PDFs to merge")
        return
    
    await query.message.reply_text("🔄 Merging your PDFs... This may take a moment.")
    
    try:
        # Create temp output file
        with tempfile.NamedTemporaryFile(suffix='_merged.pdf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Merge PDFs
        pdf_processor.merge_pdfs(files, output_path)
        
        # Send merged file
        with open(output_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file,
                caption="✅ PDFs merged successfully!",
                filename="merged_document.pdf"
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
        clear_user_session(chat_id)
        
        # Show main menu
        await query.message.reply_text(
            "What would you like to do next?",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Merge error: {e}")
        await query.message.reply_text(f"❌ Error merging PDFs: {str(e)[:100]}")

async def handle_watermark_position(query, context):
    """Handle watermark position selection"""
    chat_id = query.message.chat_id
    position = query.data.replace('pos_', '')
    
    session = get_user_session(chat_id)
    if session:
        data = session.get('data', {})
        data['position'] = position
        update_user_session(chat_id, data=data)
    
    # Process watermark
    await process_watermark(chat_id, context)

async def process_watermark(chat_id, context):
    """Process watermark with all parameters"""
    session = get_user_session(chat_id)
    if not session:
        await context.bot.send_message(chat_id, "❌ Session expired")
        return
    
    data = session.get('data', {})
    
    if not all(k in data for k in ['file_path', 'watermark_text', 'position']):
        await context.bot.send_message(chat_id, "❌ Missing watermark parameters")
        return
    
    file_path = data['file_path']
    if not os.path.exists(file_path):
        await context.bot.send_message(chat_id, "❌ File not found")
        return
    
    await context.bot.send_message(chat_id, "🔄 Adding watermark...")
    
    try:
        # Create output file
        with tempfile.NamedTemporaryFile(suffix='_watermarked.pdf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Add watermark with fixed opacity
        pdf_processor.add_watermark(
            input_path=file_path,
            output_path=output_path,
            text=data['watermark_text'],
            position=data['position'],
            opacity=0.3  # Fixed opacity for simplicity
        )
        
        # Send file
        with open(output_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file,
                caption="✅ Watermark added successfully!",
                filename="watermarked_document.pdf"
            )
        
        # Cleanup
        try:
            os.unlink(file_path)
            os.unlink(output_path)
        except:
            pass
        
        # Clear session
        clear_user_session(chat_id)
        
        # Show menu
        await context.bot.send_message(
            chat_id,
            "What would you like to do next?",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Watermark error: {e}")
        await context.bot.send_message(
            chat_id,
            f"❌ Error adding watermark: {str(e)[:100]}"
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded PDF files"""
    chat_id = update.effective_chat.id
    document = update.message.document
    
    # Check if it's a PDF
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("❌ Please send a PDF file only.")
        return
    
    # Check file size
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
        return
    
    # Download file
    await update.message.reply_text("📥 Downloading file...")
    
    try:
        file = await context.bot.get_file(document.file_id)
        downloaded_file = await file.download_as_bytearray()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(downloaded_file)
            file_path = tmp_file.name
        
        # Handle based on current state
        session = get_user_session(chat_id)
        state = session.get('state', BotState.WAITING)
        
        if state == BotState.UPLOADING_MERGE:
            await handle_merge_file(chat_id, file_path, document.file_name, context)
        elif state == BotState.UPLOADING_RENAME:
            await handle_rename_file(chat_id, file_path, context)
        elif state == BotState.UPLOADING_WATERMARK:
            await handle_watermark_file(chat_id, file_path, context)
        else:
            await update.message.reply_text(
                "Please select an option from the menu first.",
                reply_markup=get_main_menu()
            )
            os.unlink(file_path)
            
    except Exception as e:
        logger.error(f"File handling error: {e}")
        await update.message.reply_text(f"❌ Error processing file: {str(e)[:100]}")

async def handle_merge_file(chat_id, file_path, file_name, context):
    """Handle file upload for merge"""
    session = get_user_session(chat_id)
    if not session:
        await context.bot.send_message(chat_id, "❌ Session expired. Please start again.")
        return
    
    # Add file to session
    data = session.get('data', {})
    if 'files' not in data:
        data['files'] = []
    
    data['files'].append(file_path)
    update_user_session(chat_id, data=data)
    
    # Show status
    file_count = len(data['files'])
    
    if file_count >= 2:
        # Auto-merge when we have at least 2 files
        await context.bot.send_message(
            chat_id,
            f"📄 *{file_name}* added!\n"
            f"Total files: {file_count}\n\n"
            "Merging files now...",
            parse_mode='Markdown'
        )
        
        # Process merge
        await process_merge(chat_id, context, data['files'])
    else:
        await context.bot.send_message(
            chat_id,
            f"📄 *{file_name}* added!\n"
            f"Total files: {file_count}\n\n"
            "Send another PDF to merge, or wait a moment...",
            parse_mode='Markdown'
        )

async def process_merge(chat_id, context, files):
    """Process the merge operation"""
    try:
        # Create temp output file
        with tempfile.NamedTemporaryFile(suffix='_merged.pdf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Merge PDFs
        pdf_processor.merge_pdfs(files, output_path)
        
        # Send merged file
        with open(output_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file,
                caption="✅ PDFs merged successfully!",
                filename="merged_document.pdf"
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
        clear_user_session(chat_id)
        
        # Show menu
        await context.bot.send_message(
            chat_id,
            "What would you like to do next?",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Merge error: {e}")
        await context.bot.send_message(chat_id, f"❌ Error merging PDFs: {str(e)[:100]}")

async def handle_rename_file(chat_id, file_path, context):
    """Handle file upload for rename"""
    # Update session
    update_user_session(
        chat_id,
        state=BotState.WAITING_FILENAME,
        data={'file_path': file_path}
    )
    
    await context.bot.send_message(
        chat_id,
        "✅ PDF received!\n\n"
        "Now please send me the *new filename* (without .pdf extension):\n"
        "Example: `my_document_v2`",
        parse_mode='Markdown'
    )

async def handle_watermark_file(chat_id, file_path, context):
    """Handle file upload for watermark"""
    # Update session
    update_user_session(
        chat_id,
        state=BotState.WAITING_WATERMARK_TEXT,
        data={'file_path': file_path}
    )
    
    await context.bot.send_message(
        chat_id,
        "✅ PDF received!\n\n"
        "Now please send me the *watermark text* you want to add:",
        parse_mode='Markdown'
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    session = get_user_session(chat_id)
    if not session:
        await update.message.reply_text("❌ Session expired. Please use /start")
        return
    
    state = session.get('state', BotState.WAITING)
    
    if state == BotState.WAITING_FILENAME:
        await handle_rename_filename(chat_id, text, session, context)
    elif state == BotState.WAITING_WATERMARK_TEXT:
        await handle_watermark_text(chat_id, text, session, context)
    else:
        await update.message.reply_text(
            "Please select an option from the menu:",
            reply_markup=get_main_menu()
        )

async def handle_rename_filename(chat_id, new_name, session, context):
    """Handle rename filename input"""
    file_path = session['data'].get('file_path')
    if not file_path or not os.path.exists(file_path):
        await context.bot.send_message(chat_id, "❌ File not found. Please upload again.")
        return
    
    # Clean filename
    new_name = new_name.replace('.pdf', '').strip()
    if not new_name:
        await context.bot.send_message(chat_id, "❌ Invalid filename. Please try again.")
        return
    
    await context.bot.send_message(chat_id, "🔄 Renaming file...")
    
    try:
        # Create renamed file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            output_path = tmp_file.name
        
        # Copy file
        with open(file_path, 'rb') as src, open(output_path, 'wb') as dst:
            dst.write(src.read())
        
        # Send file
        with open(output_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=file,
                caption=f"✅ Renamed to: *{new_name}.pdf*",
                parse_mode='Markdown',
                filename=f"{new_name}.pdf"
            )
        
        # Cleanup
        try:
            os.unlink(file_path)
            os.unlink(output_path)
        except:
            pass
        
        # Clear session
        clear_user_session(chat_id)
        
        # Show menu
        await context.bot.send_message(
            chat_id,
            "What would you like to do next?",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Rename error: {e}")
        await context.bot.send_message(chat_id, f"❌ Error: {str(e)[:100]}")

async def handle_watermark_text(chat_id, text, session, context):
    """Handle watermark text input"""
    if not text:
        await context.bot.send_message(chat_id, "❌ Please provide watermark text.")
        return
    
    # Update session
    data = session.get('data', {})
    data['watermark_text'] = text[:100]  # Limit length
    update_user_session(chat_id, data=data, state=BotState.WAITING_WATERMARK_POSITION)
    
    # Ask for position
    await context.bot.send_message(
        chat_id,
        f"✅ Watermark text: *{text[:50]}*\n\n"
        "Now choose position for the watermark:",
        parse_mode='Markdown',
        reply_markup=get_watermark_position_menu()
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ An error occurred. Please try again or use /start"
        )

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    print("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()