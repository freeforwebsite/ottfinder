import os
import requests
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
# Read keys from environment variables for Render
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY")

# TMDB Provider IDs (India)
# Netflix: 8, Prime: 119, Hotstar: 122, JioCinema: 220
# Zee5: 232, SonyLiv: 237, Sun NXT: 309, Aha: 532
PROVIDERS = "8|119|122|220|232|237|309|532"
REGION = "IN"

def get_daily_releases():
    """Fetches movies released recently on OTT platforms using TMDB API."""
    if TMDB_API_KEY == "YOUR_TMDB_API_KEY":
        return "⚠️ Please set your TMDB API key in the code to fetch real data!"

    today = datetime.date.today()
    one_week_ago = today - datetime.timedelta(days=7)
    
    two_years_ago = today - datetime.timedelta(days=365*2)
    
    url = f"https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "watch_region": REGION,
        "with_watch_providers": PROVIDERS,
        "with_release_type": "4", # 4 = Digital (OTT) release
        "release_date.gte": one_week_ago.strftime("%Y-%m-%d"),
        "release_date.lte": today.strftime("%Y-%m-%d"),
        "primary_release_date.gte": two_years_ago.strftime("%Y-%m-%d"),
        "sort_by": "popularity.desc"
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
            movie_id = movie.get("id")
            
            platform_str = "Unknown Platform"
            try:
                prov_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
                prov_res = requests.get(prov_url, params={"api_key": TMDB_API_KEY})
                if prov_res.status_code == 200:
                    prov_data = prov_res.json().get("results", {}).get(REGION, {})
                    providers = prov_data.get("flatrate", [])
                    if not providers:
                        providers = prov_data.get("free", [])
                    if not providers:
                        providers = prov_data.get("ads", [])
                    if not providers:
                        providers = prov_data.get("rent", [])
                    if not providers:
                        providers = prov_data.get("buy", [])
                        
                    if providers:
                        platform_str = " | ".join([p.get("provider_name") for p in providers])
            except Exception:
                pass
                
            message += f"{idx+1}. **{title}** (Released: {release_date}) - ⭐️ {rating}/10\n   📺 {platform_str}\n\n"
            
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


