# LangSmith Integration Guide

## Трассировка LLM вызовов для отладки промптов

LangSmith — это observability платформа для LLM applications. Позволяет видеть:
- Input/Output каждого LLM вызова
- Latency и cost
- Цепочки вызовов (если используете LangChain)
- История экспериментов с промптами

---

## 🚀 Быстрая настройка

### 1. Регистрация

Перейдите на [smith.langchain.com](https://smith.langchain.com/) и создайте аккаунт.

### 2. Получение API Key

1. В dashboard перейдите в **Settings → API Keys**
2. Создайте новый ключ: **Create API Key**
3. Скопируйте ключ (он будет виден только один раз)

### 3. Настройка .env

Добавьте в файл `.env`:

```bash
# LangSmith Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="ls-xxx-your-key-here"
LANGCHAIN_PROJECT="vendor-agent"
```

**Важно:** Добавьте `.env` в `.gitignore`, чтобы не закоммитить API ключ!

### 4. Установка зависимости

```bash
poetry add langsmith
```

### 5. Интеграция в код

#### Option A: Обертка для OpenAI (рекомендуется)

Отредактируйте файл `src/vendor_ai_agent/modules/llm_providers.py`:

```python
import os
from openai import OpenAI

try:
    from langsmith.wrappers import wrap_openai
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

class OpenAIProvider(LLMProvider):
    def __init__(self, default_model: str = "gpt-5-mini", use_flex_tier: bool = True):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        self.client = OpenAI(api_key=api_key)
        
        # Wrap client with LangSmith if available
        if LANGSMITH_AVAILABLE and os.getenv("LANGCHAIN_TRACING_V2") == "true":
            self.client = wrap_openai(self.client)
            logging.info("✅ LangSmith tracing enabled")
        
        self.default_model = default_model
        self.use_flex_tier = use_flex_tier
```

#### Option B: Ручная трассировка (если не используете LangChain)

Для более детального контроля используйте декораторы:

```python
from langsmith import traceable

@traceable(
    name="extract_tender_fields",
    run_type="llm",
    metadata={"model": "gpt-5-mini"}
)
def extract_fields(self, sections: List[TenderSection]) -> StructuredDocData:
    prompt = self._build_extraction_prompt(sections)
    
    response = self.llm_provider.generate(
        prompt,
        response_format="json_object"
    )
    
    return self._parse_response(response)
```

---

## 📊 Использование Dashboard

После настройки, все LLM вызовы будут автоматически логироваться в LangSmith.

### Просмотр трейсов

1. Перейдите на [smith.langchain.com/projects](https://smith.langchain.com/projects)
2. Выберите проект `vendor-agent`
3. Вы увидите список всех runs

### Анализ конкретного вызова

Кликните на любой trace, чтобы увидеть:
- **Input**: Полный промпт, отправленный в модель
- **Output**: Ответ модели
- **Metadata**: Model, temperature, max_tokens
- **Metrics**: Latency (ms), Token usage, Cost ($)

### Фильтрация и поиск

Используйте фильтры:
- По статусу (success / error)
- По модели (gpt-5-mini / gpt-5.1)
- По latency (> 5 секунд)
- По тегам (если добавили в код)

---

## 🎯 Практические сценарии

### Сценарий 1: Debugging "Почему модель не нашла volumes?"

1. Запустите pipeline через dashboard
2. Перейдите в LangSmith → Runs
3. Найдите run с именем `extract_tender_fields`
4. Посмотрите Input:
   - Проверьте, что в промпт попали релевантные секции
   - Убедитесь, что там есть таблицы с volumes
5. Посмотрите Output:
   - Проверьте, что модель вернула JSON с полем `volumes`
   - Если вернула пустой массив, значит проблема в промпте или контексте

### Сценарий 2: Optimization "Какая модель дешевле для profiling?"

1. Запустите один и тот же tender через:
   - `gpt-5-mini`
   - `gpt-5.1`
2. В LangSmith сравните:
   - Cost ($)
   - Latency (ms)
   - Output качество (sector detection accuracy)
3. Выберите оптимальную модель

### Сценарий 3: A/B тестирование промптов

1. Создайте две версии `FieldExtractor` с разными промптами
2. Запустите оба на тестовом датасете
3. В LangSmith используйте **Comparison View** для сравнения:
   - Accuracy (сколько полей извлечено корректно)
   - Token usage (экономия)
   - Latency (скорость)

---

## 🔧 Расширенные возможности

### Добавление кастомных метаданных

```python
from langsmith import Client

client = Client()

@traceable(metadata={
    "tender_id": tender_profile.tender_id,
    "sector": tender_profile.doc_extracted.structured.sector,
    "num_sections": len(sections)
})
def extract_keywords(sections):
    ...
```

### Создание Datasets для evaluation

LangSmith позволяет создавать тестовые датасеты:

```python
from langsmith import Client

client = Client()

# Create dataset
dataset = client.create_dataset("tender-extraction-test")

# Add examples
client.create_example(
    dataset_id=dataset.id,
    inputs={
        "sections": [{"title": "Scope", "content": "Supply of ammunition"}]
    },
    outputs={
        "sector": "Defense",
        "technical_keywords": ["ammunition", "supply", "delivery"]
    }
)

# Run evaluation
from langsmith.evaluation import evaluate

results = evaluate(
    lambda inputs: extract_fields(inputs["sections"]),
    data=dataset.name
)
```

### Offline режим (для работы без интернета)

Если не хотите отправлять данные в облако:

```bash
# В .env
LANGCHAIN_TRACING_V2=false
```

Или используйте self-hosted версию:

```bash
docker run -p 1984:1984 langchain/langsmith
```

---

## 📊 Метрики для мониторинга

Создайте dashboard в LangSmith для отслеживания:
- **Avg latency** по модулям (parser, profiler, extractor)
- **Error rate** для каждого типа документа
- **Cost per tender** для оптимизации бюджета
- **Token usage** по типам промптов

---

## 🛡️ Security Best Practices

1. **Никогда не логируйте PII**: Убедитесь, что в traces не попадают персональные данные
2. **Используйте secrets**: Храните API ключи в `.env`, не в коде
3. **Self-hosted для sensitive data**: Для гос. тендеров используйте on-premise LangSmith

---

## 🔗 Дополнительные ресурсы

- [LangSmith Documentation](https://docs.smith.langchain.com/)
- [OpenAI Integration Guide](https://docs.smith.langchain.com/integrations/openai)
- [Evaluation Guide](https://docs.smith.langchain.com/evaluation)
- [Pricing](https://smith.langchain.com/pricing) — бесплатно до 5000 traces/month
