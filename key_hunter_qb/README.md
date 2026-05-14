# 🔑 KeyHunter Pro v2.5 — Bitcoin & Multicoin Autopilot
> **CanalQb** | Motor autônomo de mineração criptográfica e validação financeira em tempo real.

---

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [Modos de Busca](#modos-de-busca)
3. [Configurações](#configurações)
4. [Arquitetura do Sistema](#arquitetura-do-sistema)
5. [Banco de Dados](#banco-de-dados)
6. [Arquivos do Projeto](#arquivos-do-projeto)
7. [Dependências](#dependências)
8. [Como Usar](#como-usar)

---

## 🎯 Visão Geral

O KeyHunter Pro é um pipeline autônomo de extração, conversão e auditoria de chaves privadas de criptomoedas. Ele varre a internet em tempo real, detecta chaves expostas e verifica automaticamente se os endereços associados possuem saldo na blockchain.

---

## 🔍 Modos de Busca

Acesse pelo menu principal ao iniciar o script:

| Opção | Modo | Descrição |
|-------|------|-----------|
| `1` | **Buscador de Chaves WIF** | Procura chaves privadas em formato WIF (Base58) |
| `2` | **Buscador de Mnemonic Seeds** | Procura frases seed de 12/24 palavras (BIP39) |
| `3` | **Buscador de Wallet Dumps** | Procura arquivos `wallet.dat` expostos |
| `4` | **Buscador de Vulnerabilidades** | Procura falhas em contratos e carteiras crypto |
| `5` | **Buscador de Blockchain** | Varre exploradores de bloco públicos |
| `6` | **Auto-Discovery** | Lê `procurarem.txt` e constrói dorks automaticamente |
| `7` | **Busca por Alvo Específico** | Pesquisa uma chave ou termo específico globalmente |
| `8` | **Busca Customizada** | Insere um termo livre para busca manual |
| `9` | **Configurações** | Painel de controle do motor |

---

## ⚙️ Configurações

Acesse pelo menu `9. Configurações`:

### 1. Threads
Quantas páginas o Hunter abre **em paralelo** por pesquisa.
- Recomendado: `2–5` para PCs; `10+` para servidores.

### 2. Limite Site (KB)
Tamanho máximo de conteúdo baixado por URL. Evita travar em dumps gigantes.
- Padrão: `1024` KB (1 MB).

### 3. Profundidade Spider
Se o Hunter deve seguir links internos das páginas encontradas.
- `0` — Analisa apenas o resultado direto da busca.
- `1` — Entra nos links internos de cada página encontrada.

### 4. Modo Verbose
- `LIGADO` — Exibe todos os detalhes técnicos no console (scanning, erros, info).
- `DESLIGADO` — Console limpo; apenas **HITS** aparecem.

### 5. Loop Infinito
- `LIGADO` — O Hunter nunca para. Ao terminar a fila de dorks, reinicia do zero. Ideal para vigilância 24/7.
- `DESLIGADO` — Encerra ao processar todas as dorks.

### 6. Salto de Busca (Offset / Tamanho de Bloco)
Define o **tamanho da janela de resultados** por sessão de busca. Sem valor máximo.

**Como funciona:**
- Você define um valor, ex: `1000`.
- Na **1ª execução**: o Hunter busca os resultados de `0` até `1000`.
- Na **2ª execução** (Loop Infinito ou próxima rodada): busca de `1001` até `2000`.
- Na **3ª execução**: de `2001` até `3000`, e assim por diante.

O sistema de **Blocos Inteligentes** armazena o ponto exato no banco de dados, garantindo cobertura contínua sem repetir resultados já minerados.

**Exemplos práticos:**
- `0` — Sem bloco; sempre recomeça do primeiro resultado.
- `100` — Janelas pequenas de 100 resultados por sessão.
- `1000` — Janelas grandes, ideal para sites extensos como Bitcointalk.
- `5000` — Blocos muito profundos para cobertura massiva.


---

## 🏗️ Arquitetura do Sistema

### Motor de Busca de 3 Vias (Parallel Query)
O Hunter processa **3 dorks simultaneamente** em vez de uma por vez. Isso triplica a velocidade de cobertura em sites extensos como Bitcointalk e GitHub.

### Rotação Inteligente de Blocos
O sistema salva no banco de dados até onde cada dork foi pesquisada (`last_offset`). Na próxima execução, ele retoma do ponto seguinte, **nunca repetindo a mesma faixa de resultados**. Isso garante cobertura progressiva e sem desperdício de consultas.

### Detector Universal de Chaves
- **WIF direto**: Detecta prefixos `5`, `K`, `L`, `9`, `c` (Bitcoin Main/Testnet).
- **Hexadecimal**: Detecta strings de 64 caracteres hexadecimais em qualquer parte do texto ou URL e converte automaticamente para WIF.
- **Multicoin**: Suporte a Litecoin (`T`/`6u`), Dogecoin (`Q`/`6J`), Dash e forks de Bitcoin (BCH, BSV, BTG).

### Geração de Endereços (4 Tipos)
Para cada chave encontrada, o sistema gera automaticamente:
| Tipo | Exemplo |
|------|---------|
| Legacy (P2PKH) | `1...` |
| P2SH (SegWit aninhado) | `3...` |
| Native SegWit (P2WPKH) | `bc1q...` |
| Taproot (P2TR) | `bc1p...` |

### Geração Dupla WIF (C e U)
Cada chave privada (hex) gera **dois registros independentes** no banco:
- **WIF Comprimido** (`K` / `L`) — endereços derivados com chave pública comprimida.
- **WIF Não-Comprimido** (`5`) — endereços derivados com chave pública não-comprimida.
Ambos são verificados na blockchain separadamente.

---

## 🗄️ Banco de Dados

O sistema usa **SQLite** com **Modo WAL (Write-Ahead Logging)** para suportar leituras e escritas simultâneas sem travamento.

**Arquivo**: `hunter_vault.db`

### Tabela `audit`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `wif` | TEXT (PK) | Chave privada — **única**, duplicatas ignoradas automaticamente |
| `addr_legacy` | TEXT | Endereço Bitcoin Legacy (1...) |
| `addr_p2sh` | TEXT | Endereço P2SH (3...) |
| `addr_bech32` | TEXT | Endereço Native SegWit (bc1q...) |
| `addr_taproot` | TEXT | Endereço Taproot (bc1p...) |
| `balance` | TEXT | `Pendente` ou `Saldo: X.XXXXXXXX BTC` |
| `timestamp` | DATETIME | Data/hora do registro |

### Tabela `search_blocks`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `dork` | TEXT (PK) | Termo de busca |
| `last_offset` | INTEGER | Último ponto pesquisado (rotação de blocos) |
| `timestamp` | DATETIME | Última atualização |

### Validador de Balanço (Thread em Segundo Plano)
- Roda como `daemon thread` — inicia junto com o script e encerra automaticamente.
- Busca registros com `balance = 'Pendente'` em lotes de 10.
- Consulta a API `blockchain.info` para cada `addr_legacy`.
- Atualiza o registro imediatamente após a resposta.
- Respeita limites de API com espera automática em caso de erro `429`.
- **Alerta de Fortuna**: Se `balance > 0`, dispara log `[ALERT]` destacado.

---

## 📁 Arquivos do Projeto

| Arquivo | Descrição |
|---------|-----------|
| `key_hunter_pro.py` | Script principal |
| `hunter_vault.db` | Banco de dados SQLite (WIFs + saldos + histórico de busca) |
| `procurarem.txt` | Lista de sites-alvo para Auto-Discovery |
| `naoprocurarem.txt` | Domínios bloqueados (nunca serão escaneados) |
| `keyhunter_config.json` | Configurações salvas (threads, offset, loop, etc.) |
| `activity_log.txt` | Log técnico completo de todas as operações |
| `encontrado_[Modo].txt` | Log de hits por modo de busca |

---

## 📦 Dependências

Instaladas automaticamente na primeira execução:

```
rich, requests, ddgs, base58, beautifulsoup4, mnemonic, bip32utils, psutil, cloudscraper, lxml
```

**Python**: 3.10+ recomendado (testado em 3.14).

---

## ▶️ Como Usar

```powershell
python key_hunter_pro.py
```

### Encerrar o Script
- `Ctrl+C` — Encerramento instantâneo. Todas as threads são eliminadas imediatamente via `os._exit()`.
- `Ctrl+Break` — Mesma ação no Windows.

### Monitorar o Banco de Dados
Use qualquer visualizador SQLite (ex: [DB Browser for SQLite](https://sqlitebrowser.org/)) para abrir `hunter_vault.db` e acompanhar os resultados em tempo real.

---

> **Aviso Legal**: Esta ferramenta foi desenvolvida para fins de pesquisa em segurança e auditoria de chaves expostas publicamente. O uso é de total responsabilidade do operador.
