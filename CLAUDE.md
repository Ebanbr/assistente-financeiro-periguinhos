# CLAUDE.md — Assistente Financeiro da Família Periguinhos 🐧

> Doc de contexto do projeto. Carregado automaticamente em toda sessão.
> Objetivo: a próxima conversa entender o projeto sem re-explorar o código.
> **Responder SEMPRE em português (pt-BR)** — inclusive resumos finais.

---

## 1. O que é

App **Streamlit multi-página** de finanças pessoais da família (Bruno/`bpchaves@gmail.com` e Pri).
Dashboard "Arctic" escuro/claro, importa fatura do C6 e sincroniza com o Notion.

- **Repo:** `github.com/Ebanbr/assistente-financeiro-periguinhos` (remote `origin`, **HTTPS**, conta Ebanbr).
- **Deploy:** Streamlit Cloud (push na `main` → deploy automático).
- **Backend de dados:** **Google Sheets** (via `gspread` + `google.oauth2.service_account`, scope só `spreadsheets`). Os nomes `*.parquet` em `config.py` são apenas **chaves de tabela** (mapeadas em `utils._resolve_tabela`), NÃO arquivos locais no deploy.
- **Pasta local:** `C:\Users\bpcha\Documents\assistentefinanceirofamilia`.

---

## 2. Como rodar / testar

```bash
# App local
streamlit run app.py

# Testes (devem passar 100%)
python -m pytest -q
```

- `requirements.txt` é **unpinned** de propósito. **NÃO fixar versões com `==`** — pins quebraram o deploy do Streamlit Cloud (sem wheel compatível). Lição aprendida.
- Testes: `tests/test_core.py`, `tests/test_expense_defaults.py`, `tests/test_ui_theme.py`.

---

## 3. Arquitetura

### Módulos da raiz
| Arquivo | Papel |
|---|---|
| `app.py` | Home / dashboard "Arctic" (KPIs, gráficos, campo de categorização, tile "Fatura C6 Bru"). |
| `config.py` | Constantes: caminhos, `MESES_PT`, categorias, colunas das tabelas, `MAPEAMENTOS_PADRAO` (regras palavra→categoria). |
| `utils.py` | **Núcleo.** Acesso ao Google Sheets, parsing de datas, guards de gravação, cache, helpers (`esc`, `formatar_moeda`, `gerar_id`). |
| `auth.py` | Login (`exigir_login`): 5 tentativas + 300s de bloqueio, `hmac.compare_digest`, sessão expira em 12h. |
| `fatura_projection.py` | Funções puras: parse de parcela (`3/10`), projeção de parcelas futuras, ciclo/competência de fatura (dia de fechamento), semana do ciclo, máscara de crédito por cartão. |
| `ui_theme.py` | Tema Escuro/Claro (`aplicar_tema`), barra de navegação no topo, `paleta_graficos(tema)`, `estilizar_figura`. |
| `expense_defaults.py` | Lembra categoria por estabelecimento + crédito como padrão do gasto semanal. |
| `notion_sync.py` | Sincroniza lançamentos direto da API do Notion. |
| `activity_log.py` | Log de atividade. |
| `style.css` / `style-light.css` | Skin do tema escuro / complemento do claro. |

### Páginas (`pages/`)
1. `1_📆_Gastos_Semanais.py` — gasto da semana + fatura estimada do mês + parcelas comprometidas + **editor da semana atual** (inline) + **histórico de semanas editável** (via `aplicar_edicoes_semanais`). São dois editores com propósitos diferentes (atual vs histórico), não duplicação.
2. `2_🔎_Categorias.py` — explorador: ranking de categorias, drill-down (evolução mensal, estabelecimentos, tabela completa). Exclui `fonte == "Semanal"` do macro.
3. `3_🌴_Projeto_Ferias.py` — meta de viagem.
4. `4_👴👵_Aposentadoria.py` — projeção de futuro.
5. `5_⚙️_Configuracoes.py` — import C6 (zip AES), sync Notion, mapeamentos/regras.

### Tabelas no Google Sheets
`despesas`, `receitas`, `cartoes`, `lancamentos`, `metas`, `mapeamentos` + (adicionadas pelo CODEX) `faturas_base`, `fechamentos_fatura`, `limites_semanais`.
Colunas canônicas em `config.py` (`COLUNAS_DESPESAS`, etc.). `fonte` ∈ {`Manual`, `Notion`, `C6 Bank`, `Semanal`}.

---

## 4. Convenções inegociáveis

