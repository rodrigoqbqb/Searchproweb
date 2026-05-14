# CanalQb SearchPRO Web 🚀

CanalQb SearchPRO Web é um motor de busca híbrido de autoaprendizado. Ele integra dados do OpenStreetMap (OSM) com inteligência extraída da web (Web Hunter) para fornecer resultados precisos de pontos de interesse (POI) baseados no CEP do usuário. O grande diferencial do sistema é sua capacidade de **aprender novas etiquetas autonomamente** quando encontra termos desconhecidos, construindo uma base de conhecimento local.

---

## 📂 Estrutura do Projeto e Arquitetura

O projeto é dividido em uma interface gráfica moderna (PyQt5) e um back-end de serviços assíncronos (Asyncio + Httpx).

### Raiz
- **`gui_main.py`**
  - **Função:** Ponto de entrada do sistema. Gerencia a Interface Gráfica (GUI) construída em PyQt5.
  - **Lógica Principal:**
    - Possui um input dinâmico de autocompletar que lê do banco de termos conhecidos.
    - Utiliza **QThread (Worker)** para evitar que a interface congele durante a busca. Os resultados são emitidos via sinais (`pyqtSignal`) em formato de _stream_ (aparecem um a um).
    - **Cálculo de Distância:** Implementa a fórmula de Haversine para calcular a distância em linha reta do CEP pesquisado até cada estabelecimento.
    - **Ordenação:** Ordena a lista final por distância e envia os resultados "Sem Coordenada" (Web Hunter) para o final da lista (9999km).

### `backend/core/` (Núcleo de Dados)
- **`vault.py`**
  - **Função:** Gerenciador de Banco de Dados SQLite (`vault.db`).
  - **Lógica:** Opera em **WAL Mode** (`PRAGMA journal_mode=WAL`), o que permite leituras e escritas assíncronas concorrentes sem corromper o banco.
  - **Tabela Principal (`etiquetas`):** Armazena o aprendizado ativo da inteligência. Exemplo: `termo: "mexicano" -> key: "amenity", value: "restaurant", fonte: "Active Learning"`.

- **`cache.py`**
  - **Função:** Sistema de Cache em memória (Dicionário assíncrono).
  - **Lógica:** Evita requisições repetidas para APIs externas num curto período. Por exemplo, se o usuário pesquisar o mesmo CEP duas vezes, o cache devolve as coordenadas do Nominatim sem bater na API novamente.

### `backend/services/` (Motores de Inteligência)

- **`cep_service.py`** (Motor de Busca Híbrido)
  - **Função:** Orquestra a busca completa por coordenadas e estabelecimentos.
  - **Estratégia de Fallback (Camadas):**
    1. **Banco de Dados:** Tenta usar tags (`key=value`) previamente aprendidas pelo `tag_discovery.py`.
    2. **Busca por Nome (Regex):** Se as tags falharem, usa Regex (ex: `name~"mexicano|mexican"`) para achar locais no raio de 5km no OSM.
    3. **Aprendizado (Hunt):** Se não achar nada, chama o `tag_discovery.py` para caçar novas tags por até 2 minutos.
    4. **Web Hunter (Paralelo):** Paralelamente, faz scraping no Bing/DuckDuckGo para suprir locais não cadastrados no OSM.
  - **Principais Variáveis:** `SEARCH_RADIUS` (5000 metros), `MAX_HUNT_TIME` (tempo limite do loop de descoberta).

- **`tag_discovery.py`** (Cérebro de Autoaprendizado)
  - **Função:** Descobre quais tags do OpenStreetMap (ex: `cuisine=mexican`, `amenity=fast_food`) correspondem a um termo digitado pelo usuário.
  - **Lógica de "Wide Radius":** Se um termo ("mexicano") retorna `0` resultados locais, este script aciona o OSM via Overpass em um **raio de 500km**. Ele procura por um estabelecimento que tenha o nome "mexicano" neste estado/país, extrai as tags técnicas (`amenity`, `shop`, etc.) dele e salva no banco de dados para ser usado na cidade do usuário.

- **`web_service.py`** (Web Hunter)
  - **Função:** Scraping Híbrido em Bing e DuckDuckGo (HTML).
  - **Lógica:** 
    - Foca em varrer resultados de buscas como `"mexicano" "09111780"`.
    - Utiliza decodificação robusta (`html.unescape`) para corrigir acentuação (ex: `Gr&#225;tis` vira `Grátis`).
    - Usa Regex complexo (`re.findall`) ao invés de classes CSS porque motores de busca mudam de estrutura de CSS frequentemente.
    - Extrai telefone via regex padrão de (DD) XXXX-XXXX.

- **`translator_service.py`**
  - **Função:** Como o OpenStreetMap utiliza tags em inglês, este serviço traduz o termo do usuário (ex: "padaria" -> "bakery") para otimizar as queries regex e facilitar o Discovery num ambiente globalizado.

- **`category.py` e `synonyms.py`**
  - **Função:** Bases de dicionários estáticos. Atualmente servem primariamente para alimentar a lógica do auto-completar da Interface Gráfica, já que a descoberta foi delegada integralmente ao banco de dados pelo Active Learning.

---

## 🛠️ Tecnologias e API Utilizadas

1. **Overpass API (`overpass-api.de`):** Banco de dados global e comunitário de mapas. Utilizado para buscar `nodes`, `ways` e `relations`.
2. **Nominatim / ViaCEP:** Utilizado para converter o número do CEP em Coordenadas Geográficas (Latitude e Longitude) que o Overpass possa entender (Radius Search).
3. **Bing / DuckDuckGo:** Interfaces de scraping que formam a camada "Web Hunter", garantindo zero resultado vazio.
4. **PyQt5:** Framewok robusto escolhido para renderização C++ visual do aplicativo, garantindo fluidez via Signals & Slots.
