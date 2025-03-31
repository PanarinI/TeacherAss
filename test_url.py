import boto3
from botocore.exceptions import ClientError

# Конфигурация (замените своими значениями)
CONFIG = {
    "endpoint": "https://s3.timeweb.cloud",  # или https://s3.twcstorage.ru
    "bucket": "47ebf6c8-b07131f2-a7c5-45b2-9db0-9b0a86ad3cca",  # ваш bucket ID
    "access_key": "SCJC187UUO758WCR6BGV",  # ваш ключ (начинается на SCJ)
    "secret_key": "Rd9LmpU1F2KErPA7aEQvDwDDIzQ8FD8YzymiBQEt",  # длинная строка из TimeWeb S3 API
    "file_path": "Materials/small.txt"  # путь к тестовому файлу
}


def test_upload():
    """Тест загрузки файла с максимально простой конфигурацией"""
    try:
        # 1. Инициализация клиента
        s3 = boto3.client(
            's3',
            endpoint_url=CONFIG['endpoint'],
            aws_access_key_id=CONFIG['access_key'],
            aws_secret_access_key=CONFIG['secret_key'],
            region_name='ru-1',
            config=boto3.session.Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            )
        )

        # 2. Проверка доступа к бакету
        print("\n1. Проверка доступа к бакету...")
        s3.head_bucket(Bucket=CONFIG['bucket'])
        print(f"✅ Бакет '{CONFIG['bucket']}' доступен")

        # 3. Чтение файла
        print("\n2. Чтение файла...")
        with open(CONFIG['file_path'], 'rb') as f:
            file_data = f.read()
        print(f"✅ Файл прочитан ({len(file_data)} байт)")

        # 4. Загрузка файла
        print("\n3. Загрузка файла...")
        # Вместо put_object используем upload_file
        s3.upload_file(
            CONFIG['file_path'],
            CONFIG['bucket'],
            "test_upload.png",
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': 'image/png'
            }
        )
        print("✅ Файл успешно загружен")

        # 5. Проверка доступности
        print("\n4. Проверка доступности...")
        url = f"{CONFIG['endpoint']}/{CONFIG['bucket']}/test_upload.png"
        print(f"URL файла: {url}")

        # Проверка через head_object
        response = s3.head_object(Bucket=CONFIG['bucket'], Key="test_upload.png")
        print(f"Статус: {response['ResponseMetadata']['HTTPStatusCode']}")
        print(f"Размер: {response['ContentLength']} байт")

    except ClientError as e:
        print("\n❌ Критическая ошибка:")
        print(f"Тип: {type(e).__name__}")
        print(f"Код: {e.response['Error']['Code']}")
        print(f"Сообщение: {e.response['Error']['Message']}")
        print(f"Детали: {e.response}")

    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {str(e)}")


if __name__ == "__main__":
    print("=== Тест загрузки в TimeWeb S3 ===")
    test_upload()