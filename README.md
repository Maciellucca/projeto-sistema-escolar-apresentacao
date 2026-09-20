# 🏫 Projeto Sistema Escolar — versão de apresentação

Recorte enxuto do Sistema Escolar completo, feito para apresentação do
projeto integrador. Mantém só o essencial do fluxo de dados: **Início**
(painel de turmas), **Importar alunos**, **Importar notas** e
**Arquivo Morto**, além do **Portal do responsável** (acesso somente
leitura ao boletim, por token).

Feito com **Python + Flask** e banco de dados **SQLite ou MySQL** (você
escolhe via variável de ambiente — veja `docs/MYSQL.md`), sem build step no
front-end (HTML/CSS puro renderizado pelo servidor, com um pouco de
JavaScript para a busca ao vivo e o painel de estatísticas).

👉 Para colocar no ar rapidamente, siga o **[INICIO_RAPIDO.md](INICIO_RAPIDO.md)**.

## ⚠️ Leia antes de tudo — dados pessoais de crianças

Este sistema foi desenhado para lidar com dados pessoais sensíveis de
crianças (nome, data de nascimento, RA/INEP e, para alunos AEE,
laudo/diagnóstico de saúde) — mesmo quando usado, como neste projeto, com
uma base de alunos **fictícia** para fins acadêmicos. Isso é dado protegido
pela LGPD, com atenção redobrada por se tratar de menores e, no caso do AEE,
de dado de saúde — as proteções abaixo ficam ativas por padrão para que o
projeto já demonstre a prática correta, mesmo em ambiente de estudo.

**O projeto já vem estruturado para isso:**
- A pasta `data/raw/` (planilhas e PDFs originais) e `instance/` (o banco
  SQLite gerado) estão no `.gitignore` — **nunca vão para o Git**, nem em
  repositório privado.
- As fotos enviadas em `static/photos/` também estão no `.gitignore`.
- O detalhe do laudo AEE só aparece na tela para os perfis `admin` e `aee`.
  Todos os demais perfis veem apenas o selo "AEE" (sem detalhe).
- O acesso do responsável é por token aleatório; só o hash do token fica
  salvo no banco.

Leia **[docs/LGPD_PRIVACIDADE.md](docs/LGPD_PRIVACIDADE.md)** antes de subir
o projeto para o GitHub ou colocá-lo em produção — mesmo em repositório
**privado**, o cuidado é o mesmo.

## Estrutura

```
projeto-sistema-escolar-apresentacao/
├── app.py                  # ponto de entrada Flask (registra só os blueprints usados aqui)
├── config.py
├── models.py                # schema SQLite + MySQL (models.get_db() abstrai qual está em uso)
├── auth.py                  # login staff + token do responsável
├── routes/
│   ├── staff.py              # painel da equipe escolar + login/criação de admin + ficha do aluno
│   ├── importacao.py         # upload de Ata Bimestral + tela de conferência + importar alunos/AEE/fotos
│   ├── arquivo_morto.py      # aba Arquivo Morto
│   ├── guardian.py           # portal do responsável (acesso por token)
│   ├── cursos.py             # só o utilitário de ciclo de ensino, usado pelo portal do responsável
│   └── api.py                # API JSON interna (busca ao vivo, estatísticas da turma)
├── templates/                # HTML (Jinja2)
├── static/{css,js,photos}/   # js/turma.js consome a API para busca e o painel de estatísticas
├── tests/                    # suíte pytest (isolada, roda sempre contra SQLite)
├── scripts/
│   ├── importar_base_dados.py # Base_de_dados.xlsx (fictícia) -> students + aee_info
│   ├── gerar_ata_ficticia.py  # gera um PDF de Ata Bimestral fictícia (mesmo layout do SGP)
│   ├── exportar_notas_json.py # lê um PDF localmente -> .json (upload rápido em hospedagem fraca)
│   ├── import_students.py    # formato PILOTO (.xlsx) -> tabela students
│   ├── import_aee.py         # formato AEE separado (.xlsx) -> aee=1 + aee_info
│   ├── import_atas.py        # AtaBimestral (.pdf) -> tabela grades (via CLI, sem revisão)
│   ├── import_arquivo_morto.py # planilha por letra -> tabela arquivo_morto
│   ├── seed_turnos.py         # aplica de uma vez um mapeamento turma -> turno
│   └── criar_usuario.py       # cria/atualiza login de um profissional
├── data/
│   ├── raw/                  # coloque aqui os arquivos originais (gitignored)
│   └── templates/            # arquivos de apoio (este SIM vai pro Git)
└── docs/{LGPD_PRIVACIDADE.md, MYSQL.md}
```

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # edite SECRET_KEY e ADMIN_SETUP_KEY
```

## Primeiro acesso — criar o admin

Não existe cadastro público. Você pode criar o primeiro usuário de duas formas:

- **Pela web**: rode `python app.py`, acesse `/login`, clique em
  "Criar usuário administrador" e informe usuário, nome, setor, senha e a
  **chave de configuração do servidor** (`ADMIN_SETUP_KEY` do `.env` — ou
  `SECRET_KEY`, se você não definiu uma chave própria).
- **Pelo terminal** (alternativa, sem depender da chave web):
  ```bash
  python scripts/criar_usuario.py admin "Seu Nome" admin --setor "Direção"
  ```

Perfis disponíveis: `admin`, `secretaria`, `professor`, `aee`. A tela web só
cria perfil `admin`; para os demais perfis use o script no terminal.

## Passo a passo para colocar os dados

0. **Banco de dados** — por padrão usa SQLite (zero configuração). Para usar
   MySQL, siga **[docs/MYSQL.md](docs/MYSQL.md)** primeiro e defina
   `DB_BACKEND=mysql` no `.env` antes dos próximos passos.

1. **Alunos + AEE** — pela tela **"Importar alunos"** (menu lateral) ou por
   linha de comando:
   ```bash
   python scripts/importar_base_dados.py data/raw/sua_planilha.xlsx
   ```

2. **Notas (Ata Bimestral) — com tela de conferência**: tela **"Importar
   notas"** no menu superior. O sistema **não grava nada direto no
   boletim**: leva a uma tela de conferência, aluno por aluno, antes de
   confirmar.

3. **Fotos** — envie manualmente pela tela do aluno (`/aluno/<id>`) ou em
   lote pela tela "Importar alunos".

## Rodando o sistema

```bash
python app.py
```
Acesse `http://127.0.0.1:5000`.

