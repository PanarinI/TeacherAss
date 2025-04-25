METHODOLOGY_TIPS = {
    "PPP": """
    [МЕТОДИКА PPP]
    Обязательные этапы:
    1. Presentation (5-10 мин): Покажи пример через диалог/текст
    2. Practice (15 мин): Упражнения на подстановку/трансформацию
    3. Production (20 мин): Ролевая игра или создание своего контента
    Пример: стр. 45 учебника → упражнение 3A → написание диалога
    """,

    "TTT": """
    [МЕТОДИКА TTT]
    Обязательные этапы:
    1. Test (10 мин): Диагностический тест
    2. Teach (15 мин): Объяснение проблемных мест
    3. Test (20 мин): Применение в новой ситуации
    Пример: предтест на времена → объяснение Past Perfect → кейсы
    """
}


def build_prompt(params):
    base_prompt = f"""
    Создай план урока по этим данным:
    - Страница из учебника, которую ты видишь
    - Учебник: {params['textbook']} or 
    - Уровень учебника по CEFR: {params['cefr']}
    - Тема занятия: {params['topic']}
    - Цель занятия: {params['goal']}
    - Продолжительность: {params['duration']} мин
    - Кол-во учащихся: {params['num_students']} чел, возраст: {params['age']}
    - Методика: {params['methodology']}

    Особые указания:
    """

    # Добавляем советы по методике
    methodology_advice = METHODOLOGY_TIPS.get(params['methodology'], "")

    return base_prompt + methodology_advice