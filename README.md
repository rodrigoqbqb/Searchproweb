# CanalQb SearchPRO Web 🚀

CanalQb SearchPRO Web é um motor de busca híbrido de autoaprendizado. Ele integra dados do OpenStreetMap (OSM) com inteligência extraída da web (Web Hunter) para fornecer resultados precisos de pontos de interesse (POI) baseados no CEP do usuário. O grande diferencial do sistema é sua capacidade de **aprender novas etiquetas autonomamente** quando encontra termos desconhecidos, construindo uma base de conhecimento local, e seu sistema avançado de Fallback que garante precisão na localização.

---

## 🗺️ O Conceito do CEP e Localização (Master Fallback)

O sistema de busca funciona fundamentalmente a partir do CEP do usuário. O processo de geolocalização funciona assim:
1. **Consulta Primária (ViaCEP & Nominatim):** O sistema converte o CEP num endereço (Rua, Cidade, Estado) e o Nominatim traduz esse endereço em Coordenadas Geográficas (Latitude e Longitude exatas).
2. **Master CEP Fallback Inteligente:** Caso um CEP seja inválido, recém-criado ou muito específico (sem mapeamento GPS na base global), a inteligência recua automaticamente. O sistema substituirá os últimos 3 dígitos por `000` (buscando a central do bairro/região) e, se falhar, substituirá por `0000` (buscando o centro geográfico da cidade inteira). Isso garante que o motor de busca sempre tenha um raio geográfico para iniciar as medições de distância.

## 🔍 Como é realizada a Pesquisa do Termo e Criação de Categorias?

A criação e busca de categorias são o coração da aplicação. O aplicativo não usa uma lista "dura" de categorias. Em vez disso, ele constrói conhecimento dinamicamente através do funil híbrido de autoaprendizado executado no `SearchWorker`:

1. **Consulta Cérebro (SQLite `etiquetas`):** Ao buscar por `hamburgueria`, o aplicativo consulta primeiro sua tabela `etiquetas` (`SELECT tag_key, tag_value FROM etiquetas WHERE termo = 'hamburgueria'`). Se existir, ele usa as tags do OSM exatas (ex: `amenity=fast_food`).
2. **Busca por Expressão (Regex):** Se o banco local falhar, ele faz uma varredura nas redondezas procurando estabelecimentos cujo nome inclua o termo em português ou traduzido pelo módulo interno para inglês (ex: `name~"hamburgueria|hamburger"`).
3. **Wide-Radius Discovery (Criação da Categoria):** Se nada for achado num raio de 5km, o `tag_discovery.py` entra no "Modo de Caça". Ele abre um raio global de 500km via Overpass para achar QUALQUER lugar no país que tenha aquele nome. Quando acha, ele extrai a tag técnica do OSM (ex: `amenity=restaurant`) e **insere essa nova categoria no banco de dados**, validando e aprendendo para que a próxima pesquisa por aquele termo seja ultrarrápida (Cache Persistente).
4. **Camada Web Hunter (Bing & DuckDuckGo):** Paralelamente ao OSM, o aplicativo cruza os resultados com a Web. Caso o OpenStreetMap não possua o lugar, o Web Hunter raspa o HTML puro de motores de busca, contornando bloqueios anti-bot e extraindo a URL oficial encapsulada (Base64 Decode) do Bing, devolvendo resultados extras que não existiam no mapa.

## 🪪 Como funciona cada item do Card (ResultCard)?

Cada estabelecimento encontrado é renderizado numa caixa inteligente e responsiva:
- **Título & Endereço (WordWrap):** Se adaptam verticalmente e de forma justificada (Word Wrap) para nunca cortar e não forçar o aparecimento de barras de rolagem.
- **Distância (`📍 X.XX km`):** O cálculo Haversine mede a quilometragem linear perfeita do seu CEP até a porta da loja. Resultados Web Hunter não têm coordenadas, logo ganham `9999.00 km` e vão inteligentemente pro fim da fila.
- **Botão Amarelo (Fonte Web Hunter):** Ao invés de uma marca d'água estática, se a origem foi de um buscador web, este botão guarda o **Link Oficial da Pesquisa**. Clicar nele abre no navegador exatamente a query do Bing/DuckDuckGo que achou aquele lugar.
- **Botões GPS (Maps e Waze):**
  - Se o local veio do OSM (possuindo Latitude e Longitude), clicar nestes botões abrirá os mapas cravados no **alfinete cirúrgico** (coordenadas brutas).
  - Se o local veio pela Web Hunter (sem GPS), os botões enviarão o *Nome e Endereço* como texto via URL, forçando o Waze e Google Maps a procurarem e abrirem o estabelecimento localmente para o cliente.
- **Botão Verde (Website):** Caso o card possua uma URL (seja via OSM ou links decodificados em Base64 através das proteções do Bing Tracker), este botão se responsabiliza por abrir a página oficial/destino final do negócio.

## 📊 O Botão de Exportar (CSV)

No final de cada busca, um botão com ícone amarelo 📄 fica disponível para salvar todos os dados numa planilha.
- **O que ele exporta:** A planilha gerada obedece à rigorosa formatação de dados divididos por Ponto e Vírgula (`;`), garantindo abertura perfeita no Excel/Google Sheets. As colunas fixas estruturadas são:
  - `LOCALIDADE`: Nome do estabelecimento.
  - `ENDERECO`: Logradouro completo.
  - `DISTANCIA_KM`: Raio a partir do CEP (em string com casa decimal 0.00).
  - `TELEFONE`: Número identificado.
  - `WEBSITE`: O destino oficial da loja na internet.
  - `MAPS`: Um Link "Smart" já programado para jogar o cliente direto na Rota do Google Maps.
  - `WAZE`: Um Link "Smart" já programado para rotear diretamente no Waze do Celular/Web.
  - `WEB_HUNTER_SOURCE`: O rastro de qual URL de pesquisa originou o achado.
  - `FONTE`: Se a extração ocorreu via 'OSM', 'Web Hunter (Bing)', ou 'Web Hunter (DuckDuckGo)'.

