/**
 * JavaScript приложение для управления торговыми стратегиями.
 */

// Глобальное состояние
let strategies = [];
let currentStrategyId = null;
let config = { symbols: [], timeframes: [] };
let currentTestId = null;

// ============================================================================
// Инициализация
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    await loadStrategies();
    setupEventListeners();
    initializeDateInputs();
});

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        config = await response.json();
        
        // Заполняем селект таймфреймов с правильным форматом (M5, M15, H1, H4, D1)
        const baseTimeframeSelect = document.getElementById('base-timeframe');
        baseTimeframeSelect.innerHTML = config.timeframes.map(tf => 
            `<option value="${tf}">${formatTimeframe(tf)}</option>`
        ).join('');
        
        // Заполняем селект инструментов
        const testSymbolSelect = document.getElementById('test-symbol');
        testSymbolSelect.innerHTML = config.symbols.map(sym => 
            `<option value="${sym}">${sym}</option>`
        ).join('');
        
        // Заполняем чекбоксы таймфреймов
        const timeframesContainer = document.getElementById('timeframes-container');
        timeframesContainer.innerHTML = config.timeframes.map(tf => 
            `<label><input type="checkbox" name="timeframe" value="${tf}"> ${formatTimeframe(tf)}</label>`
        ).join('');
    } catch (error) {
        console.error('Failed to load config:', error);
    }
}

/**
 * Форматирует таймфрейм в читаемый вид (M5, M15, H1, H4, D1)
 */
function formatTimeframe(minutes) {
    if (minutes < 60) {
        return `M${minutes}`;
    } else if (minutes < 1440) {
        const hours = minutes / 60;
        return `H${hours}`;
    } else {
        return 'D1';
    }
}

async function loadStrategies() {
    try {
        const response = await fetch('/api/strategies');
        const data = await response.json();
        strategies = data.strategies || [];
        renderStrategiesList();
    } catch (error) {
        console.error('Failed to load strategies:', error);
    }
}

function renderStrategiesList() {
    const container = document.getElementById('strategies-list');
    
    if (strategies.length === 0) {
        container.innerHTML = '<p style="color: #95a5a6;">Нет сохранённых стратегий</p>';
        return;
    }
    
    container.innerHTML = strategies.map(s => `
        <div class="strategy-item ${s.id === currentStrategyId ? 'active' : ''}" 
             data-id="${s.id}">
            ${s.name}
        </div>
    `).join('');
    
    // Добавляем обработчики кликов
    container.querySelectorAll('.strategy-item').forEach(item => {
        item.addEventListener('click', () => selectStrategy(item.dataset.id));
    });
}

function setupEventListeners() {
    // Новая стратегия
    document.getElementById('btn-new-strategy').addEventListener('click', createNewStrategy);
    
    // Сохранение стратегии
    document.getElementById('strategy-form').addEventListener('submit', saveStrategy);
    
    // Удаление стратегии
    document.getElementById('btn-delete-strategy').addEventListener('click', deleteStrategy);
    
    // Добавить индикатор
    document.getElementById('btn-add-indicator').addEventListener('click', addIndicatorRow);
    
    // Улучшение промптов
    document.getElementById('btn-improve-open').addEventListener('click', () => improvePrompt('open'));
    document.getElementById('btn-improve-close').addEventListener('click', () => improvePrompt('close'));
    
    // Запуск тестирования
    document.getElementById('btn-run-backtest').addEventListener('click', runBacktest);
}

function initializeDateInputs() {
    const today = new Date().toISOString().split('T')[0];
    const lastMonth = new Date();
    lastMonth.setMonth(lastMonth.getMonth() - 1);
    const lastMonthStr = lastMonth.toISOString().split('T')[0];
    
    document.getElementById('test-start').value = lastMonthStr;
    document.getElementById('test-end').value = today;
}

// ============================================================================
// Управление стратегиями
// ============================================================================

