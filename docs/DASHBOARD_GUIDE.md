# Tender AI Agent Dashboard

## Observability Dashboard для отладки ML Pipeline

Dashboard предоставляет полную визуализацию всех этапов обработки:
- **Parsing**: Просмотр извлеченных секций и таблиц из PDF
- **Profiling**: Анализ keywords и search terms, генерируемых LLM
- **Extraction**: Проверка структурированных данных (volumes, certifications, contact info)
- **Vendors**: Список найденных и ранжированных вендоров

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
poetry install
```

Это установит `streamlit` и все необходимые зависимости.

### 2. Запуск Dashboard

**Вариант A: Через скрипт**
```bash
chmod +x scripts/run_dashboard.sh
./scripts/run_dashboard.sh
```

**Вариант B: Напрямую через poetry**
```bash
poetry run streamlit run src/vendor_ai_agent/dashboard.py
```

**Вариант C: Через python**
```bash
poetry shell
python -m streamlit run src/vendor_ai_agent/dashboard.py
```

Dashboard откроется автоматически в браузере по адресу: `http://localhost:8501`

---

## 📊 Возможности Dashboard

### Tab 1: Overview
- Метрики: Total Sections, Sector, Vendors Discovered, Final Matches
- Technical Keywords (топ-15)
- Search Terms для vendor discovery

### Tab 2: Extracted Data
- **Basic Info**: Reference numbers, Location, Contact info
- **Requirements**: Volume items, Certifications, Licenses
- **Raw JSON**: Полный дамп `StructuredDocData`

### Tab 3: Document Content
- Просмотр всех распарсенных секций
- Фильтрация по типу (text, table, qa_pair, addendum)
- Предварительный просмотр контента и метаданных

### Tab 4: Vendors
- **Final Matches**: Топовые вендоры с capability score
- **All Discovered**: Полный список после enrichment
- **Stats**: Метрики по pipeline (raw → enriched → matched)

### Tab 5: Debug
- Полный дамп `TenderProfile`
- API Metadata
- Dynamic Context

---

## 🛠 Настройки (Sidebar)

- **LLM Model**: Выбор между `gpt-5-mini` (дешево) и `gpt-5.1` (качество)
- **Use Flex Tier**: Включить Flex Tier OpenAI для снижения стоимости
- **Auto Ingestion**: Автоматическое скачивание attachments из Canada Buys API

---

## 🐛 Отладка

### Проблема: "Import streamlit could not be resolved"

**Решение:**
```bash
poetry add streamlit
poetry install
```

### Проблема: "No module named 'vendor_ai_agent'"

**Решение:**
```bash
poetry shell
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
streamlit run src/vendor_ai_agent/dashboard.py
```

### Проблема: Pipeline зависает на этапе parsing

**Решение:** Проверьте размер PDF файлов. Для больших файлов (>100 страниц) используйте:
- Добавьте `st.spinner()` для отображения прогресса
- Включите debug logging в sidebar

---

## 📝 Пример использования

1. Запустите dashboard
2. Загрузите тестовый tender из `data/Object _ rfx_18106 - OPP-1984/`
3. Выберите модель `gpt-5-mini` для быстрого теста
4. Нажмите "Run Pipeline"
5. Проверьте результаты:
   - **Overview**: Убедитесь, что sector определен корректно
   - **Extracted Data**: Проверьте, что volumes извлечены правильно
   - **Document Content**: Найдите таблицы с pricing
   - **Vendors**: Посмотрите топ-10 matched vendors

---

## 🔧 Расширение Dashboard

### Добавление новой метрики

Отредактируйте функцию `render_overview_tab()` в `dashboard.py`:

```python
with col5:
    st.metric("Your Metric", your_value)
```

### Добавление нового Tab

```python
with tab6:
    st.subheader("Your Custom Tab")
    st.json(your_data)
```

---

## 🚀 Production Deployment

Для production deployment используйте:

```bash
poetry run streamlit run src/vendor_ai_agent/dashboard.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true
```

**Docker:**
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev
COPY . .
EXPOSE 8501
CMD ["poetry", "run", "streamlit", "run", "src/vendor_ai_agent/dashboard.py", "--server.headless", "true"]
```

---

## 📚 Дополнительные ресурсы

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Pipeline Architecture](../docs/ARCHITECTURE.md)
- [Pipeline Workflow](../docs/PIPELINE_WORKFLOW.md)
