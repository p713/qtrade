//+------------------------------------------------------------------+
//|                                              ForexCollector.mq5 |
//|                                  Copyright 2024, Forex Trading App |
//|                                   Советник для сбора данных и торговли |
//+------------------------------------------------------------------+
#property copyright "Forex Trading App"
#property version   "1.00"
#property strict
#property description "Сбор котировок и исполнение торговых команд через сокет"

#include <WinSock2.mqh>

// --- Входные параметры ---
input string Symbols = "EURUSD,GBPUSD,USDJPY,USDCHF,USDCAD,EURJPY,GBPJPY,CHFJPY,GBPCHF,AUDUSD,AUDJPY";
input string DbFile = "forex_data.sqlite";
input int HistoryBars = 500;
input string ServerIP = "127.0.0.1";
input int ServerPort = 9999;

// --- Глобальные переменные ---
int db_handle = INVALID_HANDLE;
string symbol_list[];
int timeframes_minutes[] = {60, 240, 1440}; // H1, H4, D1

// Сокет для связи с приложением
int socket_handle = INVALID_SOCKET;
bool connected_to_app = false;
char recv_buffer[];
ArrayResize(recv_buffer, 4096);

// --- Инициализация ---
int OnInit()
{
   Print("=== Forex Collector EA Starting ===");
   
   // Разбиваем список символов
   StringSplit(Symbols, ',', symbol_list);
   Print("Symbols: ", Symbols, ", Count: ", ArraySize(symbol_list));
   
   // Открываем/создаём базу данных
   db_handle = DatabaseOpen(DbFile, DATABASE_OPEN_READWRITE | DATABASE_OPEN_CREATE);
   if (db_handle == INVALID_HANDLE)
   {
      Print("Failed to open database: ", GetLastError());
      return(INIT_FAILED);
   }
   Print("Database opened: ", DbFile);
   
   // Создаём таблицу если не существует
   if (!DatabaseExecute(db_handle, 
       "CREATE TABLE IF NOT EXISTS price_data ("
       "symbol TEXT, "
       "timeframe INT, "
       "time INTEGER, "
       "open REAL, "
       "high REAL, "
       "low REAL, "
       "close REAL, "
       "volume INTEGER, "
       "PRIMARY KEY(symbol, timeframe, time));"))
   {
      Print("Failed to create table: ", GetLastError());
      DatabaseClose(db_handle);
      return(INIT_FAILED);
   }
   Print("Table price_data created");
   
   // Инициализируем WinSocket
   if (!WSAStartup(0x0202))
   {
      Print("WSAStartup failed: ", WSAGetLastError());
      DatabaseClose(db_handle);
      return(INIT_FAILED);
   }
   
   // Подключаемся к серверу приложения
   ConnectToApp();
   
   // Устанавливаем таймер для периодических операций
   EventSetTimer(5); // Каждые 5 секунд
   
   Print("=== Forex Collector EA Initialized ===");
   return(INIT_SUCCEEDED);
}

// --- Деинициализация ---
void OnDeinit(const int reason)
{
   Print("Deinitializing...");
   
   // Закрываем сокет
   if (socket_handle != INVALID_SOCKET)
   {
      closesocket(socket_handle);
      socket_handle = INVALID_SOCKET;
   }
   
   // Очищаем WinSocket
   WSACleanup();
   
   // Закрываем базу данных
   if (db_handle != INVALID_HANDLE)
   {
      DatabaseClose(db_handle);
      Print("Database closed");
   }
   
   EventKillTimer();
}

// --- Таймер ---
void OnTimer()
{
   // Проверяем соединение
   if (!connected_to_app)
   {
      ConnectToApp();
   }
   
   // Если подключены, проверяем входящие команды
   if (connected_to_app)
   {
      CheckForCommands();
   }
}

// --- Подключение к приложению ---
void ConnectToApp()
{
   if (connected_to_app) return;
   
   Print("Connecting to app at ", ServerIP, ":", ServerPort);
   
   socket_handle = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
   if (socket_handle == INVALID_SOCKET)
   {
      Print("Socket creation failed: ", WSAGetLastError());
      return;
   }
   
   sockaddr_in server_addr;
   server_addr.sin_family = AF_INET;
   server_addr.sin_port = htons(ServerPort);
   server_addr.sin_addr.s_addr = inet_addr(ServerIP);
   
   int connect_result = connect(socket_handle, server_addr, SizeOf(server_addr));
   if (connect_result == SOCKET_ERROR)
   {
      Print("Connection failed: ", WSAGetLastError());
      closesocket(socket_handle);
      socket_handle = INVALID_SOCKET;
      return;
   }
   
   connected_to_app = true;
   Print("Connected to application!");
   
   // Отправляем handshake
   SendHandshake();
}

// --- Отправка handshake ---
void SendHandshake()
{
   string message = "{\"type\":\"handshake\",\"ea_name\":\"ForexCollector\"}\n";
   send(socket_handle, StringToBuffer(message), StringLen(message), 0);
   Print("Sent handshake");
}

