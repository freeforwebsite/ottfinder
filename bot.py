import os
import requests
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
# Read keys from environment variables for Render
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY")

# TMDB Provider IDs (Example IDs for India, you can change region)
# Netflix: 8, Amazon Prime Video: 119, Disney+ Hotstar: 122, JioCinema: 220
PROVIDERS = "8|119|122|220"
REGION = "IN"

def get_daily_releases():
    """Fetches movies released recently on OTT platforms using TMDB API."""
    if TMDB_API_KEY == "YOUR_TMDB_API_KEY":
        return "⚠️ Please set your TMDB API key in the code to fetch real data!"

    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)
    
    url = f"https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "watch_region": REGION,
        "with_watch_providers": PROVIDERS,
        "primary_release_date.gte": one_week_ago.strftime("%Y-%m-%d"),
        "primary_release_date.lte": today.strftime("%Y-%m-%d"),
        "sort_by": "primary_release_date.desc"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            return "🎬 No major OTT releases found for today."

        message = f"🍿 **Recent OTT Releases (Up to {today})** 🍿\n\n"
        for idx, movie in enumerate(results[:10]): # Limit to top 10
            title = movie.get("title")
            release_date = movie.get("release_date")
            rating = movie.get("vote_average", "N/A")
            message += f"{idx+1}. **{title}** (Released: {release_date}) - ⭐️ {rating}/10\n"
            
        return message

    except Exception as e:
        return f"❌ Error fetching releases: {e}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message and instructions when the command /start is issued."""
    chat_id = update.effective_chat.id
    welcome_text = (
        "👋 Hello! I am your Daily OTT Release Bot.\n\n"
        "I will send you daily updates about new movies on Netflix, Prime Video, Hotstar, etc.\n"
        "Use /releases to get the latest releases right now.\n"
        "Use /subscribe to get daily automated messages."
    )
    await context.bot.send_message(chat_id=chat_id, text=welcome_text)


async def fetch_releases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the latest releases to the user manually."""
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="🔍 Checking for releases...")
    
    releases = get_daily_releases()
    await context.bot.send_message(chat_id=chat_id, text=releases, parse_mode="Markdown")


async def send_daily_update(context: ContextTypes.DEFAULT_TYPE):
    """The scheduled task that sends the daily update to all subscribed users."""
    job = context.job
    chat_id = job.chat_id
    
    releases = get_daily_releases()
    await context.bot.send_message(chat_id=chat_id, text=releases, parse_mode="Markdown")


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Subscribes the user to daily updates."""
    chat_id = update.effective_chat.id
    
    # Remove existing jobs for this chat if any (to prevent duplicates)
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    for job in current_jobs:
        job.schedule_removal()
        
    # Schedule a daily message at a specific time (e.g., 09:00 UTC)
    # Note: time is in UTC by default. Adjust accordingly.
    time_to_run = datetime.time(hour=9, minute=0, second=0) 
    
    context.job_queue.run_daily(
        send_daily_update, 
        time=time_to_run, 
        chat_id=chat_id, 
        name=str(chat_id)
    )
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text="✅ You are now subscribed! I will send you daily OTT releases every day."
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribes the user from daily updates."""
    chat_id = update.effective_chat.id
    
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if not current_jobs:
        await context.bot.send_message(chat_id=chat_id, text="You are not currently subscribed.")
        return

    for job in current_jobs:
        job.schedule_removal()
        
    await context.bot.send_message(chat_id=chat_id, text="❌ You have been unsubscribed from daily updates.")


import asyncio
from aiohttp import web

async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Dummy web server started on port {port}")

async def main():
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or TELEGRAM_BOT_TOKEN is None:
        print("ERROR: Please set your TELEGRAM_BOT_TOKEN in the code before running.")
        return

    # Start the dummy web server
    await start_web_server()

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("releases", fetch_releases))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))

    print("Bot is starting...")
    # Initialize and start the application correctly
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep the application running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
