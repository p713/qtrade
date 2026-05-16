# Настройка LLM для Forex App

## Проблема: Ошибка 404 при подключении к LLM

Если вы получаете ошибку `Error code: 404 - {'detail': 'Not Found'}`, это означает, что приложение не может подключиться к API LLM.

## Возможные причины и решения:

### 1. Не указан API ключ

**Решение:** Откройте файл `config.json` и укажите действительный API ключ:

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

### 2. Используется локальная модель (Ollama, LM Studio, etc.)

Если вы используете локальную модель, проверьте настройки:

#### Для Ollama:
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

#### Для LM Studio:
```json
{
  "llm_fast": {
    "api_base": "http://localhost:1234/v1",
    "api_key": "lm-studio",
    "model": "local-model"
  },
  "llm_slow": {
    "api_base": "http://localhost:1234/v1",
    "api_key": "lm-studio",
    "model": "local-model"
  }
}
```

**Важно:** Убедитесь, что сервер запущен и доступен по указанному адресу!

### 3. Неправильный URL api_base

Некоторые локальные серверы требуют разный формат URL:
- С `/v1` на конце: `http://localhost:11434/v1`
- Без `/v1`: `http://localhost:11434`

Попробуйте оба варианта.

### 4. Модель недоступна

Убедитесь, что указанная модель существует на сервере:
- Для OpenAI: `gpt-3.5-turbo`, `gpt-4`, `gpt-4-turbo`
- Для Ollama: `llama3`, `mistral`, `gemma` (проверьте командой `ollama list`)
- Для LM Studio: название загруженной модели

## Проверка подключения

Вы можете проверить подключение к LLM через консоль Python:

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key",
    base_url="http://localhost:11434/v1"  # или ваш URL
)

try:
    response = client.chat.completions.create(
        model="your-model",
        messages=[{"role": "user", "content": "Test"}]
    )
    print("Success:", response.choices[0].message.content)
except Exception as e:
    print("Error:", e)
```

## Тестирование после настройки

После обновления `config.json`:
1. Перезапустите приложение: `python main.py`
2. Попробуйте улучшить промпт через веб-интерфейс
3. Проверьте консоль приложения на наличие ошибок
