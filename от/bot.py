import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from database import Database
import config
from datetime import datetime

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TipCalculatorBot:
    def __init__(self):
        self.db = Database()
        self.currency_rates = {}
        self.last_currency_update = None
        self.setup_keyboards()

    def setup_keyboards(self):
        """Создает клавиатуры для команд"""
        self.main_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("/tip"), KeyboardButton("/convert")],
                [KeyboardButton("/history"), KeyboardButton("/clear_history")],
                [KeyboardButton("/set_default_tip"), KeyboardButton("/help")]
            ],
            resize_keyboard=True
        )

        self.tip_examples_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("/tip 2000 15% 4")],
                [KeyboardButton("/tip 1500 10% 2")],
                [KeyboardButton("/tip 3000 def 3")],
                [KeyboardButton("Назад")]
            ],
            resize_keyboard=True
        )

        self.convert_examples_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("/convert 100 USD")],
                [KeyboardButton("/convert 50 EUR")],
                [KeyboardButton("Назад")]
            ],
            resize_keyboard=True
        )

    async def update_currency_rates(self):
        """Обновляет курсы валют с сайта ЦБ РФ"""
        try:
            response = requests.get('https://www.cbr-xml-daily.ru/daily_json.js')
            data = response.json()
            self.currency_rates = {
                'USD': data['Valute']['USD']['Value'],
                'EUR': data['Valute']['EUR']['Value'],
            }
            self.last_currency_update = datetime.now()
            logger.info("Курсы валют успешно обновлены")
        except Exception as e:
            logger.error(f"Ошибка при обновлении курсов валют: {e}")

    async def get_currency_rate(self, currency_code):
        """Возвращает курс валюты"""
        currency_code = currency_code.upper()
        if currency_code == 'RUB':
            return 1.0
        
        if not self.last_currency_update or (datetime.now() - self.last_currency_update).days >= 1:
            await self.update_currency_rates()
        
        return self.currency_rates.get(currency_code)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        default_tip = self.db.get_default_tip(user.id)
        await update.message.reply_text(
            f"Привет, {user.first_name}! Я бот для расчета чаевых.\n"
            f"Текущий процент чаевых по умолчанию: {default_tip}%\n"
            "Используй кнопки ниже или команды для работы с ботом",
            reply_markup=self.main_keyboard
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        user_id = update.effective_user.id
        default_tip = self.db.get_default_tip(user_id)
        
        help_text = f"""
📝 Список доступных команд:

/tip <сумма> [процент] [количество человек] - Рассчитать чаевые
Если процент не указан, будет использовано {default_tip}%
Примеры:
/tip 2000 15% 4 - явное указание процента
/tip 2000 4     - процент по умолчанию ({default_tip}%) для 4 человек
/tip 2000       - просто расчет чаевых

/convert <сумма> <валюта> - Конвертировать в рубли (USD, EUR)
Пример: /convert 100 USD

/history - Показать историю расчетов
/clear_history - Очистить историю расчетов
/set_default_tip <процент> - Установить процент по умолчанию
/help - Показать это сообщение
"""
        await update.message.reply_text(
            help_text,
            reply_markup=self.main_keyboard
        )

    async def show_tip_examples(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает примеры для команды /tip"""
        await update.message.reply_text(
            "Выберите пример расчета чаевых:",
            reply_markup=self.tip_examples_keyboard
        )

    async def show_convert_examples(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает примеры для команды /convert"""
        await update.message.reply_text(
            "Выберите пример конвертации валют:",
            reply_markup=self.convert_examples_keyboard
        )

    async def back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат в главное меню"""
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=self.main_keyboard
        )

    async def convert_currency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /convert"""
        try:
            args = context.args if context.args else update.message.text.split()[1:]
            
            if len(args) < 2:
                await update.message.reply_text(
                    "Недостаточно аргументов. Пример: /convert 100 USD",
                    reply_markup=self.convert_examples_keyboard
                )
                return

            amount = float(args[0])
            currency = args[1].upper()

            rate = await self.get_currency_rate(currency)
            if not rate:
                await update.message.reply_text(
                    f"Валюта {currency} не поддерживается. Доступные: USD, EUR",
                    reply_markup=self.convert_examples_keyboard
                )
                return

            result = amount * rate
            await update.message.reply_text(
                f"🧾 Результат конвертации:\n"
                f"{amount:.2f} {currency} = {result:.2f} RUB\n"
                f"Курс ЦБ РФ: 1 {currency} = {rate:.2f} RUB",
                reply_markup=self.main_keyboard
            )

        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка в convert_currency: {e}")
            await update.message.reply_text(
                "Некорректные данные. Пример: /convert 100 USD",
                reply_markup=self.convert_examples_keyboard
            )

    async def calculate_tip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /tip"""
        try:
            user_id = update.effective_user.id
            args = context.args if context.args else update.message.text.split()[1:]
            
            if not args:
                await update.message.reply_text(
                    "Не указана сумма. Пример: /tip 2000 15% 4",
                    reply_markup=self.tip_examples_keyboard
                )
                return

            amount_str = ''.join(c for c in args[0] if c.isdigit() or c == '.')
            amount = float(amount_str) if amount_str else 0
            
            tip_percent = self.db.get_default_tip(user_id)
            people = 1
            
            if len(args) > 1:
                if any(c in args[1] for c in ['%', 'd', 'e', 'f']):
                    percent_str = ''.join(c for c in args[1] if c.isdigit())
                    if percent_str:
                        tip_percent = int(percent_str)
                    
                    if len(args) > 2:
                        people_str = ''.join(c for c in args[2] if c.isdigit())
                        if people_str:
                            people = int(people_str)
                else:
                    people_str = ''.join(c for c in args[1] if c.isdigit())
                    if people_str:
                        people = int(people_str)

            if amount <= 0 or tip_percent <= 0 or people <= 0:
                await update.message.reply_text(
                    "Все значения должны быть положительными числами",
                    reply_markup=self.tip_examples_keyboard
                )
                return

            tip_amount = amount * tip_percent / 100
            total = amount + tip_amount
            per_person = total / people

            self.db.save_calculation(user_id, amount, tip_percent, total, per_person if people > 1 else None)

            response = (
                f"🧮 Результат (использован {tip_percent}%):\n"
                f"• Сумма: {amount:.2f} ₽\n"
                f"• Чаевые: {tip_amount:.2f} ₽\n"
                f"• Итого: {total:.2f} ₽"
            )
            if people > 1:
                response += f"\n• С каждого: {per_person:.2f} ₽"

            await update.message.reply_text(
                response,
                reply_markup=self.main_keyboard
            )

        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка в calculate_tip: {e}")
            await update.message.reply_text(
                "Некорректные данные. Примеры:\n"
                "/tip 2000 15% 4\n"
                "/tip 2000 4\n"
                "/tip 2000",
                reply_markup=self.tip_examples_keyboard
            )

    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /history"""
        user_id = update.effective_user.id
        history = self.db.get_history(user_id)

        if not history:
            await update.message.reply_text(
                "У вас пока нет истории расчетов",
                reply_markup=self.main_keyboard
            )
            return

        response = "📊 История расчетов:\n"
        for calc in history[-5:]:
            response += (
                f"{calc['timestamp']}: {calc['amount']} ₽ + {calc['tip_percent']}% = "
                f"{calc['total']:.2f} ₽"
            )
            if calc['per_person']:
                response += f" (с каждого: {calc['per_person']:.2f} ₽)"
            response += "\n"

        await update.message.reply_text(
            response,
            reply_markup=self.main_keyboard
        )

    async def clear_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /clear_history"""
        user_id = update.effective_user.id
        deleted_count = self.db.clear_history(user_id)
        
        if deleted_count > 0:
            await update.message.reply_text(
                f"✅ Удалено {deleted_count} записей из истории",
                reply_markup=self.main_keyboard
            )
        else:
            await update.message.reply_text(
                "ℹ️ История расчетов уже пуста",
                reply_markup=self.main_keyboard
            )

    async def set_default_tip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /set_default_tip"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "Укажите процент. Пример: /set_default_tip 15",
                    reply_markup=self.main_keyboard
                )
                return
            
            percent_str = ''.join(c for c in context.args[0] if c.isdigit())
            tip_percent = int(percent_str) if percent_str else 0
            
            if tip_percent <= 0 or tip_percent > 100:
                await update.message.reply_text(
                    "Процент должен быть от 1 до 100",
                    reply_markup=self.main_keyboard
                )
                return

            user_id = update.effective_user.id
            self.db.set_default_tip(user_id, tip_percent)
            await update.message.reply_text(
                f"Процент чаевых по умолчанию установлен: {tip_percent}%",
                reply_markup=self.main_keyboard
            )

        except (ValueError, IndexError):
            await update.message.reply_text(
                "Некорректный процент. Пример: /set_default_tip 15",
                reply_markup=self.main_keyboard
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        text = update.message.text
        
        if text == "/tip":
            await self.show_tip_examples(update, context)
        elif text == "/convert":
            await self.show_convert_examples(update, context)
        elif text == "Назад":
            await self.back_to_main(update, context)
        elif text.startswith("/tip "):
            await self.calculate_tip(update, context)
        elif text.startswith("/convert "):
            await self.convert_currency(update, context)
        else:
            await update.message.reply_text(
                "Используйте кнопки или команды для работы с ботом",
                reply_markup=self.main_keyboard
            )

def main():
    """Запуск бота"""
    bot = TipCalculatorBot()
    application = Application.builder().token(config.TOKEN).build()

    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("tip", bot.calculate_tip))
    application.add_handler(CommandHandler("convert", bot.convert_currency))
    application.add_handler(CommandHandler("history", bot.show_history))
    application.add_handler(CommandHandler("clear_history", bot.clear_history))
    application.add_handler(CommandHandler("set_default_tip", bot.set_default_tip))

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()