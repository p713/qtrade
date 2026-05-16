"""
Модуль для расчёта технических индикаторов.
Все функции принимают pandas DataFrame с колонками: time, open, high, low, close, volume
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple


def sma(df: pd.DataFrame, period: int) -> pd.Series:
    """
    Simple Moving Average (простая скользящая средняя).
    
    Args:
        df: DataFrame с колонкой 'close'
        period: Период расчёта
    
    Returns:
        Series со значениями SMA
    """
    return df['close'].rolling(window=period).mean()


def ema(df: pd.DataFrame, period: int) -> pd.Series:
    """
    Exponential Moving Average (экспоненциальная скользящая средняя).
    
    Args:
        df: DataFrame с колонкой 'close'
        period: Период расчёта
    
    Returns:
        Series со значениями EMA
    """
    return df['close'].ewm(span=period, adjust=False).mean()


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3, slowing: int = 3) -> Tuple[pd.Series, pd.Series]:
    """
    Stochastic Oscillator.
    
    Args:
        df: DataFrame с колонками 'high', 'low', 'close'
        k_period: Период %K
        d_period: Период %D (сглаживание %K)
        slowing: Сглаживание %K
    
    Returns:
        Кортеж (%K, %D)
    """
    lowest_low = df['low'].rolling(window=k_period).min()
    highest_high = df['high'].rolling(window=k_period).max()
    
    # Быстрый стохастик
    fast_k = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)
    
    # Сглаженный %K
    k = fast_k.rolling(window=slowing).mean()
    
    # %D - скользящая средняя от %K
    d = k.rolling(window=d_period).mean()
    
    return k, d


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (индекс относительной силы).
    
    Args:
        df: DataFrame с колонкой 'close'
        period: Период расчёта
    
    Returns:
        Series со значениями RSI
    """
    delta = df['close'].diff()
    
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi_values = 100 - (100 / (1 + rs))
    
    return rsi_values


def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands (полосы Боллинджера).
    
    Args:
        df: DataFrame с колонкой 'close'
        period: Период расчёта средней линии
        std_dev: Количество стандартных отклонений
    
    Returns:
        Кортеж (upper_band, middle_band, lower_band)
    """
    middle = sma(df, period)
    std = df['close'].rolling(window=period).std()
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return upper, middle, lower


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range (средний истинный диапазон).
    
    Args:
        df: DataFrame с колонками 'high', 'low', 'close'
        period: Период расчёта
    
    Returns:
        Series со значениями ATR
    """
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_values = true_range.rolling(window=period).mean()
    
    return atr_values


# ============================================================================
# Вспомогательные функции (п. 3.2 ТЗ)
# ============================================================================

def is_ma_rising(ma_series: pd.Series, n: int) -> bool:
    """
    Проверяет, растёт ли скользящая средняя на последних n свечах.
    
    Args:
        ma_series: Series со значениями MA
        n: Количество свечей для проверки
    
    Returns:
        True если MA растёт на всех n свечах, False иначе
    """
    if len(ma_series) < n:
        return False
    
    last_n = ma_series.tail(n).dropna()
    if len(last_n) < n:
        return False
    
    # Проверяем, что каждое следующее значение больше предыдущего
    for i in range(1, len(last_n)):
        if last_n.iloc[i] <= last_n.iloc[i-1]:
            return False
    
    return True


def is_ma_falling(ma_series: pd.Series, n: int) -> bool:
    """
    Проверяет, убывает ли скользящая средняя на последних n свечах.
    
    Args:
        ma_series: Series со значениями MA
        n: Количество свечей для проверки
    
    Returns:
        True если MA убывает на всех n свечах, False иначе
    """
    if len(ma_series) < n:
        return False
    
    last_n = ma_series.tail(n).dropna()
    if len(last_n) < n:
        return False
    
    # Проверяем, что каждое следующее значение меньше предыдущего
    for i in range(1, len(last_n)):
        if last_n.iloc[i] >= last_n.iloc[i-1]:
            return False
    
    return True


