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
    """Загружает изображение на catbox.moe"""
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
        logging.error(f"Ошибка загрузки: {str(e)}")
        raise gr.Error("Не удалось загрузить изображение")


def analyze_image(image_url: str) -> tuple[str, str]:
    """Анализ изображения через Vision API"""
    if not client:
        raise gr.Error("API ключ не настроен")

    try:
        response = client.responses.create(
            instructions="Определи предмет и учебник по обложке",
            input=[
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": "Ответь в формате:\nПредмет: [название]\nУчебник: [название]"}
            ],
            model="gpt-4o-mini",
            max_output_tokens=300
        )
        return parse_response(response.output_text)
    except Exception as e:
        logging.error(f"Vision API error: {str(e)}")
        raise gr.Error(f"Ошибка анализа: {str(e)}")


def parse_response(text: str) -> tuple[str, str]:
    """Парсинг ответа от API"""
    subject = textbook = "Не определено"
    for line in text.split('\n'):
        line = line.lower().strip()
        if "предмет:" in line:
            subject = line.split("предмет:")[1].strip().capitalize()
        elif "учебник:" in line:
            textbook = line.split("учебник:")[1].strip().capitalize()
    return subject, textbook


def generate_lesson_plan(
        textbook: str,
        subject: str,
        methodology: str,
        duration: int,
        hw_required: bool,
        file_search: bool,
        image_path: Optional[str] = None
) -> str:
    """Основная функция генерации плана"""
    if not client:
        raise gr.Error("API ключ не работает")

    # Загрузка изображения
    image_url = None
    if image_path:
        try:
            with open(image_path, "rb") as f:
                image_url = upload_to_catbox(f.read())
        except Exception as e:
            logging.error(f"Image error: {str(e)}")

    # Формирование запроса
    content = [
        {"type": "text", "text": f"""
        Создай план урока:
        - Учебник: {textbook}
        - Предмет: {subject}
        - Методика: {methodology}
        - Длительность: {duration} мин
        - ДЗ: {'Да' if hw_required else 'Нет'}
        """}
    ]

    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    # Настройка инструментов
    tools = []
    if file_search and VS_ID:
        tools.append({
            "type": "file_search",
            "vector_store_ids": [VS_ID],
            "max_num_results": 10
        })

    try:
        response = client.responses.create(
            instructions="Ты эксперт-педагог. Составь детальный план урока.",
            input=content,
            model="gpt-4o-mini",
            tools=tools if tools else None,
            tool_choice={"type": "file_search"} if tools else None,
            include=["file_search_call.results"] if tools else None,
            max_output_tokens=2000
        )
        return response.output_text
    except Exception as e:
        logging.error(f"Generation error: {str(e)}")
        raise gr.Error(f"Ошибка генерации: {str(e)}")


# Интерфейс
with gr.Blocks(title="Генератор уроков") as app:
    with gr.Row():
        with gr.Column():
            auto_detect = gr.Checkbox(label="Автоопределение", value=True)
            image = gr.Image(label="Фото учебника", type="filepath")

            textbook = gr.Textbox(label="Учебник*")
            subject = gr.Textbox(label="Предмет*")
            methodology = gr.Dropdown(
                label="Методика*",
                choices=["PPP", "TTT", "Интерактивная"],
                value="PPP"
            )

            with gr.Accordion("Дополнительно"):
                duration = gr.Slider(15, 120, 45, step=5, label="Длительность (мин)")
                hw_required = gr.Checkbox(label="Домашнее задание")
                file_search = gr.Checkbox(label="Поиск в базах")

            btn = gr.Button("Сгенерировать", variant="primary")

        with gr.Column():
            output = gr.Markdown("## План урока")

    btn.click(
        fn=lambda img, tb, sb, meth, dur, hw, fs, ad: (
            analyze_image(upload_to_catbox(open(img, "rb").read())) if ad and img else (tb, sb),
            generate_lesson_plan(tb, sb, meth, dur, hw, fs, img)
        )[1],
        inputs=[image, textbook, subject, methodology, duration, hw_required, file_search, auto_detect],
        outputs=output
    )

if __name__ == "__main__":
    app.launch(server_port=7860)