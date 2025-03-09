#!/usr/bin/env python3
import logging
import requests
import bs4
import re
import os
import yaml
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from telebot import TeleBot, types
from pathlib import Path
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from systemd.journal import JournalHandler

#open yaml config and get config data
with open('config.yml', 'r') as file:
    conf = yaml.safe_load(file)

TIMEOUT = conf["timeout"]

THM_WEEK_FILENAME = conf["filename"]["thm_week"]
THM_FILENAME = conf["filename"]["thm"]
UNIMA_WEEK_FILENAME = conf["filename"]["unima_week_menu.txt"]
ABO_FILENAME = conf["filename"]["abo"]

CANTEEN_ID_THM = conf["canteens"]["thm"]
CANTEEN_ID_UMA = conf["canteens"]["uma"]

# get token and initialize bot
load_dotenv()
API_KEY = os.getenv("API_KEY")
bot = TeleBot(API_KEY)

def parse_menue(data)->dict:
    """parse the json menue of one day"""
    menues = {}
    # loop through json data and return dict of tpye {"menue category":"{meal} - {price}"}
    for i in range(len(data)):
        menue = f"{data[0]['name']} - {data[1]['prices']['students']}€"
        menues[data[i]['category']] = menue
    return menues

def download_hsma():
    """cache the mensa menue of today and write to .txt file"""
    log.info("caching mensa menue of today")
    # Get the current date and format as yyyy-mm-dd
    date:datetime = datetime.now()
    date = date.strftime('%Y-%m-%d')

    # request menue from open mensa api
    url=f"https://openmensa.org/api/v2/canteens/{CANTEEN_ID_THM}/days/{date}/meals"
    response = requests.get(url)

    menue_cache = ""
    read_menue:bool = True
    if response.status_code != 200:
        menue_cache = "Nichts gefunden"
        log.error(f"request for [mensa today] failed. status code: {response.status_code}")
        read_menue = False
    data = response.json()
    if date is None:
        menue_cache = "Hochschulmensa hat zu 💩"
        read_menue = False
    # parse mensa menue only if valid data was sent
    if read_menue:
        today_menues = parse_menue(data)
        menue_cache = f"{date.strftime("%A")}\n\n"
        for menue in today_menues:
            menue_cache += f"{menue}\n{today_menues[menue]}\n\n"
    with open(THM_FILENAME, 'w', encoding='utf-8') as file:
        file.write(menue_cache)

def download_hsma_week():
    with requests.get("https://www.stw-ma.de/Essen+_+Trinken/Speisepl%C3%A4ne/Hochschule+Mannheim-view-week.html", timeout=5) as url:
        soup = BeautifulSoup(url.content)
    match = soup.find_all(class_='active1')
    if match is not None:
        data = parse_week(match)
        menu = "".join(data)
    else:
        menu = "Es konnte kein Menü gefunden werden."
    
    with open(THM_WEEK_FILENAME, 'w', encoding='utf-8') as file:
        file.write(menu)

def download_unima_week():
    with requests.get("https://www.stw-ma.de/men%C3%BCplan_schlossmensa-view-week.html", timeout=5) as url:
        soup = BeautifulSoup(url.content)
    match = soup.find_all(class_='active1')
    if match is not None:
        data = parse_week(match)
        menu = "".join(data)
    else:
        menu = "Unimensa hat zu 💩"

    with open(UNIMA_WEEK_FILENAME, 'w', encoding='utf-8') as file:
        file.write(menu)

def create_abos():
    abos = Path(ABO_FILENAME)
    abos.touch(exist_ok=True)

def cache_all_menus():
    "caches all menus as files"
    log.info("caching menus")
    download_hsma_week()
    download_hsma()
    download_unima_week()
    # download_test()


@bot.message_handler(commands=["start", "help"])
def start(message):
    welcome_string = """Willkommen beim inoffiziellen Mensabot
"""
    bot.reply_to(message, welcome_string)

@bot.message_handler(commands=['mensa'])
def mensa(message):
    """return todays mensa menu"""
    log.info("mensa was called")
    # Open the file and read its contents
    with open(THM_FILENAME, 'r') as file:
        menue_cache = file.read()
    bot.reply_to(message, menue_cache)

@bot.message_handler(commands=['mensa_week'])
def mensa_week(message):
    """return this weeks thm mensa menu"""
    log.info("mensa_week was called")
    # Open the file and read its contents
    with open(THM_WEEK_FILENAME, 'r') as file:
        menue_cache = file.read()
    bot.reply_to(message, menue_cache)

@bot.message_handler(commands=['unimensa_week'])
def uni_mensa(message):
    """return this weeks uni mensa menu"""
    log.info("unimensa_week was called")
    # Open the file and read its contents
    with open(UNIMA_WEEK_FILENAME, 'r') as file:
        menue_cache = file.read()
    bot.reply_to(message, menue_cache)

@bot.message_handler(commands=['abo'])
def abo(message):
    all_abos = []
    chatid = str(message.chat.id)
    with open(ABO_FILENAME, 'r', encoding="utf-8") as abofile:
        for line in abofile:
            all_abos.append(line.replace("\n",""))
    if chatid not in all_abos:
        all_abos.append(chatid)
        bot.reply_to(
            message,
            "du wirst jetzt täglich Infos zur mensa erhalten")
        log.info(f"added chat with chatid {chatid}")
    else:
        all_abos.remove(chatid)
        bot.reply_to(
            message,
            "du wirst jetzt täglich **keine** Infos zur mensa erhalten",
            parse_mode="markdown")
        log.info(f"removed chat with chatid {chatid}")

    with open(ABO_FILENAME, 'w', encoding="utf-8") as abofile:
        for abo in all_abos:
            abofile.write("%s\n" % abo)

def send_all_abos():
    all_abos = []
    with open(ABO_FILENAME, 'r', encoding="utf-8") as abofile:
        for line in abofile:
            all_abos.append(line)
    log.info(f"sending abos. currently there are {len(all_abos)} abos")
    with open(THM_FILENAME, 'r', encoding="utf-8") as file:
        menu = file.read()
        if len(all_abos) > 0:
            for chat_id in all_abos:
                bot.send_message(chat_id, menu)

def bot_poll():
    # pass
    while True:
        log.info("polling msgs")
        bot.infinity_polling()

def run_scheduler():
    log.info("running scheduler")
    sched = BackgroundScheduler()
    sched.configure(timezone='Europe/Rome')
    sched.add_job(
        cache_all_menus,
        'cron',
        year="*",
        month="*",
        day_of_week="0-4",
        hour="*",
        minute="*/30",
        second=0
    )
    sched.add_job(
        send_all_abos,
        'cron',
        year="*",
        month="*",
        day_of_week="0-4",
        hour=9,
        minute=0,
        second=0
    )
    sched.start()


def set_options():
    bot.set_my_commands([
        types.BotCommand("/help", "Hilfe"),
        types.BotCommand("/mensa", "Mensamenü des Tages"),
        types.BotCommand("/mensa_week", "Mensamenü der Woche"),
        types.BotCommand("/unimensa_week", "unimensamenu der woche"),
        types.BotCommand("/abo", "(De)Abboniere den Täglichen Mensareport"),
    ]
    )


def main():
    log.info("running background tasks")
    set_options()
    run_scheduler()
    bot_poll()


if __name__ == '__main__':
    log = logging.getLogger("marcel_davis")
    log.addHandler(JournalHandler())
    log.setLevel(logging.INFO)
    # logging.basicConfig(level=logging.INFO)
    log.info("starting bot")
    cache_all_menus()
    create_abos()
    log.info("running mainloop")
    main()
