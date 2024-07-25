import logging
import re
from datetime import datetime, timedelta
import pytz
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Define states for conversation
ASK_MEMBERSHIP, ASK_FIRST_NAME, ASK_MIDDLE_NAME, ASK_LAST_NAME, ASK_ID, ASK_BATCH, CONFIRM_INFO, ASK_FEEDBACK, THANK_YOU = range(9)

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

async def send_feedback_to_channel(feedback_text: str):
    # Send the feedback to the channel
    await application.bot.send_message(chat_id=CHANNEL_ID, text=feedback_text)

async def send_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id

    if user_id != FEEDBACK_RECIPIENT_ID:
        await update.message.reply_text("You are not authorized to request feedback.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Today's Feedback", callback_data='today')],
        [InlineKeyboardButton("Last 3 Days Feedback", callback_data='last_3_days')],
        [InlineKeyboardButton("Last 7 Days Feedback", callback_data='last_7_days')],
        [InlineKeyboardButton("Last 10 Days Feedback", callback_data='last_10_days')],
        [InlineKeyboardButton("Last 15 Days Feedback", callback_data='last_15_days')],
        [InlineKeyboardButton("Last 30 Days Feedback", callback_data='last_30_days')],
        [InlineKeyboardButton("Last 2 Months Feedback", callback_data='last_2_months')],
        [InlineKeyboardButton("All Time Feedback", callback_data='all_time')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please choose the feedback you want to retrieve:", reply_markup=reply_markup)
    return ConversationHandler.END

async def handle_feedback_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    filter_type = query.data
    now = datetime.now(pytz.timezone('Africa/Nairobi'))

    if filter_type == 'today':
        start_date = now - timedelta(days=1)
    elif filter_type == 'last_3_days':
        start_date = now - timedelta(days=3)
    elif filter_type == 'last_7_days':
        start_date = now - timedelta(days=7)
    elif filter_type == 'last_10_days':
        start_date = now - timedelta(days=10)
    elif filter_type == 'last_15_days':
        start_date = now - timedelta(days=15)
    elif filter_type == 'last_30_days':
        start_date = now - timedelta(days=30)
    elif filter_type == 'last_2_months':
        start_date = now - timedelta(days=60)
    elif filter_type == 'all_time':
        start_date = datetime.min
    else:
        await query.edit_message_text("Invalid option selected.")
        return ConversationHandler.END

    filtered_feedback = [fb for fb in feedback_storage if fb['timestamp'] >= start_date]
    feedback_text = '\n\n'.join([
        f"Timestamp: {fb['timestamp']}\n"
        f"Membership: {fb['membership']}\n"
        f"Full Name: {fb['first_name']} {fb['middle']}{fb['last_name']}\n"
        f"ID Number: {fb['id_number']}\n"
        f"Batch: {fb['batch']}\n"
        f"Feedback: {fb['feedback']}"
        for fb in filtered_feedback
    ])

    if not feedback_text:
        feedback_text = "No feedback available for the selected period."

    await query.edit_message_text(f"Feedback for {filter_type.replace('_', ' ')}:\n\n{feedback_text}")
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token("7064344482:AAHHA7p9ldTmwTpbk6wjBP6nafxJTVsfLys").build()

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
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('send_feedback', send_feedback))
    application.add_handler(CallbackQueryHandler(handle_feedback_request, pattern='^(today|last_3_days|last_7_days|last_10_days|last_15_days|last_30_days|last_2_months|all_time)$'))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_feedback_to_channel, 'cron', hour=23, minute=59, args=['Your daily feedback summary'])
    scheduler.start()

    application.run_polling()

if __name__ == '__main__':
    main()
