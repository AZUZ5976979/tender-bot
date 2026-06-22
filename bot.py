import time
import logging
from telegram import Bot
from telegram.ext import Updater, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler

from config import BOT_TOKEN, KEYWORDS, MIN_AMOUNT, MAX_AMOUNT, CHECK_INTERVAL, YOUR_CHAT_ID
from database import Database
from parser import GosZakupParser

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
db = Database()
parser = GosZakupParser()

def format_amount(amount):
    """Форматирование суммы"""
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.2f} млрд сум"
    elif amount >= 1_000_000:
        return f"{amount / 1_000_000:.2f} млн сум"
    else:
        return f"{amount:,.0f} сум"

def check_tenders():
    """Проверка новых тендеров"""
    logger.info("Начинаю проверку тендеров...")
    
    try:
        tenders = parser.get_recent_tenders(days_back=1)
        logger.info(f"Найдено {len(tenders)} тендеров")
        
        new_tenders = []
        
        for tender in tenders:
            if db.is_tender_sent(tender['id']):
                continue
            
            text_to_check = f"{tender['title']} {tender['description']}".upper()
            if not any(keyword.upper() in text_to_check for keyword in KEYWORDS):
                continue
            
            if not (MIN_AMOUNT <= tender['amount'] <= MAX_AMOUNT):
                continue
            
            new_tenders.append(tender)
            db.mark_tender_sent(tender['id'])
        
        if new_tenders:
            send_tenders(new_tenders)
            logger.info(f"Отправлено {len(new_tenders)} новых тендеров")
        else:
            logger.info("Новых тендеров не найдено")
    
    except Exception as e:
        logger.error(f"Ошибка при проверке тендеров: {e}")

def send_tenders(tenders):
    """Отправка тендеров в Telegram"""
    for tender in tenders:
        message = f"""
🔔 <b>Новый тендер!</b>

📋 <b>{tender['title']}</b>

💰 <b>Сумма:</b> {format_amount(tender['amount'])}
🏢 <b>Заказчик:</b> {tender['customer']}
📅 <b>Дедлайн:</b> {tender['deadline']}

🔗 <a href="{tender['link']}">Подробнее</a>
        """
        
        try:
            bot.send_message(
                chat_id=YOUR_CHAT_ID,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            time.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")

def start(update, context):
    """Команда /start"""
    update.message.reply_text(
        '🤖 Бот мониторинга тендеров запущен!\n\n'
        f'📊 Ключевые слова: {", ".join(KEYWORDS)}\n'
        f'💰 Диапазон сумм: {format_amount(MIN_AMOUNT)} - {format_amount(MAX_AMOUNT)}\n'
        f'⏰ Проверка каждые {CHECK_INTERVAL} минут'
    )

def main():
    """Главная функция"""
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CommandHandler('start', start))
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_tenders, 'interval', minutes=CHECK_INTERVAL)
    scheduler.start()
    
    logger.info("Бот запущен...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
