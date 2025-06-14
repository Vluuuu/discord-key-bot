import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import sqlite3
from flask import Flask
from threading import Thread
from webdriver_manager.chrome import ChromeDriverManager

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Setup database
def setup_db():
    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_keys
                 (user_id TEXT PRIMARY KEY, key TEXT, expiry TEXT, status TEXT)''')
    conn.commit()
    conn.close()

def get_user_key(user_id):
    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    c.execute("SELECT * FROM user_keys WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {
            "key": result[1],
            "expiry": datetime.fromisoformat(result[2]),
            "status": result[3]
        }
    return None

def save_user_key(user_id, key_data):
    conn = sqlite3.connect('keys.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO user_keys 
                 (user_id, key, expiry, status) 
                 VALUES (?, ?, ?, ?)''',
              (user_id, key_data['key'], key_data['expiry'].isoformat(), key_data['status']))
    conn.commit()
    conn.close()

# Setup browser
def setup_browser():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,720")
    return webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)

# Key retrieval logic
async def get_luarmor_key(interaction):
    try:
        await interaction.response.defer()
        existing_key = get_user_key(str(interaction.user.id))
        if existing_key and existing_key['expiry'] > datetime.now():
            return await interaction.followup.send(
                f"✅ Kamu sudah memiliki key aktif:\n```\n{existing_key['key']}\n```\n"
                f"Berlaku hingga: {existing_key['expiry'].strftime('%Y-%m-%d %H:%M')}",
                ephemeral=True
            )

        browser = setup_browser()
        await interaction.followup.send("🌐 Membuka luarmor.net...")
        browser.get("https://ads.luarmor.net/get_key?for=-QliJkLVEYVnH")

        await interaction.followup.send("🔘 Menekan tombol START...")
        start_button = WebDriverWait(browser, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(text(), 'START', 'start'), 'start')]")))
        start_button.click()

        await interaction.followup.send("🔄 Menunggu redirect...")
        await asyncio.sleep(5)

        await interaction.followup.send("🔍 Mengambil key...")
        get_key_button = WebDriverWait(browser, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(text(), 'GET A NEW KEY', 'get a new key'), 'get a new key')]")))
        get_key_button.click()
        await asyncio.sleep(3)

        key_element = WebDriverWait(browser, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'key')]//span | //div[@class='key-display']")))
        key = key_element.text.strip()

        expiry = datetime.now() + timedelta(hours=12)
        save_user_key(str(interaction.user.id), {
            "key": key,
            "expiry": expiry,
            "status": "active"
        })

        await interaction.followup.send(
            f"🎉 Key berhasil diambil:\n```\n{key}\n```\n⏳ Berlaku hingga: {expiry.strftime('%Y-%m-%d %H:%M')}"
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        await interaction.followup.send(f"❌ Gagal mengambil key: {e}")
    finally:
        if 'browser' in locals():
            browser.quit()

# Discord command
@bot.tree.command(name="getkey", description="Ambil key dari luarmor.net")
async def getkey(interaction: discord.Interaction):
    await get_luarmor_key(interaction)

@bot.event
async def on_ready():
    setup_db()
    await bot.tree.sync()
    logger.info(f"Bot {bot.user} sudah online!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="/getkey"))

# Flask server to keep Railway alive
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run).start()

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