## As 4 guias do menu

- **Início** — painel com busca de aluno, estatísticas gerais e as turmas
  organizadas por turno (Manhã / Integral / Tarde), separadas por série.
- **Importar notas** — upload da Ata Bimestral (PDF) com tela de
  conferência antes de gravar, ou envio de um `.json` já processado.
- **Importar alunos** — upload de planilha (três formatos aceitos: PILOTO,
  simplificado, AEE separado) e envio de fotos em lote.
- **Arquivo Morto** — registro permanente de todo aluno que já passou pela
  escola, organizado em gavetas por letra (A–Z). Aluno marcado como
  transferido (na página do aluno) entra aqui automaticamente.

## Portal do responsável

1. Na página do aluno, clique em "Gerar token de acesso".
2. O token só é mostrado **uma vez** — copie e entregue ao responsável por um
   canal seguro.
3. O responsável acessa `/responsavel`, digita o token e vê o boletim do
   filho/filha — nunca RA, CPF, filiação, laudo AEE ou qualquer outro dado
   além disso.

## Identificação AEE

Alunos marcados como AEE mostram um selo "AEE" no card e na página do
aluno, visível para **qualquer profissional logado**. O **detalhe** do
laudo/diagnóstico só aparece para quem estiver logado com o perfil `admin`
ou `aee`.

## API interna e busca ao vivo

A tela de turma tem um campo de busca por nome que consulta
`GET /api/turma/<turma>/alunos?q=<termo>` via JavaScript (`static/js/turma.js`),
sem recarregar a página. A mesma tela também mostra um painel de
estatísticas (frequência média por bimestre, distribuição de conceitos),
alimentado por `GET /api/turma/<turma>/estatisticas` — a parte de análise de
dados do projeto. Ambos os endpoints exigem login.

## Acessibilidade

- Link "pular para o conteúdo" no topo de cada página.
- Avisos do sistema (`flash`) marcados com `aria-live` para leitores de tela.
- Indicador de foco visível no teclado (`:focus-visible`) em links, botões e campos.
- Cabeçalhos de tabela com `scope="col"`.
- `lang="pt-br"` no HTML e `alt`/`aria-label` em fotos e nos círculos de iniciais.

## Testes automatizados

```bash
pip install -r requirements-dev.txt
pytest
```

## Requisitos do projeto integrador — onde cada um aparece

| Requisito | Onde está |
|---|---|
| Framework web | Flask (`app.py`, `routes/`) |
| Banco de dados | SQLite/MySQL (`models.py`, `docs/MYSQL.md`) |
| Script web (JavaScript) | `static/js/turma.js`, `busca_aluno_dashboard.js`, `revisar_lote.js` |
| Nuvem | `render.yaml`, `Procfile` — deploy documentado no `INICIO_RAPIDO.md` |
| Uso de API | `routes/api.py` (busca ao vivo + estatísticas, consumida via `fetch`) |
| Acessibilidade | seção acima |
| Controle de versão | este repositório Git/GitHub |
| Testes | `tests/` (pytest) |
| Análise de dados (opcional) | `GET /api/turma/<turma>/estatisticas` — frequência média por bimestre e distribuição de conceitos |

## Licença

Uso interno da unidade escolar. Adapte livremente conforme a necessidade da
sua rede — só não esqueça da seção de privacidade acima.
