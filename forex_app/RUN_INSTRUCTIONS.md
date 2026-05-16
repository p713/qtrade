# Инструкция по запуску Forex Trading Application

## Быстрый старт

### 1. Установка зависимостей
```bash
cd /workspace/forex_app
pip install -r requirements.txt
```

### 2. Настройка конфигурации

**Важно:** Перед использованием приложения необходимо настроить API ключи для LLM!

1. Скопируйте файл `config.json.example` в `config.json` (если файл ещё не создан):
```bash
cp config.json.example config.json
```

2. Отредактируйте файл `config.json`:
   - **Обязательно укажите ваши API ключи** для `llm_fast.api_key` и `llm_slow.api_key`
   - При необходимости измените `api_base` для использования альтернативных провайдеров (LocalAI, Ollama и т.д.)
   - Укажите названия моделей в `model`
   - При необходимости измените порт для MT5

Пример конфигурации для OpenAI:
```json
{
  "llm_fast": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "sk-your-actual-api-key-here",
    "model": "gpt-3.5-turbo"
  },
  "llm_slow": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "sk-your-actual-api-key-here",
    "model": "gpt-4"
  }
}
```

Пример конфигурации для локальной модели (Ollama):
```json
{
  "llm_fast": {
    "api_base": "http://localhost:11434/v1",
    "api_key": "ollama",
    "model": "llama3"
  },
  "llm_slow": {
    "api_base": "http://localhost:11434/v1",
    "api_key": "ollama",
    "model": "llama3"
  }
}
```

### 3. Запуск приложения
```bash
python main.py
```

Приложение будет доступно по адресу: http://localhost:8000

### 4. Настройка MT5 советника (опционально)
Если вы хотите использовать сбор данных из MT5:

1. Скопируйте файл `mt5_expert/ForexCollector.mq5` в папку Experts вашего терминала MT5
2. Откройте MetaEditor и скомпилируйте советник
3. Добавьте советник на любой график
4. В настройках укажите:
   - ServerIP: 127.0.0.1 (или IP вашего сервера)
   - ServerPort: 9999 (должен совпадать с config.json)

## Проверка работы

### Тестирование без MT5
Вы можете тестировать приложение без подключения MT5:

1. Создайте стратегию через веб-интерфейс
2. Добавьте индикаторы
3. Настройте промпты для LLM

Для полноценного тестирования стратегий потребуется:
- Подключенный MT5 с советником
- Или предварительно загруженные данные в SQLite

## Структура файлов

```
/workspace/forex_app/
├── main.py                 # Запускается для старта приложения
├── config.json             # Конфигурация (API ключи, порт)
├── strategies/strategies.json  # Сохранённые стратегии
├── static/                 # Веб-интерфейс
│   ├── index.html
│   ├── style.css
│   └── app.js
└── mt5_expert/
    └── ForexCollector.mq5  # Советник для MT5
```

## API для разработчиков

После запуска приложения доступна документация API:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Пример создания стратегии через API

```bash
curl -X POST http://localhost:8000/api/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Strategy",
    "timeframes": [60, 240],
    "indicators": [
      {"type": "SMA", "timeframe": 60, "params": {"period": 14}}
    ],
    "prompt_open": "Анализируй рынок...",
    "prompt_close": "Закрывай сделку когда...",
    "base_timeframe": 60
  }'
```

## Troubleshooting

### Ошибка подключения к MT5
- Убедитесь, что советник запущен в MT5
- Проверьте, что порт в config.json совпадает с настройками советника
- Проверьте брандмауэр Windows

### Ошибка LLM API (404 Not Found)

**Причина:** Неверно настроен API ключ, модель или базовый URL в `config.json`.

**Решение:**
1. Проверьте файл `config.json`:
   - Убедитесь, что `api_key` указан правильно (не `"your-api-key-here"`)
   - Проверьте название модели в поле `model`
   - Убедитесь, что `api_base` соответствует вашему провайдеру

2. Для OpenAI:
   ```json
   {
     "llm_fast": {
       "api_base": "https://api.openai.com/v1",
       "api_key": "sk-ваш-реальный-ключ",
       "model": "gpt-3.5-turbo"
     }
   }
   ```

3. Для локальных моделей (Ollama, LocalAI):
   ```json
   {
     "llm_fast": {
       "api_base": "http://localhost:11434/v1",
       "api_key": "ollama",
       "model": "llama3"
     }
   }
   ```

4. Перезапустите приложение после изменения конфигурации

### Ошибка LLM API (недостаточно прав)

- Проверьте, что ваш API ключ активен и имеет доступ к указанным моделям
- Проверьте баланс аккаунта (для платных API)

### Данные не загружаются
- Убедитесь, что советник MT5 имеет доступ к истории котировок
- Проверьте, что символы указаны правильно (например, EURUSD не EURUSDrfd)
