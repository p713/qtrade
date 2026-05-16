"""
Модуль для управления стратегиями.
CRUD операции с файлом strategies.json.
"""

import json
import uuid
from typing import List, Optional, Dict
from datetime import datetime


STRATEGIES_FILE = "strategies/strategies.json"


def load_strategies() -> dict:
    """Загружает все стратегии из файла."""
    try:
        with open(STRATEGIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"strategies": []}


def save_strategies(data: dict):
    """Сохраняет стратегии в файл."""
    with open(STRATEGIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_all_strategies() -> List[dict]:
    """Возвращает список всех стратегий."""
    data = load_strategies()
    return data.get("strategies", [])


def get_strategy_by_id(strategy_id: str) -> Optional[dict]:
    """
    Возвращает стратегию по ID.
    
    Args:
        strategy_id: UUID стратегии
    
    Returns:
        Стратегия или None если не найдена
    """
    strategies = get_all_strategies()
    for strategy in strategies:
        if strategy["id"] == strategy_id:
            return strategy
    return None


def create_strategy(name: str, timeframes: List[int], indicators: List[dict],
                    prompt_open: str, prompt_close: str, 
                    base_timeframe: int = 60) -> dict:
    """
    Создаёт новую стратегию.
    
    Args:
        name: Название стратегии
        timeframes: Список таймфреймов в минутах
        indicators: Список индикаторов с параметрами
        prompt_open: Промпт для открытия сделки
        prompt_close: Промпт для закрытия сделки
        base_timeframe: Основной таймфрейм для тестирования (в минутах)
    
    Returns:
        Созданная стратегия
    """
    strategy = {
        "id": str(uuid.uuid4()),
        "name": name,
        "timeframes": timeframes,
        "indicators": indicators,
        "prompt_open": prompt_open,
        "prompt_close": prompt_close,
        "base_timeframe": base_timeframe,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    data = load_strategies()
    data["strategies"].append(strategy)
    save_strategies(data)
    
    return strategy


def update_strategy(strategy_id: str, **kwargs) -> Optional[dict]:
    """
    Обновляет существующую стратегию.
    
    Args:
        strategy_id: UUID стратегии
        **kwargs: Поля для обновления
    
    Returns:
        Обновлённая стратегия или None если не найдена
    """
    data = load_strategies()
    
    for i, strategy in enumerate(data["strategies"]):
        if strategy["id"] == strategy_id:
            # Обновляем указанные поля
            for key, value in kwargs.items():
                if key in ["name", "timeframes", "indicators", "prompt_open", 
                          "prompt_close", "base_timeframe"]:
                    strategy[key] = value
            
            strategy["updated_at"] = datetime.now().isoformat()
            data["strategies"][i] = strategy
            save_strategies(data)
            return strategy
    
    return None


def delete_strategy(strategy_id: str) -> bool:
    """
    Удаляет стратегию по ID.
    
    Args:
        strategy_id: UUID стратегии
    
    Returns:
        True если удалена, False если не найдена
    """
    data = load_strategies()
    
    initial_count = len(data["strategies"])
    data["strategies"] = [s for s in data["strategies"] if s["id"] != strategy_id]
    
    if len(data["strategies"]) < initial_count:
        save_strategies(data)
        return True
    
    return False
