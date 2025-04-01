мне нужно сделать простое приложение по генерации планов уроков на базе предоставленной фотографии страницы учебника. 
Для интерфейса используем streamlit. Логика такая - экран делится не левую и правую части. В левой части область загрузки 
фотографии страницы учебника + поля заполнения и настройки (они появляются после успешной загрузки). 
При загрузке файла и получения его url, url первый раз передается в LLM (gpt-4o-mini) через chat.completions. 
Промпт дает модели задание определить предмет (английский, математика и т.п.) и название учебника. 
Я предлагаю использовать structured output для этого. Предмет и название учебника попадают в поля, которые появляются под областью загрузки (в области слева). 
Если модель не смогла определить предмет и/или учебник - поля просто остаются пустыми и являются обязательнми для заполнения учителем. 
Это первый шаг. Второй шаг - это настройки. Учитель определяет количество детей в классе от 1 до 40 (ползунок) и нажимает кнопку "создать план урока", 
которая становится активна только после заполнения полей предмета и учебника. Ползунок количества детей изначально стоит на значении 10. 
Эти данные (предмет, учебник, количество детей в классе) передаются на второй запрос к chat.completions вместе с url страницы учебника. 
Этот второй запрос должен создать план урока по промпту. В промпте мы просим модель создать план урока на основании предоставленного изображения 
страницы учебника и на основании переданных данных (предмет, учебник, количество детей в классе) План урока должен обязательно опираться на 
предоставленный материал - где нужно указываются номера упражнений, примеры и так далее. 

Модель gpt-4o-mini поддержкивает input image.
Длительное хранение загруженных изображений не требуется, поэтому решение tmpfiles.org подходит.


Structured Outputs через response_format с JSON Schema , так как:


from pydantic import BaseModel
from openai import OpenAI

class TextbookInfo(BaseModel):
    subject: str  # Предмет (например, "Английский язык")
    textbook_name: str  # Название учебника (например, "Spotlight 5")

client = OpenAI()
completion = client.beta.chat.completions.parse(
    model="gpt-4o-mini-2024-07-18",  # Убедитесь, что модель поддерживает Structured Outputs
    messages=[
        {"role": "system", "content": "Определи предмет и название учебника по изображению страницы. Если не уверен — оставь поля пустыми."},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": uploaded_image_url}},
            {"type": "text", "text": "Что это за учебник? Определи предмет и точное название."}
        ]}
    ],
    response_format=TextbookInfo  # Автоматически генерирует JSON Schema
)
textbook_data = completion.choices[0].message.parsed

Image input:

Analyze the content of an image

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                },
            },
        ],
    }],
)

print(response.choices[0].message.content)


Вот так мы получаем url:

def upload_image(image_bytes):
    """Загрузка изображения"""
    try:
        response = requests.post(
            "https://tmpfiles.org/api/v1/upload",
            files={"file": image_bytes},
            timeout=10
        )
        return response.json()["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return None