"""
Модуль для работы с LLM-моделями.
Быстрая модель - для торговых решений.
Медленная модель - для редактирования промптов.
"""

import json
from typing import Optional
from openai import OpenAI


def load_config() -> dict:
    """Загружает конфигурацию из config.json"""
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_llm_client(llm_type: str = "fast") -> OpenAI:
    """
    Возвращает клиент для LLM API.
    
    Args:
        llm_type: "fast" или "slow"
    
    Returns:
        OpenAI клиент
    """
    config = load_config()
    llm_config = config[f"llm_{llm_type}"]
    
    client = OpenAI(
        api_key=llm_config["api_key"],
        base_url=llm_config["api_base"]
    )
    return client


def call_llm(messages: list, llm_type: str = "fast") -> str:
    """
    Отправляет запрос к LLM модели.
    
    Args:
        messages: Список сообщений в формате [{"role": "user", "content": "..."}]
        llm_type: "fast" или "slow"
    
    Returns:
        Ответ от модели (строка)
    """
    config = load_config()
    llm_config = config[f"llm_{llm_type}"]
    client = get_llm_client(llm_type)
    
    response = client.chat.completions.create(
        model=llm_config["model"],
        messages=messages,
        temperature=0.7,
        max_tokens=2000
    )
    
    return response.choices[0].message.content.strip()


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
