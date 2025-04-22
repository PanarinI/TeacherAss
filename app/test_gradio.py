import os
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
import requests
import logging
from typing import Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Загрузка переменных окружения
load_dotenv()
api_key = os.getenv("API_KEY_openai")
client = OpenAI(api_key=api_key) if api_key else None
VS_ID = os.getenv("VECTOR_STORE_ID", "")


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
        logging.error(f"Ошибка загрузки: {e}")
        raise gr.Error("Не удалось загрузить изображение")


def generate_lesson_plan(
    textbook: str,
    subject: str,
    methodology: str,
    duration: int,
    hw_required: bool,
    file_search: bool,
    image_path: Optional[str] = None
) -> str:
    """Генерация детального плана урока"""
    if not client:
        raise gr.Error("API ключ не настроен или некорректен")

    image_url = None
    if image_path:
        try:
            with open(image_path, "rb") as f:
                image_url = upload_to_catbox(f.read())
        except Exception as e:
            logging.error(f"Image error: {e}")

    # Формируем контент для запроса
    content = [
        {"type": "text", "text": (
            f"Создай подробный план урока:\n"
            f"- Учебник: {textbook}\n"
            f"- Предмет: {subject}\n"
            f"- Методика: {methodology}\n"
            f"- Длительность: {duration} мин\n"
            f"- Домашнее задание: {'Да' if hw_required else 'Нет'}"
        )}
    ]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    # Инструмент file_search (при наличии)
    tools = None
    tool_choice = None
    include = None
    if file_search and VS_ID:
        tools = [{
            "type": "file_search",
            "vector_store_ids": [VS_ID],
            "max_num_results": 10
        }]
        tool_choice = {"type": "file_search"}
        include = ["file_search_call.results"]

    try:
        response = client.responses.create(
            instructions="Ты эксперт-педагог. Составь детальный план урока.",
            input=content,
            model="gpt-4o-mini",
            tools=tools,
            tool_choice=tool_choice,
            include=include,
            max_output_tokens=2000
        )
        return response.output_text
    except Exception as e:
        logging.error(f"Generation error: {e}")
        raise gr.Error(f"Ошибка генерации: {e}")


# Интерфейс Gradio
with gr.Blocks(title="Генератор уроков") as app:
    with gr.Row():
        with gr.Column():
            image = gr.Image(label="Фото страницы учебника (опционально)", type="filepath")
            textbook = gr.Textbox(label="Учебник*", placeholder="Название учебника")
            subject = gr.Textbox(label="Предмет*", placeholder="Название предмета")
            methodology = gr.Dropdown(
                label="Методика*",
                choices=["PPP", "TTT", "Интерактивная"],
                value="PPP"
            )
            with gr.Accordion("Дополнительно"):
                duration = gr.Slider(15, 120, 45, step=5, label="Длительность (мин)")
                hw_required = gr.Checkbox(label="Домашнее задание")
                file_search = gr.Checkbox(label="Поиск в базах документов")
            btn = gr.Button("Сгенерировать", variant="primary")
        with gr.Column():
            output = gr.Markdown("## План урока")

    btn.click(
        fn=generate_lesson_plan,
        inputs=[image, textbook, subject, methodology, duration, hw_required, file_search],
        outputs=output
    )

if __name__ == "__main__":
    app.launch()
