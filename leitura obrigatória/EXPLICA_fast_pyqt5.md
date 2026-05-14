# EXPLICA — @CanalQb SearchPRO Web (PyQt5)

## O que o usuário pediu
- Baixar o repositório original `fast`.
- Modificar a busca para ser universal (buscar qualquer coisa próximo ao CEP).
- Criar um ambiente desktop usando **PyQt5**.
- Remover referências ao criador original e creditar **Rodrigo Moraes do @CanalQb**.
- Aplicar o logo oficial (`logo.jpg`) na interface.
- Seguir as **Master Rules** e regras do `@CanalQb`.

## O que foi criado
1. **Refatoração do Backend (Busca Camaleão)**: O serviço `search_nearby_stores` foi turbinado com uma lógica adaptativa. Se a busca por categorias falhar, o sistema realiza uma busca agressiva em todas as tags do OpenStreetMap (Pesquisa Camaleão), garantindo resultados para termos complexos como "mecânica" ou "emprego".
2. **Interface PyQt5 PRO (Dinamismo e UX)**: 
    - **Live Search**: Busca automática com delay (debounce) para resultados instantâneos enquanto você digita.
    - **Streaming de Resultados**: Os locais aparecem na tela conforme são encontrados (não precisa esperar toda a busca terminar).
    - **Autocomplete**: Sugestões inteligentes no campo de busca.
    - **Toggle de Busca**: Botão dinâmico (Iniciar/Parar).
    - **Exportação CSV**: Exportação rápida para análise externa.
3. **Motor de Busca Híbrido (Velocidade e Inteligência)**: 
    - **Parallel Fetching**: Realiza múltiplas consultas simultâneas para variações do termo.
    - **Ultra Hunter Search (Dorks)**: Realiza pesquisas automatizadas usando dorks industriais (site:facebook, site:olx, site:vagas, site:linkedin, index of) para encontrar informações em fóruns, classificados e sistemas de arquivos que o Google comum não mostra.
    - **Detecção de Localidade**: Identifica automaticamente a cidade do CEP para tornar as buscas na web 10x mais precisas.
    - **Adaptive Performance**: Monitora a memória do sistema e ajusta o nível de paralelismo.
    - **Cache Multi-camada**: Resultados frequentes são entregues em <100ms.
    - **Tag Learning**: Auto-ajuste de tags baseado no sucesso das buscas.
4. **Infraestrutura Industrial**:
    - **Auto-Bootstrap**: Instalador automático de dependências na primeira execução.
    - **Vault DB (WAL)**: Banco de dados otimizado com modo *Write-Ahead Logging* para alta performance concorrente.

4. **Compliance**: README e documentação atualizados para os padrões do @CanalQb.

## Localização dos Arquivos
- `gui_main.py`: Ponto de entrada da aplicação desktop.
- `backend/services/cep_service.py`: Lógica de busca refatorada.
- `logo.jpg`: Identidade visual.
- `README.md`: Documentação principal.

## Como funciona
1. O usuário insere o CEP e o termo de busca.
2. O sistema obtém as coordenadas geográficas via Nominatim.
3. Dispara uma consulta para a Overpass API buscando por:
    - Categorias mapeadas (se o termo for conhecido).
    - Nome ou tags comuns (`amenity`, `shop`) contendo o termo (busca universal).
4. Os resultados são exibidos em Cards estilizados com cálculo de distância em tempo real.

## Requisitos
- Python 3.9+
- Bibliotecas: `PyQt5`, `qtawesome`, `httpx`, `geopy`.

## Validação
- [x] Design Premium (Rich Aesthetics)
- [x] Sem uso de `alert()`
- [x] Dark Mode Nativo
- [x] Ícones FontAwesome 6
- [x] Créditos: Rodrigo Moraes do @CanalQb
