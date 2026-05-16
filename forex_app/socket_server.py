"""
Сервер сокетов для взаимодействия с советником MT5.
Асинхронный TCP-сервер на asyncio.
"""

import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime


class MT5SocketServer:
    """
    Сервер сокетов для подключения советника MT5.
    """
    
    def __init__(self, host: str = "localhost", port: int = 9999):
        self.host = host
        self.port = port
        self.mt5_writer: Optional[asyncio.StreamWriter] = None
        self.mt5_reader: Optional[asyncio.StreamReader] = None
        self.connected = False
        self.pending_responses: Dict[str, asyncio.Future] = {}
        self.message_handlers: Dict[str, callable] = {}
    
    async def start_server(self):
        """Запускает сервер сокетов."""
        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        print(f"MT5 Socket Server started on {self.host}:{self.port}")
        
        async with server:
            await server.serve_forever()
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Обработчик подключений клиентов.
        
        Args:
            reader: StreamReader для чтения данных
            writer: StreamWriter для отправки данных
        """
        addr = writer.get_extra_info('peername')
        print(f"MT5 EA connected from {addr}")
        self.connected = True
        self.mt5_writer = writer
        self.mt5_reader = reader
        
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                
                message = data.decode('utf-8').strip()
                print(f"Received from MT5: {message}")
                
                try:
                    msg_data = json.loads(message)
                    await self.process_message(msg_data)
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {message}")
        
        except asyncio.CancelledError:
            pass
        finally:
            print(f"MT5 EA disconnected")
            self.connected = False
            self.mt5_writer = None
            self.mt5_reader = None
            writer.close()
            await writer.wait_closed()
    
    async def process_message(self, msg_data: dict):
        """
        Обрабатывает полученное сообщение от MT5.
        
        Args:
            msg_data: Распарсенное JSON-сообщение
        """
        msg_type = msg_data.get("type", "")
        
        # Если есть ожидающий ответ для этого типа сообщения
        if msg_type in self.pending_responses:
            future = self.pending_responses[msg_type]
            if not future.done():
                future.set_result(msg_data)
        
        # Вызываем зарегистрированные обработчики
        if msg_type in self.message_handlers:
            await self.message_handlers[msg_type](msg_data)
    
    def register_handler(self, msg_type: str, handler: callable):
        """
        Регистрирует обработчик для типа сообщений.
        
        Args:
            msg_type: Тип сообщения
            handler: Функция-обработчик (асинхронная)
        """
        self.message_handlers[msg_type] = handler
    
    async def send_command(self, command: dict, timeout: float = 30.0) -> Optional[dict]:
        """
        Отправляет команду советнику MT5 и ждёт ответа.
        
        Args:
            command: Команда в виде словаря
            timeout: Таймаут ожидания ответа в секундах
        
        Returns:
            Ответ от MT5 или None при таймауте
        """
        if not self.connected or self.mt5_writer is None:
            print("MT5 not connected")
            return None
        
        msg_type = command.get("type", "")
        future = asyncio.get_event_loop().create_future()
        self.pending_responses[msg_type + "_response"] = future
        
        try:
            # Отправляем команду
            message = json.dumps(command) + "\n"
            self.mt5_writer.write(message.encode('utf-8'))
            await self.mt5_writer.drain()
            print(f"Sent to MT5: {message.strip()}")
            
            # Ждём ответа
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        
        except asyncio.TimeoutError:
            print(f"Timeout waiting for response to {msg_type}")
            return None
        except Exception as e:
            print(f"Error sending command: {e}")
            return None
        finally:
            if msg_type + "_response" in self.pending_responses:
                del self.pending_responses[msg_type + "_response"]
    
    async def request_history(self, symbol: str, timeframe_minutes: int, 
                             start_date: str, end_date: str) -> bool:
        """
        Запрашивает историю котировок у советника MT5.
        
        Args:
            symbol: Валютная пара
            timeframe_minutes: Таймфрейм в минутах
            start_date: Дата начала (YYYY-MM-DD)
            end_date: Дата окончания (YYYY-MM-DD)
        
        Returns:
            True если запрос успешно отправлен
        """
        command = {
            "type": "fetch_history",
            "symbol": symbol,
            "timeframe_minutes": timeframe_minutes,
            "start_date": start_date,
            "end_date": end_date
        }
        
        response = await self.send_command(command, timeout=120.0)
        if response and response.get("status") == "ok":
            return True
        return False
    
    async def send_trade_command(self, action: str, symbol: str, volume: float,
                                 sl: Optional[float] = None, tp: Optional[float] = None,
                                 comment: str = "") -> Optional[dict]:
        """
        Отправляет торговую команду советнику MT5.
        
        Args:
            action: Действие ('buy', 'sell', 'close', 'buy_limit', 'sell_limit', etc.)
            symbol: Валютная пара
            volume: Объём лота
            sl: Stop Loss (цена)
            tp: Take Profit (цена)
            comment: Комментарий к ордеру
        
        Returns:
            Результат выполнения команды
        """
        command = {
            "type": "trade_command",
            "action": action,
            "symbol": symbol,
            "volume": volume,
            "sl": sl,
            "tp": tp,
            "comment": comment
        }
        
        response = await self.send_command(command, timeout=30.0)
        return response


# Глобальный экземпляр сервера
mt5_server: Optional[MT5SocketServer] = None


async def get_mt5_server() -> MT5SocketServer:
    """Возвращает экземпляр сервера MT5."""
    global mt5_server
    if mt5_server is None:
        import json
        with open("config.json", "r") as f:
            config = json.load(f)
        port = config.get("mt5_socket_port", 9999)
        mt5_server = MT5SocketServer(port=port)
    return mt5_server


async def start_socket_server_task():
    """Запускает сервер сокетов как фоновую задачу."""
    server = await get_mt5_server()
    await server.start_server()