// --- Проверка команд от приложения ---
void CheckForCommands()
{
   int bytes_received = recv(socket_handle, recv_buffer, ArraySize(recv_buffer), 0);
   
   if (bytes_received > 0)
   {
      string received = BufferToString(recv_buffer, bytes_received);
      Print("Received from app: ", received);
      
      // Парсим JSON команду
      ProcessCommand(received);
   }
   else if (bytes_received == 0)
   {
      Print("Server disconnected");
      connected_to_app = false;
      closesocket(socket_handle);
      socket_handle = INVALID_SOCKET;
   }
}

// --- Обработка команды ---
void ProcessCommand(string json_command)
{
   // Простая обработка JSON без библиотеки
   string cmd_type = ExtractJsonValue(json_command, "type");
   
   if (cmd_type == "fetch_history")
   {
      string symbol = ExtractJsonValue(json_command, "symbol");
      int tf_minutes = (int)StringToInteger(ExtractJsonValue(json_command, "timeframe_minutes"));
      string start_date = ExtractJsonValue(json_command, "start_date");
      string end_date = ExtractJsonValue(json_command, "end_date");
      
      FetchHistory(symbol, tf_minutes, start_date, end_date);
   }
   else if (cmd_type == "trade_command")
   {
      string action = ExtractJsonValue(json_command, "action");
      string symbol = ExtractJsonValue(json_command, "symbol");
      double volume = StringToDouble(ExtractJsonValue(json_command, "volume"));
      double sl = StringToDouble(ExtractJsonValue(json_command, "sl"));
      double tp = StringToDouble(ExtractJsonValue(json_command, "tp"));
      string comment = ExtractJsonValue(json_command, "comment");
      
      ExecuteTradeCommand(action, symbol, volume, sl, tp, comment);
   }
}

// --- Загрузка истории ---
void FetchHistory(string symbol, int tf_minutes, string start_date, string end_date)
{
   Print("Fetching history for ", symbol, " H", tf_minutes/60, ": ", start_date, " to ", end_date);
   
   ENUM_TIMEFRAMES tf = PeriodMinutesToEnum(tf_minutes);
   
   datetime start_dt = StringToTime(start_date);
   datetime end_dt = StringToTime(end_date) + 86400; // +1 день
   
   // Очищаем старые данные для этой пары и таймфрейма
   string delete_query = StringFormat(
      "DELETE FROM price_data WHERE symbol='%s' AND timeframe=%d;",
      symbol, tf_minutes);
   DatabaseExecute(db_handle, delete_query);
   
   // Копируем бары
   MqlRates rates[];
   int copied = CopyRates(symbol, tf, start_dt, end_dt, rates);
   
   if (copied > 0)
   {
      Print("Copied ", copied, " bars");
      
      // Вставляем в базу
      for (int i = 0; i < copied; i++)
      {
         InsertRate(symbol, tf_minutes, rates[i]);
      }
      
      // Отправляем уведомление о завершении
      SendResponse("{\"type\":\"fetch_history_response\",\"symbol\":\"" + symbol + 
                   "\",\"timeframe\":" + IntegerToString(tf_minutes) + 
                   ",\"status\":\"ok\",\"bars\":" + IntegerToString(copied) + "}\n");
   }
   else
   {
      Print("Failed to copy rates: ", GetLastError());
      SendResponse("{\"type\":\"fetch_history_response\",\"symbol\":\"" + symbol + 
                   "\",\"timeframe\":" + IntegerToString(tf_minutes) + 
                   ",\"status\":\"error\",\"message\":\"No data\"}\n");
   }
}

