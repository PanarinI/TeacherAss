import streamlit as st
from pdf2image import convert_from_bytes
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64
from io import BytesIO

# Загрузка переменных окружения
load_dotenv()

# Получение API-ключа
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")

# Создание клиента OpenAI
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

st.title("📚 AI-Помощник Учителя (GPT-4o)")
st.subheader("Загрузите учебник и получите план урока")

uploaded_file = st.file_uploader("Загрузите PDF-файл", type=["pdf"])
lesson_number = st.text_input("Введите номер урока (например, Unit 1B)").strip()
method = st.selectbox("Выберите методику", ["Test-Teach-Test", "PPP", "Task-based Learning"])

# Функция для кодирования изображения в base64
def encode_image(img):
    buffered = BytesIO()
    img.save(buffered, format="PNG")  # Сохраняем изображение в буфер
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")  # Кодируем в base64
    return f"data:image/png;base64,{img_base64}"  # Добавляем data-URI


if uploaded_file and lesson_number and method:
    with st.spinner("Обрабатываем документ..."):
        # Читаем PDF как байты
        pdf_bytes = uploaded_file.read()

        # Конвертируем PDF в изображения
        images = convert_from_bytes(pdf_bytes, poppler_path=r"F:\poppler-24.08.0\Library\bin")

        st.write("📸 Конвертировано", len(images), "изображений из PDF.")

        combined_text = ""  # Переменная для хранения всех данных с изображений

        for index, img in enumerate(images):
            # Логируем отправку изображения
            st.write(f"🖼️ Отправка изображения {index + 1} в OpenAI для анализа...")

            # Кодируем изображение в base64
            img_base64 = encode_image(img)

            # Отправляем изображение в OpenAI
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are an AI assistant that can see and interpret pages."},
                          {"role": "user", "content": f"Найти на изображении в левом верхнем углу раздел {lesson_number}"}]
            )

            extracted_text = response.choices[0].message.content
            st.write(f"🔍 Ответ от OpenAI для изображения {index + 1}: {extracted_text[:200]}...")  # Показываем первые 200 символов

            combined_text += extracted_text  # Собираем всю информацию с изображений

        # Логируем общий текст, который был собран
        st.write("📄 Собранный текст с изображений:", combined_text[:500])  # Показываем первые 500 символов из всего текста

        # Проверка, что в объединенном тексте найден урок
        if f"Unit {lesson_number}" in combined_text or f"Lesson {lesson_number}" in combined_text:
            # Генерация плана урока
            prompt = f"""
            Ты - эксперт в планировании уроков. Составь структурированный план урока по методу {method} на базе материала.

            Lesson Material:
            {combined_text}
            """

            st.write("📝 Генерация плана урока...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "You are a professional lesson planner."},
                          {"role": "user", "content": prompt}]
            )

            st.success("✅ План урока создан!")
            st.text_area("Результат", response.choices[0].message.content, height=300)
        else:
            st.error("❌ Урок не найден в тексте. Проверьте номер.")
            st.write("❌ Не удалось найти урок с номером", lesson_number)
