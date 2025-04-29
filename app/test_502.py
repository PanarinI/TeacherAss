import gradio as gr

def greet(name):
    return f"Привет, {name}!"

demo = gr.Interface(
    fn=greet,
    inputs=gr.Textbox(label="Введите ваше имя"),
    outputs=gr.Textbox(label="Приветствие")
)

if __name__ == "__main__":
    # Отключаем проверку localhost и пробуем разные порты
    try:
        demo.launch(
            server_port=7860,
            prevent_thread_lock=True,  # Не блокировать основной поток
            show_error=True,          # Показывать детальные ошибки
            inbrowser=True            # Автоматически открывать браузер
        )
        input("Нажмите Enter чтобы остановить сервер...")  # Держим сервер активным
    except Exception as e:
        print(f"Ошибка: {e}")