- **Datas SEMPRE ISO `YYYY-MM-DD`** no armazenamento. Parser único: `utils._parse_data_robusta` (ISO não-ambíguo + BR dayfirst). Nunca re-parsear com `dayfirst` inconsistente. (bug clássico: `2026/06/05` virava maio → regex trata slash como ISO.)
- **Guards de gravação (não remover):**
  - `_ler_gsheet` **levanta** em falha de leitura (não devolve vazio) — evita sobrescrever a base com vazio.
  - `salvar_parquet(tabela, df, permitir_vazio=False) -> bool`: checa `_gravacao_bloqueada`; **sempre checar o retorno** e só então `invalidar_cache` + mensagem de sucesso. Passar `permitir_vazio=True` só quando esvaziar é intencional.
- **Import C6:** detecta o mês pelo **nome do arquivo** (não pela data da compra); idempotente (remove C6 Bank + reembolsos antes de reinserir); captura `parcela`/`data_compra`.
- **XSS/layout:** todo texto vindo de dados passa por `esc()` (`html.escape`) antes de ir pra HTML.
- **Cache:** `st.cache_data(ttl=300)`; invalidar com `invalidar_cache(tabela)` após gravar.

---

## 5. 🔒 Segurança (NUNCA commitar)

- `.streamlit/secrets.toml` é **gitignored** — senhas de login, token do Notion e senha do zip da fatura C6 vivem **só** aí. **Nunca** escrever esses valores em código, em doc (incl. este arquivo) ou no chat.
- `data/`, `*.parquet`, `*.csv`, `backups_notion_migracao/` também gitignored (contêm dados financeiros).

---

## 6. Estado atual (2026-10-06)

- `main` == `origin/main`, árvore limpa. Último commit: `fdc5f1b` (hardening pós-revisão CODEX + limpeza do repo).
- CODEX adicionou ~15 commits (projeção de fatura, tema claro/escuro, gastos semanais expandidos). **Tudo compila, testes passam, guards intactos.**
- Correções recentes minhas: checagem do retorno de `salvar_parquet` no editor da semana; `.gitignore` dos artefatos de preview/teste.
- **Encerramento manual da fatura** (pág. 1): botão "🔒 Encerrar fatura" grava `encerrada_em` (ISO) em `fechamentos_fatura` no registro do mês seguinte. A fatura fica em aberto até o Bruno encerrar; ao encerrar, a semana é recortada (`janela_semana`) e zera a partir do dia seguinte. Sem nenhum encerramento manual, vale a regra automática do dia 4. Funções puras: `faturas_encerradas`, `fatura_aberta`, `janela_semana`.
- **Regra do encerramento (Bruno):** a data de encerramento divide tudo. Até ela = passado (aba Faturas fechadas); depois dela = Semana atual + Histórico + conta para a fatura seguinte. Registros antigos de `fechamentos_fatura` (só `dia`, sem `encerrada_em`) também valem como encerramento. Fatura encerrada e não importada aparece na aba de fechadas com os lançamentos manuais no crédito (`lancamentos_semanais_fatura`) até ser importada.
- **Pág. 1 em abas:** "📆 Semana atual" (lançamentos manuais `fonte=Semanal` + Histórico de semanas embaixo) e "🧾 Faturas fechadas" (passado = faturas importadas do C6, agrupadas em semanas seg–dom pela data da compra; `semanas_fatura_importada`). Parcelas antigas/compras atrasadas ficam num bloco à parte; semanas + bloco = total da fatura (validado ao centavo em 05/2025–09/2026).
- **Fechamento real do C6 NÃO é dia 4:** pelos dados importados, a última compra de cada fatura cai no dia 28–2. A aba de faturas fechadas lê o ciclo da própria fatura (`ciclo_fatura_importada`). A data da compra das importações antigas só existe em `observacao` ("Compra em dd/mm/aaaa"); o importador novo grava `data_compra` (também dd/mm/aaaa).

### Pendências / decisões do Bruno (NÃO mexer sem confirmar)
1. **Sidebar colapsada por padrão** + nav no topo (mudança de UX do CODEX) — confirmar se fica.
2. **Projeção de parcelas só popula após RE-IMPORTAR as faturas** pelo app (dados antigos, importados por script, não têm colunas de parcela). Não é bug.
3. Validar contraste do **tema Claro**.

### Regra de trabalho (feedback do Bruno)
- **Não recategorizar em massa por conta própria.** Já houve "cancela" por overreach (mover restaurantes/criar 241 regras sem pedir). Categorias são decisão do Bruno — ele dirige, eu executo o que for pedido.

---

## 7. Git

- `origin` é **HTTPS** (não voltar pra SSH). `git fetch` antes de `push`.
- Commits terminam com:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