// --- Исполнение торговой команды ---
void ExecuteTradeCommand(string action, string symbol, double volume, double sl, double tp, string comment)
{
   Print("Trade command: ", action, " ", symbol, " vol=", volume, " SL=", sl, " TP=", tp);
   
   long ticket = -1;
   bool result = false;
   
   if (action == "buy" || action == "sell")
   {
      // Рыночный ордер
      MqlTradeRequest request = {};
      MqlTradeResult trade_result = {};
      
      request.action = TRADE_ACTION_DEAL;
      request.symbol = symbol;
      request.volume = volume;
      request.type = (action == "buy") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      request.price = (action == "buy") ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
      request.sl = sl;
      request.tp = tp;
      request.comment = comment;
      request.magic = 123456;
      
      if (OrderSend(request, trade_result))
      {
         ticket = trade_result.order;
         result = true;
         Print("Order executed, ticket: ", ticket);
      }
      else
      {
         Print("OrderSend failed: ", GetLastError(), " retcode=", trade_result.retcode);
      }
   }
   else if (StringFind(action, "limit") >= 0 || StringFind(action, "stop") >= 0)
   {
      // Отложенный ордер
      MqlTradeRequest request = {};
      MqlTradeResult trade_result = {};
      
      request.action = TRADE_ACTION_PENDING;
      request.symbol = symbol;
      request.volume = volume;
      request.type = StringFind(action, "buy") >= 0 ? 
                     (StringFind(action, "limit") >= 0 ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_BUY_STOP) :
                     (StringFind(action, "limit") >= 0 ? ORDER_TYPE_SELL_LIMIT : ORDER_TYPE_SELL_STOP);
      request.price = sl; // Используем SL как цену для отложенного ордера
      request.sl = sl;
      request.tp = tp;
      request.comment = comment;
      request.magic = 123456;
      
      if (OrderSend(request, trade_result))
      {
         ticket = trade_result.order;
         result = true;
         Print("Pending order placed, ticket: ", ticket);
      }
      else
      {
         Print("OrderSend failed: ", GetLastError());
      }
   }
   else if (action == "close")
   {
      // Закрытие позиции
      if (PositionSelect(symbol))
      {
         ulong position_ticket = PositionGetInteger(POSITION_TICKET);
         long position_type = PositionGetInteger(POSITION_TYPE);
         double position_volume = PositionGetDouble(POSITION_VOLUME);
         
         MqlTradeRequest request = {};
         MqlTradeResult trade_result = {};
         
         request.action = TRADE_ACTION_DEAL;
         request.position = position_ticket;
         request.symbol = symbol;
         request.volume = position_volume;
         request.type = (position_type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (position_type == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_BID) : SymbolInfoDouble(symbol, SYMBOL_ASK);
         
         if (OrderSend(request, trade_result))
         {
            ticket = trade_result.order;
            result = true;
            Print("Position closed, ticket: ", ticket);
         }
         else
         {
            Print("Close failed: ", GetLastError());
         }
      }
      else
      {
         Print("No position to close for ", symbol);
      }
   }
   
   // Отправляем результат
   string status = result ? "ok" : "error";
   string response = "{\"type\":\"trade_command_response\",\"ticket\":" + IntToString(ticket) + 
                     ",\"status\":\"" + status + "\"}\n";
   SendResponse(response);
}

// --- Вставка бара в базу ---
void InsertRate(string sym, int timeframe_minutes, const MqlRates &rate)
{
   string query = StringFormat(
      "INSERT OR IGNORE INTO price_data "
      "(symbol, timeframe, time, open, high, low, close, volume) "
      "VALUES ('%s', %d, %I64d, %.5f, %.5f, %.5f, %.5f, %I64d);",
      sym, timeframe_minutes, rate.time, rate.open, rate.high, rate.low, rate.close, rate.tick_volume);
   
   if (!DatabaseExecute(db_handle, query))
   {
      Print("Insert failed: ", GetLastError());
   }
}

// --- Отправка ответа ---
void SendResponse(string message)
{
   if (connected_to_app && socket_handle != INVALID_SOCKET)
   {
      send(socket_handle, StringToBuffer(message), StringLen(message), 0);
      Print("Sent response: ", message);
   }
}

// --- Конвертация минут в ENUM_TIMEFRAMES ---
ENUM_TIMEFRAMES PeriodMinutesToEnum(int minutes)
{
   switch(minutes)
   {
      case 1:    return PERIOD_M1;
      case 5:    return PERIOD_M5;
      case 15:   return PERIOD_M15;
      case 30:   return PERIOD_M30;
      case 60:   return PERIOD_H1;
      case 120:  return PERIOD_H2;
      case 240:  return PERIOD_H4;
      case 480:  return PERIOD_H8;
      case 1440: return PERIOD_D1;
      default:   return PERIOD_CURRENT;
   }
}

// --- Вспомогательная функция для извлечения значения из JSON ---
string ExtractJsonValue(string json, string key)
{
   string search_key = "\"" + key + "\":";
   int pos = StringFind(json, search_key);
   
   if (pos < 0) return "";
   
   int start = pos + StringLen(search_key);
   
   // Пропускаем пробелы
   while (start < StringLen(json) && StringSubstr(json, start, 1) == " ") start++;
   
   // Определяем тип значения
   char first_char = StringSubstr(json, start, 1);
   
   if (first_char == '"')
   {
      // Строка
      start++;
      int end = start;
      while (end < StringLen(json) && StringSubstr(json, end, 1) != '"') end++;
      return StringSubstr(json, start, end - start);
   }
   else
   {
      // Число или булево
      int end = start;
      while (end < StringLen(json) && 
             StringSubstr(json, end, 1) != ',' && 
             StringSubstr(json, end, 1) != '}' &&
             StringSubstr(json, end, 1) != '\n') end++;
      
      return StringTrimRight(StringSubstr(json, start, end - start));
   }
}

// --- Конвертация строки в буфер ---
uchar& StringToBuffer(string str)
{
   uchar buffer[];
   int len = StringLen(str);
   ArrayResize(buffer, len);
   
   for (int i = 0; i < len; i++)
   {
      buffer[i] = (uchar)StringGetCharacter(str, i);
   }
   
   return buffer;
}

// --- Конвертация буфера в строку ---
string BufferToString(uchar &buffer[], int length)
{
   string result = "";
   for (int i = 0; i < length && buffer[i] != 0; i++)
   {
      result += ShortToString(buffer[i]);
   }
   return result;
}
//+------------------------------------------------------------------+
