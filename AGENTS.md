# AGENTS.md — Assistente Financeiro da Família Periguinhos 🐧

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
- Testes: `tests/test_core.py`, `tests/test_expense_defaults.py`, `tests/test_ui_theme.py`, `tests/test_notion_sync.py`, `tests/test_cupom_fiscal.py` (XML fictício — repo é público, nunca commitar cupom real), `tests/test_categorias.py`, `tests/test_custo_vida.py`, `tests/test_api.py` (API do app com planilha em memória).
- Rodar a página sem login para conferir: `streamlit.testing.v1.AppTest.from_file("app.py")` + `session_state` `logado/usuario/_login_ts` + `switch_page(...)` (lê o Sheets de produção — só leitura, nunca clicar em botões que gravam).

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
| `cupom_fiscal.py` | NFC-e pelo link do QR Code (só SEFAZ-PE): baixa o XML, lê itens, sugere categoria (item já classificado > NCM > 🛒 Supermercado), agrupa por categoria. |
| `dados.py` | Regras de dados **sem Streamlit** (parser de data, esquema das abas, `gerar_id`, `agora`); o `utils` reexporta e a API usa. |
| `leitor_qr.py` | Câmera **ao vivo** para o QR do cupom (`st.components.v2`, Streamlit ≥ 1.51): `BarcodeDetector` nativo do navegador (Chrome Android) ou jsQR do CDN como reserva; devolve o texto por trigger. Sem v2 (ex.: Streamlit 1.50 local) a página cai na `st.camera_input` antiga. |
| `style.css` / `style-light.css` | Skin do tema escuro / complemento do claro. |

### Páginas (`pages/`)
1. `1_📆_Gastos_Semanais.py` — gasto da semana + fatura estimada do mês + parcelas comprometidas + **editor da semana atual** (inline) + **histórico de semanas editável** (via `aplicar_edicoes_semanais`). São dois editores com propósitos diferentes (atual vs histórico), não duplicação.
2. `2_🔎_Categorias.py` — explorador: ranking de categorias, drill-down (evolução mensal, estabelecimentos, tabela completa). Usa `despesas_da_analise` (mesma regra do dashboard).
3. `3_🌴_Projeto_Ferias.py` — meta de viagem.
4. `4_👴👵_Aposentadoria.py` — projeção de futuro.
5. `5_⚙️_Configuracoes.py` — import C6 (zip AES), sync Notion, mapeamentos/regras.
6. `6_💰_Custo_de_Vida.py` — custo mínimo para viver = média mensal de Fixas + Variáveis essenciais (lógica pura em `custo_vida.py`). Tipos: Fixa / Variável essencial / Variável cortável / Fora da conta; classificação aprovada pelo Bruno em `CLASSIFICACAO_PADRAO`, ajustes salvos na aba `tipos_categoria`. Usa `despesas_da_analise` e exclui receitas C6 (reembolsos); janela começa na 1ª fatura C6. Fora da conta (decisão do Bruno): 💳 Cartões (fatura importada é que vale), 💸 Pix Avulso (ele vai analisar), 🐷 Poupança Kids, ajuda à família (Mãe/Pai/Sandra).

### Tabelas no Google Sheets
`despesas`, `receitas`, `cartoes`, `lancamentos`, `metas`, `mapeamentos` + (adicionadas pelo CODEX) `faturas_base`, `fechamentos_fatura`, `limites_semanais` + `itens_cupom` (um item de cupom fiscal por linha; `despesa_id` aponta a linha agrupada em `despesas`).
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

## 6. Estado atual (2026-10-27)

