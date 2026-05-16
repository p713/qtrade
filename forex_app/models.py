"""
Pydantic модели для API.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class IndicatorParams(BaseModel):
    """Параметры индикатора."""
    period: Optional[int] = None
    k_period: Optional[int] = None
    d_period: Optional[int] = None
    slowing: Optional[int] = None
    std_dev: Optional[float] = None


class IndicatorConfig(BaseModel):
    """Конфигурация индикатора."""
    type: str = Field(..., description="Тип индикатора (SMA, EMA, STOCHASTIC, RSI, BOLLINGER, ATR)")
    timeframe: int = Field(..., description="Таймфрейм в минутах")
    params: Dict[str, Any] = Field(default_factory=dict, description="Параметры индикатора")


class StrategyCreate(BaseModel):
    """Модель для создания стратегии."""
    name: str = Field(..., min_length=1, max_length=100)
    timeframes: List[int] = Field(..., description="Список таймфреймов в минутах")
    indicators: List[IndicatorConfig] = Field(default_factory=list)
    prompt_open: str = Field(default="", description="Промпт для открытия сделки")
    prompt_close: str = Field(default="", description="Промпт для закрытия сделки")
    base_timeframe: int = Field(default=60, description="Основной таймфрейм для тестирования")


class StrategyUpdate(BaseModel):
    """Модель для обновления стратегии."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    timeframes: Optional[List[int]] = None
    indicators: Optional[List[IndicatorConfig]] = None
    prompt_open: Optional[str] = None
    prompt_close: Optional[str] = None
    base_timeframe: Optional[int] = None


class BacktestRequest(BaseModel):
    """Запрос на тестирование стратегии."""
    symbol: str = Field(..., description="Валютная пара")
    start_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Дата начала (YYYY-MM-DD)")
    end_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Дата окончания (YYYY-MM-DD)")


class EditPromptRequest(BaseModel):
    """Запрос на редактирование промпта."""
    prompt: str = Field(..., description="Текущий текст промпта")
    request: str = Field(..., description="Запрос пользователя на изменение")


class TradeCommand(BaseModel):
    """Торговая команда для MT5."""
    action: str = Field(..., description="Действие (buy, sell, close, buy_limit, etc.)")
    symbol: str = Field(..., description="Валютная пара")
    volume: float = Field(..., gt=0, description="Объём лота")
    sl: Optional[float] = Field(None, description="Stop Loss")
    tp: Optional[float] = Field(None, description="Take Profit")
    comment: str = Field(default="", description="Комментарий")


class ConfigResponse(BaseModel):
    """Ответ с конфигурацией приложения."""
    symbols: List[str]
    timeframes: List[int]


class TestStatusResponse(BaseModel):
    """Статус тестирования."""
    test_id: Optional[str] = None
    status: str = Field(..., description="status: running, completed, failed")
    progress: int = Field(default=0, ge=0, le=100, description="Прогресс в процентах")
    logs: List[str] = Field(default_factory=list)
    results: Optional[Dict[str, Any]] = None
