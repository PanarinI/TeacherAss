import requests

def upload_to_catbox(file_path):
    """Загружает файл на catbox.moe и возвращает прямую ссылку"""
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                "https://catbox.moe/user/api.php",
                files={"fileToUpload": f},
                data={"reqtype": "fileupload"}
            )
            response.raise_for_status()
            return response.text.strip()  # Пример: https://files.catbox.moe/abc123.png
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

url = upload_to_catbox("materials/test.png")
if url:
    print(f"✅ Прямая ссылка на файл: {url}")
else:
    print("Не удалось загрузить файл")