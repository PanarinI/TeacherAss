import streamlit as st
from openai import OpenAI, BadRequestError
from pydantic import BaseModel
import requests
import logging
import os
from dotenv import load_dotenv
import json

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- Загрузка переменных окружения ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://api.openai.com/v1")

if not API_KEY:
    logger.error("API_KEY не найден в переменных окружения")
    st.error("Ошибка: API_KEY не найден. Проверьте файл .env")
    st.stop()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# --- Pydantic модель для структурированного вывода ---
class TextbookInfo(BaseModel):
    subject: str = ""
    textbook_name: str = ""


# --- Функция загрузки изображения на catbox.moe ---
def upload_to_catbox(file_bytes):
    try:
        response = requests.post(
            "https://catbox.moe/user/api.php",
            files={"fileToUpload": file_bytes},
            data={"reqtype": "fileupload"}
        )
        response.raise_for_status()
        url = response.text.strip()

        # Проверяем, что URL действительно начинается с https://files.catbox.moe/
        if not url.startswith("https://files.catbox.moe/"):
            raise ValueError("Некорректный URL после загрузки")

        return url
    except Exception as e:
        logger.error(f"Ошибка загрузки на catbox.moe: {e}")
        st.error("Не удалось загрузить изображение. Попробуйте снова.")
        return None

# --- Инициализация состояний ---
if "textbook_data" not in st.session_state:
    st.session_state.textbook_data = TextbookInfo()
if "image_url" not in st.session_state:
    st.session_state.image_url = None
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

# --- Интерфейс ---
st.set_page_config(page_title="Генератор планов уроков", layout="wide")
left_col, right_col = st.columns([2, 3])

with left_col:
    st.header("Загрузка учебника")
    uploaded_file = st.file_uploader("Выберите изображение страницы", type=["jpg", "png", "jpeg"])

    if uploaded_file and not st.session_state.analysis_done:
        # Загрузка изображения только при новом файле
        image_bytes = uploaded_file.getvalue()
        image_url = upload_to_catbox(image_bytes)
        if image_url:
            st.session_state.image_url = image_url
            st.success("Изображение загружено успешно!")
            st.session_state.analysis_done = True  # Блокируем повторный анализ


            # Обновленный промпт для строгого формата ответа
            ANALYSIS_PROMPT = """Анализируй изображение страницы учебника. Определи предмет и название учебника Ответь ТОЛЬКО в формате:
            Предмет: [название предмета]
            Учебник: [полное название учебника]

            Если не можешь определить - напиши "Не определено"."""


            # Простой и надежный парсер
            def parse_response(text: str) -> tuple[str, str]:
                subject = "Не определено"
                textbook = "Не определено"

                # Удаляем лишние символы и приводим к нижнему регистру
                clean_text = text.lower().replace("*", "").strip()

                # Парсим построчно
                for line in clean_text.split('\n'):
                    if "предмет:" in line:
                        subject = line.split("предмет:")[1].strip().capitalize()
                    elif "учебник:" in line:
                        textbook = line.split("учебник:")[1].strip().capitalize()

                return subject, textbook


            # Обновленный блок обработки
            with st.spinner("Анализ изображения..."):
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": image_url}},
                                    {"type": "text", "text": ANALYSIS_PROMPT}
                                ]
                            }
                        ]
                    )

                    if not response.choices:
                        st.warning("API не вернул результатов. Заполните данные вручную")
                        st.session_state.textbook_data = TextbookInfo()
                    else:
                        raw_text = response.choices[0].message.content
                        st.session_state.raw_response = raw_text  # Сохраняем для отладки

                        subject, textbook = parse_response(raw_text)

                        # Частичное заполнение данных
                        result = {}
                        if "не определено" not in subject.lower():
                            result["subject"] = subject
                        if "не определено" not in textbook.lower():
                            result["textbook_name"] = textbook

                        st.session_state.textbook_data = TextbookInfo(**result)

                        # Информационные сообщения
                        if not result.get("subject"):
                            st.warning("Не удалось определить предмет. Укажите его вручную")
                        if not result.get("textbook_name"):
                            st.warning("Не удалось определить учебник. Укажите его вручную")

                        if not result:
                            st.info("Автоматический анализ не дал результатов. Заполните все поля вручную")

                except Exception as e:
                    logger.error(f"Ошибка анализа: {str(e)} | Ответ: {raw_text}")
                    st.error("Произошла ошибка при анализе. Проверьте данные и при необходимости укажите их вручную")
                    st.session_state.textbook_data = TextbookInfo()

    # Поля для редактирования
    if st.session_state.image_url:
        st.subheader("Данные учебника")
        subject = st.text_input("Предмет", value=st.session_state.textbook_data.subject)
        textbook_name = st.text_input("Название учебника", value=st.session_state.textbook_data.textbook_name)

        # Обновление состояния только при изменении
        if subject != st.session_state.textbook_data.subject or textbook_name != st.session_state.textbook_data.textbook_name:
            st.session_state.textbook_data.subject = subject
            st.session_state.textbook_data.textbook_name = textbook_name

        # Настройки
        num_students = st.slider("Количество учеников", 1, 40, 10)
        generate_disabled = not (
                    st.session_state.textbook_data.subject.strip() and st.session_state.textbook_data.textbook_name.strip())

        if st.button("Создать план урока", disabled=generate_disabled):
            with st.spinner("Генерация плана..."):
                try:
                    # Второй запрос к LLM
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
                    logger.error(f"Ошибка генерации: {e}")
                    st.error("Не удалось создать план урока. Попробуйте снова.")

with right_col:
    st.header("План урока")
    if not st.session_state.textbook_data.subject or not st.session_state.textbook_data.textbook_name:
        st.info("Загрузите изображение и укажите данные учебника")