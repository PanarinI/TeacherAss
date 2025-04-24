import os
import logging
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
from docx import Document
import requests
from typing import Optional

# --- Настройка ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()
api_key = os.getenv("API_KEY_openai")
client = OpenAI(api_key=api_key) if api_key else None
VS_ID = os.getenv("VECTOR_STORE_ID", "")  # vector store for file_search if needed

# --- Утилиты ---
def upload_to_catbox(file_bytes: bytes) -> str:
    """Загружает файл на catbox.moe и возвращает URL"""
    try:
        response = requests.post(
            "https://catbox.moe/user/api.php",
            files={"fileToUpload": file_bytes},
            data={"reqtype": "fileupload"},
            timeout=10
        )
        response.raise_for_status()
        return response.text.strip()
    except Exception as e:
        logging.error(f"Ошибка загрузки изображения: {e}")
        raise gr.Error("Не удалось загрузить изображение")


def generate_docx(text: str) -> str:
    """Сохраняет текст в .docx и возвращает путь"""
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    tmp = tempfile.gettempdir()
    path = os.path.join(tmp, f"lesson_plan_{datetime.now().strftime('%Y%m%d%H%M%S')}.docx")
    doc.save(path)
    return path


# --- Основная функция генерации ---
def generate_lesson_plan(
        image_path: Optional[str],
        textbook: str,
        cefr: str,
        topic: str,
        goal: str,
        format_type: str,
        num_students: int,
        age: str,
        adults: bool,
        level_match: int,
        duration: int,
        inventory: str,
        methodology: str,
        hw_required: bool,
        web_search: bool,
        repetition: bool,
        application: bool,
        analysis: bool,
        creativity: bool
) -> str:
    # Валидация API клиента
    if not client:
        raise gr.Error("API ключ не настроен")
    # Проверка наличия изображения
    if not image_path:
        return "❗ Загрузите фото страницы учебника для генерации урока"

    # Загружаем изображение и получаем URL
    try:
        with open(image_path, "rb") as f:
            image_url = upload_to_catbox(f.read())
    except Exception as e:
        logging.error(f"Image upload error: {e}")
        raise gr.Error("Не удалось загрузить изображение")

    # Собираем текстовый prompt
    params_list = [
        f"- **Учебник**: {textbook}",
        f"- **CEFR-уровень**: {'определи по загруженной странице' if cefr.strip() == '' else cefr}",
        f"- **Тема**: {topic or 'определи по загруженной странице'}",
        f"- **Цель занятия**: {goal or 'определи по загруженной странице'}",
        f"- **Формат**: {format_type} ({num_students} {'ребёнок' if num_students == 1 else 'детей'})",
        f"- **Возраст**: {'взрослые' if adults else age}",
        f"- **Соответствие уровня**: {['below', 'on-level', 'above', 'mixed'][level_match]}",
        f"- **Длительность**: {duration} минут",
        f"- **Инвентарь**: {inventory if inventory else 'стандартный'}",
        f"- **Методика**: {methodology}",
        # f"- **Таксономия**: {', '.join([level for level, checked in [('Повторение', repetition),
        #                                                              ('Применение', application),
        #                                                              ('Анализ', analysis),
        #                                                              ('Творчество', creativity)] if checked]) or 'не указано'}"
        f"- **Домашнее задание**: {'да' if hw_required else 'нет'}"
    ]

    if web_search:
        params_list.append("- **Используется web search**: да")

    # Собираем входные данные согласно API
    input_content = [
        {
            "type": "input_text",
            "text": "Параметры занятия:\n" + "\n".join(params_list)
        },
        {
            "type": "input_image",
            "image_url": image_url,
            "detail": "high"
        }
    ]

    # Опции инструментов
    tools = []
    tool_choice = None
    if web_search:
        tools.append({
            "type": "web_search_preview",
            "search_context_size": "medium",
            "user_location": {"type": "approximate", "country": "RU"}
        })
        tool_choice = {"type": "web_search_preview"}

    # Вызов LLM
    try:
        response = client.responses.create(
            instructions="Ты эксперт-педагог. Составь детальный план урока по заданным параметрам и изображению страницы учебника.",
            input=[{"role": "user", "content": input_content}],
            model="gpt-4o-mini",
            tools=tools or None,
            tool_choice=tool_choice,
            max_output_tokens=2000,
            stream=False
        )
        return response.output_text

    except Exception as e:
        logging.error(f"Generation error: {e}")
        raise gr.Error(f"Ошибка генерации: {e}")


