# 1. Импорты (все библиотеки)
import streamlit as st
from openai import OpenAI, BadRequestError
from pydantic import BaseModel
import requests
import logging
import os
from dotenv import load_dotenv


# 2. Первая команда Streamlit (ДОЛЖНА БЫТЬ ПЕРВОЙ)
st.set_page_config(page_title="Генератор планов уроков", layout="wide")

# Вот этот волшебный CSS:
st.markdown("""
<style>
    /* Полностью отключаем running статус */
    [data-testid="stStatusWidget"] {
        display: none !important;
    }
    /* Фикс для полей ввода */
    .stTextInput, .stSlider {
        opacity: 1 !important;
    }
</style>
""", unsafe_allow_html=True)

# Отключаем реактивность формы
st.session_state.setdefault("form_values", {
    "subject": "",
    "textbook": "",
    "students": 10
})

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


# 7. Pydantic модель
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


# 9. Инициализация состояний
if "textbook_data" not in st.session_state:
    st.session_state.textbook_data = TextbookInfo()
if "image_url" not in st.session_state:
    st.session_state.image_url = None
if "form_data" not in st.session_state:
    st.session_state.form_data = {"subject": "", "textbook": "", "students": 10}

# 10. Основной интерфейс (все st. команды после этого пункта)
left_col, right_col = st.columns([2, 3])

with left_col:
    st.header("Загрузка учебника")
    uploaded_file = st.file_uploader("Выберите изображение страницы", type=["jpg", "png", "jpeg"])

    if uploaded_file and st.session_state.image_url is None:
        image_url = upload_to_catbox(uploaded_file.getvalue())
        if image_url:
            st.session_state.image_url = image_url
            st.success("Изображение загружено!")

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
                        text = response.choices[0].message.content
                        subject = text.split("Предмет:")[1].split("\n")[0].strip() if "Предмет:" in text else ""
                        textbook = text.split("Учебник:")[1].strip() if "Учебник:" in text else ""

                        st.session_state.textbook_data = TextbookInfo(
                            subject=subject,
                            textbook_name=textbook
                        )
                        st.session_state.force_form_update = True  # Важная строка!
                        st.session_state.form_data["subject"] = subject
                        st.session_state.form_data["textbook"] = textbook

                except Exception as e:
                    logger.error(f"Ошибка анализа: {e}")
                    st.error("Ошибка при анализе изображения")

    if st.session_state.image_url:
        st.subheader("Данные учебника")

        # Критически важный блок - обновляем form_values при первом показе или изменении textbook_data
        if 'form_values' not in st.session_state or st.session_state.get('force_form_update', True):
            st.session_state.form_values = {
                "subject": st.session_state.textbook_data.subject,
                "textbook": st.session_state.textbook_data.textbook_name,
                "students": 10
            }
            st.session_state.force_form_update = False

        with st.form(key="lesson_form"):
            # Поля ввода
            subject = st.text_input(
                "Предмет",
                value=st.session_state.form_values["subject"],
                key="form_subject"
            )

            textbook_name = st.text_input(
                "Название учебника",
                value=st.session_state.form_values["textbook"],
                key="form_textbook"
            )

            num_students = st.slider(
                "Количество учеников",
                1, 40, st.session_state.form_values["students"],
                key="form_students"
            )

            submitted = st.form_submit_button("Создать план урока")

            if submitted:
                st.session_state.form_values.update({
                    "subject": subject,
                    "textbook": textbook_name,
                    "students": num_students
                })

                if not subject or not textbook_name:
                    st.warning("Заполните все поля")
                else:
                    with st.spinner("Генерация плана..."):
                        try:
                            response = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[
                                    {
                                        "role": "system",
                                        "content": "Ты опытный учитель. Создай план урока на основе представленного материала"
                                    },
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "image_url", "image_url": {"url": st.session_state.image_url}},
                                            {"type": "text", "text": f"""
                                            Предмет: {subject}
                                            Учебник: {textbook_name}
                                            Учеников: {num_students}
                                            """}
                                        ]
                                    }
                                ]
                            )
                            right_col.markdown(response.choices[0].message.content)
                        except Exception as e:
                            st.error(f"Ошибка: {str(e)}")

    with right_col:
        st.header("План урока")
        if not st.session_state.image_url:
            st.info("Загрузите изображение учебника")