def ma_cross(fast_ma: pd.Series, slow_ma: pd.Series, n: int = 1, direction: str = 'any') -> Optional[str]:
    """
    Проверяет пересечение быстрой MA медленной MA на последних n свечах.
    
    Args:
        fast_ma: Series со значениями быстрой MA
        slow_ma: Series со значениями медленной MA
        n: Количество свечей для проверки
        direction: 'above' (быстрая пересекает снизу вверх), 
                   'below' (быстрая пересекает сверху вниз),
                   'any' (любое пересечение)
    
    Returns:
        'bullish' если быстрое пересекло медленное снизу вверх,
        'bearish' если быстрое пересекло медленное сверху вниз,
        None если пересечения не было
    """
    if len(fast_ma) < 2 or len(slow_ma) < 2:
        return None
    
    # Берём последние n+1 значений для проверки пересечения
    last_fast = fast_ma.tail(n + 1).dropna()
    last_slow = slow_ma.tail(n + 1).dropna()
    
    if len(last_fast) < 2 or len(last_slow) < 2:
        return None
    
    # Выравниваем индексы
    common_idx = last_fast.index.intersection(last_slow.index)
    if len(common_idx) < 2:
        return None
    
    last_fast = last_fast.loc[common_idx]
    last_slow = last_slow.loc[common_idx]
    
    # Проверяем пересечения на каждом шаге
    for i in range(1, len(common_idx)):
        prev_idx = common_idx[i-1]
        curr_idx = common_idx[i]
        
        prev_fast_above = last_fast.loc[prev_idx] > last_slow.loc[prev_idx]
        curr_fast_above = last_fast.loc[curr_idx] > last_slow.loc[curr_idx]
        
        # Пересечение снизу вверх (bullish)
        if not prev_fast_above and curr_fast_above:
            if direction in ['any', 'above']:
                return 'bullish'
        
        # Пересечение сверху вниз (bearish)
        if prev_fast_above and not curr_fast_above:
            if direction in ['any', 'below']:
                return 'bearish'
    
    return None


def price_distance_to_ma(price: float, ma_series: pd.Series, percent: bool = True) -> float:
    """
    Расстояние от цены до скользящей средней.
    
    Args:
        price: Текущая цена
        ma_series: Series со значениями MA
        percent: Если True, возвращает процентное расстояние, иначе абсолютное
    
    Returns:
        Расстояние (в процентах или абсолютное)
    """
    if len(ma_series) == 0 or pd.isna(ma_series.iloc[-1]):
        return 0.0
    
    ma_value = ma_series.iloc[-1]
    
    if percent:
        return ((price - ma_value) / ma_value) * 100
    else:
        return price - ma_value


def calculate_indicator(df: pd.DataFrame, indicator_type: str, params: dict) -> dict:
    """
    Универсальная функция для расчёта индикатора по типу и параметрам.
    
    Args:
        df: DataFrame с данными
        indicator_type: Тип индикатора ('SMA', 'EMA', 'STOCHASTIC', 'RSI', 'BOLLINGER', 'ATR')
        params: Параметры индикатора
    
    Returns:
        Словарь с результатами расчёта
    """
    indicator_type = indicator_type.upper()
    
    if indicator_type == 'SMA':
        period = params.get('period', 14)
        values = sma(df, period)
        return {'sma': values}
    
    elif indicator_type == 'EMA':
        period = params.get('period', 14)
        values = ema(df, period)
        return {'ema': values}
    
    elif indicator_type == 'STOCHASTIC':
        k_period = params.get('k_period', 14)
        d_period = params.get('d_period', 3)
        slowing = params.get('slowing', 3)
        k, d = stochastic(df, k_period, d_period, slowing)
        return {'stoch_k': k, 'stoch_d': d}
    
    elif indicator_type == 'RSI':
        period = params.get('period', 14)
        values = rsi(df, period)
        return {'rsi': values}
    
    elif indicator_type == 'BOLLINGER':
        period = params.get('period', 20)
        std_dev = params.get('std_dev', 2.0)
        upper, middle, lower = bollinger_bands(df, period, std_dev)
        return {'bb_upper': upper, 'bb_middle': middle, 'bb_lower': lower}
    
    elif indicator_type == 'ATR':
        period = params.get('period', 14)
        values = atr(df, period)
        return {'atr': values}
    
    else:
        raise ValueError(f"Неизвестный тип индикатора: {indicator_type}")
