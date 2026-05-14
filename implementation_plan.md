# Plano de Implementação - @CanalQb SearchPRO Web (Refatoração e PyQt5)

## 🎯 Objetivo
Transformar o buscador de lojas em uma ferramenta universal de busca local (@CanalQb SearchPRO Web) com interface desktop (PyQt5), permitindo buscar qualquer termo próximo a um CEP informado. O projeto será creditado a **Rodrigo Moraes do @CanalQb** e utilizará a identidade visual oficial.

## 🛠️ Alterações Técnicas

### 1. Backend (Refatoração de Busca)
- **Arquivo**: `backend/services/cep_service.py`
- **Mudança**: Modificar `search_nearby_stores` para aceitar um termo de busca genérico. 
- **Lógica**: 
    - Se o termo estiver no `CATEGORY_MAP`, usa a chave/valor pré-definida.
    - Se não estiver, realiza uma busca mais ampla no Overpass API usando `["name"~"termo", i]` ou tentando chaves comuns (`amenity`, `shop`, `office`, `leisure`).

### 2. Interface Desktop (PyQt5)
- **Novo Arquivo**: `gui_main.py`
- **Branding**: 
    - Título: `@CanalQb SearchPRO Web`
    - Criador: `Rodrigo Moraes do @CanalQb`
    - Logo: Uso do arquivo `logo.jpg` na interface e como ícone da janela.
- **Estética**: Design Premium (Rich Aesthetics) seguindo o CanalQb.
    - Dark mode por padrão (com toggle opcional).
    - Cores: Primária `#28a745`, Alerta `#d32f2f`.
    - Ícones: FontAwesome via `qtawesome`.
    - Componentes: Input de CEP, Input de busca, Botão de Pesquisa, Lista de resultados em Cards.
    - Micro-animações: Transições suaves e hover effects.

### 3. Integração
- Criar uma classe controladora para fazer a ponte entre a UI e os serviços assíncronos do backend.
- Remover a dependência de `FastAPI` (uvicorn) para execução local, chamando as funções diretamente.

## 📋 Checklist de Tarefas
- [ ] Criar `implementation_plan.md` (Este arquivo)
- [ ] Criar `task.md` para acompanhamento de progresso
- [ ] Refatorar `backend/services/cep_service.py` para busca genérica
- [ ] Instalar dependências necessárias (`PyQt5`, `httpx`, `qtawesome`)
- [ ] Desenvolver `gui_main.py` com design premium
- [ ] Implementar lógica de busca assíncrona na GUI
- [ ] Validar conformidade com as Master Rules (Acessibilidade, Performance, Design)
- [ ] Criar documentação em `leitura obrigatória/EXPLICA_fast_pyqt5.md`

## ⚖️ Compliance
- Garantir que não haja `alert()`, usando diálogos customizados ou toasts.
- Seguir padrões de nomenclatura do projeto.
- Manter o código limpo e modular.