- `main` == `origin/main`, **69 testes passando**. Commits de 16–27/10: `f8099cd` (resumo por categoria nas semanas encerradas), `be568a6` (cupom vira uma compra com total + produtos), `ee7c64a` (nota offline sem itens), `4b1c262` (AGENTS.md p/ o Codex). Commits de 14/10: `491d094` (categoria sem padrão AABB), `58cd058` (cupom fiscal), `c76b052` (emojis), `cf19bb7` (Custo de vida), `c9bf07d` (QR por foto), `3c11354` (nota offline), `46f9db5` (cupons esperando a SEFAZ). Antes: `eb466a3` (gráficos do dashboard), `382acd9` (sync Notion).
- **Fatura 11/2026 do C6 BRU (aberta, ciclo 02/10–04/11) lançada à mão em 27/10** a partir de prints do app do C6 (fonte=Semanal, crédito C6 BRU; o cartão "final 3301" é o C6 BRU). Depois disso a fatura estimada do app **bateu ao centavo com o valor do banco**. Nos prints, compra ainda em processamento aparece como "MasterCard" em vez do nome da loja. Estorno entra **negativo, no crédito**, na categoria da compra. Decisões do Bruno: Abastece Aí = ⛽Combustível, Bule Café = 🔄 Reembolso, AS COCO = 🛒 Supermercado, mercado pago a pessoa física = 🛒 Supermercado ou 📦 Outros (perguntar), Invisalign e dentista = **💊 Saúde - Dentista** (categoria nova, criada pelo uso; ainda sem tipo no Custo de vida). Antes de gravar, mostrar a tabela e esperar aprovação; não lançar o que o Bruno já lançou pelo QR.
- Fatura **10/2026 do C6 BRU já importada** (07/10). Sync do Notion rodou com sucesso no GitHub (1.200 registros → 888 despesas + 285 receitas).
- CODEX adicionou ~15 commits antes (projeção de fatura, tema claro/escuro, gastos semanais expandidos). Guards intactos.
- **Dashboard (`app.py`):** eixos com `automargin` + valores curtos (`ui_theme.valor_curto`/`eixo_reais`, "R$ 20 mil"); Fluxo mensal vai da 1ª fatura C6 importada até o mês atual (meses futuros agendados no Notion ficam fora, com aviso); linhas retas, sem preenchimento. "Onde foi o dinheiro": **uma cor por categoria** (`ui_theme.CATEGORICAS`, paleta validada p/ daltonismo nos 2 temas; slot = ranking de TODO o histórico, não muda com o filtro; fora do top 8 = cinza). Bruno reprovou tudo-vermelho — não voltar para cor única.
- **Encerramento manual da fatura** (pág. 1): botão "🔒 Encerrar fatura" grava `encerrada_em` (ISO) em `fechamentos_fatura` no registro do mês seguinte. A fatura fica em aberto até o Bruno encerrar; ao encerrar, a semana é recortada (`janela_semana`) e zera a partir do dia seguinte. Sem nenhum encerramento manual, vale a regra automática do dia 4. Funções puras: `faturas_encerradas`, `fatura_aberta`, `janela_semana`.
- **Regra do encerramento (Bruno):** a data de encerramento divide tudo. Até ela = passado (aba Faturas fechadas); depois dela = Semana atual + Histórico + conta para a fatura seguinte. Registros antigos de `fechamentos_fatura` (só `dia`, sem `encerrada_em`) também valem como encerramento. Fatura encerrada e não importada aparece na aba de fechadas com os lançamentos manuais no crédito (`lancamentos_semanais_fatura`) até ser importada.
- **Pág. 1 em abas:** "📆 Semana atual" (lançamentos manuais `fonte=Semanal` + Histórico de semanas embaixo) e "🧾 Faturas fechadas" (passado = faturas importadas do C6, agrupadas em semanas seg–dom pela data da compra; `semanas_fatura_importada`). Parcelas antigas/compras atrasadas ficam num bloco à parte; semanas + bloco = total da fatura (validado ao centavo em 05/2025–09/2026).
- **Fechamento real do C6 NÃO é dia 4:** pelos dados importados, a última compra de cada fatura cai no dia 28–2. A aba de faturas fechadas lê o ciclo da própria fatura (`ciclo_fatura_importada`). A data da compra das importações antigas só existe em `observacao` ("Compra em dd/mm/aaaa"); o importador novo grava `data_compra` (também dd/mm/aaaa).

