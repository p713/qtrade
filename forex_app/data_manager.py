"""
Модуль для работы с историческими данными.
Запрос данных у MT5 и загрузка из SQLite.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import asyncio


def load_config() -> dict:
    """Загружает конфигурацию из config.json"""
    import json
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_db_connection():
    """Возвращает подключение к базе данных SQLite."""
    config = load_config()
    db_path = config.get("db_path", "forex_data.sqlite")
    conn = sqlite3.connect(db_path)
    return conn


def load_dataframe(symbol: str, timeframe_minutes: int, 
                   start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    Загружает данные котировок из базы данных SQLite.
    
    Args:
        symbol: Валютная пара
        timeframe_minutes: Таймфрейм в минутах
        start_date: Дата начала (YYYY-MM-DD)
        end_date: Дата окончания (YYYY-MM-DD)
    
    Returns:
        DataFrame с колонками: time, open, high, low, close, volume
        или None если данных нет
    """
    conn = get_db_connection()
    
    query = """
        SELECT time, open, high, low, close, volume
        FROM price_data
        WHERE symbol = ? AND timeframe = ?
          AND time >= ? AND time <= ?
        ORDER BY time ASC
    """
    
    # Конвертируем даты в timestamp
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    end_ts = int((datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).timestamp())
    
    df = pd.read_sql_query(query, conn, params=(symbol, timeframe_minutes, start_ts, end_ts))
    conn.close()
    
    if len(df) == 0:
        return None
    
    # Конвертируем timestamp в datetime
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    
    return df


def calculate_working_period(test_start: str, test_end: str, 
                            timeframes: List[int], indicators: List[dict]) -> tuple:
    """
    Вычисляет рабочий период для загрузки данных с учётом индикаторов.
    
    Args:
        test_start: Дата начала тестирования (YYYY-MM-DD)
        test_end: Дата окончания тестирования (YYYY-MM-DD)
        timeframes: Список таймфреймов в минутах
        indicators: Список индикаторов с параметрами
    
    Returns:
        Кортеж (working_start, working_end) - расширенные даты
    """
    # Находим максимальный период среди всех индикаторов
    max_period = 0
    for ind in indicators:
        params = ind.get("params", {})
        period = max(params.values()) if params else 0
        max_period = max(max_period, period)
    
    # Добавляем запас в 2 раза больше максимального периода
    buffer_bars = max_period * 2 if max_period > 0 else 100
    
    # Находим минимальный таймфрейм для расчёта запаса в днях
    min_timeframe = min(timeframes) if timeframes else 60  # По умолчанию H1
    
    # Переводим бары в дни (примерно)
    buffer_days = max(1, int(buffer_bars * min_timeframe / (60 * 24)))
    
    # Расширяем период назад
    test_start_dt = datetime.strptime(test_start, "%Y-%m-%d")
    working_start_dt = test_start_dt - timedelta(days=buffer_days)
    working_start = working_start_dt.strftime("%Y-%m-%d")
    
    return working_start, test_end


async def request_history_from_mt5(socket_server, symbol: str, timeframe_minutes: int,
                                   start_date: str, end_date: str) -> bool:
    """
    Запрашивает историю котировок у советника MT5 через сокет.
    
    Args:
        socket_server: Экземпляр MT5SocketServer
        symbol: Валютная пара
        timeframe_minutes: Таймфрейм в минутах
        start_date: Дата начала (YYYY-MM-DD)
        end_date: Дата окончания (YYYY-MM-DD)
    
    Returns:
        True если данные успешно загружены
    """
    success = await socket_server.request_history(
        symbol=symbol,
        timeframe_minutes=timeframe_minutes,
        start_date=start_date,
        end_date=end_date
    )
    return success


async def fetch_all_required_data(socket_server, symbol: str, timeframes: List[int],
                                  indicators: List[dict], test_start: str, 
                                  test_end: str) -> Dict[tuple, pd.DataFrame]:
    """
    Загружает все необходимые данные для тестирования стратегии.
    
    Args:
        socket_server: Экземпляр MT5SocketServer
        symbol: Валютная пара
        timeframes: Список таймфреймов
        indicators: Список индикаторов
        test_start: Дата начала тестирования
        test_end: Дата окончания тестирования
    
    Returns:
        Словарь {(symbol, timeframe): DataFrame} с данными
    """
    # Вычисляем рабочий период
    working_start, working_end = calculate_working_period(
        test_start, test_end, timeframes, indicators
    )
    
    print(f"Working period: {working_start} to {working_end}")
    print(f"Test period: {test_start} to {test_end}")
    
    data_dict = {}
    
    # Запрашиваем данные для каждого таймфрейма
    for tf in timeframes:
        print(f"Requesting data for {symbol} H{tf//60}...")
        
        success = await request_history_from_mt5(
            socket_server, symbol, tf, working_start, working_end
        )
        
        if success:
            df = load_dataframe(symbol, tf, working_start, working_end)
            if df is not None:
                data_dict[(symbol, tf)] = df
                print(f"Loaded {len(df)} bars for {symbol} H{tf//60}")
            else:
                print(f"No data loaded for {symbol} H{tf//60}")
        else:
            print(f"Failed to request data for {symbol} H{tf//60}")
    
    return data_dict
