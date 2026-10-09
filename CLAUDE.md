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

## 6. Estado atual (2026-10-09)

- `main` == `origin/main`, árvore limpa, **43 testes passando**. Último commit: `eb466a3` (dashboard: gráficos legíveis + cor por categoria). Antes: `382acd9` (sync Notion), `19d7468` (encerramento de fatura + aba Faturas fechadas).
- Fatura **10/2026 do C6 BRU já importada** (07/10). Sync do Notion rodou com sucesso no GitHub (1.200 registros → 888 despesas + 285 receitas).
- CODEX adicionou ~15 commits antes (projeção de fatura, tema claro/escuro, gastos semanais expandidos). Guards intactos.
- **Dashboard (`app.py`):** eixos com `automargin` + valores curtos (`ui_theme.valor_curto`/`eixo_reais`, "R$ 20 mil"); Fluxo mensal vai da 1ª fatura C6 importada até o mês atual (meses futuros agendados no Notion ficam fora, com aviso); linhas retas, sem preenchimento. "Onde foi o dinheiro": **uma cor por categoria** (`ui_theme.CATEGORICAS`, paleta validada p/ daltonismo nos 2 temas; slot = ranking de TODO o histórico, não muda com o filtro; fora do top 8 = cinza). Bruno reprovou tudo-vermelho — não voltar para cor única.
- **Encerramento manual da fatura** (pág. 1): botão "🔒 Encerrar fatura" grava `encerrada_em` (ISO) em `fechamentos_fatura` no registro do mês seguinte. A fatura fica em aberto até o Bruno encerrar; ao encerrar, a semana é recortada (`janela_semana`) e zera a partir do dia seguinte. Sem nenhum encerramento manual, vale a regra automática do dia 4. Funções puras: `faturas_encerradas`, `fatura_aberta`, `janela_semana`.
- **Regra do encerramento (Bruno):** a data de encerramento divide tudo. Até ela = passado (aba Faturas fechadas); depois dela = Semana atual + Histórico + conta para a fatura seguinte. Registros antigos de `fechamentos_fatura` (só `dia`, sem `encerrada_em`) também valem como encerramento. Fatura encerrada e não importada aparece na aba de fechadas com os lançamentos manuais no crédito (`lancamentos_semanais_fatura`) até ser importada.
- **Pág. 1 em abas:** "📆 Semana atual" (lançamentos manuais `fonte=Semanal` + Histórico de semanas embaixo) e "🧾 Faturas fechadas" (passado = faturas importadas do C6, agrupadas em semanas seg–dom pela data da compra; `semanas_fatura_importada`). Parcelas antigas/compras atrasadas ficam num bloco à parte; semanas + bloco = total da fatura (validado ao centavo em 05/2025–09/2026).
- **Fechamento real do C6 NÃO é dia 4:** pelos dados importados, a última compra de cada fatura cai no dia 28–2. A aba de faturas fechadas lê o ciclo da própria fatura (`ciclo_fatura_importada`). A data da compra das importações antigas só existe em `observacao` ("Compra em dd/mm/aaaa"); o importador novo grava `data_compra` (também dd/mm/aaaa).

### Pendências / decisões do Bruno (NÃO mexer sem confirmar)
1. **Sidebar colapsada por padrão** + nav no topo (mudança de UX do CODEX) — confirmar se fica.
2. **Projeção de parcelas só popula após RE-IMPORTAR as faturas** pelo app (dados antigos, importados por script, não têm colunas de parcela). Não é bug.
3. Validar contraste do **tema Claro**.
4. **Dia de fechamento padrão = 4** na Semana atual/Fatura estimada, mas o C6 real fecha ~dia 2 (ver abaixo). Perguntei se troca p/ 2 — sem resposta. Na prática o botão "Encerrar fatura" resolve.
5. **Categorias do Notion:** sync traz o "Tipo" cru (regras do app desligadas). Ligar `aplicar_regras=True` recategoriza ~840 lançamentos — só se o Bruno pedir.
6. Avisos do GitHub Actions (Node 20 em `checkout@v4`/`setup-python@v5`; ubuntu-latest → 26 em 19/10/2026): não quebram nada; ofereci atualizar as versões.
7. Faturas fechadas não importadas mostram só **crédito** lançado à mão; PIX/débito anteriores ao encerramento não aparecem em lugar nenhum — ofereci incluir.

### Regra de trabalho (feedback do Bruno)
- **Não recategorizar em massa por conta própria.** Já houve "cancela" por overreach (mover restaurantes/criar 241 regras sem pedir). Categorias são decisão do Bruno — ele dirige, eu executo o que for pedido.

---

## 6.1 Sincronização automática Notion → Sheets

- **Só leitura do Notion** (a Pri lança no Notion, o Bruno vê no dashboard). Nada é escrito no Notion.
- GitHub Actions `.github/workflows/sync-notion.yml`, todo dia 03:00 UTC (00:00 Brasília) + botão "Run workflow". Roda `scripts/sync_notion.py` (`--dry-run` para simular local).
- Regra única em `notion_import.py` (`linhas_do_notion`, `mesclar_notion`), usada também pelo botão de Configurações. Troca só `fonte=Notion`; C6/Manual/Semanal intactos.
- **Categoria = "Tipo" do Notion, cru.** As regras do app (`mapeamentos`) NÃO são aplicadas (`aplicar_regras=False`): ligá-las recategorizaria ~840 lançamentos de uma vez. Decisão do Bruno se quiser mudar.
- Busca resolve só a relação "Tipo" (~60s); falha ao ler título de categoria aborta (não grava "Outros" em silêncio). Retry em 429/5xx.
- Travas: Notion vazio ou queda > 50% → aborta sem gravar. `salvar_parquet` agora devolve False se o Sheets falhar.
- **Repo é PÚBLICO:** logs do Actions são públicos → o script imprime só contagens. Secrets no GitHub: `SPREADSHEET_ID`, `GCP_SERVICE_ACCOUNT` (JSON), `NOTION_TOKEN`, `NOTION_DATABASE_ID` — cadastrados pelo Bruno via `scripts/configurar_secrets_github.py`.
- GitHub desativa agendamentos de repo público após 60 dias sem commits (avisa por e-mail; reativar em Actions).

---

## 7. Git

- `origin` é **HTTPS** (não voltar pra SSH). `git fetch` antes de `push`.
- Commits terminam com:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
