# Forex Trading Application

Приложение для торговли на Форекс, разработки и тестирования стратегий на Python с использованием LLM.

## Архитектура

- **Backend:** Python 3.11+, FastAPI (веб-сервер + REST API)
- **Frontend:** HTML + ванильный JavaScript (без фреймворков)
- **База данных:** SQLite (котировки), JSON-файлы (настройки стратегий)
- **Сервер сокетов:** asyncio TCP-сервер для подключения советника MT5
- **MT5 советник:** MQL5 EA для сбора данных и исполнения торговых команд
- **LLM:** OpenAI-совместимый API для торговых решений и редактирования промптов

## Структура проекта

```
forex_app/
├── main.py                 # Главный файл FastAPI приложения
├── models.py               # Pydantic модели для API
├── strategy_manager.py     # Управление стратегиями (CRUD)
├── indicators.py           # Технические индикаторы
├── llm.py                  # Интеграция с LLM
├── socket_server.py        # Сервер сокетов для MT5
├── data_manager.py         # Работа с историческими данными
├── backtester.py           # Движок тестирования стратегий
├── config.json             # Конфигурация приложения
├── strategies/
│   └── strategies.json     # Хранилище стратегий
├── static/
│   ├── index.html          # Веб-интерфейс
│   ├── style.css           # Стили
│   └── app.js              # Frontend логика
└── mt5_expert/
    └── ForexCollector.mq5  # Советник для MT5
```

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте `config.json`:
- Укажите API ключи для LLM моделей
- Настройте порт для подключения MT5
- Укажите список символов и таймфреймов

3. Запустите приложение:
```bash
python main.py
```

4. Откройте браузер: `http://localhost:8000`

## Настройка MT5 советника

1. Скопируйте `ForexCollector.mq5` в папку Experts вашего терминала MT5
2. Скомпилируйте советник в MetaEditor
3. Добавьте советник на график
4. В настройках укажите:
   - ServerIP: IP адрес сервера приложения
   - ServerPort: Порт (по умолчанию 9999)
   - Symbols: Список инструментов для торговли

## Функционал

### Стратегии
- Создание и редактирование торговых стратегий
- Настройка таймфреймов для анализа
- Добавление технических индикаторов (SMA, EMA, Stochastic, RSI, Bollinger Bands, ATR)
- Редактирование промптов для LLM с помощью AI-помощника

### Индикаторы
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Stochastic Oscillator
- Relative Strength Index (RSI)
- Bollinger Bands
- Average True Range (ATR)

### Вспомогательные функции
- Проверка роста/падения MA на отрезке времени
- Определение пересечения быстрой и медленной MA
- Расчёт расстояния от цены до скользящей средней

### Тестирование стратегий
- Выбор периода тестирования
- Автоматическая загрузка истории котировок из MT5
- Расчёт индикаторов
- Запрос решений у LLM
- Симуляция открытия/закрытия сделок
- Подробные результаты и статистика

### Редактирование промптов через LLM
- Два поля: текст промпта и запрос к LLM
- Медленная модель используется для улучшения промптов
- Быстрая модель используется для торговых решений

## API Endpoints

- `GET /api/config` - Конфигурация приложения
- `GET /api/strategies` - Список стратегий
- `POST /api/strategies` - Создать стратегию
- `GET /api/strategies/{id}` - Получить стратегию
- `PUT /api/strategies/{id}` - Обновить стратегию
- `DELETE /api/strategies/{id}` - Удалить стратегию
- `POST /api/strategies/{id}/test` - Запустить тестирование
- `GET /api/strategies/{id}/test/status` - Статус тестирования
- `POST /api/llm/edit_prompt` - Улучшить промпт через LLM
- `POST /api/mt5/command` - Отправить торговую команду в MT5

## Конфигурация (config.json)

```json
{
  "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
  "timeframes": [60, 240, 1440],
  "llm_fast": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "your-key",
    "model": "gpt-3.5-turbo"
  },
  "llm_slow": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "your-key",
    "model": "gpt-4"
  },
  "mt5_socket_port": 9999,
  "db_path": "forex_data.sqlite"
}
```

## Важные замечания

- Приложение не предназначено для высокочастотной торговли
- Запросы к LLM происходят по ручному запросу или при наступлении редких условий
- Для работы требуется установленный терминал MT5 с поддержкой MQL5
- База данных SQLite создаётся автоматически при первом запуске советника MT5
