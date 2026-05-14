# 🚀 Guia de Otimização — @CanalQb SearchPRO Web

> **Criado por:** Mavis (MiniMax Agent) | **Data:** 13/05/2026
> **Objetivo:** Transformar o FastSearch em uma ferramenta mais inteligente, dinâmica e extremamente rápida.

---

## 🎯 Resumo Executivo

- Implementar cache inteligente para reduzir chamadas de API em até 80%
- Adicionar learning layer para melhorar resultados baseado no histórico
- Otimizar requisições com parallel fetching e early termination
- Criar sistema de sugestões contextuais e autocomplete
- Implementar retry inteligente com backoff exponencial

---

## 1. ⚡ OTIMIZAÇÃO DE VELOCIDADE

### 1.1 Cache em Múltiplas Camadas

```python
# backend/core/cache.py
import time
import hashlib
from functools import lru_cache
from typing import Optional, Any
import asyncio

class MultiLayerCache:
    """Cache em memória + disco para máxima performance."""
    
    def __init__(self):
        self._memory_cache = {}
        self._ttl = {
            "coords": 86400,    # 24h - CEP não muda
            "stores": 3600,     # 1h  - resultados podem mudar
            "categories": 604800  # 7 dias - mapa de categorias
        }
    
    def _make_key(self, prefix: str, *args) -> str:
        return f"{prefix}:{hashlib.md5(str(args).encode()).hexdigest()}"
    
    async def get_or_fetch(
        self, 
        prefix: str, 
        key: str, 
        fetch_func,
        *args,
        ttl: Optional[int] = None
    ):
        cache_key = self._make_key(prefix, key)
        
        # Check memory cache
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if time.time() - cached["ts"] < (ttl or self._ttl.get(prefix, 3600)):
                return cached["data"]
        
        # Fetch fresh data
        data = await fetch_func(*args)
        
        # Store in cache
        self._memory_cache[cache_key] = {
            "data": data,
            "ts": time.time()
        }
        
        return data
```

**Impacto:** Reduz latência de ~2-5s para <100ms em resultados já buscados.

---

### 1.2 Parallel Fetching com Early Termination

```python
# Substituir busca sequencial por并发查询
async def search_nearby_stores_optimized(
    latitude: float,
    longitude: float,
    search_term: str,
    max_results: int = 50
):
    overpass_url = "https://overpass-api.de/api/interpreter"
    search_term_lower = search_term.lower()
    
    # Build queries concurrently
    queries = build_queries(search_term_lower, latitude, longitude)
    
    async with httpx.AsyncClient(timeout=30) as client:
        # Fire ALL queries simultaneously
        tasks = [
            client.post(overpass_url, data=q, headers={"User-Agent": "buscador-lojas"})
            for q in queries
        ]
        
        # Use asyncio.as_completed for early termination
        results = []
        async for future in asyncio.as_completed(tasks):
            response = await future
            data = response.json()
            elements = data.get("elements", [])
            results.extend(process_elements(elements))
            
            # Early termination: já tem resultados suficientes
            if len(results) >= max_results:
                # Cancel remaining requests
                for task in tasks:
                    task.cancel()
                break
        
        return deduplicate_and_sort(results, latitude, longitude, max_results)
```

**Impacto:** Reduz tempo de busca de ~8s para ~2-3s em cenário de cache miss.

---

### 1.3 Retry Inteligente com Backoff Exponencial

```python
async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0
):
    """Retry com backoff exponencial + jitter para evitar thundering herd."""
    
    for attempt in range(max_retries):
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response
            
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            if attempt == max_retries - 1:
                raise
                
            # Exponential backoff with jitter
            delay = base_delay * (2 ** attempt)
            jitter = delay * 0.1 * (hash(time.time()) % 10)
            await asyncio.sleep(delay + jitter)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limited
                await asyncio.sleep(60)  # Wait a full minute
            else:
                raise
```

---

## 2. 🧠 INTELIGÊNCIA E ADAPTABILIDADE

