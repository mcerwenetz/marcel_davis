#!/usr/bin/env python3
import logging
import requests
import bs4
import re
from bs4 import BeautifulSoup
from tgbot_config import API_KEY
from telebot import TeleBot, types
from pathlib import Path
from datetime import datetime
import locale


from apscheduler.schedulers.background import BackgroundScheduler

from systemd.journal import JournalHandler

TIMEOUT = 5
HSMA_WEEK_FILENAME = "hsma_week_menu.txt"
UNIMA_WEEK_FILENAME = "unima_week_menu.txt"
ABO_FILENAME = "abos.txt"

bot = TeleBot(API_KEY)


def download_hsma_week():
    url = "https://openmensa.org/api/v2/canteens/289/meals"

    response = requests.get(url)

    # Check if the request was successful (status code 200)
    data = response.json()

    menu = ""
    for day in data:
        if day["closed"] is True:
            continue
        date = datetime.datetime.strptime(day[date], "%Y-%m-%d")
        weekday = date.strftime("%A")
        menu += f"**{weekday}**"

        meals = day[meals]
        for meal in meals:
            category = meal["category"]
            meanu += "\n"
            menu += f"*{category}*"
            menu += "\n\n" +  meal["name"] + str(meal["prices"]["students"])

    with open(HSMA_WEEK_FILENAME, 'w', encoding='utf-8') as file:
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


def replace_paranthesis(stri):
    para_auf = [i for i in range(len(stri)) if stri[i] == "("]
    para_zu = [i for i in range(len(stri)) if stri[i] == ")"]
    para = list(zip(para_auf, para_zu))
    words = [stri[pair[0] - 1:pair[1] + 1] for pair in para]
    for word in words:
        stri = stri.replace(word, " ")
    return stri


@bot.message_handler(commands=['mensa'])
def mensa(message):
    log.info("mensa was called")
    with open(HSMA_FILENAME, 'r', encoding="utf-8") as file:
        menu = file.read()
    bot.reply_to(message, menu, parse_mode='Markdown')


@bot.message_handler(commands=['mensa_week'])
def mensa_week(message):
    log.info("mensaweek was called")
    with open(HSMA_WEEK_FILENAME, 'r', encoding="utf-8") as file:
        menu = file.read()
    menu_days = menu.split("*")

    menu_days = menu_days[1:]

    menu_days = [menu_days[i] + menu_days[i + 1]
                 for i in range(0, len(menu_days) - 1, 2)]

    for day in menu_days:
        bot.reply_to(message, day, parse_mode="Markdown")


@bot.message_handler(commands=['unimensa_week'])
def uni_mensa(message):
    log.info("unimensa was called")
    with open(UNIMA_WEEK_FILENAME, 'r', encoding="utf-8") as file:
        menu = file.read()

    menu_days = menu.split("*")

    menu_days = menu_days[1:]

    menu_days = [menu_days[i] + menu_days[i + 1]
                 for i in range(0, len(menu_days) - 1, 2)]

    for day in menu_days:
        bot.reply_to(message, day, parse_mode="Markdown")


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
    with open(HSMA_FILENAME, 'r', encoding="utf-8") as file:
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
        hour=7,
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
    locale.setlocale(locale.LC_ALL, "de_DE.UTF-8")
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
