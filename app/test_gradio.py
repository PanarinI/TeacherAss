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
    hw_required: bool,
    web_search: bool
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
        f"- **CEFR-уровень**: {'определи по загруженной странице' if not cefr else cefr}",
        f"- **Тема**: {topic or 'определи по загруженной странице'}",
        f"- **Цель занятия**: {goal or 'определи по загруженной странице'}",
        f"- **Формат**: {format_type} ({num_students} {'ребёнок' if num_students==1 else 'детей'})",
        f"- **Возраст**: {'взрослые' if adults else age}",
        f"- **Соответствие класса уровню учебника**: {['below','on-level','above','mixed'][level_match]}",
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
            "detail": "high"  # или "auto" для автоматической оптимизации
        }
    ]


    # Опции инструментов
    tools = []
    tool_choice = None
    # web_search заглушка
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
            #include=["file_search_call.results"],
            max_output_tokens=2000,
            #reasoning={"effort": "medium"},
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
            textbook = gr.Textbox(label="Учебник", placeholder="Название учебника, напр. English File Beginner")
            cefr = gr.Dropdown(label="CEFR-уровень", choices=["A1", "A2", "B1", "B2", "C1", "C2"], value="",
                               info="необязательно")
            topic = gr.Textbox(label="Тема занятия", placeholder="напр. Daily routines", info="необязательно")
            goal = gr.Textbox(label="Цель", placeholder="напр. практика Present Simple в вопросах",
                              info="необязательно")
            format_type = gr.Radio(label="Формат занятия", choices=["Индивидуальное", "Групповое"], value="Групповое")

            # Контейнер для элементов, зависящих от формата занятия
            with gr.Group(visible=True) as group_settings:
                num_students = gr.Slider(label="Количество детей*", minimum=2, maximum=40, value=10, step=1)

            # Контейнер для элементов возраста
            with gr.Group() as age_group:
                age = gr.Textbox(label="Возраст*", placeholder="напр. 10–11", interactive=True)
                adults = gr.Checkbox(label="Взрослые")

            level_match = gr.Slider(label="Соответствие уровня учебника", minimum=0, maximum=3, step=1, value=1,
                                    info="0=below,1=on-level,2=above,3=mixed")

            hw_required = gr.Checkbox(label="Домашнее задание")
            web_search = gr.Checkbox(label="Доп. материалы из интернета")
            btn = gr.Button("Сгенерировать план", variant="primary")

        with gr.Column(scale=2):  # правый блок
            output = gr.Markdown("## План урока появится здесь...")
            download_btn = gr.DownloadButton(label="⬇️ Скачать .docx", visible=False)


    # Функция для переключения видимости полей в зависимости от формата занятия
    def toggle_format(selected_format):
        if selected_format == "Индивидуальное":
            return gr.update(visible=False)
        else:
            return gr.update(visible=True)


    # Функция для переключения поля возраста
    def toggle_age(adult_checked):
        return gr.update(interactive=not adult_checked)


    # Привязка событий
    format_type.change(fn=toggle_format, inputs=format_type, outputs=group_settings)
    adults.change(fn=toggle_age, inputs=adults, outputs=age)

    # Коллбек генерации
    def get_inputs():
        """Централизованное место объявления всех inputs"""
        return [
            image, textbook, cefr, topic, goal, format_type,
            num_students, age, adults, level_match, hw_required, web_search
        ]


    def on_generate(*args):
        # Проверка обязательных полей
        if not args[0] or (not args[7] and not args[8]):  # image, age, adults
            return gr.update(value="❗ Заполните обязательные поля..."), gr.update(visible=False)

        text = generate_lesson_plan(*args)
        docx_path = generate_docx(text) if not text.startswith("❗") else None
        return gr.update(value=text), gr.update(visible=bool(docx_path), value=docx_path)


    # Использование:
    inputs = get_inputs()
    btn.click(fn=on_generate, inputs=inputs, outputs=[output, download_btn])

if __name__ == "__main__":
    app.launch()
