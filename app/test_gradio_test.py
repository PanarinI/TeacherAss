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

import random
from app.quotes import quotes
from app.drawings import drawings
from app.knowledge_base.textbooks import TEXTBOOKS
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

# названия textbooks для автозаполнения поля Учебник
import json

## Сохраняем отзыв через POST в google-таблицу
GOOGLE_SHEET_URL = os.getenv("FEEDBACK_GS_URL")

def save_feedback(comment, rate):
    payload = {
        "comment": comment,
        "rate": rate
    }
    try:
        requests.post(GOOGLE_SHEET_URL, json=payload, timeout=3)
    except Exception as e:
        print(f"Ошибка при отправке отзыва: {e}")

### ОСНОВНАЯ ФУНКЦИЯ ГЕНЕРАЦИИ
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
        extra_info: str,
        methodology: str,
        target_language: str,
        hw_required: bool,
        web_search: bool
        # repetition: bool,
        # application: bool,
        # analysis: bool,
        # creativity: bool
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
    lesson_params = {
        'methodology': methodology,
        'target_language': target_language, # для PPP
        'textbook': textbook,
        'cefr': cefr,
        'topic': topic,
        'goal': goal,
        'num_students': num_students,
        'age': 'Взрослые' if adults else age,
        'level_match': level_match,
        'duration': duration,
        'inventory': inventory,
        'hw_required': hw_required,
        'extra_info': extra_info
    }

    # Получаем готовый промпт
    from app.prompt_builder.prompt import build_prompt
    full_prompt = build_prompt(lesson_params)

    # Собираем входные данные согласно API
    input_content = [
        {
            "type": "input_text",
            "text": full_prompt
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
            input=[{"role": "user", "content": input_content}],
            model="o4-mini", #  gpt-4o-mini    gpt-4.1
            tools=tools or None,
            tool_choice=tool_choice,
            max_output_tokens=8192,
            reasoning= {"effort":"medium"},
            stream=False
        )
        return response.output_text

    except Exception as e:
        logging.error(f"Generation error: {e}")
        raise gr.Error(f"Ошибка генерации: {e}")



########## ИНТЕРФЕЙС
# Случайный рисунок в блокноте
drawing = random.choice(drawings)
# Текст с подсказкой и рисунком в блокноте
hint_text = f"""Здесь появится план занятия — заполните вводные и нажмите кнопку **Создать план**<br>
Создание может занять до 1 минуты
<pre>
{drawing}
</pre>
"""

#ТЕМА И СТИЛИ
### css привязывать именно так
#theme='earneleh/paris'
theme = gr.themes.Base(
    secondary_hue="rose",
    neutral_hue="stone",
).set(
    body_background_fill='*primary_50',
    body_text_color='*primary_900',
    body_text_size='*text_lg',
    body_text_color_subdued='*primary_700',
    body_text_weight='600',
)
css_path = os.path.join(os.path.dirname(__file__), "styles.css")

# ИНТЕРФЕЙС
with gr.Blocks(theme=theme, css_paths=css_path) as app:
    advanced_settings_visible = gr.State(value=False)  # Импортируем gr.State для хранения состояния
    feedback_visible = gr.State(False)  # Хранит, открыт ли блок отзыва

    gr.Markdown("# План урока английского языка", elem_classes=["main-title"])
    quote_box = gr.Markdown(random.choice(quotes), elem_classes=["quote-block"])
    with gr.Row():
        with gr.Column(elem_classes=["left-col"], scale=1):
            image = gr.Image(
                label="Фото страницы учебника*",
                type="filepath",
                height=100,  # Автоматическая высота
                container=False  # Не растягивать контейнер
            )

            # Блок 1: Учебник
            with gr.Column(variant="panel"):
                gr.Markdown("### 📚 Учебник", elem_classes=["block-title"])
                textbook = gr.Textbox(label="Название учебника", placeholder="напр. English File Beginner", elem_id="textbook_input")

                cefr = gr.Dropdown(label="CEFR-уровень", choices=["", "A1", "A2", "B1", "B2", "C1", "C2"],
                                   value="", info="Выберите уровень")
            # Блок 2: Класс
            with gr.Column(variant="panel"):
                gr.Markdown("### 👥 Класс", elem_classes=["block-title"])
                format_type = gr.Radio(label="Формат занятия", choices=["Индивидуальное", "Групповое"],
                                       value="Групповое")

                with gr.Group(visible=True) as group_settings:
                    num_students = gr.Slider(label="Количество учеников", minimum=1, maximum=40,
                                             value=10, step=1, info="Для групповых занятий")

                with gr.Group() as age_group:
                    age = gr.Textbox(label="Возраст", placeholder="напр. 10–11", interactive=True)
                    adults = gr.Checkbox(label="Взрослые")

                level_match = gr.Dropdown(label = "Уровень учеников относительно учебника",
                    choices = ["ниже", "на уровне", "выше", "mixed"], value = "на уровне")

            # Блок 3: Занятие
            with gr.Column(variant="panel"):
                gr.Markdown("### 📄 Занятие", elem_classes=["block-title"])
                topic = gr.Textbox(label="Тема", placeholder="напр. Daily routines")
                goal = gr.Textbox(label="Цель", placeholder="К концу урока ученики смогут...")
                duration = gr.Slider(label="Длительность (мин)", minimum=30, maximum=180, value=60, step=5)
                inventory = gr.Textbox(label="Инвентарь", placeholder="по умолчанию - доска и проектор")
                extra_info = gr.Textbox(label="Допонительная информация", placeholder="Класс весёлый и взвинченный после физкультуры")

            # Блок 4: Методика
            with gr.Column(variant="panel"):
                gr.Markdown("### 🎓 Методика", elem_classes=["block-title"])
                methodology = gr.Dropdown(label="Методика преподавания",
                                          choices=["PPP (Presentation-Practice-Production)",
                                                   "TTT (Test-Teach-Test)"],
                                          value="PPP (Presentation-Practice-Production)")
                target_language = gr.Textbox(
                    label="Target language",
                    placeholder="Например: 'I have been to...' 'How long have you...?' (Present Perfect experience)",
                    visible=True  # По умолчанию видно, так как PPP выбран
                )

                # advanced_btn = gr.Button(value="➕ Продвинутые настройки (в разработке", size="sm")
                #
                # # Блок продвинутых настроек, изначально скрыт
                # with gr.Column(visible=False) as advanced_block:
                #     gr.Markdown("**💡 Уровни задач (таксономия):**")
                #     repetition = gr.Checkbox(label="Повторение")
                #     application = gr.Checkbox(label="Применение")
                #     analysis = gr.Checkbox(label="Анализ")
                #     creativity = gr.Checkbox(label="Творчество")

                hw_required = gr.Checkbox(label="Домашнее задание")
                web_search = gr.Checkbox(label="Доп. материалы из интернета")

            btn = gr.Button("Создать план", variant="primary", size="lg")

        # Правая колонка — результат (output)
        with gr.Column(elem_classes=["right-col"], scale=2):
            # Общий блок-панель для правой колонки
            with gr.Column(variant="panel"):  # <<< Главная панель
                gr.Markdown("### План урока", elem_classes=["block-title"])  # Заголовок ВНУТРИ панели
                # Блок с выводом плана
                output = gr.Markdown(
                    hint_text,
                    elem_id="plan-output"
                )
                # Кнопка скачивания (оставляем внутри панели)
                download_btn = gr.DownloadButton(
                    label="⬇️ Скачать .docx",
                    visible=False
                )
            # Кнопка "Помогите нам стать лучше"
            feedback_btn = gr.Button("💬 Помогите нам стать лучше", elem_classes=["feedback-button"])

            # Скрытый блок с обратной связью
            with gr.Column(visible=False) as feedback_block:
                gr.Markdown("_Спасибо, что попробовали! Как вам?_\n_Ваши наблюдения и замечания помогают нам расти._")


                def toggle_feedback_block(current_visible):
                    return (
                        gr.update(visible=not current_visible),  # показать/скрыть блок
                        not current_visible,  # обновить состояние
                        gr.update(visible=False)  # скрыть благодарность при открытии/закрытии
                    )
                feedback_text = gr.Textbox(
                    label="Ваше наблюдение или комментарий",
                    placeholder="Например: 'Для 3 лет лексика подбирается неправильно — какая там 'машина', максимум - 'би-би'",
                    lines=4
                )

                rating = gr.Radio(
                    choices=["1", "2", "3", "4", "5"],
                    label="Оценка"
                )

                send_feedback = gr.Button("📩 Отправить отзыв")

                feedback_confirmation = gr.Markdown(
                    visible=False,
                    elem_classes=["feedback-confirmation"]
                )

            # <-- Блок благодарности — ВНЕ feedback_block, но СРАЗУ ПОСЛЕ
            with gr.Column(visible=False) as feedback_confirmation:
                gr.Markdown("✅ Спасибо! Ваш комментарий передан и, возможно, уже сегодня ассистент станет полезнее :)")

            # Остальное
            gr.Markdown(
                """
                🙌 Если вас заинтересовал проект, мы приглашаем
                👉 [присоединиться к Telegram-группе](https://t.me/+ygYoYjeD1msyMWZi)
                """
            )

    ### --- Логика интерфейса ---
    # Доп. настройки
    def toggle_advanced_settings(visible):
        return gr.update(visible=not visible), not visible

    # advanced_btn.click(
    #     fn=toggle_advanced_settings,
    #     inputs=[advanced_settings_visible],
    #     outputs=[advanced_block, advanced_settings_visible]
    # )

    # Формат занятия - видимость поля если выбрано групповое
    def toggle_format(selected_format):
        return gr.update(visible=selected_format == "Групповое")
    format_type.change(fn=toggle_format, inputs=format_type, outputs=group_settings)

    # Возраст - деактивация поля если нажато "Взрослые"
    def toggle_age(adult_checked):
        return gr.update(interactive=not adult_checked)
    adults.change(fn=toggle_age, inputs=adults, outputs=age)

    # Функция для переключения видимости Target language
    def toggle_target_language(methodology_value):
        return gr.update(visible=methodology_value == "PPP (Presentation-Practice-Production)")
    methodology.change(fn=toggle_target_language, inputs=methodology, outputs=target_language)

    # JS для автодополнения
    app.load(
        None,
        None,
        js=f"""
        const textbooks = {TEXTBOOKS};

        function setupAutocomplete() {{
            const input = document.getElementById('textbook_input');
            if (!input) return;

            const datalist = document.createElement('datalist');
            datalist.id = 'textbook_suggestions';

            textbooks.forEach(book => {{
                const option = document.createElement('option');
                option.value = book;
                datalist.appendChild(option);
            }});

            input.setAttribute('list', datalist.id);
            document.body.appendChild(datalist);
        }}

        // Запускаем после загрузки
        if (document.readyState === 'complete') {{
            setupAutocomplete();
        }} else {{
            document.addEventListener('DOMContentLoaded', setupAutocomplete);
        }}
        """
    )
    ### СПИСОК ВСЕХ ПАРАМЕТРОВ ИНТЕРФЕЙСА
    all_inputs = [
        image,  # Gradio компонент, соответствует image_path в функциях
        textbook,
        cefr,
        topic,
        goal,
        format_type,
        num_students,
        age,
        adults,
        level_match,
        duration,
        inventory,
        extra_info,
        methodology,
        target_language,
        hw_required,
        web_search
        # repetition,
        # application,
        # analysis,
        # creativity
    ]

    # Коллбек генерации
    def on_generate(
            image_path: Optional[str],  # Переименовано из image
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
            extra_info: str,
            methodology: str,
            target_language: str,
            hw_required: bool,
            web_search: bool
            # repetition: bool,
            # application: bool,
            # analysis: bool,
            # creativity: bool
    ):
        # Проверка обязательных полей
        if not image_path or (not adults and not age):
            return gr.update(value="❗ Заполните обязательные поля (отмечены *)"), gr.update(visible=False)

        # Собираем все аргументы в словарь
        kwargs = locals()

        # Генерация плана
        text = generate_lesson_plan(**kwargs)

        # Создание DOCX
        docx_path = generate_docx(text) if not text.startswith("❗") else None
        return gr.update(value=text), gr.update(visible=bool(docx_path), value=docx_path)

    btn.click(
        fn=on_generate,
        inputs=all_inputs,
        outputs=[output, download_btn]
    )

    # Логика: показать форму по нажатию на кнопку
    feedback_btn.click(
        fn=toggle_feedback_block,
        inputs=[feedback_visible],
        outputs=[feedback_block, feedback_visible, feedback_confirmation]
    )

    # Логика отправки обратной связи
    def send_feedback_fn(comment, rate):
        save_feedback(comment, rate)  # Сохраняем отзыв
        return (
            gr.update(visible=False),  # свернуть форму
            False,  # сбросить состояние
            gr.update(
                value="✅ Спасибо! Ваш комментарий передан, и, возможно, уже сегодня ассистент станет полезнее :)",
                visible=True
            )
        )

    send_feedback.click(
        fn=send_feedback_fn,
        inputs=[feedback_text, rating],
        outputs=[feedback_block, feedback_visible, feedback_confirmation]
    )


if __name__ == "__main__":
    app.launch()