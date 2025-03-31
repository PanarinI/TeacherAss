import logging
import os
import base64
import json
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# --- Конфигурация ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
if not API_KEY:
    logger.error("API_KEY не найден в переменных окружения")
    exit(1)
if not BASE_URL:
    logger.warning("BASE_URL не указан, будет использован URL по умолчанию")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def encode_image(uploaded_file):
    """Оптимизированная конвертация в base64"""
    try:
        return base64.b64encode(uploaded_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Ошибка конвертации: {e}")
        return None


def analyze_content(image_b64: str):
    """Единый оптимизированный запрос для анализа"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "Анализ страницы учебника. Ответь ТОЛЬКО в формате:\n"
                        "{\n"
                        "  \"subject\": \"Предмет\",\n"
                        "  \"textbook\": \"Учебник\",\n"
                        "  \"topic\": \"Тема\",\n"
                        "  \"exercises\": [\"конкретные задания из текста\"],\n"
                        "  \"examples\": [\"конкретные примеры из текста\"]\n"
                        "}"
                    )},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=1500
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        return None


def generate_lesson_plan(context: dict):
    """Генерация плана с привязкой к контексту"""
    try:
        prompt = f"""
        СОЗДАЙ ДЕТАЛЬНЫЙ ПЛАН УРОКА С ОПОРОЙ НА МАТЕРИАЛ УЧЕБНИКА.
        Обязательно включи:
        - Конкретные упражнения: {context.get('exercises', [])[:3]}
        - Примеры из учебника: {context.get('examples', [])[:2]}
        - Номера страниц и разделов
        - Пошаговые инструкции для учителя

        Параметры:
        - Предмет: {context['subject']}
        - Учебник: {context['textbook']}
        - Тема: {context['topic']}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        return None


# --- Интерфейс ---
st.set_page_config(layout="wide")
st.title("📘 Генератор уроков с привязкой к учебнику")

if "context" not in st.session_state:
    st.session_state.context = {}

# Левая панель
with st.sidebar:
    st.header("Загрузка материалов")

    uploaded_file = st.file_uploader("Страница учебника", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        with st.spinner("Анализ контента..."):
            if image_b64 := encode_image(uploaded_file):
                analysis = analyze_content(image_b64)
                if analysis:
                    st.session_state.context.update(analysis)
                    st.success("Контент проанализирован!")
                else:
                    st.error("Ошибка анализа изображения")

# Основная панель
col1, col2 = st.columns([1, 3])

with col1:
    if st.session_state.context:
        st.subheader("Обнаруженные элементы:")
        st.json(st.session_state.context)

    if st.button("Сгенерировать план урока", disabled=not st.session_state.context):
        with st.spinner("Создаем персонализированный план..."):
            plan = generate_lesson_plan(st.session_state.context)
            if plan:
                st.session_state.plan = plan
                st.rerun()

with col2:
    if "plan" in st.session_state:
        st.markdown(st.session_state.plan)
        st.download_button(
            "Скачать план",
            data=st.session_state.plan,
            file_name="lesson_plan.md",
            mime="text/markdown"
        )