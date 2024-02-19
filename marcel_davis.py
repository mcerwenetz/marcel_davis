#!/usr/bin/env python3
import logging
import requests
import tgbot_config as conf
from bs4 import BeautifulSoup
from secret import API_KEY
from telebot import TeleBot, types
import datetime
import shelve

from apscheduler.schedulers.background import BackgroundScheduler

from systemd.journal import JournalHandler


bot = TeleBot(token=API_KEY)


class DownloadConf():

    class Types():
        NotInit = "NotInit"
        Uni= "Uni"
        HS = "HS"

    def __init__(self, typ, week_key, next_week_key, url) -> None:
        self.typ = typ
        self.week_key = week_key
        self.next_week_key = next_week_key
        self.url : list[str] = url


menus = {}
download_confs : list[DownloadConf] = []


def parse_week(match) -> list[str]:
    data = [ele.text for ele in match]
    data = [ele.replace("\t", '').replace("\n\n\n", "\n\n") for ele in data]
    data = [ele.replace("Montag", "*Montag*") for ele in data]
    data = [ele.replace("Dienstag", "*Dienstag*") for ele in data]
    data = [ele.replace("Mittwoch", "*Mittwoch*") for ele in data]
    data = [ele.replace("Donnerstag", "*Donnerstag*") for ele in data]
    data = [ele.replace("Freitag", "*Freitag*") for ele in data]
    data = [ele.replace("`", "'") for ele in data]
    return data


def get_all_menus():
    for download_conf in download_confs:
        weeks = (download_conf.week_key, download_conf.next_week_key)
        timedelta = 0
        for week in weeks:
            url = create_URL(download_conf.url, timedelta)
            with requests.get(url, timeout=5) as request:
                soup = BeautifulSoup(request.content, features="lxml")
            match = soup.find_all(class_=conf.SOUP_STRING)
            if match is not None:
                data = parse_week(match)
                menus[download_conf.typ][week] = data
            else:
                menus[download_conf.typ][week] = "Hochschulmensa hat zu 💩"
            timedelta += 7

    with shelve.open(conf.SHELVE_FILE_NAME) as file:
        file["menus"] = menus



def create_URL(URL, timedelta) -> tuple[str, str]:
    today = datetime.datetime.now()

    timestamp = today + datetime.timedelta(days=timedelta)

    delim = """%25252d"""
    url_timestamp = str(timestamp.year) + delim + \
        str(timestamp.month) + delim + str(timestamp.day)


    return URL[0] + url_timestamp + URL[1]

  


@bot.message_handler(commands=["start", "help"])
def start(message):
    welcome_string = """Willkommen beim inoffiziellen Mensabot
"""
    bot.reply_to(message, welcome_string)



@bot.message_handler(commands=['hsma_today'])
def hsma_today(message):
    log.info("hsma_today was called")
    menu = menus[DownloadConf.Types.HS][conf.HSMA_MENSA_THIS_WEEK_KEY][0]
    bot.reply_to(message, menu, parse_mode='Markdown')


@bot.message_handler(commands=['hsma_this_week'])
def hsma_this_week(message):
    log.info("mensaweek was called")
    
    for day in menus[DownloadConf.Types.HS][conf.HSMA_MENSA_THIS_WEEK_KEY]:
        bot.reply_to(message, day, parse_mode="Markdown")
    return [day for day in  menus[DownloadConf.Types.HS][conf.HSMA_MENSA_THIS_WEEK_KEY]]

@bot.message_handler(commands=['hsma_next_week'])
def hsma_next_week(message):
    log.info("hsma_next_week was called")
    
    for day in menus[DownloadConf.Types.HS][conf.HSMA_MENSA_NEXT_WEEK_KEY]:
        bot.reply_to(message, day, parse_mode="Markdown")

    # return [day for day in  menus[DownloadConf.Types.HS][conf.HSMA_MENSA_THIS_WEEK_KEY]]

@bot.message_handler(commands=['uni_today'])
def uni_today(message):
    log.info("hsma_today was called")
    menu = menus[DownloadConf.Types.Uni][conf.UNI_MENSA_THIS_WEEK_KEY][0]
    bot.reply_to(message, menu, parse_mode='Markdown')


@bot.message_handler(commands=['uni_this_week'])
def uni_this_week(message):
    log.info("mensaweek was called")
    
    for day in menus[DownloadConf.Types.Uni][conf.UNI_MENSA_THIS_WEEK_KEY]:
        bot.reply_to(message, day, parse_mode="Markdown")

