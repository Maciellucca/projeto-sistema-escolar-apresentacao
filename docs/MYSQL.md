# Configurando o MySQL

Por padrão o sistema usa SQLite (zero configuração — ótimo para testar
rápido). Para usar MySQL, siga este guia.

## 1. Ter um servidor MySQL disponível

Qualquer uma destas opções serve:

- **Local**: instale o MySQL Server (ou MariaDB, compatível) na sua máquina.
  - Windows/Mac: [MySQL Installer](https://dev.mysql.com/downloads/installer/)
    ou XAMPP/WAMP (já vem com MySQL + phpMyAdmin).
  - Linux: `sudo apt install mysql-server` (Debian/Ubuntu).
- **Docker** (rápido, não instala nada no sistema):
  ```bash
  docker run --name sistema-escolar-mysql -e MYSQL_ROOT_PASSWORD=escolha-uma-senha \
    -e MYSQL_DATABASE=sistema_escolar -p 3306:3306 -d mysql:8
  ```
- **Nuvem** (para hospedar o site com banco incluso): Railway, PlanetScale,
  Aiven ou Clever Cloud oferecem MySQL gerenciado com camada gratuita/trial.

## 2. Criar o banco (se ainda não existir)

Pelo cliente `mysql` ou uma ferramenta gráfica (MySQL Workbench, DBeaver,
phpMyAdmin, TablePlus):

```sql
CREATE DATABASE sistema_escolar CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE USER 'sistema_escolar'@'%' IDENTIFIED BY 'escolha-uma-senha-forte';
GRANT ALL PRIVILEGES ON sistema_escolar.* TO 'sistema_escolar'@'%';
FLUSH PRIVILEGES;
```

O sistema cria as **tabelas** sozinho na primeira vez que rodar (não precisa
rodar nenhum script `.sql` de schema à mão) — só o banco/usuário acima
precisam existir antes.

## 3. Configurar o `.env`

```bash
DB_BACKEND=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=sistema_escolar
MYSQL_PASSWORD=escolha-uma-senha-forte
MYSQL_DATABASE=sistema_escolar
```

Se estiver usando um MySQL na nuvem, `MYSQL_HOST` vai ser o endereço que o
provedor te der (algo como `containers-us-west-1.railway.app`), não
`localhost`.

## 4. Rodar o sistema normalmente

```bash
python app.py
```

Na primeira execução, o sistema cria automaticamente todas as tabelas no
banco MySQL configurado (mesma lógica do SQLite — `models.init_db()`).

## 5. Importar os dados

Os scripts de importação funcionam exatamente igual, independente do banco
escolhido — a única diferença é a variável `DB_BACKEND` no `.env`:

```bash
python scripts/importar_base_dados.py data/raw/Base_de_dados.xlsx
python scripts/criar_usuario.py admin "Seu Nome" admin --setor "Coordenação"
```

## Como funciona por baixo dos panos

Todo o código de `routes/` e `scripts/` escreve SQL usando `?` como
placeholder (estilo SQLite) e chama sempre `models.get_db()`. A tradução
para a sintaxe do MySQL (`%s`, `AUTO_INCREMENT`, `ON DUPLICATE KEY UPDATE`
etc.) fica isolada dentro de `models.py` — nenhuma rota precisa saber qual
banco está em uso. Isso significa:

- Trocar de banco é só mudar `DB_BACKEND` no `.env` — não precisa mexer em
  nenhuma outra parte do sistema.
- Os testes automatizados (`pytest`) sempre rodam contra SQLite (mais
  rápido, sem precisar de um servidor MySQL disponível), mesmo que sua
  instalação normal use MySQL — isso é proposital.

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `ModuleNotFoundError: No module named 'pymysql'` | Rode `pip install -r requirements.txt` de novo — o PyMySQL foi adicionado lá |
| `Access denied for user` | Usuário/senha errados no `.env`, ou o usuário não tem `GRANT` no banco certo |
| `Can't connect to MySQL server` | `MYSQL_HOST`/`MYSQL_PORT` errados, ou o servidor MySQL não está rodando |
| Erro `1071 Specified key was too long` ao criar tabelas | Charset do banco não é `utf8mb4` — recrie o banco com o `CREATE DATABASE` acima |
