import requests
import datetime
from bs4 import BeautifulSoup
from application import models
import pymorphy2
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw
import os
import tweepy
import telegram
import vk_api



import locale
locale.setlocale(locale.LC_TIME, "ru_RU.utf8")

import environ
env = environ.Env()

def pogibli(num):
    if num[-1] == "1" and num[-2:] != "11":
        return "погиб"
    else:
        return "погибли"


def postradali(num):
    if num[-1] == "1" and num[-2:] != "11":
        return "пострадал"
    else:
        return "пострадали"


def get_word_form(word, number):
    morph = pymorphy2.MorphAnalyzer()
    result = morph.parse(word)[0].make_agree_with_number(int(number)).word
    if result == "людей":
        return "человек"
    return result


def get_today_data():
    try:
        print("[get_today_data] Starting request...")
        
        # Добавляем заголовки, чтобы запрос выглядел более "человеческим"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(
            'https://xn--80aebkobnwfcnsfk1e0h.xn--p1ai/',
            timeout=60,
            proxies={'https': env('PROXY') or None},
            headers=headers,
            verify=False	# Если есть проблемы с SSL сертификатами
        )
        
        print(f"[get_today_data] Response status code: {response.status_code}")
        print(f"[get_today_data] Response headers: {dict(response.headers)}")
        print(f"[get_today_data] Response encoding: {response.encoding}")
        print(f"[get_today_data] Response text length: {len(response.text)}")
        
        # Сохраняем сырой HTML для отладки
        with open('debug_response.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("[get_today_data] Raw HTML saved to debug_response.html")
        
        # Проверяем успешность запроса
        if response.status_code != 200:
            print(f"[get_today_data] ERROR: Bad status code: {response.status_code}")
            print(f"[get_today_data] Response text sample: {response.text[:500]}...")
            return None
            
        # Проверяем, что ответ не пустой
        if not response.text.strip():
            print("[get_today_data] ERROR: Empty response")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        print(f"[get_today_data] Soup created, title: {soup.title.string if soup.title else 'No title'}")

        # Ищем таблицу с данными
        block_count = soup.find("table", "b-crash-stat")
        
        if not block_count:
            print("[get_today_data] ERROR: Table 'b-crash-stat' not found")
            print("[get_today_data] Available tables:")
            tables = soup.find_all("table")
            for i, table in enumerate(tables):
                print(f"Table {i}: classes={table.get('class')}")
            return None

        print(f"[get_today_data] Table found: {block_count}")

        # Извлекаем дату
        date_th = block_count.find("th")
        if not date_th:
            print("[get_today_data] ERROR: No 'th' element found in table")
            return None
            
        source_date = date_th.text.strip().split(" ")[-1]
        print(f"[get_today_data] Extracted date string: '{source_date}'")
        
        try:
            date = datetime.datetime.strptime(source_date, '%d.%m.%Y').date()
            string_date = date.strftime("%-d %B")
            weekday = date.strftime("%A").lower()
        except ValueError as e:
            print(f"[get_today_data] ERROR: Date parsing failed: {e}")
            print(f"[get_today_data] Raw date text: '{date_th.text}'")
            return None

        print(f"[get_today_data] Parsed date: {date}, string_date: {string_date}, weekday: {weekday}")

        # ПРАВИЛЬНАЯ ПРОВЕРКА ДАТЫ С БАЗОЙ ДАННЫХ
        print(f"[get_today_data] Checking if we need to update data for date: {date}")
        
        try:
            # Получаем САМУЮ ПОСЛЕДНЮЮ запись из БД (независимо от полученной даты)
            db_entry_on_date = models.BriefData.objects.filter(date=date).first()
            
            if db_entry_on_date:
                # Запись найдена, выходим из функции
                print(f"[get_today_data] DB entry on date: {db_entry_on_date.date}")
                print(f"[get_today_data] Parsed date: {date}")
                
                return None

            else:
                # Записи нет, продолжаем парсинг и обработку данных
                print(f"[get_today_data] PROCEEDING: No existing entries in DB")
                
        except Exception as e:
            print(f"[get_today_data] ERROR: Failed to check DB: {e}")
            import traceback
            print(f"[get_today_data] Traceback: {traceback.format_exc()}")
            # Продолжаем парсинг в случае ошибки БД

        # Если дошли сюда - парсим данные
        data_blocks = block_count.findAll("tr")
        print(f"[get_today_data] Found {len(data_blocks)} table rows")
        
        if len(data_blocks) < 6:
            print("[get_today_data] ERROR: Not enough table rows")
            for i, row in enumerate(data_blocks):
                print(f"Row {i}: {row.text.strip()}")

            return None

        try:
            crashes_num = str(data_blocks[1].findChildren()[1].text).strip()
            crashes_deaths = str(data_blocks[2].findChildren()[1].text).strip()
            crashes_child_deaths = str(data_blocks[3].findChildren()[1].text).strip()
            crashes_injured = str(data_blocks[4].findChildren()[1].text).strip()
            crashes_child_injured = str(data_blocks[5].findChildren()[1].text).strip()
            
            print(f"[get_today_data] Extracted data:")
            print(f"  Crashes: {crashes_num}")
            print(f"  Deaths: {crashes_deaths}")
            print(f"  Child deaths: {crashes_child_deaths}")
            print(f"  Injured: {crashes_injured}")
            print(f"  Child injured: {crashes_child_injured}")
            
        except IndexError as e:
            print(f"[get_today_data] ERROR: Data extraction failed: {e}")
            print("[get_today_data] Table structure:")
            for i, row in enumerate(data_blocks):
                children = row.findChildren()
                print(f"Row {i}: {len(children)} children")
                for j, child in enumerate(children):
                    print(f"  Child {j}: '{child.text.strip()}'")

            return None

        # Сохраняем данные в базу
        created = models.BriefData.objects.update_or_create(
            date=date,
            defaults={
                "dtp_count": crashes_num,
                "death_count": crashes_deaths,
                "injured_count": crashes_injured,
                "child_death_count": crashes_child_deaths,
                "child_injured_count": crashes_child_injured,
            }
        )
        
        print(f"[get_today_data] Data saved successfully, created: {created}")

        # Возвращаем полный словарь со всеми необходимыми полями
        return {
            "date": date,
            "string_date": string_date,
            "weekday": weekday,
            "crashes_num": crashes_num,
            "crashes_deaths": crashes_deaths,
            "crashes_child_deaths": crashes_child_deaths,
            "crashes_injured": crashes_injured,
            "crashes_child_injured": crashes_child_injured,
            "death_count": crashes_deaths,
            "injured_count": crashes_injured,
            "child_death_count": crashes_child_deaths,
            "child_injured_count": crashes_child_injured
        }

    except requests.exceptions.RequestException as e:
        print(f"[get_today_data] ERROR: Request failed: {e}")
        return None

    except Exception as e:
        print(f"[get_today_data] ERROR: Unexpected error: {e}")
        import traceback
        print(f"[get_today_data] Traceback: {traceback.format_exc()}")
        return None



def generate_text(data, post_type):
    morph = pymorphy2.MorphAnalyzer()
    if post_type == "today_post":
        return (data['string_date'] + ", " + data['weekday'] + ", в ДТП " + pogibli(data['crashes_deaths']) + " " + data[
            'crashes_deaths'] + " " + get_word_form("человек", data['crashes_deaths']))
    elif post_type == "week_post":
        return (
        "За последнюю неделю в ДТП " + pogibli(data['crashes_deaths']) + " " + data['crashes_deaths'] + " " + get_word_form("человек", data['crashes_deaths']))
    elif post_type == "month_post":
        return (
        "За " + morph.parse(data['date'].strftime("%B"))[0].inflect({'nomn'}).word + " в ДТП " + pogibli(data['crashes_deaths']) + " " + data['crashes_deaths'] + " "  + get_word_form("человек", data['crashes_deaths']))


def make_img(source):
    img = Image.open(os.path.dirname(os.path.abspath(__file__)) + "/template.png").convert('RGBA')
    W, H = (1138, 630)

    logo = Image.open(os.path.dirname(os.path.abspath(__file__)) + "/logo.png").convert('RGBA')
    logo_w, logo_h = logo.size
    logo = logo.resize((int(logo_w/2.3),int(logo_h/2.3)), Image.ANTIALIAS)
    logo_w, logo_h = logo.size
    #logo.show()


    #date_font = ImageFont.truetype("fonts/Roboto-Regular.ttf", 35)
    #header_font = ImageFont.truetype("fonts/Roboto-Bold.ttf", 32)
    #number_font = ImageFont.truetype("fonts/Roboto-Bold.ttf", 140)
    number_font = ImageFont.truetype(os.path.dirname(os.path.abspath(__file__)) + "/Circe-Regular.ttf", 300)
    text_font = ImageFont.truetype(os.path.dirname(os.path.abspath(__file__)) + "/Circe-Regular.ttf", 45)
    low_line_font = ImageFont.truetype(os.path.dirname(os.path.abspath(__file__)) + "/Circe-Regular.ttf", 32)

    crashes_deaths_ratio = W/2

    draw = ImageDraw.Draw(img)

    # number
    text = source['crashes_deaths']
    w, h = draw.textsize(text, font=number_font)
    draw.text((crashes_deaths_ratio - w / 2, -0.02*H), text, (253, 0, 0), font=number_font)

    # text first line
    text = get_word_form("человек", source['crashes_deaths']) + " " + pogibli(source['crashes_deaths']) + " в ДТП"
    w, h = draw.textsize(text, font=text_font)
    draw.text((crashes_deaths_ratio - w / 2, 0.55*H), text, (255, 255, 255), font=text_font)

    # text second line
    text = "на дорогах России "
    w_text, h_text = draw.textsize(text, font=text_font)
    w, h = draw.textsize(text + source['string_date'], font=text_font)
    w_coord = crashes_deaths_ratio - w / 2
    h_coord = 0.65 * H
    draw.text((w_coord, h_coord), text, (255, 255, 255), font=text_font)

    text = " " + source['string_date'] + " "
    w_string, h_string = draw.textsize(text, font=text_font)
    draw.rectangle(((w_coord + w_text, h_coord*1.01),(w_coord + w_text + w_string, (h_coord + h)*1.01)), fill="white")
    draw.text((w_coord + w_text, 0.65 * H), text, (0, 0, 0), font=text_font)

    # low line
    low_line = int(0.85 * H)
    img.paste(logo, (int(0.09*W), low_line, int(int(0.09*W) + logo_w), int(low_line + logo_h)), logo)

    text = "гибдд.рф, " + source['date'].strftime("%Y")
    w, h = draw.textsize(text, font=low_line_font)
    draw.text((crashes_deaths_ratio - w / 2, low_line*0.98), text, (56,56,56), font=low_line_font)

    text = "dtp-stat.ru"
    draw.text((int(0.78*W), low_line*0.98), text, (255, 255, 255), font=low_line_font)

    img.save(os.path.dirname(os.path.abspath(__file__)) + "/img.png")


def send_tweet(text):
    consumer_key = env('TWITTER_CONSUMER_KEY')
    consumer_secret = env('TWITTER_CONSUMER_SECRET')
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    access_token = env('TWITTER_CONSUMER_TOKEN')
    access_token_secret = env('TWITTER_CONSUMER_TOKEN_SECRET')
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)
    apiNew = tweepy.Client(
        access_token=access_token,
        access_token_secret=access_token_secret,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret
    )

    filename = os.path.dirname(os.path.abspath(__file__)) + "/img.png"
    media = api.simple_upload(filename)
    api.create_media_metadata(media_id=media.media_id, alt_text="")
    apiNew.create_tweet(text=text, media_ids=[media.media_id])