# --- Gradio UI ---
with gr.Blocks(title="AI-Генератор уроков по фото учебника") as app:
    with gr.Row():
        with gr.Column(scale=1):  # левый блок
            image = gr.Image(label="Фото страницы учебника*", type="filepath")

            # Блок 1: Учебник
            with gr.Column(variant="panel"):
                gr.Markdown("### 📚 Учебник", elem_classes=["block-title"])
                textbook = gr.Textbox(label="Название учебника*", placeholder="English File Beginner")
                cefr = gr.Dropdown(label="CEFR-уровень", choices=["A1", "A2", "B1", "B2", "C1", "C2"],
                                   value="A1", info="Выберите уровень")

            # Блок 2: Класс
            with gr.Column(variant="panel"):
                gr.Markdown("### 👥 Класс", elem_classes=["block-title"])
                format_type = gr.Radio(label="Формат занятия*", choices=["Индивидуальное", "Групповое"],
                                       value="Групповое")

                with gr.Group(visible=True) as group_settings:
                    num_students = gr.Slider(label="Количество учеников*", minimum=1, maximum=40,
                                             value=10, step=1, info="Для групповых занятий")

                with gr.Group() as age_group:
                    adults = gr.Checkbox(label="Взрослые")
                    age = gr.Textbox(label="Возраст*", placeholder="10–11", interactive=True)

                level_match = gr.Slider(label="Соответствие уровня учебника", minimum=0, maximum=3,
                                        step=1, value=1, info="0=ниже,1=соответствует,2=выше,3=смешанный")

            # Блок 3: Занятие
            with gr.Column(variant="panel"):
                gr.Markdown("### 📄 Занятие", elem_classes=["block-title"])
                topic = gr.Textbox(label="Тема", placeholder="Daily routines")
                goal = gr.Textbox(label="Цель", placeholder="Практика Present Simple")
                duration = gr.Slider(label="Длительность (мин)*", minimum=30, maximum=180, value=60, step=5)
                inventory = gr.Textbox(label="Инвентарь", placeholder="Карточки, проектор...")

            # Блок 4: Методика
            with gr.Column(variant="panel"):
                gr.Markdown("### 🎓 Методика", elem_classes=["block-title"])
                methodology = gr.Dropdown(label="Методика преподавания*",
                                          choices=["PPP (Presentation-Practice-Production)",
                                                   "TTT (Test-Teach-Test)"],
                                          value="PPP (Presentation-Practice-Production)")

                advanced_btn = gr.Button(value="➕ Продвинутые настройки", size="sm")

                # Блок продвинутых настроек, изначально скрыт
                with gr.Column(visible=False) as advanced_block:
                    gr.Markdown("**💡 Уровни задач (таксономия):**")
                    repetition = gr.Checkbox(label="Повторение")
                    application = gr.Checkbox(label="Применение")
                    analysis = gr.Checkbox(label="Анализ")
                    creativity = gr.Checkbox(label="Творчество")

                hw_required = gr.Checkbox(label="Домашнее задание")
                web_search = gr.Checkbox(label="Доп. материалы из интернета")

            btn = gr.Button("Сгенерировать план", variant="primary", size="lg")

        with gr.Column(scale=2):  # правый блок
            output = gr.Markdown("## План урока появится здесь...")
            download_btn = gr.DownloadButton(label="⬇️ Скачать .docx", visible=False)


    # --- Логика интерфейса ---
    def toggle_advanced():
        return gr.update(visible=True)


    advanced_btn.click(
        fn=lambda v: not v,
        inputs=advanced_block,
        outputs=advanced_block
    )


    # Функция для переключения видимости полей в зависимости от формата занятия
    def toggle_format(selected_format):
        return gr.update(visible=selected_format == "Групповое")


    format_type.change(fn=toggle_format, inputs=format_type, outputs=group_settings)


    # Функция для переключения поля возраста
    def toggle_age(adult_checked):
        return gr.update(interactive=not adult_checked)


    adults.change(fn=toggle_age, inputs=adults, outputs=age)


    # Коллбек генерации
    def on_generate(
            image, textbook, cefr, topic, goal, format_type, num_students,
            age, adults, level_match, duration, inventory, methodology,
            hw_required, web_search, repetition, application, analysis, creativity
    ):
        # Проверка обязательных полей
        if not image or (not adults and not age):
            return gr.update(value="❗ Заполните обязательные поля (отмечены *)"), gr.update(visible=False)

        text = generate_lesson_plan(
            image, textbook, cefr, topic, goal, format_type, num_students,
            age, adults, level_match, duration, inventory, methodology,
            hw_required, web_search, repetition, application, analysis, creativity
        )

        docx_path = generate_docx(text) if not text.startswith("❗") else None
        return gr.update(value=text), gr.update(visible=bool(docx_path), value=docx_path)


    btn.click(
        fn=on_generate,
        inputs=[
            image, textbook, cefr, topic, goal, format_type, num_students,
            age, adults, level_match, duration, inventory, methodology,
            hw_required, web_search, repetition, application, analysis, creativity
        ],
        outputs=[output, download_btn]
    )

if __name__ == "__main__":
    app.launch()