- **Lançamento manual (pág. 1):** categoria começa vazia e é obrigatória (antes caía em "AABB", a 1ª da lista, quando a escolha se perdia). A "categoria lembrada" do estabelecimento só preenche se o campo estiver vazio ou ainda com a sugestão anterior.
- **Cupom fiscal (2026-10-14)** — seção "🧾 Lançar cupom fiscal (QR Code)" na pág. 1, lógica pura em `cupom_fiscal.py`. **Só presente/futuro — NÃO recategorizar o passado** (decisão do Bruno).
  - Entrada: **📷 câmera ao vivo** (`leitor_qr.py`, desde 27/10 — a foto/`camera_input` quase nunca lia e o Bruno tinha que abrir a câmera do celular e colar o link), 🖼️ foto (upload, decodifica com `zxing-cpp`) ou colar o link. Só SEFAZ-PE (`nfce.sefaz.pe.gov.br`). O link do QR devolve o XML da NFC-e **sem CAPTCHA** (a consulta manual pela chave tem reCAPTCHA — não contornar). `validar_link` aceita `%7C` e link sem `?p=` (`.../consultarNFCe<chave>|...`).
  - Grava uma linha por categoria em `despesas` (`fonte=Semanal`, descrição "Mercado · Categoria", `observacao="NFC-e <chave>"`) + item a item em `itens_cupom` (com `cnpj`, `despesa_id`). Sugestão de categoria: o que já foi dado ao mesmo produto > NCM (`_NCM_CATEGORIA`) > 🛒 Supermercado. Nome do estabelecimento editável e lembrado por CNPJ (nome fantasia às vezes é o bairro). Cupom repetido é bloqueado enquanto existir linha com aquela observação; se as linhas forem excluídas, pode relançar (itens antigos são trocados).
  - **Nota offline (contingência, 35º dígito da chave = 9):** a SEFAZ responde erro 236 até o mercado enviar (até 24 h). O QR já traz data, total e CNPJ → botão "⚡ Lançar agora só com o total" grava 1 linha com `observacao="NFC-e <chave> · itens pendentes"` e guarda o link em `cupons_pendentes`. A seção mostra "⏳ Cupons esperando a SEFAZ" com "🔄 Já chegou?"; quando chega, lançar com itens **troca** a linha do total pela divisão por categoria. **Descoberta (16/10):** depois que a SEFAZ recebe a nota offline, o link do QR de contingência responde `<erro>100</erro>` **sem os itens**. Pelo XSL da SEFAZ-PE (`nfce-web/xsl/an/NFCe_2.xsl`): 100 = "QR Code Inválido", 236 = "Nota não se encontra na base", 202 = problema na chave. O QR do Recibom tem só 6 campos (chave|2|1|dia|valor|hash, sem `?p=`), não os 8 do padrão offline. `ler_cupom` levanta `NotaSemItens` no 100 e a página oferece "✔️ Ficar só com o total" (`concluir_pendente` troca a observação para `NFC-e <chave>`). Caso real: Recibom 14/10 (R$ 56,61). Não há como pegar os itens desse QR: a consulta pela chave tem reCAPTCHA (não contornar); o site Seja Pernambuco (promoção da ASPA) mostra produtos porque recebe dados dos mercados, sem API pública. Bruno descartou ler a foto do cupom (cupons enormes); upload do XML baixado à mão = ideia oferecida, sem resposta. Obs.: os cupons do Recibom de 26/10 foram lidos com itens normalmente.
  - Categorias de item (`CATEGORIAS_CUPOM`): 🥬 Hortifruti, 🥩 Carnes e Peixes, 🧀 Frios e Laticínios, 🥖 Padaria, 🥫 Mercearia, 🥤 Bebidas, 🧽 Limpeza, 🧴 Higiene e Beleza, 🐾 Pets, 💊 Saúde - Farmácia, ⛽Combustível, 🛒 Supermercado. Bebidas alcoólicas separadas = ideia oferecida, sem resposta. NCM 2105 (sorvete/picolé) cai em 🥫 Mercearia pelo prefixo "21" — ofereci mover (🥤 Bebidas ou 🍦 Sorvetes), sem resposta.
  - **Semana atual (27/10):** cada cupom aparece como **uma linha com o total da compra** (`agrupar_compras`, agrupa pela chave em `observacao`); tocando (`<details>`), abre categorias e, dentro delas, os produtos de `itens_cupom` (pela `despesa_id`). Pedido do Bruno: ver o total primeiro e o detalhe depois.
  - **Histórico de semanas (27/10):** semana encerrada (`_fim < HOJE`) abre com resumo por categoria (`fatura_projection.resumo_categorias`: valor, %, barra). Título do expander escapa `$` (dois "R$" viravam fórmula). Editor do histórico aceita valor negativo (estorno), só recusa zero.
  - Depois que a fatura do C6 é importada, a compra volta a ser 1 linha (a do banco); antes disso o dashboard mostra a divisão do cupom (regra na seção 6.0).
- **Deploy no Streamlit Cloud:** push que muda só código **não reinicia o processo** → módulo auxiliar fica velho na memória e a página dá `ImportError`. Depois de mexer em `cupom_fiscal.py`/outros módulos, fazer **Reboot** (share.streamlit.io → ⋮ do app → Reboot). Push que muda `requirements.txt` reinstala e reinicia sozinho. Cloud roda Python 3.14 e versões novas (requirements sem pin). O Bruno instalou o app como PWA no Galaxy S25.

- **Emojis nas categorias (2026-10-14):** `categorias.py` (`NOMES_COM_EMOJI`, `com_emoji`) dá emoji às categorias que vinham cruas (Padaria → 🥖 Padaria etc., por parte em "Pix Avulso, AABB"). Aplicado no sync do Notion (`linhas_do_notion`) para não voltar o nome cru, e renomeado uma vez na planilha (despesas, receitas, mapeamentos; backup em `data/backup_emojis_2026-10-14/`). Internet/Streaming/Saúde foram juntadas com as que já tinham emoji. Nova categoria crua no Notion → acrescentar em `NOMES_COM_EMOJI`.
- **Limpeza de categorias sem lançamento:** o Bruno desistiu ("pode dar merda"). NÃO excluir regras/categorias sem ele pedir de novo.

