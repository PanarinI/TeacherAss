import os
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
import requests
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Загрузка переменных окружения
load_dotenv()
api_key = os.getenv("API_KEY_openai")
client = OpenAI(api_key=api_key) if api_key else None


def analyze_image(image_url: str):
    if not client:
        raise gr.Error("API ключ OpenAI не настроен")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Исправлено на корректное имя модели
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
            ],
            max_tokens=300
        )
        return parse_response(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"Ошибка анализа: {e}")
        raise gr.Error(f"Ошибка при анализе изображения: {str(e)}")


def generate_lesson_plan(
    textbook: str,
    subject: str,
    methodology: str,
    duration: int,
    hw_required: bool,
    file_search: bool,
    image_url: str = None
):
    # Формирование контента для API
    content = [
        {"type": "text", "text": f"""
        Создай структурированный план урока со следующими параметрами:
        - Учебник: {textbook}
        - Предмет: {subject}
        - Методика: {methodology}
        - Длительность: {duration} минут
        - Домашнее задание: {'требуется' if hw_required else 'не требуется'}
        """}
    ]

    # Динамически добавляем изображение если есть
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})

    # Подготовка инструментов
    tools = []
    tool_choice = None
    if file_search:
        tools.append({
            "type": "file_search",
            "vector_store_ids": [VS_ID],
            "max_num_results": 10
        })
        tool_choice = {"type": "file_search"}

    # Вызов API через responses.create()
    try:
        response = client.responses.create(
            instructions="Ты эксперт в области образования. Составь детальный план урока.",
            input=content,
            model="gpt-4o-mini",
            tools=tools if tools else None,
            tool_choice=tool_choice,
            include=["file_search_call.results"] if file_search else None,
            max_output_tokens=8192,
            #reasoning={"effort": "medium"},
            stream=False
        )

        # Обработка ответа
        try:
            return response.output_text
        except AttributeError:
            logging.error("Не удалось получить output_text из ответа")
            return "Ошибка: некорректный формат ответа"

    except Exception as e:
        logging.error(f"API Error: {str(e)}")
        raise gr.Error(f"Ошибка генерации: {str(e)}")


# Упрощенный интерфейс для тестирования
def process_inputs(image, textbook, subject, methodology, auto_detect):
    try:
        if image and auto_detect:
            # Для теста просто возвращаем примерные значения
            return "Математика", "Алгебра 7 класс", "Пример плана урока будет здесь"

        return generate_lesson_plan(
            textbook=textbook or "Не указан",
            subject=subject or "Не указан",
            methodology=methodology or "PPP"
        )
    except Exception as e:
        return f"Ошибка: {str(e)}"


with gr.Blocks(title="Генератор планов уроков") as demo:
    gr.Markdown("## Генератор планов уроков")

    with gr.Row():
        with gr.Column():
            # Секция изображения
            auto_detect = gr.Checkbox(label="Использовать автоопределение", value=True)
            image = gr.Image(label="Обложка учебника", type="filepath")

            # Основные параметры
            textbook = gr.Textbox(label="Название учебника*")
            subject = gr.Textbox(label="Предмет*")
            methodology = gr.Dropdown(
                label="Методика обучения*",
                choices=["PPP", "TTT", "Интерактивная", "Проектная"],
                value="PPP"
            )

            # Дополнительные параметры
            with gr.Accordion("Дополнительные настройки", open=False):
                duration = gr.Slider(15, 120, value=45, step=5, label="Длительность урока (мин)")
                hw_required = gr.Checkbox(label="Домашнее задание")
                file_search = gr.Checkbox(label="Использовать файловый поиск", value=False)

            btn = gr.Button("Сгенерировать план", variant="primary")

        with gr.Column():
            output = gr.Markdown("## Ваш план урока появится здесь")

    btn.click(
        fn=generate_lesson_plan,
        inputs=[textbook, subject, methodology, duration, hw_required, file_search, image],
        outputs=output
    )

if __name__ == "__main__":
    try:
        demo.launch(
            server_port=7861,  # Пробуем другой порт
            inbrowser=True,
            show_error=True
        )
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        demo.launch()