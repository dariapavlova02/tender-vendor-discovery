# Quick Start: Dashboard Observability

## Проблема
При работе с ML pipeline (PDF → Parser → LLM → JSON → Search) невозможно понять, где именно возникают ошибки:
- Парсер плохо читает таблицы?
- LLM галлюцинирует поля?
- Search не находит релевантных вендоров?

## Решение: Streamlit Dashboard

### 1️⃣ Установка (1 минута)

```bash
# Clone repo (if not done)
cd vendor_ai_agent

# Install dependencies
poetry install

# Setup environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2️⃣ Запуск (10 секунд)

```bash
./scripts/run_dashboard.sh
```

Или напрямую:

```bash
poetry run streamlit run src/vendor_ai_agent/dashboard.py
```

Dashboard откроется автоматически: `http://localhost:8501`

### 3️⃣ Использование (30 секунд)

1. **Upload** tender files (PDF/DOCX/Excel)
2. **Configure** в Sidebar:
   - Model: `gpt-5-mini` (быстро) или `gpt-5.1` (качество)
   - Auto Ingestion: ON (для скачивания attachments)
3. **Click** "Run Pipeline"
4. **Inspect** results в 5 табах:
   - Overview: Метрики + keywords
   - Extracted Data: Структурированные поля
   - Document Content: Все секции PDF
   - Vendors: Найденные компании с scores
   - Debug: Raw JSON dumps

### 4️⃣ Типовые сценарии

#### Сценарий A: "Почему volumes не извлекаются?"

1. Tab "Document Content" → Filter "table"
2. Проверьте, что таблицы с pricing распарсены
3. Tab "Extracted Data" → "Requirements"
4. Если volumes пустые → проблема в `FieldExtractor`
5. Tab "Debug" → посмотрите, какие keywords LLM нашел

#### Сценарий B: "Какой sector определился?"

1. Tab "Overview" → Metric "Detected Sector"
2. Tab "Extracted Data" → "Basic Info"
3. Если sector = "Unknown" → проверьте technical keywords

#### Сценарий C: "Почему мало вендоров?"

1. Tab "Vendors" → "Stats"
2. Сравните: Raw Vendors → After Enrichment → Final Matches
3. Если мало Raw → проблема в search terms
4. Если много фильтруется → проблема в `VendorFilter`

---

## Расширенная отладка: LangSmith

Для детального анализа LLM промптов:

### 1. Регистрация

[smith.langchain.com](https://smith.langchain.com/) → Create Account → Get API Key

### 2. Настройка

```bash
# В .env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-your-key-here
LANGCHAIN_PROJECT=vendor-agent

# Install
poetry add langsmith
```

### 3. Интеграция

Edit `src/vendor_ai_agent/modules/llm_providers.py`:

```python
from langsmith.wrappers import wrap_openai

# In OpenAIProvider.__init__:
if os.getenv("LANGCHAIN_TRACING_V2") == "true":
    self.client = wrap_openai(self.client)
```

### 4. Использование

После запуска pipeline:
1. Перейдите на [smith.langchain.com/projects](https://smith.langchain.com/projects)
2. Выберите проект `vendor-agent`
3. Посмотрите все LLM вызовы:
   - Input: Полный prompt
   - Output: Ответ модели
   - Metrics: Latency, tokens, cost

---

## Сравнение подходов

| Критерий | Streamlit Dashboard | LangSmith |
|----------|---------------------|-----------|
| **Цель** | Визуализация всего pipeline | Отладка LLM промптов |
| **Setup Time** | 1 минута | 5 минут |
| **Cost** | Free | Free (до 5000 traces) |
| **Use Case** | End-to-end проверка | Prompt engineering |
| **UI** | Локальный браузер | Cloud dashboard |

**Рекомендация:** Начните с Streamlit Dashboard для общего понимания. Добавьте LangSmith, когда будете тюнить промпты.

---

## Troubleshooting

### Dashboard не запускается

```bash
poetry lock
poetry install
./scripts/validate_dashboard.sh
```

### "Import streamlit not found"

```bash
poetry add streamlit
poetry install
```

### Pipeline зависает

Проверьте размер PDF файлов. Для файлов >100 страниц используйте pagination в dashboard.

### "OPENAI_API_KEY not set"

```bash
cp .env.example .env
# Edit .env and add your key
```

---

## Next Steps

1. **Test with real data**: Upload `data/Object _ rfx_18106 - OPP-1984/` PDFs
2. **Compare models**: Test `gpt-5-mini` vs `gpt-5.1` via sidebar
3. **Export results**: Download vendors as CSV/Excel from "Vendors" tab
4. **Setup LangSmith**: For prompt optimization

Full guides:
- [Dashboard Guide](DASHBOARD_GUIDE.md)
- [LangSmith Integration](LANGSMITH_INTEGRATION.md)
- [Pipeline Architecture](ARCHITECTURE.md)
