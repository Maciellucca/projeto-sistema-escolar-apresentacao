# 🚀 Início rápido — Projeto Sistema Escolar

Guia direto para colocar o sistema no ar. Para detalhes de cada parte, veja
o [README.md](README.md) e o [docs/LGPD_PRIVACIDADE.md](docs/LGPD_PRIVACIDADE.md).

## 1. Instalar

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## 2. Configurar as chaves

```bash
cp .env.example .env
```

Abra o `.env` e troque `SECRET_KEY` e `ADMIN_SETUP_KEY` por valores aleatórios
e diferentes entre si. Para gerar um valor aleatório:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Rode duas vezes (uma para cada chave).

## 3. Escolher o banco de dados (opcional)

Por padrão o sistema usa **SQLite** — não precisa fazer nada, já funciona.
Se quiser usar **MySQL** (recomendado para o projeto integrador), siga o
**[docs/MYSQL.md](docs/MYSQL.md)** antes de continuar e defina
`DB_BACKEND=mysql` no seu `.env`.

## 4. Colocar os dados na base

Coloque sua planilha (formato simplificado, com aluno e AEE juntos) em
`data/raw/` (fora do Git) e rode:

```bash
python scripts/importar_base_dados.py data/raw/sua_planilha.xlsx
```

Esse script já lê alunos **e** AEE de uma vez (a planilha traz as duas
informações juntas). O resultado vai para SQLite ou MySQL, conforme o que
você configurou no passo 3.

Só quer testar o sistema sem ter uma planilha real em mãos? Monte uma
planilha fictícia rapidinho com as colunas que o script espera (veja os
comentários de `scripts/importar_base_dados.py`) — nenhum dado de exemplo
vem versionado no repositório, então a base de teste é sempre a que você
mesmo criar.

*Trabalhando com os arquivos originais de uma rede real (formato PILOTO +
AEE em planilhas separadas, mais os PDFs de Ata Bimestral)? Use
`scripts/import_students.py` e `scripts/import_aee.py` em vez do script
acima — os PDFs de notas continuam se importando pela tela "Importar notas"
do sistema, do jeito descrito no passo 7.*

**Alternativa pela web (sem usar terminal)**: depois de logado, a tela
**"Importar alunos"** no menu lateral aceita os três formatos (PILOTO,
simplificado, AEE) direto pelo navegador — útil sobretudo em produção,
onde é a forma recomendada de subir dados reais sem eles passarem pelo
Git/GitHub (veja a seção "Hospedando na internet" mais abaixo).

## 5. Subir o servidor

```bash
python app.py
```

Acesse **http://127.0.0.1:5000**.

## 6. Criar o seu usuário administrador

Na tela de login, clique em **"Criar usuário administrador"** e informe
usuário, nome, setor, senha e a chave `ADMIN_SETUP_KEY` definida no passo 2.

*(Alternativa sem usar a web: `python scripts/criar_usuario.py admin "Seu Nome" admin`)*

## 7. Importar as notas (com conferência)

Já logado como admin/secretaria, clique em **"Importar notas"** no menu.
Tem duas formas:

- **Enviar o PDF direto** — a leitura roda **em segundo plano** no
  servidor; a página volta na hora com uma tela "Lendo o PDF…" que
  atualiza sozinha até terminar. Funciona bem na maioria das hospedagens,
  mas **em planos muito limitados (ex: Free do Render) pode nunca
  terminar** — depois de alguns minutos travado, a própria tela avisa e
  deixa cancelar.
- **Ler no seu computador e enviar só o resultado** (recomendado se a
  opção acima travar, ou se a hospedagem for de plano gratuito):
  ```bash
  python scripts/exportar_notas_json.py sua_ata.pdf --ano 2026 --bimestre 1
  ```
  Isso gera um `.json` ao lado do PDF. Envie esse `.json` na seção "Já
  tenho o arquivo processado" da mesma tela — como não tem leitura pesada
  envolvida (só gravar o que já foi lido), é praticamente instantâneo,
  mesmo em hospedagem fraca, e pula direto pra conferência.

De qualquer um dos dois jeitos, revise a tela de conferência — corrija o
que precisar — e só então clique em **"Confirmar e gravar"**. Nada chega
ao boletim dos responsáveis antes dessa confirmação.