### 2.1 Sistema de Sugestões com Autocomplete

```python
# backend/services/suggestions.py
from collections import Counter
import re

class SuggestionEngine:
    """
    Engine que analisa histórico e gera sugestões inteligentes.
    Integra com vault.db para aprender padrões.
    """
    
    def __init__(self):
        self.common_patterns = [
            "supermercado", "farmácia", "padaria", "restaurante",
            "mecânica", "academia", "barbearia", "pet shop",
            "banco", "correios", "posto de combustível"
        ]
    
    def get_suggestions(self, partial: str, limit: int = 5) -> list[str]:
        partial = partial.lower().strip()
        
        if not partial:
            return self.common_patterns[:limit]
        
        # Combine with learned patterns from vault
        learned = self._get_learned_patterns()
        all_patterns = set(self.common_patterns + learned)
        
        # Fuzzy match
        matches = [
            p for p in all_patterns
            if p.startswith(partial) or partial in p
        ]
        
        # Sort by popularity (from vault) + alphabetical
        return sorted(matches, key=lambda x: (
            -self._get_popularity(x), x
        ))[:limit]
    
    def _get_learned_patterns(self) -> list[str]:
        """Carrega padrões aprendidos do vault."""
        # TODO: Query vault.db for successful searches
        return []
```

### 2.2 Aprendizado de Tags Vencedoras (Expansão)

```python
# Melhorar lógica de aprendizado no cep_service.py
def analyze_and_learn(self, search_term: str, results: list[dict]):
    """
    Após cada busca, analisa quais tags geraram bons resultados.
    """
    if not results:
        return
    
    search_term = search_term.lower()
    
    # Analisa tags dos resultados retornados
    tag_counts = Counter()
    for store in results:
        tags = store.get("matched_tags", {})
        for key, value in tags.items():
            tag_counts[(key, value)] += 1
    
    if tag_counts:
        # Salva a tag mais frequente para este termo
        best_tag = tag_counts.most_common(1)[0]
        save_learned_tag(search_term, best_tag[0], best_tag[1])
        
        # Salva também como "related" para buscas futuras
        for tag, count in tag_counts.most_common(5):
            save_related_tag(search_term, f"{tag[0]}={tag[1]}", count)

def save_related_tag(search_term: str, related: str, weight: int):
    """Salva tags relacionadas no vault."""
    conn = get_vault_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO learned_relations 
        (term, related_tag, weight, success_count)
        VALUES (?, ?, ?, ?)
    """, (search_term, related, weight, weight))
    conn.commit()
```

### 2.3 Sistema de Sinônimos e Variações

```python
# backend/services/synonyms.py
SYNONYM_MAP = {
    "mercado": ["supermercado", "minimercado", "empório", "quitanda"],
    "farmacia": ["farmácia", "drogaria", "medicamento"],
    "mecanica": ["mecânica", "oficina", "automecânica", "carro"],
    "lanche": ["lanchonete", "lanche", "snack", "fast food"],
    "pizza": ["pizzaria", "pizza", " pizz"],
    "academia": ["ginástica", "musculação", "fitness", "crossfit"],
    "bar": ["bar", "boteco", "pub", "balada"],
    "hotel": ["hospede", "pousada", "hostel", "resort"],
    "restaurante": ["restaurante", "resto", "comida", "jantar", "almoço"],
}

def expand_search_term(term: str) -> list[str]:
    """Expande termo de busca com sinônimos."""
    term = term.lower().strip()
    variations = [term]
    
    for key, synonyms in SYNONYM_MAP.items():
        if term in synonyms or term == key:
            variations.extend(synonyms)
            variations.append(key)
            break
    
    return list(set(variations))
```

---

## 3. 🎯 DINAMISMO E UX

### 3.1 Busca em Tempo Real (Live Search)