@bot.message_handler(commands=['uni_next_week'])
def uni_next_week(message):
    log.info("hsma_next_week was called")
    
    for day in menus[DownloadConf.Types.Uni][conf.UNI_MENSA_NEXT_WEEK_KEY]:
        bot.reply_to(message, day, parse_mode="Markdown")





@bot.message_handler(commands=['abo'])
def abo(message):
    chatid = int(message.chat.id)
    abos : list[int] = []
    with shelve.open(conf.SHELVE_FILE_NAME) as file:
        if conf.ABO_KEY not in file:
            file[conf.ABO_KEY] = []
        abos = file[conf.ABO_KEY]
        if chatid not in abos:
            abos.append(chatid)
            bot.reply_to(
                message,
                "du wirst jetzt täglich Infos zur mensa erhalten")
            log.info(f"added chat with chatid {chatid}")
        else:
            abos.remove(chatid)
            bot.reply_to(
                message,
                "du wirst jetzt täglich **keine** Infos zur mensa erhalten",
                parse_mode="markdown")
            log.info(f"removed chat with chatid {chatid}")

        file[conf.ABO_KEY] = abos


def send_all_abos():
    abos : list[int] = []
    with shelve.open(conf.SHELVE_FILE_NAME) as file:
        abos = file[conf.ABO_KEY]
    log.info(f"sending abos. currently there are {len(abos)} abos")
    menu = menus[DownloadConf.Types.HS][conf.HSMA_MENSA_THIS_WEEK_KEY][0]
    if len(abos) > 0:
        for chat_id in abos:
            bot.send_message(chat_id, menu, parse_mode="Markdown")


def bot_poll():
    # pass
    while True:
        # try:
        log.info("polling msgs")
        bot.polling(none_stop=True, timeout=120)
        # except requests.exceptions.ReadTimeout:
        #     print("Timeout connecting to Telegram")

def run_scheduler():
    log.info("running scheduler")
    sched = BackgroundScheduler()
    sched.configure(timezone='Europe/Rome')
    sched.add_job(
        get_all_menus,
        'cron',
        year="*",
        month="*",
        day_of_week="0-4",
        # day="*",
        hour=4,
        # hour="*",
        minute=0,
        # minute="*",
        second=0
        # second="*/5"
    )
    sched.add_job(
        send_all_abos,
        'cron',
        year="*",
        month="*",
        day_of_week="0-4",
        # day="*",
        hour=7
        # hour="*",
        minute=0,
        # minute="*",
        second=0
        # second="*/5"
    )
    sched.start()


def set_options():
    bot.set_my_commands([
        types.BotCommand("/help", "Hilfe"),
        types.BotCommand("/hsma_today", "HS-Mensamenü des Tages"),
        types.BotCommand("/mensa_week", "Mensamenü der Woche"),
        types.BotCommand("/unimensa_week", "unimensamenu der woche"),
        types.BotCommand("/abo", "(De)Abboniere den Täglichen Mensareport"),
    ]
    )


def startup(download_confs):
    uni_mensa_download_conf = DownloadConf(
        DownloadConf.Types.Uni,
        conf.UNI_MENSA_THIS_WEEK_KEY,
        conf.UNI_MENSA_NEXT_WEEK_KEY,
        conf.URL_UNI_WEEK
    )
    
    hsma_mensa_download_conf = DownloadConf(
        DownloadConf.Types.HS,
        conf.HSMA_MENSA_THIS_WEEK_KEY,
        conf.HSMA_MENSA_NEXT_WEEK_KEY,
        conf.URL_HSMA_WEEK)
    
    download_confs += [uni_mensa_download_conf, hsma_mensa_download_conf]

    menus[DownloadConf.Types.HS] = {}
    menus[DownloadConf.Types.Uni] = {}

    menus[DownloadConf.Types.HS][conf.HSMA_MENSA_THIS_WEEK_KEY] = []
    menus[DownloadConf.Types.HS][conf.HSMA_MENSA_THIS_WEEK_KEY] = []
    menus[DownloadConf.Types.Uni][conf.UNI_MENSA_THIS_WEEK_KEY] = []
    menus[DownloadConf.Types.Uni][conf.UNI_MENSA_NEXT_WEEK_KEY] = []

def main():
    log.info("running background tasks")
    set_options()
    run_scheduler()
    bot_poll()


if __name__ == '__main__':
    log = logging.getLogger("marcel_davis")
    log.addHandler(JournalHandler())
    # log.setLevel(logging.INFO)
    logging.basicConfig(level=logging.INFO)
    log.info("starting bot")
    startup(download_confs=download_confs)
    get_all_menus()
    log.info("running mainloop")
    main()
