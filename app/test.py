import os
import logging

from dotenv import load_dotenv
import requests
from pydantic import BaseModel
from openai import OpenAI, APIError
import streamlit as st



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

# Настройки
st.set_page_config(page_title="Генератор планов уроков", layout="wide")


# Pydantic модель для структурированного вывода
class TextbookInfo(BaseModel):
    subject: str = ""
    textbook_name: str = ""


# Функция загрузки изображения на catbox.moe
def upload_to_catbox(file_bytes):
    """Загружает файл на catbox.moe и возвращает прямую ссылку"""
    try:
        response = requests.post(
            "https://catbox.moe/user/api.php",
            files={"fileToUpload": file_bytes},
            data={"reqtype": "fileupload"}
        )
        response.raise_for_status()
        return response.text.strip()  # Пример: https://files.catbox.moe/abc123.png
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return None

# Инициализация состояний
if "textbook_data" not in st.session_state:
    st.session_state.textbook_data = TextbookInfo()
if "image_url" not in st.session_state:
    st.session_state.image_url = None

# Интерфейс
left_col, right_col = st.columns([2, 3])

with left_col:
    st.header("Загрузка учебника")
    uploaded_file = st.file_uploader("Выберите изображение страницы", type=["jpg", "png", "jpeg"])

    if uploaded_file:
        # Загрузка изображения и получение URL через catbox.moe
        image_bytes = uploaded_file.getvalue()
        try:
            image_url = upload_to_catbox(image_bytes)
            if not image_url:
                logger.error("Не удалось получить URL изображения после загрузки.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке изображения: {e}")
            st.error("Не удалось загрузить изображение. Попробуйте снова.")
        if image_url:
            st.session_state.image_url = image_url
            st.success("Изображение загружено успешно!")

            # Первый запрос к LLM для определения предмета и учебника
            with st.spinner("Анализ изображения..."):
                try:
                    completion = client.beta.chat.completions.parse(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system",
                             "content": "Определи предмет и название учебника по изображению страницы. Если не уверен — оставь поля пустыми."},
                            {"role": "user", "content": [
                                {"type": "image_url", "image_url": {"url": image_url}},
                                {"type": "text", "text": "Что это за учебник? Определи предмет и точное название."}
                            ]}
                        ],
                        response_format=TextbookInfo
                    )
                    st.session_state.textbook_data = completion.choices[0].message.parsed
                except Exception as e:
                    st.error(f"Ошибка анализа: {e}")
                    st.session_state.textbook_data = TextbookInfo()

        else:
            st.error("Не удалось загрузить изображение")

    # Поля для редактирования
    if st.session_state.image_url:
        st.subheader("Данные учебника")
        subject = st.text_input("Предмет", value=st.session_state.textbook_data.subject)
        textbook_name = st.text_input("Название учебника", value=st.session_state.textbook_data.textbook_name)

        # Обновление состояния при ручном вводе
        st.session_state.textbook_data.subject = subject
        st.session_state.textbook_data.textbook_name = textbook_name

        # Настройки
        num_students = st.slider("Количество учеников", 1, 40, 10)
        generate_disabled = not (
                st.session_state.textbook_data.subject.strip() and
                st.session_state.textbook_data.textbook_name.strip()
        )

        if st.button("Создать план урока", disabled=generate_disabled):
            if not st.session_state.textbook_data.subject or not st.session_state.textbook_data.textbook_name:
                st.error("Пожалуйста, заполните все обязательные поля.")
            else:
                with st.spinner("Генерация плана..."):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system",
                                 "content": "Ты опытный учитель. Создай детальный план урока на русском языке."},
                                {"role": "user", "content": [
                                    {"type": "image_url", "image_url": {"url": st.session_state.image_url}},
                                    {"type": "text", "text": f"""
                                    Создай план урока для:
                                    - Предмет: {st.session_state.textbook_data.subject}
                                    - Учебник: {st.session_state.textbook_data.textbook_name}
                                    - Количество учеников: {num_students}

                                    Используй материалы с загруженной страницы: укажи номера упражнений, примеры, 
                                    ключевые темы и методические рекомендации.
                                    """}
                                ]}
                            ]
                        )
                        lesson_plan = response.choices[0].message.content
                        right_col.write(lesson_plan)
                    except Exception as e:
                        logger.error(f"Ошибка при генерации плана урока: {e}")
                        st.error("Не удалось создать план урока. Попробуйте снова.")


with right_col:
    st.header("План урока")
    if not st.session_state.textbook_data.subject or not st.session_state.textbook_data.textbook_name:
        st.info("Загрузите изображение и укажите данные учебника")