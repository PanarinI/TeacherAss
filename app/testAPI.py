import os
import logging
from openai import OpenAI, APIError
from dotenv import load_dotenv

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
# --- Получение ключей API из окружения ---
load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
if not API_KEY:
    logger.error("API_KEY не найден в переменных окружения")
    exit(1)
if not BASE_URL:
    logger.warning("BASE_URL не указан, будет использован URL по умолчанию")


client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def test_chat_completions_endpoint():
    """Тестирование эндпоинта chat/completions."""
    try:
        logger.info("Тестируем эндпоинт chat/completions...")
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # Убедитесь, что модель доступна
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ]
        )
        logger.info("Ответ от chat/completions: %s", completion.choices[0].message.content)
    except APIError as e:
        logger.error(f"Ошибка при вызове chat/completions: {e}")

def test_responses_endpoint():
    """Тестирование эндпоинта responses."""
    try:
        logger.info("Тестируем эндпоинт responses...")
        response = client.responses.create(
            model="gpt-4o-mini",  # Убедитесь, что модель доступна
            input="Tell me a three sentence bedtime story about a unicorn."
        )
        logger.info("Ответ от responses: %s", response)
    except APIError as e:
        logger.error(f"Ошибка при вызове responses: {e}")

def test_assistants_endpoint():
    try:
        logger.info("Тестируем эндпоинт assistants...")
        response = client.beta.assistants.create(
    instructions="You are a personal math tutor. When asked a question, write and run Python code to answer the question.",
    name="Math Tutor",
    tools=[{"type": "code_interpreter"}],
    model="gpt-4o-mini"
        )
        logger.info("Ответ от assistants: %s", response)
    except APIError as e:
        logger.error(f"Ошибка при вызове assistants: {e}")


if __name__ == "__main__":
    logger.info("Начинаем тестирование API OpenAI...")
    test_chat_completions_endpoint()
    test_responses_endpoint()
    test_assistants_endpoint()
    logger.info("Тестирование завершено.")

