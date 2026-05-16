"""
Главный файл приложения FastAPI.
Веб-сервер + REST API + сервер сокетов для MT5.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from models import (
    StrategyCreate, StrategyUpdate, BacktestRequest,
    EditPromptRequest, TradeCommand, ConfigResponse
)
from strategy_manager import (
    get_all_strategies, get_strategy_by_id,
    create_strategy, update_strategy, delete_strategy
)
from llm import edit_prompt
from socket_server import get_mt5_server, start_socket_server_task
from backtester import run_strategy_backtest


# Хранилище статусов тестирования
test_statuses: Dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan контекст для запуска и остановки сервера сокетов.
    """
    # Запуск при старте
    print("Starting application...")
    
    # Загружаем конфигурацию
    with open("config.json", "r") as f:
        config = json.load(f)
    print(f"Loaded config: symbols={config.get('symbols')}, timeframes={config.get('timeframes')}")
    
    # Запускаем сервер сокетов в фоновой задаче
    socket_task = asyncio.create_task(start_socket_server_task())
    
    yield
    
    # Остановка при завершении
    print("Shutting down application...")
    socket_task.cancel()


app = FastAPI(
    title="Forex Trading Application",
    description="Приложение для торговли на Форекс и тестирования стратегий",
    version="1.0.0",
    lifespan=lifespan
)

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================================
# Основные маршруты
# ============================================================================

@app.get("/")
async def root():
    """Отдаёт главную страницу приложения."""
    return FileResponse("static/index.html")


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """Возвращает конфигурацию приложения (символы, таймфреймы)."""
    with open("config.json", "r") as f:
        config = json.load(f)
    
    return ConfigResponse(
        symbols=config.get("symbols", []),
        timeframes=config.get("timeframes", [])
    )


# ============================================================================
# CRUD стратегии
# ============================================================================

@app.get("/api/strategies")
async def list_strategies():
    """Возвращает список всех стратегий."""
    strategies = get_all_strategies()
    return {"strategies": strategies}


@app.post("/api/strategies")
async def create_new_strategy(strategy: StrategyCreate):
    """Создаёт новую стратегию."""
    indicators_dict = [ind.model_dump() for ind in strategy.indicators]
    
    new_strategy = create_strategy(
        name=strategy.name,
        timeframes=strategy.timeframes,
        indicators=indicators_dict,
        prompt_open=strategy.prompt_open,
        prompt_close=strategy.prompt_close,
        base_timeframe=strategy.base_timeframe
    )
    
    return {"strategy": new_strategy}


@app.get("/api/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Возвращает стратегию по ID."""
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return {"strategy": strategy}


@app.put("/api/strategies/{strategy_id}")
async def update_existing_strategy(strategy_id: str, strategy_update: StrategyUpdate):
    """Обновляет существующую стратегию."""
    update_data = {k: v for k, v in strategy_update.model_dump().items() if v is not None}
    
    updated = update_strategy(strategy_id, **update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return {"strategy": updated}


@app.delete("/api/strategies/{strategy_id}")
async def remove_strategy(strategy_id: str):
    """Удаляет стратегию."""
    success = delete_strategy(strategy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return {"status": "deleted"}


# ============================================================================
# LLM - редактирование промптов
# ============================================================================

@app.post("/api/llm/edit_prompt")
async def edit_prompt_endpoint(request: EditPromptRequest):
    """
    Редактирует промпт с помощью медленной LLM.
    
    Используется для улучшения промптов открытия и закрытия сделок.
    """
    try:
        result = edit_prompt(request.prompt, request.request)
        return {"result": result}
    except Exception as e:
        # Логируем полную информацию об ошибке
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in edit_prompt_endpoint: {error_details}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


# ============================================================================
# Тестирование стратегий
# ============================================================================

@app.post("/api/strategies/{strategy_id}/test")
async def start_backtest(strategy_id: str, request: BacktestRequest, background_tasks: BackgroundTasks):
    """
    Запускает тестирование стратегии.
    
    Тестирование выполняется в фоновом режиме.
    """
    strategy = get_strategy_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    test_id = f"{strategy_id}_{request.symbol}_{request.start_date}_{request.end_date}"
    
    # Инициализируем статус
    test_statuses[test_id] = {
        "test_id": test_id,
        "status": "running",
        "progress": 0,
        "logs": [],
        "results": None
    }
    
    # Запускаем тестирование в фоне
    async def run_test():
        try:
            results = await run_strategy_backtest(
                strategy_id=strategy_id,
                symbol=request.symbol,
                start_date=request.start_date,
                end_date=request.end_date
            )
            
            test_statuses[test_id]["status"] = "completed"
            test_statuses[test_id]["progress"] = 100
            test_statuses[test_id]["results"] = results
            
            if "logs" in results:
                test_statuses[test_id]["logs"] = results["logs"]
        
        except Exception as e:
            test_statuses[test_id]["status"] = "failed"
            test_statuses[test_id]["logs"].append(f"Error: {str(e)}")
    
    background_tasks.add_task(run_test)
    
    return {"test_id": test_id, "status": "started"}


@app.get("/api/strategies/{strategy_id}/test/status")
async def get_test_status(test_id: str):
    """Возвращает статус тестирования."""
    if test_id not in test_statuses:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return test_statuses[test_id]


# ============================================================================
# Торговые команды MT5
# ============================================================================

@app.post("/api/mt5/command")
async def send_mt5_command(command: TradeCommand):
    """
    Отправляет торговую команду советнику MT5.
    """
    socket_server = await get_mt5_server()
    
    if not socket_server.connected:
        raise HTTPException(status_code=503, detail="MT5 not connected")
    
    result = await socket_server.send_trade_command(
        action=command.action,
        symbol=command.symbol,
        volume=command.volume,
        sl=command.sl,
        tp=command.tp,
        comment=command.comment
    )
    
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to send command to MT5")
    
    return {"result": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
