import streamlit as st
from openai import OpenAI, BadRequestError
from pydantic import BaseModel
import requests
import logging
import os
from dotenv import load_dotenv

# 1. Конфигурация полей формы
FORM_CONFIG = {
    "main_fields": {
        "subject": {"label": "Предмет", "type": "text", "default": ""},
        "textbook": {"label": "Название учебника", "type": "text", "default": ""},
        "students": {"label": "Количество учеников", "type": "slider", "min": 1, "max": 40, "default": 10},
        "methodology": {
            "label": "Методика обучения",
            "type": "selectbox",
            "options": ["PPP", "TTT"],
            "default": "PPP"
        }
    }
}

AUTO_DETECT_ENABLED = True  # Флаг по умолчанию

# 2. Первая команда Streamlit (должна быть первой)
st.set_page_config(page_title="Генератор планов уроков", layout="wide")

# 3. CSS для отключения running состояний
st.markdown("""
<style>
    [data-testid="stStatusWidget"] {
        display: none !important;
    }
    .stTextInput, .stSlider, .stSelectbox {
        opacity: 1 !important;
    }
</style>
""", unsafe_allow_html=True)

# 4. Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# 5. Загрузка переменных окружения
load_dotenv()
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")

if not API_KEY:
    logger.error("API_KEY не найден в переменных окружения")
    st.error("Ошибка: API_KEY не найден. Проверьте файл .env")
    st.stop()

# 6. Инициализация клиента OpenAI
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# 7. Модель данных
class TextbookInfo(BaseModel):
    subject: str = ""
    textbook_name: str = ""


# 8. Функция загрузки изображения
def upload_to_catbox(file_bytes):
    try:
        with st.spinner("Загрузка изображения на сервер..."):
            response = requests.post(
                "https://catbox.moe/user/api.php",
                files={"fileToUpload": file_bytes},
                data={"reqtype": "fileupload"}
            )
            response.raise_for_status()
            url = response.text.strip()
            if not url.startswith("https://files.catbox.moe/"):
                raise ValueError("Некорректный URL")
            return url
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
        st.error("Не удалось загрузить изображение")
        return None


# 9. Функция парсинга ответа
def parse_response(text: str) -> tuple[str, str]:
    subject = "Не определено"
    textbook = "Не определено"

    lines = text.lower().replace("*", "").strip().split('\n')
    for line in lines:
        if "предмет:" in line:
            subject = line.split("предмет:")[1].strip().capitalize()
        elif "учебник:" in line:
            textbook = line.split("учебник:")[1].strip().capitalize()

    return subject, textbook


# 10. Инициализация состояний
if "textbook_data" not in st.session_state:
    st.session_state.textbook_data = TextbookInfo()
if "image_url" not in st.session_state:
    st.session_state.image_url = None
if "form_values" not in st.session_state:
    st.session_state.form_values = {
        field: config["default"]
        for field, config in FORM_CONFIG["main_fields"].items()
    }
if "force_form_update" not in st.session_state:
    st.session_state.force_form_update = True

# 11. Основной интерфейс
left_col, right_col = st.columns([2, 3])

with left_col:
    st.header("Настройки")
    AUTO_DETECT_ENABLED = st.toggle(
        "Автоматическое распознавание учебника",
        value=True,
        key="auto_detect_toggle"
    )
    st.header("Загрузка учебника")
    uploaded_file = st.file_uploader("Выберите изображение страницы", type=["jpg", "png", "jpeg"])

    # Обработка загрузки изображения
    if uploaded_file and not st.session_state.image_url:
        image_url = upload_to_catbox(uploaded_file.getvalue())
        if image_url:
            st.session_state.image_url = image_url
            st.success("Изображение загружено!")

            if AUTO_DETECT_ENABLED:  # Только если включено
                with st.spinner("Анализ изображения..."):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "image_url", "image_url": {"url": image_url}},
                                        {"type": "text", "text": """Определи предмет и учебник. Ответь строго в формате:
                                        Предмет: [название]
                                        Учебник: [название]"""}
                                    ]
                                }
                            ]
                        )

                        if response.choices:
                            subject, textbook = parse_response(response.choices[0].message.content)
                            st.session_state.textbook_data = TextbookInfo(
                                subject=subject,
                                textbook_name=textbook
                            )
                            st.session_state.force_form_update = True

                    except Exception as e:
                        logger.error(f"Ошибка анализа: {e}")
                        st.error("Ошибка при анализе изображения")
            else:
                st.info("Автораспознавание отключено. Заполните данные вручную")
                st.session_state.textbook_data = TextbookInfo()
                st.session_state.force_form_update = True

    # Форма с настройками
    if st.session_state.image_url:
        st.subheader("Данные учебника")

        # Обновление значений формы при необходимости
        if st.session_state.force_form_update:
            st.session_state.form_values.update({
                "subject": st.session_state.textbook_data.subject,
                "textbook": st.session_state.textbook_data.textbook_name
            })
            st.session_state.force_form_update = False

        with st.form(key="lesson_form"):
            # Динамическое создание полей из конфига
            for field, config in FORM_CONFIG["main_fields"].items():
                if config["type"] == "text":
                    st.session_state.form_values[field] = st.text_input(
                        config["label"],
                        value=st.session_state.form_values[field],
                        key=f"form_{field}"
                    )
                elif config["type"] == "slider":
                    st.session_state.form_values[field] = st.slider(
                        config["label"],
                        min_value=config["min"],
                        max_value=config["max"],
                        value=st.session_state.form_values[field],
                        key=f"form_{field}"
                    )
                elif config["type"] == "selectbox":
                    st.session_state.form_values[field] = st.selectbox(
                        config["label"],
                        options=config["options"],
                        index=config["options"].index(st.session_state.form_values[field]),
                        key=f"form_{field}"
                    )

            submitted = st.form_submit_button("Создать план урока")

            if submitted:
                if not st.session_state.form_values["subject"] or not st.session_state.form_values["textbook"]:
                    st.warning("Заполните все обязательные поля")
                else:
                    with st.spinner("Генерация плана урока..."):
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[
                                    {
                                        "role": "system",
                                        "content": "Ты опытный учитель. Создай детальный план урока."
                                    },
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "image_url", "image_url": {"url": st.session_state.image_url}},
                                            {"type": "text", "text": f"""
                                            Создай план урока по методике {st.session_state.form_values['methodology']}
                                            Детали:
                                            - Предмет: {st.session_state.form_values['subject']}
                                            - Учебник: {st.session_state.form_values['textbook']}
                                            - Учеников: {st.session_state.form_values['students']}
                                            """}
                                        ]
                                    }
                                ]
                            )
                            right_col.markdown(response.choices[0].message.content)
                        except Exception as e:
                            st.error(f"Ошибка генерации: {e}")

with right_col:
    st.header("План урока")
    if not st.session_state.image_url:
        st.info("Загрузите изображение учебника")