def send_telegram_post(text):
    bot = telegram.Bot(token=env('TELEGRAM_TOKEN'))

    channels_str = os.getenv('TELEGRAMM_CHANNELS', '')
    print(f"[send_telegram_post] TELEGRAMM_CHANNELS = {channels_str}")

    channels = [ch.strip() for ch in channels_str.split(';') if ch.strip()]

    photo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img.png")

    with open(photo_path, 'rb') as photo:
        for channel in channels:
            print(f"[send_telegram_post] Отправка фото в канал/чат: {channel}")
            try:
                bot.sendPhoto(channel, photo, caption=text)
                print(f"[send_telegram_post] Успешно отправлено в {channel}")
            except Exception as e:
                print(f"[send_telegram_post] Ошибка при отправке в {channel}: {e}")
            photo.seek(0)


def send_vk_post(text):
    log_template = "[send_vk_post] {0}"

    phone_number = env("VK_ACCOUNT_PHONE_NUMBER")
    password = env("VK_ACCOUNT_PASSWORD")
    community_id = env("VK_COMMUNITY_ID")

    vk_session = vk_api.VkApi(phone_number, password)
    try:
        vk_session.auth(token_only=True)
    except Exception as e:
        print(log_template.format(f"Ошибка авторизации в VK: {e}"))
        return

    vk = vk_session.get_api()
    photo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img.png")
    try:
        upload = vk_api.VkUpload(vk_session)
        photo = upload.photo_wall(photo_path, group_id=community_id)[0]
    except Exception as e:
        print(log_template.format(f"Ошибка загрузки фото на сервер VK: {e}"))
        return
    try:
        attachment = f"photo{photo['owner_id']}_{photo['id']}"
        vk.wall.post(owner_id=-int(community_id), from_group=1, message=text, attachments=attachment)
    except Exception as e:
        print(log_template.format(f"Ошибка при отправке поста в VK: {e}"))
        return

    print(log_template.format("Пост успешно отправлен в VK"))


def main(message="today"):
    print("[main] Запуск main() с message =", message)

    if message == "today":
        data = get_today_data()
        print("[main] Получены данные:", bool(data))

        if data:
            text = generate_text(data, "today_post")
            make_img(data)

            if os.getenv("SEND_TWEETER") == "1":
                print("[main] SEND_TWEETER=1 → отправка в Twitter")
                send_tweet(text)
            else:
                print("[main] SEND_TWEETER не установлен или не 1 → пропуск")

            if os.getenv("SEND_TELEGRAM") == "1":
                print("[main] SEND_TELEGRAM=1 → отправка в Telegram")
                send_telegram_post(text)
            else:
                print("[main] SEND_TELEGRAM не установлен или не 1 → пропуск")

            if os.getenv("SEND_VK") == "1":
                print("[main] SEND_VK=1 → отправка в VK")
                send_vk_post(text)
            else:
                print("[main] SEND_VK не установлен или не 1 → пропуск")