```python
# Adicionar debounce na GUI
class FastSearchApp(QMainWindow):
    def __init__(self):
        # ... código existente ...
        
        # Timer para debounce
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_live_search)
        
        # Conectar ao textChanged dos inputs
        self.search_input.textChanged.connect(self._on_input_changed)
    
    def _on_input_changed(self, text):
        """Debounce de 300ms para live search."""
        self._search_timer.start(300)
    
    def _do_live_search(self):
        """Executa busca após usuário parar de digitar."""
        cep = self.cep_input.text().strip()
        term = self.search_input.text().strip()
        
        if len(term) >= 3 and cep:
            self.start_search()
```

### 3.2 Resultados Progressivos (Streaming)

```python
async def search_with_streaming(self, signals, max_results=50):
    """
    Retorna resultados conforme encontrados, não espera tudo terminar.
    """
    elements_found = 0
    
    async for batch in self._stream_overpass_results():
        for element in batch:
            store = self._process_element(element)
            if store:
                signals.progress.emit(store)  # Sinal intermediário
                elements_found += 1
                
                if elements_found >= max_results:
                    return
        
        # Se já tem resultados suficientes, para
        if elements_found >= max_results:
            break

# Adicionar novo sinal ao WorkerSignals
class WorkerSignals(QObject):
    finished = pyqtSignal(list)
    progress = pyqtSignal(dict)  # Novo: resultado individual
    error = pyqtSignal(str)
```

### 3.3 Histórico e Favoritos

```python
# Adicionar aos resultados no vault.db
def save_favorite(self, store: dict, cep: str, term: str):
    """Salva um resultado como favorito."""
    conn = get_vault_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO favorites 
        (store_id, name, latitude, longitude, address, 
         website, phone, cep, search_term, saved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        store.get("id"), store.get("name"), store.get("latitude"),
        store.get("longitude"), store.get("address"),
        store.get("website"), store.get("phone"), cep, term
    ))
    conn.commit()

def get_recent_searches(self, limit=10) -> list[dict]:
    """Retorna últimas buscas do usuário."""
    conn = get_vault_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT cep, search_term, max(results_count) as count,
               max(searched_at) as last_searched
        FROM search_logs
        GROUP BY cep, search_term
        ORDER BY last_searched DESC
        LIMIT ?
    """, (limit,))
    
    return [
        {"cep": row[0], "term": row[1], "count": row[2], "last": row[3]}
        for row in cursor.fetchall()
    ]
```

### 3.4 Mapa Integrado (OpenStreetMap)

```python
# Adicionar visualização em mapa com Folium ou similar
from folium import Map as FoliumMap, Marker, Icon

def generate_map(results: list[dict], center_lat: float, center_lon: float) -> str:
    """Gera HTML de mapa com marcadores."""
    m = FoliumMap(location=[center_lat, center_lon], zoom_start=14)
    
    # Marcador do centro (CEP)
    Marker(
        [center_lat, center_lon],
        popup="Você está aqui",
        icon=Icon(color='red', icon='home')
    ).add_to(m)
    
    # Marcadores dos resultados
    for store in results:
        if store.get("latitude") and store.get("longitude"):
            Marker(
                [store["latitude"], store["longitude"]],
                popup=f"""
                    <b>{store['name']}</b><br>
                    {store.get('address', '')}<br>
                    {store.get('phone', '')}
                """,
                icon=Icon(color='green', icon='info-sign')
            ).add_to(m)
    
    return m._repr_html_()

# Na GUI, adicionar botão "Ver no Mapa"
def show_on_map(self):
    html = generate_map(self.current_results, self.center_lat, self.center_lon)
    # Abrir no navegador ou em widget QWebEngineView
    webbrowser.open(f"data:text/html;base64,{b64encode(html.encode()).decode()}")
```

---

## 4. 📊 SISTEMA DE METRICAS

### 4.1 Dashboard de Performance