function createNewStrategy() {
    currentStrategyId = null;
    document.getElementById('editor-title').textContent = 'Новая стратегия';
    document.getElementById('strategy-form').reset();
    document.getElementById('strategy-id').value = '';
    document.getElementById('indicators-container').innerHTML = '';
    document.getElementById('candles-count').value = '5';
    
    // Снимаем выделение со списка
    document.querySelectorAll('.strategy-item').forEach(item => item.classList.remove('active'));
}

function selectStrategy(strategyId) {
    currentStrategyId = strategyId;
    const strategy = strategies.find(s => s.id === strategyId);
    
    if (!strategy) return;
    
    document.getElementById('editor-title').textContent = strategy.name;
    document.getElementById('strategy-id').value = strategy.id;
    document.getElementById('strategy-name').value = strategy.name;
    document.getElementById('base-timeframe').value = strategy.base_timeframe || 60;
    document.getElementById('candles-count').value = strategy.candles_count || 5;
    document.getElementById('prompt-open').value = strategy.prompt_open || '';
    document.getElementById('prompt-close').value = strategy.prompt_close || '';
    
    // Чекбоксы таймфреймов
    document.querySelectorAll('input[name="timeframe"]').forEach(cb => {
        cb.checked = strategy.timeframes.includes(parseInt(cb.value));
    });
    
    // Индикаторы
    const indicatorsContainer = document.getElementById('indicators-container');
    indicatorsContainer.innerHTML = '';
    (strategy.indicators || []).forEach(ind => {
        addIndicatorRow(ind.type, ind.timeframe, ind.params);
    });
    
    // Подсвечиваем в списке
    renderStrategiesList();
}

