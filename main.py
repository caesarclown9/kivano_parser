import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from difflib import SequenceMatcher
from telegram import Bot
from dotenv import load_dotenv
import os
import schedule
import time


url = "https://www.kivano.kg/mobilnye-telefony"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")




def save_initial_html(url, save_path="previous_version.html"):
    """
    Сохраняет текущую версию HTML-страницы в файл для последующего анализа.
    """
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, "w", encoding="utf-8") as file:
            file.write(response.text)
        print(f"HTML страницы сохранен в файл {save_path}.")
    else:
        print(f"Ошибка загрузки страницы: {response.status_code}")




def parse_page(url):
    response = requests.get(url)

    if response.status_code != 200:
        return None



    soup = BeautifulSoup(response.text, 'html.parser')


    products = []

    for prod_item in soup.find_all("div", class_='item product_listbox oh'):
        name = prod_item.find("div", class_='listbox_title oh')
        price = prod_item.find("div", class_='listbox_price text-center')

        if name and price:
            prod_name = name.get_text(strip=True)
            final_price_tag = price.find("strong")

            if final_price_tag:
                final_price = final_price_tag.get_text(strip=True)

                price_cleaned = re.sub(r'[^\d.,]', '', final_price)

            try:
                price_final = float(price_cleaned.replace(',', '.'))
            except ValueError:
                price_final = None
            products.append((prod_name, price_final))

    return products



def compare_html(url, saved_html="previous_version.html"):
    """
    Сравнивает текущую версию HTML с сохраненной и выводит процент схожести.
    """
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Ошибка загрузки страницы: {response.status_code}")
        return

    current_html = response.text

    try:
        with open(saved_html, "r", encoding="utf-8") as file:
            old_html = file.read()

        similarity = SequenceMatcher(None, old_html, current_html).ratio()
        print(f"Схожесть текущей и сохраненной версий: {similarity:.2%}")

        return similarity
    except FileNotFoundError:
        print(f"Файл {saved_html} не найден. Сохраните начальную версию c помощью save_initial_html")
        return None



def get_total_pages(url):
    response = requests.get(url)
    if response.status_code != 200:
        return 1  

    soup = BeautifulSoup(response.text, 'html.parser')
    

    pagination = soup.find("ul", class_="pagination")
    
    if pagination:
        last_page_item = pagination.find('li', class_='last')
        if last_page_item:
            last_page_link = last_page_item.find("a", href=True)
            if last_page_link:
                last_page_url = last_page_link['href']
                last_page_number = last_page_url.split('=')[-1] 
                return int(last_page_number)  
    return 1 


def compare_and_update_html(url, saved_html="previous_version.html"):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Ошибка загрузки страницы: {response.status_code}")
        return

    current_html = response.text

    try:
        with open(saved_html, "r", encoding="utf-8") as file:
            old_html = file.read()

        similarity = SequenceMatcher(None, old_html, current_html).ratio()
        print(f"Схожесть текущей и сохраненной версий: {similarity:.2%}")

        if similarity < 0.95:
            print("Структура сайта изменилась! Обновляем сохраненную версию")
            send_telegram_message(
                token=TELEGRAM_BOT_TOKEN,
                chat_id=TELEGRAM_CHAT_ID,
                message="Структура сайта изменилась!"
            )
            with open(saved_html, "w", encoding="utf-8") as file:
                file.write(current_html)
        else:
            print("Изменений не обнаружено")
    except FileNotFoundError:
        print(f"Файл {saved_html} не найден. Сохраняем текущую версию.")
        with open(saved_html, "w", encoding="utf-8") as file:
            file.write(current_html)
    

def parse_all_pages(base_url):
    total_pages = get_total_pages(base_url)
    all_products = []

    for page_num in range(1, total_pages + 1):
        print(page_num)
        if page_num == 1:
            url = base_url
        else:
            url = f"{base_url}?page={page_num}"

        products = parse_page(url)

        if not products:

            break

        all_products.extend(products)

    return all_products


# save_initial_html(url)
# compare_html(url)


base_url = "https://www.kivano.kg/mobilnye-telefony"



def send_telegram_message(token, chat_id, message):
    bot = Bot(token=token)
    bot.send_message(chat_id=chat_id, text=message)


def run_parser():
    # Проверяем структуру сайта
    compare_and_update_html(url)

    # Если изменений нет, запускаем парсер
    all_products = parse_all_pages(base_url)
    df = pd.DataFrame(all_products, columns=["Product", "Price"])
    df.to_csv("products.csv", index=False)
    print("Data saved")



if __name__ == "__main__":
    schedule.every().day.at("18:00").do(run_parser)

    while True:
        schedule.run_pending()
        time.sleep(1)