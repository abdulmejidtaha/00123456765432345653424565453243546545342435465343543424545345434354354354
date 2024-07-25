import logging
import re
from datetime import datetime, timedelta
import pytz
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Define states for conversation
ASK_MEMBERSHIP, ASK_FIRST_NAME, ASK_MIDDLE_NAME, ASK_LAST_NAME, ASK_ID, ASK_BATCH, CONFIRM_INFO, ASK_FEEDBACK, THANK_YOU, SELECT_TIME_RANGE = range(10)

# URLs and IDs
GROUP_URL = "https://t.me/SCOME_ARSI"
CHANNEL_ID = 2157812543  # Channel ID to post feedback
FEEDBACK_RECIPIENT_ID = 1009374108  # Telegram user ID of the recipient

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store feedbacks
feedback_storage = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id

    try:
        member = await context.bot.get_chat_member(chat_id='@SCOME_ARSI', user_id=user_id)
        if member.status not in ['member', 'administrator', 'creator']:
            keyboard = [[InlineKeyboardButton("Join Group", url=GROUP_URL)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "You must join the SCOME-ARSI Telegram group to use this bot. Please join the group using the button below, and then /start again.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking group membership: {e}")
        keyboard = [[InlineKeyboardButton("Join Group", url=GROUP_URL)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "You must join the SCOME-ARSI Telegram group to use this bot. Please join the group using the button below.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Yes", callback_data='yes')],
        [InlineKeyboardButton("No", callback_data='no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Hi! Welcome to the SCOME-ARSI feedback bot.\nAre you an EMSA-ARSI member?",
        reply_markup=reply_markup
    )
    return ASK_MEMBERSHIP

async def ask_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['membership'] = query.data
    await query.edit_message_text("Please enter your first name:")
    return ASK_FIRST_NAME

async def ask_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['first_name'] = update.message.text
    await update.message.reply_text("Please enter your middle name:")
    return ASK_MIDDLE_NAME

async def ask_middle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['middle_name'] = update.message.text
    await update.message.reply_text("Please enter your last name:")
    return ASK_LAST_NAME

async def ask_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['last_name'] = update.message.text
    await update.message.reply_text("Great! Now, please enter your ID number (e.g., ABC/12345/67):")
    return ASK_ID

async def ask_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    id_number = update.message.text.replace(" ", "")
    pattern = re.compile(r'^[A-Za-z]+/\d+/\d{2}$')

    if pattern.match(id_number):
        context.user_data['id_number'] = id_number
        await update.message.reply_text("Thanks! Please enter your batch:")
        return ASK_BATCH
    else:
        await update.message.reply_text("Invalid format. Please enter your ID number in the format ABC/12345/67:")
        return ASK_ID

async def ask_batch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['batch'] = update.message.text
    membership = context.user_data['membership']
    first_name = context.user_data['first_name']
    middle_name = context.user_data['middle_name']
    last_name = context.user_data['last_name']
    id_number = context.user_data['id_number']
    batch = context.user_data['batch']

    info_text = (
        f"Membership: {membership}\n"
        f"Full Name: {first_name} {middle_name} {last_name}\n"
        f"ID Number: {id_number}\n"
        f"Batch: {batch}\n"
        "Is this information correct?"
    )
    keyboard = [
        [InlineKeyboardButton("Approve", callback_data='approve')],
        [InlineKeyboardButton("Change", callback_data='change')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(info_text, reply_markup=reply_markup)
    return CONFIRM_INFO

async def confirm_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'approve':
        await query.edit_message_text("Please enter your feedback:")
        return ASK_FEEDBACK
    else:
        await query.edit_message_text("Let's start over. Please enter your first name:")
        return ASK_FIRST_NAME

async def ask_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['feedback'] = update.message.text
    # Store the feedback
    feedback_storage.append({
        'timestamp': datetime.now(pytz.timezone('Africa/Nairobi')),
        **context.user_data
    })

    # Send feedback to the channel immediately
    feedback_text = (
        f"Timestamp: {datetime.now(pytz.timezone('Africa/Nairobi'))}\n"
        f"Membership: {context.user_data['membership']}\n"
        f"Full Name: {context.user_data['first_name']} {context.user_data['middle_name']} {context.user_data['last_name']}\n"
        f"ID Number: {context.user_data['id_number']}\n"
        f"Batch: {context.user_data['batch']}\n"
        f"Feedback: {context.user_data['feedback']}"
    )
    await context.bot.send_message(chat_id=CHANNEL_ID, text=feedback_text)

    keyboard = [
        [InlineKeyboardButton("Yes", callback_data='yes')],
        [InlineKeyboardButton("No", callback_data='no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Thank you for your feedback! Is there anything else you would like to share?", reply_markup=reply_markup)
    return THANK_YOU

async def thank_you(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'yes':
        await query.edit_message_text("Please share anything else you would like to add:")
        return ASK_FEEDBACK
    else:
        await query.edit_message_text("Your feedback has been submitted successfully! Goodbye! Have a nice day!")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Feedback collection cancelled. Have a nice day!')
    return ConversationHandler.END

def get_feedback_text(start_date: datetime) -> str:
    filtered_feedback = [fb for fb in feedback_storage if fb['timestamp'] >= start_date]
    feedback_text = '\n\n'.join([
        f"Timestamp: {fb['timestamp']}\n"
        f"Membership: {fb['membership']}\n"
        f"Full Name: {fb['first_name']} {fb['middle_name']} {fb['last_name']}\n"
        f"ID Number: {fb['id_number']}\n"
        f"Batch: {fb['batch']}\n"
        f"Feedback: {fb['feedback']}"
        for fb in filtered_feedback
    ])

    if not feedback_text:
        feedback_text = "No feedback available for the selected time period."

    return feedback_text

async def send_feedback_to_recipient():
    now = datetime.now(pytz.timezone('Africa/Nairobi'))
    start_date = now - timedelta(days=1)
    feedback_text = get_feedback_text(start_date)

    await application.bot.send_message(chat_id=FEEDBACK_RECIPIENT_ID, text=feedback_text)

async def send_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id

    if user_id != FEEDBACK_RECIPIENT_ID:
        await update.message.reply_text("You are not authorized to request feedback.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Past 24 hours", callback_data='24h')],
        [InlineKeyboardButton("Past 3 days", callback_data='3d')],
        [InlineKeyboardButton("Past week", callback_data='1w')],
        [InlineKeyboardButton("Past 10 days", callback_data='10d')],
        [InlineKeyboardButton("Past 2 weeks", callback_data='2w')],
        [InlineKeyboardButton("Past 3 weeks", callback_data='3w')],
        [InlineKeyboardButton("Past month", callback_data='1m')],
        [InlineKeyboardButton("Past 2 months", callback_data='2m')],
        [InlineKeyboardButton("Past 6 months", callback_data='6m')],
        [InlineKeyboardButton("Lifetime", callback_data='lifetime')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the time range for the feedback:", reply_markup=reply_markup)
    return SELECT_TIME_RANGE

async def send_selected_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    now = datetime.now(pytz.timezone('Africa/Nairobi'))
    if query.data == '24h':
        start_date = now - timedelta(days=1)
    elif query.data == '3d':
        start_date = now - timedelta(days=3)
    elif query.data == '1w':
        start_date = now - timedelta(weeks=1)
    elif query.data == '10d':
        start_date = now - timedelta(days=10)
    elif query.data == '2w':
        start_date = now - timedelta(weeks=2)
    elif query.data == '3w':
        start_date = now - timedelta(weeks=3)
    elif query.data == '1m':
        start_date = now - timedelta(days=30)
    elif query.data == '2m':
        start_date = now - timedelta(days=60)
    elif query.data == '6m':
        start_date = now - timedelta(days=180)
    elif query.data == 'lifetime':
        start_date = datetime.min.replace(tzinfo=pytz.timezone('Africa/Nairobi'))

    feedback_text = get_feedback_text(start_date)
    await query.edit_message_text(feedback_text)
    return ConversationHandler.END

# Set up the application
application = Application.builder().token("7064344482:AAHHA7p9ldTmwTpbk6wjBP6nafxJTVsfLys").build()

# Set up the conversation handler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        ASK_MEMBERSHIP: [CallbackQueryHandler(ask_membership)],
        ASK_FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_first_name)],
        ASK_MIDDLE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_middle_name)],
        ASK_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_last_name)],
        ASK_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_id)],
        ASK_BATCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_batch)],
        CONFIRM_INFO: [CallbackQueryHandler(confirm_info)],
        ASK_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_feedback)],
        THANK_YOU: [CallbackQueryHandler(thank_you)],
        SELECT_TIME_RANGE: [CallbackQueryHandler(send_selected_feedback)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

# Add handlers to the application
application.add_handler(conv_handler)
application.add_handler(CommandHandler('send_feedback', send_feedback))

# Set up the scheduler
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Africa/Nairobi'))
scheduler.add_job(send_feedback_to_recipient, trigger='cron', hour=23, minute=59)
scheduler.start()

# Start the bot
application.run_polling()