async function saveStrategy(event) {
    event.preventDefault();
    
    const strategyId = document.getElementById('strategy-id').value;
    const name = document.getElementById('strategy-name').value;
    const baseTimeframe = parseInt(document.getElementById('base-timeframe').value);
    const candlesCount = parseInt(document.getElementById('candles-count').value) || 5;
    const promptOpen = document.getElementById('prompt-open').value;
    const promptClose = document.getElementById('prompt-close').value;
    
    // Собираем таймфреймы
    const timeframes = Array.from(document.querySelectorAll('input[name="timeframe"]:checked'))
        .map(cb => parseInt(cb.value));
    
    // Собираем индикаторы
    const indicators = [];
    document.querySelectorAll('.indicator-row').forEach(row => {
        const type = row.querySelector('.indicator-type').value;
        const timeframe = parseInt(row.querySelector('.indicator-timeframe').value);
        
        let params = {};
        
        if (type === 'STOCHASTIC') {
            params.k_period = parseInt(row.querySelector('.indicator-k-period')?.value) || 14;
            params.d_period = parseInt(row.querySelector('.indicator-d-period')?.value) || 3;
            params.slowing = parseInt(row.querySelector('.indicator-slowing')?.value) || 3;
        } else if (type === 'BOLLINGER') {
            params.period = parseInt(row.querySelector('.indicator-period')?.value) || 20;
            params.std_dev = parseFloat(row.querySelector('.indicator-std-dev')?.value) || 2.0;
        } else if (type === 'IS_PINBAR') {
            params.min_body_ratio = parseFloat(row.querySelector('.indicator-min-body')?.value) || 0.3;
            params.min_shadow_ratio = parseFloat(row.querySelector('.indicator-min-shadow')?.value) || 2.0;
        } else if (['SMA', 'EMA', 'RSI', 'ATR', 'ADX'].includes(type)) {
            params.period = parseInt(row.querySelector('.indicator-period')?.value) || 14;
        }
        // Для LAST_CANDLE_SIZE_PIPS и ENGULFING params остаётся пустым
        
        indicators.push({ type, timeframe, params });
    });
    
    try {
        let response;
        if (strategyId) {
            // Обновление
            response = await fetch(`/api/strategies/${strategyId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    timeframes,
                    indicators,
                    prompt_open: promptOpen,
                    prompt_close: promptClose,
                    base_timeframe: baseTimeframe,
                    candles_count: candlesCount
                })
            });
        } else {
            // Создание
            response = await fetch('/api/strategies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    timeframes,
                    indicators,
                    prompt_open: promptOpen,
                    prompt_close: promptClose,
                    base_timeframe: baseTimeframe,
                    candles_count: candlesCount
                })
            });
        }
        
        const data = await response.json();
        
        if (response.ok) {
            alert('Стратегия сохранена!');
            await loadStrategies();
            if (!strategyId && data.strategy) {
                selectStrategy(data.strategy.id);
            }
        } else {
            alert('Ошибка: ' + (data.detail || 'Не удалось сохранить стратегию'));
        }
    } catch (error) {
        console.error('Failed to save strategy:', error);
        alert('Ошибка при сохранении стратегии');
    }
}

async function deleteStrategy() {
    if (!currentStrategyId) {
        alert('Сначала выберите стратегию');
        return;
    }
    
    if (!confirm('Вы уверены, что хотите удалить эту стратегию?')) return;
    
    try {
        const response = await fetch(`/api/strategies/${currentStrategyId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            createNewStrategy();
            await loadStrategies();
            alert('Стратегия удалена');
        } else {
            alert('Ошибка при удалении стратегии');
        }
    } catch (error) {
        console.error('Failed to delete strategy:', error);
        alert('Ошибка при удалении стратегии');
    }
}

// ============================================================================
// Индикаторы
// ============================================================================

function addIndicatorRow(type = 'SMA', timeframe = 60, params = {}) {
    const container = document.getElementById('indicators-container');
    const rowId = Date.now();
    
    // Добавлены новые индикаторы: ADX, LAST_CANDLE_SIZE_PIPS, IS_PINBAR, ENGULFING
    const indicatorTypes = [
        'SMA', 'EMA', 'STOCHASTIC', 'RSI', 'BOLLINGER', 'ATR', 
        'ADX', 'LAST_CANDLE_SIZE_PIPS', 'IS_PINBAR', 'ENGULFING'
    ];
    const timeframeOptions = config.timeframes.map(tf => 
        `<option value="${tf}" ${tf === timeframe ? 'selected' : ''}>${formatTimeframe(tf)}</option>`
    ).join('');
    
    const row = document.createElement('div');
    row.className = 'indicator-row';
    row.dataset.id = rowId;
    
    let paramInputs = getParamInputs(type, params);
    
    row.innerHTML = `
        <select class="indicator-type" onchange="updateIndicatorParams(${rowId})">
            ${indicatorTypes.map(t => `<option value="${t}" ${t === type ? 'selected' : ''}>${t}</option>`).join('')}
        </select>
        <select class="indicator-timeframe">
            ${timeframeOptions}
        </select>
        ${paramInputs}
        <button type="button" class="btn btn-remove" onclick="removeIndicatorRow(${rowId})">✕</button>
    `;
    
    container.appendChild(row);
}

/**
 * Возвращает HTML для параметров индикатора в зависимости от типа
 */
function getParamInputs(type, params = {}) {
    if (type === 'STOCHASTIC') {
        return `
            <input type="number" class="indicator-k-period" placeholder="K" value="${params.k_period || 14}" style="width:60px">
            <input type="number" class="indicator-d-period" placeholder="D" value="${params.d_period || 3}" style="width:60px">
            <input type="number" class="indicator-slowing" placeholder="Sl" value="${params.slowing || 3}" style="width:60px">
        `;
    } else if (type === 'BOLLINGER') {
        return `
            <input type="number" class="indicator-period" placeholder="Per" value="${params.period || 20}" style="width:60px">
            <input type="number" class="indicator-std-dev" placeholder="StdDev" value="${params.std_dev || 2.0}" step="0.1" style="width:70px">
        `;
    } else if (type === 'IS_PINBAR') {
        return `
            <input type="number" class="indicator-min-body" placeholder="MinBody%" value="${params.min_body_ratio || 0.3}" step="0.1" style="width:70px">
            <input type="number" class="indicator-min-shadow" placeholder="MinShadow%" value="${params.min_shadow_ratio || 2.0}" step="0.1" style="width:70px">
        `;
    } else if (['SMA', 'EMA', 'RSI', 'ATR', 'ADX'].includes(type)) {
        return `
            <input type="number" class="indicator-period" placeholder="Period" value="${params.period || 14}" style="width:80px">
        `;
    } else {
        // Для LAST_CANDLE_SIZE_PIPS и ENGULFING параметры не нужны
        return '';
    }
}

function updateIndicatorParams(rowId) {
    const row = document.querySelector(`.indicator-row[data-id="${rowId}"]`);
    if (!row) return;
    
    const type = row.querySelector('.indicator-type').value;
    
    // Удаляем все существующие input'ы параметров
    row.querySelectorAll('.indicator-period, .indicator-k-period, .indicator-d-period, .indicator-slowing, .indicator-std-dev, .indicator-min-body, .indicator-min-shadow')
        .forEach(el => el.remove());
    
    let newInputs = getParamInputs(type, {});
    
    // Вставляем новые input'ы перед кнопкой удаления
    const removeBtn = row.querySelector('.btn-remove');
    if (newInputs.trim()) {
        removeBtn.insertAdjacentHTML('beforebegin', newInputs);
    }
}

function removeIndicatorRow(rowId) {
    const row = document.querySelector(`.indicator-row[data-id="${rowId}"]`);
    if (row) row.remove();
}

// ============================================================================
// Улучшение промптов через LLM
// ============================================================================

async function improvePrompt(promptType) {
    const promptField = document.getElementById(`prompt-${promptType}`);
    const requestField = document.getElementById(`prompt-${promptType}-request`);
    const btn = document.getElementById(`btn-improve-${promptType}`);
    
    const promptText = promptField.value;
    const userRequest = requestField.value;
    
    if (!userRequest.trim()) {
        alert('Введите запрос для улучшения промпта');
        return;
    }
    
    btn.disabled = true;
    btn.textContent = 'Обработка...';
    
    try {
        const response = await fetch('/api/llm/edit_prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: promptText,
                request: userRequest
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            promptField.value = data.result;
            requestField.value = '';
        } else {
            // Форматируем сообщение об ошибке для отображения
            let errorMessage = data.detail || 'Не удалось улучшить промпт';
            
            // Если ошибка содержит инструкции по проверке настроек, показываем их
            if (errorMessage.includes('config.json')) {
                alert('Ошибка подключения к LLM:\n\n' + errorMessage);
            } else {
                alert('Ошибка: ' + errorMessage);
            }
        }
    } catch (error) {
        console.error('Failed to improve prompt:', error);
        alert('Ошибка соединения с сервером: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Улучшить промпт (AI)';
    }
}

// ============================================================================
// Тестирование стратегий
// ============================================================================

async function runBacktest() {
    if (!currentStrategyId) {
        alert('Сначала выберите стратегию для тестирования');
        return;
    }
    
    const symbol = document.getElementById('test-symbol').value;
    const startDate = document.getElementById('test-start').value;
    const endDate = document.getElementById('test-end').value;
    
    if (!startDate || !endDate) {
        alert('Выберите даты начала и окончания тестирования');
        return;
    }
    
    const btn = document.getElementById('btn-run-backtest');
    btn.disabled = true;
    btn.textContent = 'Тестирование...';
    
    // Показываем панель результатов
    const resultsPanel = document.getElementById('backtest-results');
    resultsPanel.style.display = 'block';
    
    try {
        const response = await fetch(`/api/strategies/${currentStrategyId}/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol,
                start_date: startDate,
                end_date: endDate
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentTestId = data.test_id;
            pollTestStatus(currentTestId);
        } else {
            alert('Ошибка: ' + (data.detail || 'Не удалось запустить тестирование'));
            btn.disabled = false;
            btn.textContent = 'Запустить тестирование';
        }
    } catch (error) {
        console.error('Failed to start backtest:', error);
        alert('Ошибка при запуске тестирования');
        btn.disabled = false;
        btn.textContent = 'Запустить тестирование';
    }
}

async function pollTestStatus(testId) {
    const statusDiv = document.getElementById('test-status');
    const logsDiv = document.getElementById('test-logs');
    
    const poll = async () => {
        try {
            const response = await fetch(`/api/strategies/${currentStrategyId}/test/status?test_id=${testId}`);
            const data = await response.json();
            
            if (response.ok) {
                // Обновляем статус
                statusDiv.className = data.status;
                statusDiv.textContent = `Статус: ${data.status} (${data.progress}%)`;
                
                // Обновляем логи
                if (data.logs && data.logs.length > 0) {
                    logsDiv.innerHTML = data.logs.map(log => 
                        `<div class="log-entry">${log}</div>`
                    ).join('');
                    logsDiv.scrollTop = logsDiv.scrollHeight;
                }
                
                // Если завершено или ошибка
                if (data.status === 'completed' || data.status === 'failed') {
                    displayTestResults(data);
                    document.getElementById('btn-run-backtest').disabled = false;
                    document.getElementById('btn-run-backtest').textContent = 'Запустить тестирование';
                } else {
                    // Продолжаем опрос
                    setTimeout(poll, 2000);
                }
            }
        } catch (error) {
            console.error('Failed to poll status:', error);
            setTimeout(poll, 2000);
        }
    };
    
    poll();
}

function displayTestResults(data) {
    const summaryDiv = document.getElementById('test-summary');
    const tradesDiv = document.getElementById('test-trades');
    
    if (!data.results) {
        summaryDiv.innerHTML = '<p>Нет результатов</p>';
        return;
    }
    
    const results = data.results;
    
    // Сводка
    summaryDiv.innerHTML = `
        <div class="summary-card">
            <h4>Итоговый баланс</h4>
            <div class="value">$${results.final_balance?.toFixed(2) || '0.00'}</div>
        </div>
        <div class="summary-card">
            <h4>P&L</h4>
            <div class="value" style="color: ${results.total_pnl >= 0 ? 'green' : 'red'}">
                $${results.total_pnl?.toFixed(2) || '0.00'}
            </div>
        </div>
        <div class="summary-card">
            <h4>Всего сделок</h4>
            <div class="value">${results.total_trades || 0}</div>
        </div>
        <div class="summary-card">
            <h4>Win Rate</h4>
            <div class="value">${results.win_rate?.toFixed(1) || '0'}%</div>
        </div>
    `;
    
    // Таблица сделок
    if (results.trades && results.trades.length > 0) {
        tradesDiv.innerHTML = `
            <table class="trades-table">
                <thead>
                    <tr>
                        <th>Время закрытия</th>
                        <th>Тип</th>
                        <th>Цена открытия</th>
                        <th>Цена закрытия</th>
                        <th>Причина</th>
                        <th>P&L</th>
                    </tr>
                </thead>
                <tbody>
                    ${results.trades.map(trade => `
                        <tr class="${trade.pnl >= 0 ? 'positive' : 'negative'}">
                            <td>${trade.close_time}</td>
                            <td>${trade.type.toUpperCase()}</td>
                            <td>${trade.open_price?.toFixed(5) || '-'}</td>
                            <td>${trade.close_price?.toFixed(5) || '-'}</td>
                            <td>${trade.close_reason}</td>
                            <td>$${trade.pnl?.toFixed(2) || '0.00'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        tradesDiv.innerHTML = '<p>Сделок не было</p>';
    }
}