---

## 🗄️ Estrutura do Banco de Dados (`vault.db`)

O banco de dados SQLite opera nativamente em `PRAGMA journal_mode=WAL` (Write-Ahead Logging), permitindo Leituras e Escritas Simultâneas — uma tecnologia de banco servidor aplicada localmente, para não gerar erros de travamento concorrente na Thread gráfica e na Thread Web. 

A interação (inserção/consulta) ocorre via módulo `backend/core/vault.py`. As tabelas estruturadas são:

1. **`etiquetas` (Cérebro Principal de Autoaprendizado):**
   - `termo` (TEXT, PK): O nome genérico buscado pelo usuário (Ex: "padaria").
   - `tag_key` (TEXT): A chave técnica da tabela oficial do OSM (Ex: "shop").
   - `tag_value` (TEXT): O valor da chave técnica (Ex: "bakery").
   - `fonte` (TEXT): O serviço responsável por aprender a tag (Ex: "Active Learning").
   - `timestamp` (DATETIME): Data e hora do aprendizado.
   - *Comportamento:* Quando a varredura ampla descobre as tags (Wide Radius), o `vault.py` realiza um `INSERT OR REPLACE INTO etiquetas`. 

2. **`search_history` (Log de Metrificação):**
   - `id` (INTEGER, PK): Índice autoincremental.
   - `cep` (TEXT): O número geográfico pesquisado.
   - `term` (TEXT): A palavra buscada.
   - `results_count` (INTEGER): Quantos cartões foram achados e gerados naquela busca.
   - `timestamp` (DATETIME): Data exata do término da busca.

3. **`translations` (Tradução Estática de Termos):**
   - `portuguese` (TEXT, PK): Palavra base (Ex: "mercado").
   - `english` (TEXT): Tradução técnica (Ex: "market"), essencial para facilitar a procura de Nodes na rede global OpenStreetMap.
   - `timestamp` (DATETIME): Registro da conversão.

4. **`learned_categories` (Tabela Legado):**
   - `term`, `tag_key`, `tag_value`, `confidence`: Base antiga do sistema de heurística que mapeava inferências probabilísticas de confiabilidade na extração.

---

## 🛠️ Tecnologias e Soluções Arquiteturais Aplicadas

O sistema é construído inteiramente em **Python 3** utilizando uma abordagem assíncrona orientada a eventos para garantir máxima performance de I/O, além de interfaces avançadas e persistência resiliente.

### Inteligência e Raspagem de Dados
- **Motor Híbrido OSM:** Integração pesada com a API do **Overpass / OpenStreetMap** e **Nominatim / ViaCEP** para varreduras de mapas vetoriais usando queries avançadas em formato JSON/Overpass QL.
- **Scraping Anti-Bloqueio (Web Hunter):** Usa **`httpx`** (Assíncrono) para requisições em alta velocidade no Bing e DuckDuckGo, somado ao uso de rotação de **User-Agents** via módulo `random`.
- **Decodificador Regex e HTML:** Em vez de depender de seletores CSS frágeis (BeautifulSoup), o motor usa a biblioteca interna `re` (Expressões Regulares) para rastrear nós de DOM profundos e o módulo `html` (`html.unescape`) para reconstruir entidades web corrompidas (ex: `Gr&#225;tis` -> `Grátis`).
- **Base64 Payload Decoder:** Algoritmo de segurança implementado com a biblioteca `base64` para burlar os protetores de tracking de cliques da Microsoft (Bing `ck/a?!`), extraindo a URL oficial encapsulada dentro da querystring.
- **Smart Distance Algorithm:** Utiliza trigonometria e cálculo geodésico (Fórmula de Haversine) implementado manualmente em Python puro (módulo `math`) para descobrir distâncias esféricas perfeitas no globo terrestre.

### Concorrência e Interface Gráfica
- **PyQt5 & QThread:** Interface gráfica moderna e desktop native. A lógica pesada da internet (HTTPX) roda em um thread separado e devolve os dados em formato *Stream* contínuo para o Thread Principal via `pyqtSignal`. Isso garante que a UI com animações e _Hover effects_ (CSS embutido) nunca "congele".
- **Dynamic Layout Constraints:** Uso profundo de `QHBoxLayout`, `QVBoxLayout`, `QScrollArea`, políticas e margens (`QSizePolicy`) que permitem renderização do Word-Wrap, garantindo que a tela sempre caiba sem _scrollbars_ horizontais.
- **Event Loop Assíncrono:** Instanciação modular do `asyncio.new_event_loop()` para envelopar código Thread-Blocking dentro das _Workers_ síncronas do PyQt5 de modo nativo.

### Armazenamento e Performance
- **SQLite3 (Modo WAL):** O banco local (`vault.db`) é modificado com `PRAGMA journal_mode=WAL` (Write-Ahead Logging), permitindo Leituras e Escritas Simultâneas — uma tecnologia de banco servidor aplicada em um banco local, para não gerar erros de travamento durante o *Active Learning*.
- **Memory Cache Dinâmico:** Uma classe de cache (`cache.py`) armazena os CEPs e buscas já processadas dentro de um dicionário Python local, cortando tempos de espera de requisições web repetitivas a Zero.
- **Formatação de I/O Segura:** Exportação de planilhas formatadas na biblioteca `csv` nativa, forçando o *encoding* `utf-8-sig` (Byte Order Mark), resolvendo bugs de acentuação para leitura imediata em qualquer versão do Microsoft Excel.
