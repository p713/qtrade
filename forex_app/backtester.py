"""
Движок для тестирования торговых стратегий на исторических данных.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from indicators import calculate_indicator, is_ma_rising, is_ma_falling, ma_cross, price_distance_to_ma
from llm import get_trading_decision
from data_manager import fetch_all_required_data, load_dataframe
from socket_server import get_mt5_server


class BacktestEngine:
    """
    Движок для бэктестинга стратегий.
    """
    
    def __init__(self):
        self.test_results = {}
        self.test_logs = []
    
    async def run_backtest(self, strategy: dict, symbol: str, 
                          start_date: str, end_date: str) -> dict:
        """
        Запускает тестирование стратегии.
        
        Args:
            strategy: Настройки стратегии
            symbol: Валютная пара
            start_date: Дата начала тестирования (YYYY-MM-DD)
            end_date: Дата окончания тестирования (YYYY-MM-DD)
        
        Returns:
            Результаты тестирования
        """
        self.test_logs = []
        test_id = f"{strategy['id']}_{symbol}_{start_date}_{end_date}"
        
        self.log(f"Starting backtest for strategy '{strategy['name']}' on {symbol}")
        self.log(f"Test period: {start_date} to {end_date}")
        
        # Получаем сервер MT5
        socket_server = await get_mt5_server()
        
        # Загружаем данные
        timeframes = strategy.get("timeframes", [60])
        indicators = strategy.get("indicators", [])
        
        self.log("Fetching historical data...")
        data_dict = await fetch_all_required_data(
            socket_server, symbol, timeframes, indicators, start_date, end_date
        )
        
        if not data_dict:
            self.log("ERROR: No data loaded")
            return {"error": "No data loaded", "logs": self.test_logs}
        
        # Базовый таймфрейм для тестирования
        base_timeframe = strategy.get("base_timeframe", 60)
        self.log(f"Base timeframe: H{base_timeframe//60}")
        
        # Получаем DataFrame для базового таймфрейма
        base_df = data_dict.get((symbol, base_timeframe))
        if base_df is None:
            self.log(f"ERROR: No data for base timeframe H{base_timeframe//60}")
            return {"error": "No data for base timeframe", "logs": self.test_logs}
        
        # Рассчитываем индикаторы для всех таймфреймов
        self.log("Calculating indicators...")
        indicator_data = {}
        
        for tf in timeframes:
            df = data_dict.get((symbol, tf))
            if df is None:
                continue
            
            tf_indicators = {}
            for ind in indicators:
                if ind.get("timeframe") == tf:
                    ind_type = ind.get("type")
                    params = ind.get("params", {})
                    
                    try:
                        result = calculate_indicator(df, ind_type, params)
                        tf_indicators.update(result)
                        self.log(f"Calculated {ind_type} on H{tf//60}: {list(result.keys())}")
                    except Exception as e:
                        self.log(f"ERROR calculating {ind_type}: {e}")
            
            indicator_data[tf] = tf_indicators
        
        # Добавляем индикаторы в DataFrame
        for col_name, col_data in indicator_data.get(base_timeframe, {}).items():
            base_df[col_name] = col_data
        
        # Удаляем строки с NaN (где индикаторы ещё не рассчитаны)
        base_df = base_df.dropna()
        
        if len(base_df) == 0:
            self.log("ERROR: No data after calculating indicators")
            return {"error": "No data after indicators", "logs": self.test_logs}
        
        self.log(f"Ready to test on {len(base_df)} bars")
        
        # Инициализируем состояние
        position = None  # {'type': 'buy'/'sell', 'open_price': float, 'sl': float, 'tp': float, 'open_time': datetime}
        pending_orders = []  # [{'type': 'buy_limit'/'sell_limit'..., 'price': float, 'sl': float, 'tp': float}]
        trades = []  # Список закрытых сделок
        balance = 10000.0  # Начальный баланс
        equity = balance
        
        prompt_open = strategy.get("prompt_open", "")
        prompt_close = strategy.get("prompt_close", "")
        
        # Основной цикл тестирования
        self.log("Starting main loop...")
        
        for i in range(len(base_df)):
            current_bar = base_df.iloc[i]
            current_time = current_bar.name
            current_price = current_bar['close']
            
            # Если есть открытая позиция, проверяем условия закрытия
            if position is not None:
                close_reason = None
                close_price = None
                
                if position['type'] == 'buy':
                    # Проверка SL для лонга
                    if position['sl'] and current_bar['low'] <= position['sl']:
                        close_reason = "SL hit"
                        close_price = position['sl']
                    # Проверка TP для лонга
                    elif position['tp'] and current_bar['high'] >= position['tp']:
                        close_reason = "TP hit"
                        close_price = position['tp']
                
                elif position['type'] == 'sell':
                    # Проверка SL для шорта
                    if position['sl'] and current_bar['high'] >= position['sl']:
                        close_reason = "SL hit"
                        close_price = position['sl']
                    # Проверка TP для шорта
                    elif position['tp'] and current_bar['low'] <= position['tp']:
                        close_reason = "TP hit"
                        close_price = position['tp']
                
                # Если нужно закрывать позицию
                if close_reason:
                    # Расчёт P&L
                    if position['type'] == 'buy':
                        pnl = (close_price - position['open_price']) * 100000  # 1 лот = 100k единиц
                    else:
                        pnl = (position['open_price'] - close_price) * 100000
                    
                    balance += pnl
                    equity = balance
                    
                    trade_result = {
                        "close_time": str(current_time),
                        "close_reason": close_reason,
                        "close_price": close_price,
                        "open_price": position['open_price'],
                        "type": position['type'],
                        "pnl": pnl,
                        "balance": balance
                    }
                    trades.append(trade_result)
                    
                    self.log(f"Closed {position['type']} at {close_price}: {close_reason}, P&L: {pnl:.2f}")
                    position = None
            
            # Если нет позиции, запрашиваем решение у LLM
            if position is None and len(pending_orders) == 0:
                # Собираем значения индикаторов
                indicator_values = {}
                for col in base_df.columns:
                    if col not in ['open', 'high', 'low', 'close', 'volume']:
                        indicator_values[col] = current_bar[col]
                
                # Запрос к LLM
                decision = get_trading_decision(
                    indicator_values=indicator_values,
                    prompt=prompt_open,
                    symbol=symbol,
                    current_price=current_price
                )
                
                action = decision.get("action", "hold")
                
                self.log(f"Bar {i}: {current_time}, price={current_price}, decision={action}")
                self.log(f"Reasoning: {decision.get('reasoning', '')}")
                
                # Обработка решения
                if action in ['buy', 'sell']:
                    # Рыночный ордер
                    sl = decision.get("sl")
                    tp = decision.get("tp")
                    
                    position = {
                        "type": action,
                        "open_price": current_price,
                        "sl": sl,
                        "tp": tp,
                        "open_time": current_time
                    }
                    
                    self.log(f"Opened {action} at {current_price}, SL={sl}, TP={tp}")
                
                elif action in ['buy_limit', 'sell_limit', 'buy_stop', 'sell_stop']:
                    # Отложенный ордер
                    order_price = decision.get("price")
                    if order_price:
                        pending_orders.append({
                            "type": action,
                            "price": order_price,
                            "sl": decision.get("sl"),
                            "tp": decision.get("tp"),
                            "open_time": current_time
                        })
                        self.log(f"Placed pending order {action} at {order_price}")
            
            # Проверка отложенных ордеров
            orders_to_remove = []
            for order in pending_orders:
                activated = False
                
                if order['type'] == 'buy_limit' and current_bar['low'] <= order['price']:
                    activated = True
                elif order['type'] == 'sell_limit' and current_bar['high'] >= order['price']:
                    activated = True
                elif order['type'] == 'buy_stop' and current_bar['high'] >= order['price']:
                    activated = True
                elif order['type'] == 'sell_stop' and current_bar['low'] <= order['price']:
                    activated = True
                
                if activated:
                    position = {
                        "type": 'buy' if 'buy' in order['type'] else 'sell',
                        "open_price": order['price'],
                        "sl": order['sl'],
                        "tp": order['tp'],
                        "open_time": current_time
                    }
                    self.log(f"Activated pending order {order['type']} at {order['price']}")
                    orders_to_remove.append(order)
            
            for order in orders_to_remove:
                pending_orders.remove(order)
        
        # Финальные результаты
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        losing_trades = sum(1 for t in trades if t['pnl'] < 0)
        total_pnl = sum(t['pnl'] for t in trades)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        results = {
            "test_id": test_id,
            "strategy_name": strategy['name'],
            "symbol": symbol,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": 10000.0,
            "final_balance": balance,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "trades": trades,
            "logs": self.test_logs
        }
        
        self.log(f"Backtest completed. Total trades: {total_trades}, P&L: {total_pnl:.2f}, Win rate: {win_rate:.1f}%")
        
        return results
    
    def log(self, message: str):
        """Добавляет сообщение в лог."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.test_logs.append(log_entry)
        print(log_entry)


# Глобальный экземпляр движка
backtest_engine = BacktestEngine()


async def run_strategy_backtest(strategy_id: str, symbol: str, 
                               start_date: str, end_date: str) -> dict:
    """
    Запускает тестирование стратегии по ID.
    
    Args:
        strategy_id: ID стратегии
        symbol: Валютная пара
        start_date: Дата начала (YYYY-MM-DD)
        end_date: Дата окончания (YYYY-MM-DD)
    
    Returns:
        Результаты тестирования
    """
    from strategy_manager import get_strategy_by_id
    
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        return {"error": "Strategy not found"}
    
    results = await backtest_engine.run_backtest(strategy, symbol, start_date, end_date)
    return results