### Pendências / decisões do Bruno (NÃO mexer sem confirmar)
0. **Ideias oferecidas, aguardando o Bruno:** página 🛒 Supermercado (item a item, preço ao longo do tempo, por mercado — ele gostou, ainda não mandou fazer); levar a divisão do cupom para o dashboard (trocar a compra da fatura C6 pelas linhas do cupom); app Android "casca" (APK WebView) — perguntei se a Pri usa iPhone ou Android; 26 categorias sem tipo no Custo de vida (ele classifica na página; agora + 💊 Saúde - Dentista).
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

## 6.0 App do celular (Android) + API — desde 2026-10-27

Decisão do Bruno: **tudo da página 📆 Gastos Semanais vai para um app Android** (APK só para ele e a Pri, sem Play Store); dashboard e análises ficam no Streamlit; o import da fatura C6 continua no PC. A Pri continua lançando as contas da casa no Notion.

- **Regra do dashboard (aprovada):** lançado à mão (`fonte=Semanal`, app ou página) **entra** no dashboard, Categorias e Custo de vida (`fatura_projection.despesas_da_analise`). Exceção: crédito de cartão com fatura importada (hoje só C6 BRU; crédito sem cartão = C6 BRU) conta **até a fatura chegar** — compras até a última compra da fatura importada mais recente saem (vale a linha do banco). As que ficam vão para o **mês da fatura** delas (dia 1, como a importada): a 1ª encerrada depois da compra (`fechamentos_fatura`) ou a seguinte à última importada/encerrada. Para ver a fatura aberta em tempo real, filtrar o mês dela (o gráfico de fluxo só vai até o mês atual).
- **Trava de escrita concorrente:** o Streamlit regrava a aba inteira; `utils._salvar_gsheet` compara a impressão (hash) da aba com a da leitura e **recusa** se mudou (app/sync gravaram no meio), limpando o cache. A API nunca regrava a aba: `append_rows` / atualiza ou apaga só a linha pelo `id`.
- **API** (`api/`, FastAPI): `main.py` (rotas), `servico.py` (regras: semana, lançar/editar/excluir gasto, cupom com nota offline — mesmas da página 1), `planilha.py` (gspread linha a linha, cache 20 s), `acesso.py` (login com as senhas do `[usuarios]`, token HMAC de 90 dias, 5 tentativas + 5 min). Grava `lancado_por` (coluna nova em `despesas`). Fuso America/Recife. Rodar local: `uvicorn api.main:app --port 8080`. Deploy: `api/Dockerfile` no **Cloud Run** do projeto Google da planilha, rodando como a conta de serviço da planilha (só `SPREADSHEET_ID` no ambiente) + `APP_USUARIOS` (JSON) e `API_SEGREDO`.
- **Publicada (27/10)** no Cloud Run do projeto `dashchaves` (`southamerica-east1`, serviço `periguinhos-api`, máx. 1 instância). O endereço **não vai para o repo** (público): ver `gcloud run services describe periguinhos-api --region=southamerica-east1`. Upload do build limitado por `.gcloudignore`.
- **Corte de custo (decisão do Bruno):** orçamento de **R$ 10/mês** → Pub/Sub `corte-orcamento` → função `infra/corte_orcamento/` tira o acesso público da API (testado: fecha em ~90 s). Religar com `gcloud run services add-iam-policy-binding periguinhos-api --region=southamerica-east1 --member=allUsers --role=roles/run.invoker`. Deploy/religar só com OK do Bruno.
- **App** (`android/`, Kotlin + Compose): telas Login / Semana (total, limite, cupons esperando a SEFAZ, compras por dia com categorias e produtos, resumo) / Gasto (categoria lembrada) / Cupom. QR pelo leitor do Google Play Services (`play-services-code-scanner`). Compilar no PC: `JAVA_HOME` = `C:\Program Files\Android\Android Studio\jbr`, `cd android && ./gradlew assembleRelease -PapiUrl=https://…`. **Assinatura fixa** em `C:\Users\bpcha\.periguinhos\` (`periguinhos.jks` + `keystore.properties`, fora do Git) — perder = desinstalar/reinstalar o app. Teste no emulador: servidor `http://10.0.2.2:8080` (única exceção de HTTP).

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
  `Co-Authored-By: Codex Opus 5.5 <noreply@anthropic.com>`
