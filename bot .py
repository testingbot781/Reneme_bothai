import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from moviepy.editor import VideoFileClip
from PIL import Image
import logging
from pymongo import MongoClient

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Get env variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
LOG_GROUP = os.getenv("LOG_GROUP")
CHANNEL_ID = os.getenv("CHANNEL_ID")
FREEMIUM_LIMIT = int(os.getenv("FREEMIUM_LIMIT", 0))
MONGO_DB = os.getenv("MONGO_DB")

# MongoDB Setup
client = MongoClient(MONGO_DB)
db = client['telegram_bot']
user_data = db['users']

# In-memory counters
counter_map = {}

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not user_data.find_one({"user_id": user_id}):
        user_data.insert_one({"user_id": user_id, "count": 0})
    update.message.reply_text("👋 Bot Activated. Send a file and I'll rename it with new thumbnail!")

def clear(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_data.update_one({"user_id": user_id}, {"$set": {"count": 0}})
    counter_map[user_id] = 0
    update.message.reply_text("✅ Your rename counter and thumbnail cache has been cleared.")

def handle_file(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    file = update.message.document or update.message.video
    if not file:
        update.message.reply_text("❌ Unsupported file type.")
        return

    user = user_data.find_one({"user_id": user_id})
    count = user.get("count", 0) + 1
    user_data.update_one({"user_id": user_id}, {"$set": {"count": count}})

    file_id = file.file_id
    original_file_name = file.file_name if hasattr(file, 'file_name') else "file"
    new_file_name = f"{str(count).zfill(3)}. {original_file_name}"

    # Download file
    file_path = f"temp_{user_id}_{file.file_unique_id}"
    file_obj = context.bot.get_file(file_id)
    file_obj.download(file_path)

    # Generate thumbnail
    thumb_path = None
    try:
        clip = VideoFileClip(file_path)
        frame = clip.get_frame(1)
        image = Image.fromarray(frame)
        image.thumbnail((320, 320))
        thumb_path = f"{file_path}_thumb.jpg"
        image.save(thumb_path)
    except Exception as e:
        update.message.reply_text(f"⚠️ Thumbnail error: {e}")
        thumb_path = None

    # Send renamed file
    with open(file_path, 'rb') as f:
        context.bot.send_document(chat_id=update.effective_chat.id,
                                  document=f,
                                  filename=new_file_name,
                                  thumb=open(thumb_path, 'rb') if thumb_path else None)

    os.remove(file_path)
    if thumb_path:
        os.remove(thumb_path)

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("clear", clear))
    dp.add_handler(MessageHandler(Filters.document | Filters.video, handle_file))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()