```python
# backend/services/analytics.py
class SearchAnalytics:
    """Coleta métricas para análise de performance."""
    
    def __init__(self):
        self._metrics = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "avg_response_time": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }
    
    def record_search(
        self, 
        cep: str, 
        term: str, 
        duration_ms: float,
        results_count: int,
        from_cache: bool = False
    ):
        """Registra métricas de uma busca."""
        self._metrics["total_searches"] += 1
        
        if from_cache:
            self._metrics["cache_hits"] += 1
        else:
            self._metrics["cache_misses"] += 1
        
        if results_count > 0:
            self._metrics["successful_searches"] += 1
        else:
            self._metrics["failed_searches"] += 1
        
        # Running average
        n = self._metrics["total_searches"]
        current_avg = self._metrics["avg_response_time"]
        self._metrics["avg_response_time"] = (
            (current_avg * (n - 1) + duration_ms) / n
        )
    
    def get_report(self) -> str:
        """Gera relatório de métricas."""
        m = self._metrics
        cache_rate = (
            m["cache_hits"] / (m["cache_hits"] + m["cache_misses"]) * 100
            if (m["cache_hits"] + m["cache_misses"]) > 0 else 0
        )
        
        return f"""
📊 Relatório FastSearch
━━━━━━━━━━━━━━━━━━━━━
Total de buscas: {m['total_searches']}
Taxa de sucesso: {m['successful_searches'] / max(m['total_searches'], 1) * 100:.1f}%
Tempo médio: {m['avg_response_time']:.0f}ms
Cache hit rate: {cache_rate:.1f}%
"""
```

---

## 5. 🔧 IMPLEMENTAÇÃO PRIORITÁRIA

### Ordem Recomendada (Menor para Maior Impacto)

| Prioridade | Feature | Impacto | Esforço |
|------------|---------|---------|---------|
| 🔴 **Alta** | Cache Multi-Camada | ⚡⚡⚡⚡ | Baixo |
| 🔴 **Alta** | Parallel Fetching | ⚡⚡⚡ | Médio |
| 🟡 **Média** | Sinônimos | 🧠🧠 | Baixo |
| 🟡 **Média** | Autocomplete | 🧠🧠 | Médio |
| 🟡 **Média** | Retry Inteligente | ⚡⚡ | Baixo |
| 🟢 **Baixa** | Mapa Integrado | 📍📍 | Alto |
| 🟢 **Baixa** | Favoritos | ⭐ | Médio |

---

## 6. 🚀 QUICK WINS (Implementar Agora)

### 6.1 Adicionar Timeout Configurável

```python
# No cep_service.py
async def search_nearby_stores(
    latitude: float,
    longitude: float,
    search_term: str,
    timeout: float = 10.0  # Reduzir de 20s para 10s
):
    async with httpx.AsyncClient(timeout=timeout) as client:
        # ... resto do código
```

### 6.2 Limitar Resultados no Overpass

```python
# Adicionar "maxsize" na query Overpass
query = f"""
[out:json][timeout:10][maxsize:1073741824];
(
    node{tag_query}(around:5000,{latitude},{longitude});
    way{tag_query}(around:5000,{latitude},{longitude});
);
out count;  # Primeiro conta, depois busca
"""
```

### 6.3 Conexão HTTP Persistente

```python
# Reusar conexão httpx
class OverpassClient:
    """Cliente HTTP otimizado com connection pooling."""
    
    _instance = None
    _client = None
    
    @classmethod
    def get_instance(cls):
        if cls._client is None:
            cls._client = httpx.AsyncClient(
                timeout=15,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return cls._client
```

---

## 📋 Checklist de Implementação

```markdown
- [ ] Implementar MultiLayerCache
- [ ] Refatorar para Parallel Fetching
- [ ] Adicionar Retry com Backoff
- [ ] Criar SuggestionEngine
- [ ] Implementar sistema de Sinônimos
- [ ] Adicionar live search com debounce
- [ ] Implementar streaming de resultados
- [ ] Adicionar favoritos no vault
- [ ] Gerar mapa com Folium
- [ ] Criar dashboard de métricas
- [ ] Configurar Connection Pooling
- [ ] Testar performance com benchmarks
```

---

*Documento criado para ajudar Rodrigo Moraes (@CanalQb) a evolução do FastSearch.*