Para testar sem ter um PDF real em mãos, gere uma Ata Bimestral **fictícia**
com `scripts/gerar_ata_ficticia.py` — ele reproduz o layout do relatório
real do SGP (mesmas colunas F/CA/%/Conceito por disciplina) só que com
dados 100% inventados, para os alunos que você já tiver importado no
passo 4:

```bash
python scripts/gerar_ata_ficticia.py data/raw/AtaBimestral_ficticia_1bim.pdf --turma 1A --bimestre 1 --ano 2026
```

Depois é só enviar o PDF gerado pela tela "Importar notas".

## 8. Liberar o acesso aos responsáveis

Na página de cada aluno, clique em **"Gerar token de acesso"**. O token só
aparece uma vez — copie e entregue ao responsável por um canal seguro. Ele
acessa `/responsavel`, digita o token e vê o boletim.

## Em produção

Nunca deixe o servidor de desenvolvimento do Flask (`debug=True`) exposto na
internet. Rode atrás de um servidor WSGI de verdade, por exemplo:

```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:8000 app:app
```

E coloque um proxy com HTTPS (nginx, Caddy, etc.) na frente.

## Hospedando na internet (ex: Render.com)

Este é o caminho mais simples para deixar o sistema acessível de qualquer
lugar, com HTTPS automático e disco persistente. Leia primeiro a seção
"Colocando isso na internet" em `docs/LGPD_PRIVACIDADE.md`.

> ⚠️ **O plano Free do Render tem duas limitações importantes.** Ele não tem
> disco persistente (o `disk:` do `render.yaml` só funciona em planos
> pagos), e não sustenta a leitura da Ata Bimestral em segundo plano de
> forma confiável — o processamento pode nunca terminar, sem nenhum erro
> aparecer nos logs. Isso não é uma falha do sistema, é uma limitação
> conhecida de hospedagens gratuitas com trabalho fora do ciclo de
> requisição.
>
> Duas saídas: (1) o plano **Starter** (~US$7/mês) resolve os dois
> problemas de uma vez, ou (2) fique no Free e use
> `scripts/exportar_notas_json.py` para ler a Ata Bimestral no seu próprio
> computador, subindo só o resultado já processado (passo 7 mais abaixo) —
> isso evita completamente o problema do processamento em segundo plano,
> mas **não resolve** a falta de disco persistente (seus dados continuam
> em risco de sumir a qualquer reinício do serviço nesse plano).

1. **Suba o código (sem dados) para um repositório no GitHub.** Confira que
   `data/raw/`, `instance/` e `.env` continuam de fora (o `.gitignore` já
   cuida disso — não force `git add -f` neles).

2. **Crie uma conta no [Render](https://render.com)** e clique em
   **New → Blueprint**, apontando para o seu repositório. O Render vai ler
   o `render.yaml` que já está no projeto e configurar sozinho: o serviço
   web (plano Starter — ajuste no painel se o Blueprint criar como Free),
   um disco persistente de 1 GB montado em `/var/data`, e vai **gerar
   automaticammente** `SECRET_KEY` e `ADMIN_SETUP_KEY` aleatórias (você não
   precisa digitar nada).

   Se preferir configurar manualmente em vez de usar o Blueprint:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT --timeout 300`
   - **Disco persistente**: adicione um disk, monte em `/var/data`
   - **Variáveis de ambiente**: `SECRET_KEY`, `ADMIN_SETUP_KEY` (gere valores
     aleatórios — veja o passo 2 deste guia), `ESCOLA_FORCE_HTTPS=1`,
     `ESCOLA_DATA_DIR=/var/data`

3. **Espere o deploy terminar** e abra a URL que o Render deu ao serviço
   (algo como `https://projeto-sistema-escolar.onrender.com`).

4. **Crie o admin pela tela web** (`/login/criar-admin`), usando a chave
   `ADMIN_SETUP_KEY` que aparece nas variáveis de ambiente do serviço, no
   painel do Render.

5. **Importe os dados reais sem eles passarem pelo GitHub**: já logado como
   admin, clique em **"Importar alunos"** no menu lateral. Essa tela sobe o
   arquivo `.xlsx` (PILOTO, simplificado, ou AEE) direto para o disco
   persistente do servidor e grava no banco — o arquivo nunca é commitado,
   nunca passa pelo Git, e é apagado do servidor automaticamente assim que a
   importação termina. As Atas Bimestrais em PDF funcionam do mesmo jeito,
   pela tela **"Importar notas"** (passo 7). Essa é a forma recomendada de
   colocar dados reais no ar — o repositório no GitHub continua só com
   código, sem nenhum dado de aluno.

6. **Domínio próprio (opcional)**: no painel do serviço, em "Settings →
   Custom Domain", aponte um subdomínio da escola (ex:
   `sistema.suaescola.edu.br`) — o Render emite o certificado HTTPS
   automaticamente.