async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Searches for a movie and returns its details and poster."""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text="Please provide a movie name.\nExample: `/search Inception`", parse_mode="Markdown")
        return
        
    query = " ".join(context.args)
    
    url = f"https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "region": REGION
    }
    
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json()
        results = data.get("results", [])
        
        if not results:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ No movies found for '{query}'.")
            return
            
        # Get the first result
        movie = results[0]
        movie_id = movie.get("id")
        title = movie.get("title")
        release_date = movie.get("release_date", "N/A")
        rating = movie.get("vote_average", "N/A")
        overview = movie.get("overview", "No description available.")
        poster_path = movie.get("poster_path")
        
        # Fetch providers
        platform_str = "Not available on streaming right now."
        prov_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
        prov_res = requests.get(prov_url, params={"api_key": TMDB_API_KEY})
        if prov_res.status_code == 200:
            prov_data = prov_res.json().get("results", {}).get(REGION, {})
            providers = prov_data.get("flatrate", [])
            if not providers:
                providers = prov_data.get("free", [])
            if not providers:
                providers = prov_data.get("ads", [])
            if not providers:
                providers = prov_data.get("rent", [])
            if not providers:
                providers = prov_data.get("buy", [])
                
            if providers:
                platform_str = " | ".join([p.get("provider_name") for p in providers])
                
        # Format message
        year = release_date[:4] if release_date and len(release_date) >= 4 else 'N/A'
        caption = (
            f"🎬 **{title}** ({year})\n\n"
            f"⭐️ **Rating:** {rating}/10\n"
            f"📺 **Available on:** {platform_str}\n\n"
            f"📖 **Overview:**\n_{overview}_"
        )
        
        # Trim caption if too long (Telegram limit is 1024 for photo captions)
        if len(caption) > 1000:
            caption = caption[:1000] + "..."
            
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            await context.bot.send_photo(chat_id=chat_id, photo=poster_url, caption=caption, parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id=chat_id, text=caption, parse_mode="Markdown")
            
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error during search: {e}")


def get_releases_for_date(target_date_str):
    """Fetches movies released on a specific date."""
    if TMDB_API_KEY == "YOUR_TMDB_API_KEY" or TMDB_API_KEY is None:
        return "⚠️ Please set your TMDB API key in the code to fetch real data!"

    today = datetime.date.today()
    two_years_ago = today - datetime.timedelta(days=365*2)
    
    url = f"https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "watch_region": REGION,
        "with_watch_providers": PROVIDERS,
        "with_release_type": "4", # 4 = Digital (OTT) release
        "release_date.gte": target_date_str,
        "release_date.lte": target_date_str,
        "primary_release_date.gte": two_years_ago.strftime("%Y-%m-%d"),
        "sort_by": "popularity.desc"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            return f"🎬 No major OTT releases found for {target_date_str}."

        message = f"🍿 **OTT Releases on {target_date_str}** 🍿\n\n"
        for idx, movie in enumerate(results[:10]):
            title = movie.get("title")
            rating = movie.get("vote_average", "N/A")
            movie_id = movie.get("id")
            
            platform_str = "Unknown Platform"
            try:
                prov_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
                prov_res = requests.get(prov_url, params={"api_key": TMDB_API_KEY})
                if prov_res.status_code == 200:
                    prov_data = prov_res.json().get("results", {}).get(REGION, {})
                    providers = prov_data.get("flatrate", [])
                    if not providers:
                        providers = prov_data.get("free", [])
                    if not providers:
                        providers = prov_data.get("ads", [])
                    if not providers:
                        providers = prov_data.get("rent", [])
                    if not providers:
                        providers = prov_data.get("buy", [])
                        
                    if providers:
                        platform_str = " | ".join([p.get("provider_name") for p in providers])
            except Exception:
                pass
                
            message += f"{idx+1}. **{title}** - ⭐️ {rating}/10\n   📺 {platform_str}\n\n"
            
        return message

    except Exception as e:
        return f"❌ Error fetching releases: {e}"


async def show_dates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows an inline keyboard with recent dates."""
    keyboard = []
    today = datetime.date.today()
    
    row = []
    for i in range(10):
        d = today - datetime.timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        display_str = d.strftime("%d-%m-%Y")
        btn = InlineKeyboardButton(display_str, callback_data=f"date_{date_str}")
        row.append(btn)
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
            
    if row:
        keyboard.append(row)
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text('📅 Select a date to see OTT releases:', reply_markup=reply_markup)


async def date_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles date button clicks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("date_"):
        target_date = data.split("_")[1]
        await query.edit_message_text(text=f"🔍 Checking releases for {target_date}...")
        
        releases = get_releases_for_date(target_date)
        
        back_keyboard = [[InlineKeyboardButton("⬅️ Back to dates", callback_data="show_dates")]]
        reply_markup = InlineKeyboardMarkup(back_keyboard)
        
        await query.edit_message_text(text=releases, parse_mode="Markdown", reply_markup=reply_markup)
        
    elif data == "show_dates":
        keyboard = []
        today = datetime.date.today()
        row = []
        for i in range(10):
            d = today - datetime.timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            display_str = d.strftime("%d-%m-%Y")
            btn = InlineKeyboardButton(display_str, callback_data=f"date_{date_str}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text='📅 Select a date to see OTT releases:', reply_markup=reply_markup)


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
    application.add_handler(CommandHandler("dates", show_dates))
    application.add_handler(CommandHandler("search", search_movie))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CallbackQueryHandler(date_button_callback))

    print("Bot is starting...")
    # Initialize and start the application correctly
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep the application running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
