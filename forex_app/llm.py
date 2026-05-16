"""
Модуль для работы с LLM-моделями через LiteLLM.
Быстрая модель - для торговых решений.
Медленная модель - для редактирования промптов.
LiteLLM обеспечивает единую точку доступа к различным LLM провайдерам:
OpenAI, Anthropic, Azure, Ollama, LM Studio и др.
"""

import json
import os
from pathlib import Path
from typing import Optional
import litellm
from litellm import completion


# Получаем директорию текущего файла
BASE_DIR = Path(__file__).parent


def load_config() -> dict:
    """Загружает конфигурацию из config.json"""
    config_path = BASE_DIR / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_llm_config(llm_type: str = "fast") -> dict:
    """
    Возвращает конфигурацию для LLM.
    
    Args:
        llm_type: "fast" или "slow"
    
    Returns:
        dict с конфигурацией LLM
    
    Raises:
        ValueError: Если конфигурация не настроена
    """
    config = load_config()
    llm_config = config[f"llm_{llm_type}"]
    
    # Проверяем, что API ключ настроен (если требуется)
    api_key = llm_config.get("api_key", "")
    if not api_key or api_key in ["your-api-key-here", ""]:
        # Для некоторых провайдеров (Ollama, локальные) ключ может быть пустым
        if "api_base" not in llm_config or not llm_config["api_base"]:
            raise ValueError(
                f"API ключ для {llm_type} модели не настроен. "
                f"Пожалуйста, укажите valid API ключ в файле config.json"
            )
    
    # Проверяем, что model настроен
    if not llm_config.get("model") or llm_config["model"] in ["your-model-here", ""]:
        raise ValueError(
            f"Модель для {llm_type} LLM не настроена. "
            f"Пожалуйста, укажите название модели в файле config.json"
        )
    
    return llm_config


def call_llm(messages: list, llm_type: str = "fast") -> str:
    """
    Отправляет запрос к LLM модели через LiteLLM.
    
    Args:
        messages: Список сообщений в формате [{"role": "user", "content": "..."}]
        llm_type: "fast" или "slow"
    
    Returns:
        Ответ от модели (строка)
    """
    llm_config = get_llm_config(llm_type)
    
    # Формируем имя модели для LiteLLM
    # LiteLLM поддерживает различные форматы:
    # - openai/gpt-3.5-turbo
    # - ollama/llama2
    # - huggingface/model-name
    # Если указан api_base, используем его как proxy
    model_name = llm_config["model"]
    api_base = llm_config.get("api_base", None)
    api_key = llm_config.get("api_key", None)
    
    try:
        # Подготовка параметров для completion
        completion_kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        # Если указан api_base, используем его
        if api_base:
            completion_kwargs["api_base"] = api_base
        
        # Если указан api_key, используем его
        if api_key and api_key not in ["your-api-key-here", ""]:
            completion_kwargs["api_key"] = api_key
        
        # Вызов LiteLLM completion
        response = completion(**completion_kwargs)
        
        if not response.choices or len(response.choices) == 0:
            raise Exception("LLM returned no choices")
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        # Логируем ошибку с детальной информацией
        error_msg = f"LLM API error ({llm_type}): {str(e)}"
        print(error_msg)
        
        # Дополнительная информация об ошибке
        if hasattr(e, 'status_code'):
            print(f"Status code: {e.status_code}")
        if hasattr(e, 'response'):
            print(f"Response: {e.response}")
            try:
                if hasattr(e.response, 'text'):
                    print(f"Response text: {e.response.text}")
                elif hasattr(e.response, 'json'):
                    print(f"Response JSON: {e.response.json()}")
            except:
                pass
        
        # Добавляем подсказки для распространённых проблем
        if "404" in str(e) or "Not Found" in str(e):
            print(f"\nВозможные причины ошибки 404:")
            print(f"1. Проверьте, что API сервер запущен по адресу: {api_base or 'default'}")
            print(f"2. Убедитесь, что модель '{model_name}' доступна на этом сервере")
            print(f"3. Для локальных моделей (Ollama, LM Studio):")
            print(f"   - Ollama: api_base должен быть 'http://localhost:11434'")
            print(f"   - LM Studio: api_base должен быть 'http://localhost:1234/v1'")
            print(f"   - Модель должна быть загружена в сервис")
            print(f"4. Формат имени модели может требовать префикс провайдера:")
            print(f"   - Для OpenAI: 'openai/gpt-3.5-turbo'")
            print(f"   - Для Ollama: 'ollama/llama2' или просто 'llama2'")
            print(f"5. Проверьте, что API ключ корректен (если требуется)")
        
        if "connection" in str(e).lower() or "refused" in str(e).lower():
            print(f"\nОшибка подключения:")
            print(f"1. Убедитесь, что сервер запущен")
            print(f"2. Проверьте правильность адреса и порта в api_base")
            print(f"3. Проверьте брандмауэр и сетевые настройки")
        
        raise Exception(error_msg) from e


def edit_prompt(prompt_text: str, user_request: str) -> str:
    """
    Редактирует промпт с помощью медленной LLM.
    
    Args:
        prompt_text: Текущий текст промпта
        user_request: Запрос пользователя на изменение
    
    Returns:
        Изменённый текст промпта
    """
    system_message = (
        "Вы помощник для редактирования торговых промптов. "
        "Ваша задача - изменять текст промпта согласно запросу пользователя, "
        "сохраняя его структуру и стиль. Верните только изменённый текст промпта без дополнительных пояснений."
    )
    
    user_message = f"""Текущий промпт:
{prompt_text}

Запрос пользователя на изменение:
{user_request}

Верните изменённый текст промпта, отвечающий запросу."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
    
    result = call_llm(messages, llm_type="slow")
    return result


def get_trading_decision(indicator_values: dict, prompt: str, symbol: str, current_price: float) -> dict:
    """
    Запрашивает у быстрой LLM торговое решение.
    
    Args:
        indicator_values: Словарь со значениями индикаторов
        prompt: Промпт пользователя для принятия решения
        symbol: Валютная пара
        current_price: Текущая цена
    
    Returns:
        Распарсенный JSON с решением
    """
    import json as json_module
    
    format_instruction = """
Требования к формату ответа:
Ответ должен быть ТОЛЬКО в формате JSON без дополнительного текста. Структура JSON:
{
    "action": "buy"/"sell"/"buy_limit"/"sell_limit"/"buy_stop"/"sell_stop"/"hold",
    "price": число (цена входа, если ордер отложенный),
    "sl": число (stop loss, может быть null),
    "tp": число (take profit, может быть null),
    "reasoning": "текстовое обоснование решения"
}
"""
    
    indicators_text = "\n".join([f"{k}: {v}" for k, v in indicator_values.items()])
    
    user_message = f"""Символ: {symbol}
Текущая цена: {current_price}

Значения индикаторов:
{indicators_text}

{prompt}

{format_instruction}"""

    messages = [
        {"role": "system", "content": "Вы торговый советник. Анализируете рынок и принимаете торговые решения на основе технических индикаторов."},
        {"role": "user", "content": user_message}
    ]
    
    response_text = call_llm(messages, llm_type="fast")
    
    # Очищаем ответ от возможных маркеров кода
    response_text = response_text.replace("```json", "").replace("```", "").strip()
    
    try:
        decision = json_module.loads(response_text)
    except json_module.JSONDecodeError:
        # Если не удалось распарсить JSON, возвращаем дефолтное решение
        decision = {
            "action": "hold",
            "price": None,
            "sl": None,
            "tp": None,
            "reasoning": f"Не удалось распарсить ответ LLM: {response_text}"
        }
    
    return decision