### Alternativas ao Render

O projeto não depende de nada específico do Render — qualquer hospedagem
que rode Python + WSGI com disco persistente serve, por exemplo Railway.app
ou Fly.io (ambos leem o `Procfile` incluído), ou um VPS próprio (nesse
caso você mesmo cuida do HTTPS, com Caddy ou nginx + certbot).

### O que NÃO fazer

- Não use hospedagens com **disco totalmente efêmero** (some a cada
  redeploy) sem configurar um volume/disco persistente — você perderia o
  banco de dados e as fotos.
- Não hospede em uma plataforma que você não confia com dados de saúde de
  crianças — o AEE é dado sensível pela LGPD.
- Não pule o passo de trocar `SECRET_KEY`/`ADMIN_SETUP_KEY` pelos valores
  gerados automaticamente — nunca use os do `.env.example`.

## Testes automatizados

```bash
pip install -r requirements-dev.txt
pytest
```

A suíte cobre: hashing de senha e de token do responsável, proteção CSRF,
criação de admin (chave certa/errada, senha curta), limite de tentativas de
login, isolamento entre alunos no portal do responsável, controle de acesso
às fotos, e a API de busca/estatísticas. Cada teste roda com um banco de
dados isolado (não toca nos seus dados reais).

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| "Chave de configuração inválida" ao criar admin | `ADMIN_SETUP_KEY` no formulário não bate com o `.env` — confira espaços/quebras de linha ao copiar |
| Leitura do PDF muito lenta | Normal para arquivos com 100+ páginas — pode levar alguns minutos, e roda em segundo plano (a página "Lendo o PDF…" atualiza sozinha) |
| Timeout/erro de gateway ao importar notas no Render (ou hospedagem parecida) | Isso não deveria mais acontecer — a leitura do PDF roda em segundo plano e a página responde na hora. Se ainda acontecer, confira se você está numa versão atualizada do sistema (`git log` deve mostrar "Move leitura do PDF para segundo plano" ou commit equivalente) |
| "Arquivo grande demais" ao confirmar a tela de conferência, mesmo o arquivo original sendo pequeno | Isso não é sobre o tamanho de um arquivo — é o formulário da tela de conferência em importações grandes (centenas de alunos) esbarrando num limite interno do Werkzeug (`max_form_memory_size`, 500 KB por padrão desde a versão 3.1), que existe separado do `MAX_PDF_UPLOAD_MB`. Já corrigido (desligamos esse limite específico em `app.py`, mantendo só o `MAX_CONTENT_LENGTH` como teto). Confira se está numa versão atualizada do sistema |
| Aluno "não localizado" na conferência de notas | Nome no PDF não bate exatamente com o cadastrado — use "trocar" na tela de revisão pra buscar e selecionar o aluno certo |
| "Arquivo grande demais" ao confirmar uma importação com centenas de alunos | Já corrigido — a tela de conferência antes repetia a lista completa de alunos em cada linha (um `<select>` gigante), o que deixava a página enorme em importações grandes (900+ alunos chegava a ~95 MB). Agora usa busca ao vivo em vez de repetir a lista; se ainda acontecer, confira se está numa versão atualizada (`git log` deve mostrar algo como "conferência escala para importações grandes") |
| Erro ao importar `.xls` | O `openpyxl` só lê `.xlsx` — converta o arquivo primeiro (Excel/LibreOffice: "Salvar como" `.xlsx`) |
