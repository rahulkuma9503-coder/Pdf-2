#!/usr/bin/env python3
"""
Telegram PDF Utility Bot - Working Version
Uses python-telegram-bot 13.15 (stable)
"""

import os
import sys
import tempfile
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Import Telegram bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler
)

# Import PDF processor
try:
    from pdf_processor import PDFProcessor
    pdf_processor = PDFProcessor()
except ImportError:
    # Simple fallback PDF processor
    class PDFProcessor:
        def merge_pdfs(self, input_paths, output_path):
            from PyPDF2 import PdfMerger
            merger = PdfMerger()
            for pdf in input_paths:
                merger.append(pdf)
            merger.write(output_path)
            merger.close()
        
        def add_watermark(self, input_path, output_path, text, position='center', opacity=0.3):
            from PyPDF2 import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from io import BytesIO
            
            # Create watermark
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)
            can.setFillAlpha(opacity)
            can.setFont("Helvetica-Bold", 36)
            can.setFillColorRGB(0.5, 0.5, 0.5)
            
            # Position
            if position == 'center':
                can.drawCentredString(300, 400, text)
            elif position == 'top':
                can.drawCentredString(300, 700, text)
            elif position == 'bottom':
                can.drawCentredString(300, 100, text)
            elif position == 'diagonal':
                can.rotate(45)
                can.drawCentredString(300, 300, text)
            
            can.save()
            packet.seek(0)
            
            # Apply watermark
            reader = PdfReader(input_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                page.merge_page(PdfReader(packet).pages[0])
                writer.add_page(page)
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
    
    pdf_processor = PDFProcessor()

# Load environment variable
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable not set!")
    print("ERROR: TELEGRAM_TOKEN not set!")
    print("Please set the TELEGRAM_TOKEN environment variable on Render.com")
    sys.exit(1)

# Bot states
STATE_WAITING = 0
STATE_UPLOADING_MERGE = 1
STATE_UPLOADING_RENAME = 2
STATE_UPLOADING_WATERMARK = 3
STATE_WAITING_FILENAME = 4
STATE_WAITING_WATERMARK_TEXT = 5
STATE_WAITING_WATERMARK_POSITION = 6

# User session storage
user_sessions = {}

def get_user_session(chat_id):
    """Get or create user session"""
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {
            'state': STATE_WAITING,
            'data': {}
        }
    return user_sessions[chat_id]

def clear_user_session(chat_id):
    """Clear user session"""
    if chat_id in user_sessions:
        del user_sessions[chat_id]

def get_main_menu():
    """Create main menu"""
    keyboard = [
        [
            InlineKeyboardButton("📄 Merge PDFs", callback_data='merge'),
            InlineKeyboardButton("✏️ Rename PDF", callback_data='rename'),
        ],
        [
            InlineKeyboardButton("💧 Add Watermark", callback_data='watermark'),
            InlineKeyboardButton("❓ Help", callback_data='help'),
        ],
        [
            InlineKeyboardButton("🚫 Cancel", callback_data='cancel'),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_watermark_position_menu():
    """Create watermark position menu"""
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

def start(update, context):
    """Handle /start command"""
    welcome_text = """
🤖 *PDF Utility Bot*

I can help you with:
• 📄 Merge PDFs - Combine multiple PDFs
• ✏️ Rename PDF - Change PDF filename
• 💧 Add Watermark - Add text watermark

*How to use:*
1. Choose an option below
2. Follow the instructions
3. Download processed file

⚠️ *Limits:* Max 20MB per file, PDF only
"""
    
    update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_menu()
    )
    
    clear_user_session(update.effective_chat.id)
    return STATE_WAITING

def help_command(update, context):
    """Handle /help command"""
    help_text = """
📚 *Commands:*
/start - Show main menu
/help - Show help
/cancel - Cancel operation

🔧 *Features:*
1. *Merge PDFs*: Upload multiple PDFs to merge
2. *Rename PDF*: Upload PDF and provide new name
3. *Add Watermark*: Upload PDF, add text watermark

⚠️ *Important:*
• Only PDF files
• Max 20MB per file
• Files deleted after processing
"""
    
    update.message.reply_text(help_text, parse_mode='Markdown')
    return STATE_WAITING

def cancel(update, context):
    """Handle /cancel command"""
    clear_user_session(update.effective_chat.id)
    update.message.reply_text(
        "✅ Operation cancelled.",
        reply_markup=get_main_menu()
    )
    return STATE_WAITING

def button_handler(update, context):
    """Handle button callbacks"""
    query = update.callback_query
    query.answer()
    
    chat_id = update.effective_chat.id
    
    if query.data == 'merge':
        user_sessions[chat_id] = {
            'state': STATE_UPLOADING_MERGE,
            'data': {'files': []}
        }
        query.edit_message_text(
            text="📄 *Merge PDFs*\n\nSend me PDF files one by one. I'll merge them in order.\n\nSend first PDF now...",
            parse_mode='Markdown'
        )
        return STATE_UPLOADING_MERGE
    
    elif query.data == 'rename':
        user_sessions[chat_id] = {
            'state': STATE_UPLOADING_RENAME,
            'data': {}
        }
        query.edit_message_text(
            text="✏️ *Rename PDF*\n\nSend me the PDF file you want to rename.",
            parse_mode='Markdown'
        )
        return STATE_UPLOADING_RENAME
    
    elif query.data == 'watermark':
        user_sessions[chat_id] = {
            'state': STATE_UPLOADING_WATERMARK,
            'data': {}
        }
        query.edit_message_text(
            text="💧 *Add Watermark*\n\nSend me the PDF file you want to watermark.",
            parse_mode='Markdown'
        )
        return STATE_UPLOADING_WATERMARK
    
    elif query.data == 'help':
        help_command(update, context)
        return STATE_WAITING
    
    elif query.data == 'cancel':
        cancel(update, context)
        return STATE_WAITING
    
    elif query.data.startswith('pos_'):
        position = query.data.replace('pos_', '')
        chat_id = update.effective_chat.id
        
        if chat_id in user_sessions:
            user_sessions[chat_id]['data']['position'] = position
            
            # Process watermark
            process_watermark(chat_id, context.bot)
        
        return STATE_WAITING
    
    return STATE_WAITING

def handle_document(update, context):
    """Handle uploaded PDF files"""
    chat_id = update.effective_chat.id
    document = update.message.document
    
    # Check if PDF
    if not document.file_name.lower().endswith('.pdf'):
        update.message.reply_text("❌ Please send a PDF file only.")
        return STATE_WAITING
    
    # Check size (20MB max)
    if document.file_size > 20 * 1024 * 1024:
        update.message.reply_text("❌ File too large. Max 20MB.")
        return STATE_WAITING
    
    # Download file
    update.message.reply_text("📥 Downloading...")
    
    try:
        file = context.bot.get_file(document.file_id)
        downloaded = file.download_as_bytearray()
        
        # Save temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(downloaded)
            temp_path = f.name
        
        # Handle based on state
        if chat_id not in user_sessions:
            update.message.reply_text("Please use /start first")
            os.unlink(temp_path)
            return STATE_WAITING
        
        state = user_sessions[chat_id]['state']
        
        if state == STATE_UPLOADING_MERGE:
            return handle_merge_doc(update, context, chat_id, temp_path, document.file_name)
        
        elif state == STATE_UPLOADING_RENAME:
            user_sessions[chat_id]['data']['file_path'] = temp_path
            user_sessions[chat_id]['state'] = STATE_WAITING_FILENAME
            update.message.reply_text("✅ PDF received! Now send me the new filename (without .pdf):")
            return STATE_WAITING_FILENAME
        
        elif state == STATE_UPLOADING_WATERMARK:
            user_sessions[chat_id]['data']['file_path'] = temp_path
            user_sessions[chat_id]['state'] = STATE_WAITING_WATERMARK_TEXT
            update.message.reply_text("✅ PDF received! Now send me the watermark text:")
            return STATE_WAITING_WATERMARK_TEXT
        
        else:
            update.message.reply_text("Please select an option first", reply_markup=get_main_menu())
            os.unlink(temp_path)
            return STATE_WAITING
    
    except Exception as e:
        logger.error(f"Error: {e}")
        update.message.reply_text(f"❌ Error: {str(e)[:100]}")
        return STATE_WAITING

def handle_merge_doc(update, context, chat_id, file_path, file_name):
    """Handle merge document"""
    user_sessions[chat_id]['data']['files'].append(file_path)
    file_count = len(user_sessions[chat_id]['data']['files'])
    
    update.message.reply_text(
        f"✅ Added: {file_name}\nTotal files: {file_count}\n\nSend another PDF or wait for merge..."
    )
    
    # Auto-merge after 2 files
    if file_count >= 2:
        process_merge(chat_id, context.bot)
    
    return STATE_UPLOADING_MERGE

def process_merge(chat_id, bot):
    """Process merge operation"""
    try:
        files = user_sessions[chat_id]['data']['files']
        
        if len(files) < 2:
            bot.send_message(chat_id, "Need at least 2 PDFs to merge")
            return
        
        bot.send_message(chat_id, "🔄 Merging PDFs...")
        
        # Create output file
        with tempfile.NamedTemporaryFile(suffix='_merged.pdf', delete=False) as f:
            output_path = f.name
        
        # Merge
        pdf_processor.merge_pdfs(files, output_path)
        
        # Send result
        with open(output_path, 'rb') as file:
            bot.send_document(
                chat_id=chat_id,
                document=file,
                caption="✅ Merged successfully!",
                filename="merged.pdf"
            )
        
        # Cleanup
        for f in files:
            try:
                os.unlink(f)
            except:
                pass
        os.unlink(output_path)
        
        # Clear session
        clear_user_session(chat_id)
        bot.send_message(chat_id, "✅ Done! What next?", reply_markup=get_main_menu())
    
    except Exception as e:
        logger.error(f"Merge error: {e}")
        bot.send_message(chat_id, f"❌ Merge failed: {str(e)[:100]}")

def handle_text(update, context):
    """Handle text messages"""
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    if chat_id not in user_sessions:
        update.message.reply_text("Please use /start first", reply_markup=get_main_menu())
        return STATE_WAITING
    
    state = user_sessions[chat_id]['state']
    
    if state == STATE_WAITING_FILENAME:
        return handle_rename(update, context, chat_id, text)
    
    elif state == STATE_WAITING_WATERMARK_TEXT:
        user_sessions[chat_id]['data']['watermark_text'] = text
        user_sessions[chat_id]['state'] = STATE_WAITING_WATERMARK_POSITION
        update.message.reply_text(
            f"✅ Text: {text[:50]}\n\nChoose position:",
            reply_markup=get_watermark_position_menu()
        )
        return STATE_WAITING_WATERMARK_POSITION
    
    else:
        update.message.reply_text("Please select an option", reply_markup=get_main_menu())
        return STATE_WAITING

def handle_rename(update, context, chat_id, new_name):
    """Handle rename operation"""
    try:
        file_path = user_sessions[chat_id]['data'].get('file_path')
        if not file_path or not os.path.exists(file_path):
            update.message.reply_text("❌ File not found")
            return STATE_WAITING
        
        # Clean name
        new_name = new_name.replace('.pdf', '').strip()
        if not new_name:
            update.message.reply_text("❌ Invalid name")
            return STATE_WAITING
        
        update.message.reply_text("🔄 Renaming...")
        
        # Create output file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            output_path = f.name
        
        # Copy file (simulated rename)
        with open(file_path, 'rb') as src, open(output_path, 'wb') as dst:
            dst.write(src.read())
        
        # Send result
        with open(output_path, 'rb') as file:
            context.bot.send_document(
                chat_id=chat_id,
                document=file,
                caption=f"✅ Renamed to: {new_name}.pdf",
                filename=f"{new_name}.pdf"
            )
        
        # Cleanup
        os.unlink(file_path)
        os.unlink(output_path)
        
        # Clear session
        clear_user_session(chat_id)
        update.message.reply_text("✅ Done! What next?", reply_markup=get_main_menu())
        return STATE_WAITING
    
    except Exception as e:
        logger.error(f"Rename error: {e}")
        update.message.reply_text(f"❌ Error: {str(e)[:100]}")
        return STATE_WAITING

def process_watermark(chat_id, bot):
    """Process watermark operation"""
    try:
        data = user_sessions[chat_id]['data']
        file_path = data.get('file_path')
        text = data.get('watermark_text')
        position = data.get('position')
        
        if not all([file_path, text, position]):
            bot.send_message(chat_id, "❌ Missing data")
            return
        
        if not os.path.exists(file_path):
            bot.send_message(chat_id, "❌ File not found")
            return
        
        bot.send_message(chat_id, "🔄 Adding watermark...")
        
        # Create output file
        with tempfile.NamedTemporaryFile(suffix='_watermarked.pdf', delete=False) as f:
            output_path = f.name
        
        # Add watermark
        pdf_processor.add_watermark(file_path, output_path, text, position)
        
        # Send result
        with open(output_path, 'rb') as file:
            bot.send_document(
                chat_id=chat_id,
                document=file,
                caption="✅ Watermark added!",
                filename="watermarked.pdf"
            )
        
        # Cleanup
        os.unlink(file_path)
        os.unlink(output_path)
        
        # Clear session
        clear_user_session(chat_id)
        bot.send_message(chat_id, "✅ Done! What next?", reply_markup=get_main_menu())
    
    except Exception as e:
        logger.error(f"Watermark error: {e}")
        bot.send_message(chat_id, f"❌ Error: {str(e)[:100]}")

def error_handler(update, context):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_chat:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ An error occurred. Use /start to restart."
        )

def main():
    """Start the bot"""
    # Check token
    if not TOKEN:
        print("ERROR: TELEGRAM_TOKEN not set!")
        print("Please set the TELEGRAM_TOKEN environment variable")
        print("On Render.com: Environment → Add environment variable")
        sys.exit(1)
    
    print(f"Starting PDF Utility Bot with token: {TOKEN[:10]}...")
    
    # Create updater
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            STATE_WAITING: [
                CallbackQueryHandler(button_handler),
                CommandHandler('help', help_command),
                CommandHandler('cancel', cancel),
                MessageHandler(Filters.document, handle_document),
                MessageHandler(Filters.text, handle_text),
            ],
            STATE_UPLOADING_MERGE: [
                MessageHandler(Filters.document, handle_document),
                CommandHandler('cancel', cancel),
            ],
            STATE_UPLOADING_RENAME: [
                MessageHandler(Filters.document, handle_document),
                CommandHandler('cancel', cancel),
            ],
            STATE_UPLOADING_WATERMARK: [
                MessageHandler(Filters.document, handle_document),
                CommandHandler('cancel', cancel),
            ],
            STATE_WAITING_FILENAME: [
                MessageHandler(Filters.text, handle_text),
                CommandHandler('cancel', cancel),
            ],
            STATE_WAITING_WATERMARK_TEXT: [
                MessageHandler(Filters.text, handle_text),
                CommandHandler('cancel', cancel),
            ],
            STATE_WAITING_WATERMARK_POSITION: [
                CallbackQueryHandler(button_handler),
                CommandHandler('cancel', cancel),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    dp.add_handler(conv_handler)
    dp.add_error_handler(error_handler)
    
    # Start bot
    print("Bot is starting...")
    updater.start_polling()
    print("Bot is running! Press Ctrl+C to stop.")
    updater.idle()

if __name__ == '__main__':
    main()
