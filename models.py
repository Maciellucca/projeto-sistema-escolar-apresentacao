"""
SISTEMA ESCOLAR - camada de dados.

Suporta dois bancos, escolhidos por config.DB_BACKEND ("sqlite" ou
"mysql"), sem que o resto da aplicação precise saber qual está em uso:
routes/ e scripts/ sempre chamam get_db() e escrevem SQL com "?" como
placeholder — a tradução para MySQL (%s) acontece aqui dentro.

- sqlite (padrão): zero configuração, ótimo para rodar local e para os
  testes automatizados.
- mysql: banco relacional "de verdade", pensado para o projeto integrador
  (docs/MYSQL.md tem o passo a passo de configuração).
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import config


def agora():
    """Timestamp atual em UTC, no formato aceito por ambos os bancos.
    Usado no código Python em vez de datetime('now')/NOW() do SQL, para
    o mesmo código funcionar nos dois backends sem depender da timezone
    configurada no servidor do banco."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------- SQLite ----
SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nome TEXT NOT NULL,
    setor TEXT,
    papel TEXT NOT NULL CHECK (papel IN ('admin','professor','aee','secretaria')),
    ativo INTEGER NOT NULL DEFAULT 1,
    rg TEXT,
    nome_completo_declaracao TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_interno TEXT UNIQUE,
    nis TEXT,
    bolsa_familia INTEGER NOT NULL DEFAULT 0,
    ra_prodesp TEXT,
    inep TEXT,
    nome TEXT NOT NULL,
    nome_social TEXT,
    filiacao1 TEXT,
    data_nascimento TEXT,
    turma TEXT NOT NULL,
    serie TEXT,
    situacao TEXT,
    foto_path TEXT,
    guardian_token_hash TEXT,
    aee INTEGER NOT NULL DEFAULT 0,
    rg TEXT,
    certidao_nascimento TEXT,
    municipio_nascimento TEXT,
    recomendacoes TEXT,
    alteracoes_pendentes TEXT,
    data_transferencia TEXT,
    estado_nascimento TEXT,
    nacionalidade TEXT,
    rg_data_expedicao TEXT,
    rg_orgao_expedidor TEXT,
    rg_estado_emissor TEXT,
    certidao_numero TEXT,
    certidao_folha TEXT,
    certidao_livro TEXT,
    certidao_distrito_municipio TEXT,
    certidao_uf TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS aee_info (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    eol TEXT,
    laudo TEXT,
    observacoes TEXT,
    deficiencia TEXT,
    turno TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    ano INTEGER NOT NULL,
    bimestre INTEGER NOT NULL,
    disciplina TEXT NOT NULL,
    faltas INTEGER,
    compensacoes INTEGER,
    frequencia REAL,
    conceito TEXT,
    situacao_conselho TEXT,
    origem TEXT DEFAULT 'importado',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, ano, bimestre, disciplina)
);

CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    referencia TEXT,
    acao TEXT NOT NULL,
    ip TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS import_lotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arquivo TEXT,
    ano INTEGER NOT NULL,
    bimestre INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','confirmado','descartado')),
    criado_por TEXT,
    total_alunos INTEGER DEFAULT 0,
    total_nao_localizados INTEGER DEFAULT 0,
    total_gravado INTEGER DEFAULT 0,
    processando INTEGER NOT NULL DEFAULT 0,
    erro_mensagem TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    confirmado_em TEXT
);

CREATE TABLE IF NOT EXISTS grades_staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id INTEGER NOT NULL REFERENCES import_lotes(id) ON DELETE CASCADE,
    aluno_key TEXT NOT NULL,
    turma_pdf TEXT,
    nome_pdf TEXT,
    student_id INTEGER REFERENCES students(id),
    disciplina TEXT NOT NULL,
    faltas INTEGER,
    compensacoes INTEGER,
    frequencia REAL,
    conceito TEXT,
    situacao_conselho TEXT,
    incluir INTEGER NOT NULL DEFAULT 1
);

-- Resultado final digitado à mão pela equipe para anos/séries que o
-- sistema não tem em `grades` (anos anteriores à adoção do sistema, aluno
-- transferido de outra escola, etc.) — usado para completar o Histórico
-- Escolar. Quando há dado em `grades` para a série atual do aluno, ele tem
-- prioridade; isto aqui é só para preencher o que falta.
CREATE TABLE IF NOT EXISTS historico_manual (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    serie TEXT NOT NULL,
    disciplina TEXT NOT NULL,
    resultado TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, serie, disciplina)
);

-- Configurações simples de chave/valor (ex: ID da Unidade de Ensino na
-- SPTrans) — evita criar uma coluna/tabela nova a cada ajuste pequeno.
CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Código de Curso/Turma que a própria SPTrans atribui (documento "Cursos e
-- Turmas" da SPTrans, fora do nosso sistema) — cadastrado uma vez por
-- turma pela secretaria, reaproveitado em toda exportação.
CREATE TABLE IF NOT EXISTS sptrans_turma_codigo (
    turma TEXT PRIMARY KEY,
    codigo_curso TEXT,
    codigo_turma TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Turno de cada turma (Manhã/Tarde/Integral) — organização específica de
-- cada escola, por isso fica configurável (não é regra fixa do sistema).
-- Turma sem linha aqui aparece como "Turno não definido" no painel.
CREATE TABLE IF NOT EXISTS turma_turno (
    turma TEXT PRIMARY KEY,
    turno TEXT NOT NULL CHECK (turno IN ('Manhã','Tarde','Integral')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Dados pessoais extras exigidos SÓ pela planilha de matrícula da SPTrans
-- (passe livre estudantil) — ficam numa tabela própria, separados do
-- cadastro principal do aluno, porque incluem CPF e endereço (dado
-- sensível que a maioria das telas do sistema não precisa enxergar).
CREATE TABLE IF NOT EXISTS sptrans_dados_aluno (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    cpf TEXT,
    rg_numero TEXT,
    rg_digito TEXT,
    rg_uf TEXT,
    cep TEXT,
    endereco_numero TEXT,
    endereco_complemento TEXT,
    telefone TEXT,
    email TEXT,
    nome_responsavel TEXT,
    tipo_gratuidade TEXT NOT NULL DEFAULT '0',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Telefones de contato dos responsáveis — separado do cadastro principal
-- (mesmo espírito de sptrans_dados_aluno): número de cada filiação, o
-- responsável legal (pode ser diferente dos pais) e um número de recados
-- (ex: vizinho, outro parente) para quando não conseguir contato direto.
CREATE TABLE IF NOT EXISTS contatos_responsaveis (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    telefone_filiacao1 TEXT,
    telefone_filiacao2 TEXT,
    responsavel_legal TEXT,
    telefone_recados TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Bolsa Família / Programa Frequência (F75) — frequência mensal lançada
-- manualmente pela secretaria (faltas do mês + motivo quando abaixo do
-- mínimo), pra organizar o que depois é transcrito à mão no portal do
-- governo (Sistema Presença) a cada período bimestral.
CREATE TABLE IF NOT EXISTS frequencia_mensal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    faltas INTEGER,
    motivo TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, ano, mes)
);
CREATE INDEX IF NOT EXISTS idx_frequencia_student ON frequencia_mensal(student_id);

-- Dias letivos de cada mês do ano letivo, cadastrados manualmente pela
-- secretaria (segue o calendário oficial da rede, que varia por ano) —
-- usado pra calcular a % de frequência a partir das faltas lançadas em
-- frequencia_mensal, sem o sistema ter que adivinhar um calendário.
CREATE TABLE IF NOT EXISTS dias_letivos_mensais (
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    dias_letivos INTEGER NOT NULL,
    PRIMARY KEY (ano, mes)
);

-- TEG (Transporte Escolar Gratuito) — dados de cada aluno inscrito no
-- transporte, importados da planilha "Inscritos_Teg" gerada pelo
-- sistema da rede. Uma linha por aluno (o mesmo aluno não aparece duas
-- vezes na planilha de origem).
CREATE TABLE IF NOT EXISTS teg_alunos (
    student_id INTEGER PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    turno TEXT,
    motivo_codigo INTEGER,
    motivo_descricao TEXT,
    distancia_metros INTEGER,
    cadeirante TEXT,
    tipo_logradouro TEXT,
    logradouro TEXT,
    numero_endereco TEXT,
    complemento TEXT,
    bairro TEXT,
    cep TEXT,
    placa_veiculo TEXT,
    nome_condutor TEXT,
    capacidade_veiculo INTEGER,
    barreira_fisica TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Telefone de cada condutor do TEG — preenchido manualmente pela escola
-- (a planilha de origem não traz telefone), pra facilitar contato caso
-- uma criança fique pra trás e não consiga identificar com clareza
-- quem é o transportador dela.
CREATE TABLE IF NOT EXISTS teg_condutores (
    nome_condutor TEXT PRIMARY KEY,
    telefone TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Arquivo morto: registro permanente de todo aluno que já passou pela
-- escola (inclusive de décadas atrás, antes deste sistema existir),
-- organizado por letra (a mesma divisão em 26 abas do arquivo em
-- planilha). Quando um aluno é marcado como transferido, entra aqui
-- automaticamente no fim da letra correspondente — student_id fica
-- preenchido nesse caso (permite voltar pro cadastro), mas fica vazio
-- pros registros só importados da planilha histórica (pré-existem ao
-- sistema, não têm um cadastro de aluno correspondente aqui).
CREATE TABLE IF NOT EXISTS arquivo_morto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    letra TEXT NOT NULL,
    numero TEXT,
    nome TEXT NOT NULL,
    data_nascimento TEXT,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    origem TEXT NOT NULL DEFAULT 'importado' CHECK (origem IN ('importado', 'transferencia', 'manual')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_arquivo_morto_letra ON arquivo_morto(letra);

-- Lista de cursos gratuitos recomendados (ex: Escola Virtual.gov/ENAP),
-- organizada pelos 3 ciclos oficiais do Ensino Fundamental na Rede
-- Municipal de SP (Alfabetização 1º-3º, Interdisciplinar 4º-6º, Autoral
-- 7º-9º) — mantida manualmente pela equipe, não sincronizada automaticamente
-- com nenhuma plataforma externa (o catálogo delas muda com frequência).
CREATE TABLE IF NOT EXISTS cursos_recomendados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    descricao TEXT,
    url TEXT,
    ciclo TEXT NOT NULL CHECK (ciclo IN ('Alfabetização','Interdisciplinar','Autoral')),
    fonte TEXT,
    ativo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Agenda de atendimento com responsáveis — comunicação entre
-- secretaria/gestão e as famílias. Pode ou não estar ligado a um aluno
-- específico (às vezes é um assunto geral da secretaria).
CREATE TABLE IF NOT EXISTS atendimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora TEXT NOT NULL,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    nome_responsavel TEXT NOT NULL,
    telefone_contato TEXT,
    assunto TEXT NOT NULL,
    observacoes TEXT,
    responsavel_atendimento TEXT,
    status TEXT NOT NULL DEFAULT 'agendado' CHECK (status IN ('agendado','realizado','cancelado','faltou')),
    criado_por TEXT,
    atendido_por TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Afastamento por motivo de saúde — "motivo" é campo livre e OPCIONAL,
-- não pensado para guardar diagnóstico/condição médica, só o suficiente
-- pra equipe se organizar (ex: "afastamento médico", sem detalhar qual).
-- Serve de "guarda-chuva" para as atividades enviadas durante a ausência,
-- em atividades_afastamento.
CREATE TABLE IF NOT EXISTS afastamentos_saude (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    data_inicio TEXT NOT NULL,
    data_fim TEXT,
    motivo TEXT,
    observacoes TEXT,
    criado_por TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS atividades_afastamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    afastamento_id INTEGER NOT NULL REFERENCES afastamentos_saude(id) ON DELETE CASCADE,
    disciplina TEXT,
    titulo TEXT NOT NULL,
    descricao TEXT,
    data_envio TEXT NOT NULL,
    enviado_por TEXT,
    status TEXT NOT NULL DEFAULT 'enviada' CHECK (status IN ('enviada','entregue','pendente')),
    data_entrega TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Turno de cada turma (Manhã/Tarde/Integral) — usado só pra organizar o
-- painel principal em seções; configurado manualmente pela equipe porque
-- não tem como deduzir com certeza a partir dos dados importados.
CREATE TABLE IF NOT EXISTS turma_turno (
    turma TEXT PRIMARY KEY,
    turno TEXT NOT NULL CHECK (turno IN ('Manhã','Tarde','Integral')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_students_turma ON students(turma);
CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id);
CREATE INDEX IF NOT EXISTS idx_staging_lote ON grades_staging(lote_id);
CREATE INDEX IF NOT EXISTS idx_historico_manual_student ON historico_manual(student_id);
CREATE INDEX IF NOT EXISTS idx_atendimentos_data ON atendimentos(data_hora);
CREATE INDEX IF NOT EXISTS idx_atendimentos_student ON atendimentos(student_id);
CREATE INDEX IF NOT EXISTS idx_afastamentos_student ON afastamentos_saude(student_id);
CREATE INDEX IF NOT EXISTS idx_atividades_afastamento ON atividades_afastamento(afastamento_id);
"""


# ---------------------------------------------------------------- MySQL ----
SCHEMA_MYSQL = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    setor VARCHAR(100),
    papel VARCHAR(20) NOT NULL CHECK (papel IN ('admin','professor','aee','secretaria')),
    ativo TINYINT(1) NOT NULL DEFAULT 1,
    rg VARCHAR(30),
    nome_completo_declaracao VARCHAR(150),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo_interno VARCHAR(50) UNIQUE,
    nis VARCHAR(20),
    bolsa_familia TINYINT(1) NOT NULL DEFAULT 0,
    ra_prodesp VARCHAR(50),
    inep VARCHAR(50),
    nome VARCHAR(150) NOT NULL,
    nome_social VARCHAR(150),
    filiacao1 VARCHAR(150),
    data_nascimento VARCHAR(20),
    turma VARCHAR(10) NOT NULL,
    serie VARCHAR(30),
    situacao VARCHAR(30),
    foto_path VARCHAR(255),
    guardian_token_hash VARCHAR(64),
    aee TINYINT(1) NOT NULL DEFAULT 0,
    rg VARCHAR(30),
    certidao_nascimento VARCHAR(60),
    municipio_nascimento VARCHAR(150),
    recomendacoes TEXT,
    alteracoes_pendentes TEXT,
    data_transferencia VARCHAR(20),
    estado_nascimento VARCHAR(60),
    nacionalidade VARCHAR(60),
    rg_data_expedicao VARCHAR(20),
    rg_orgao_expedidor VARCHAR(60),
    rg_estado_emissor VARCHAR(2),
    certidao_numero VARCHAR(60),
    certidao_folha VARCHAR(20),
    certidao_livro VARCHAR(20),
    certidao_distrito_municipio VARCHAR(150),
    certidao_uf VARCHAR(2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS aee_info (
    student_id INT PRIMARY KEY,
    eol VARCHAR(50),
    laudo TEXT,
    observacoes TEXT,
    deficiencia VARCHAR(150),
    turno VARCHAR(30),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS grades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    ano INT NOT NULL,
    bimestre INT NOT NULL,
    disciplina VARCHAR(150) NOT NULL,
    faltas INT,
    compensacoes INT,
    frequencia FLOAT,
    conceito VARCHAR(10),
    situacao_conselho VARCHAR(30),
    origem VARCHAR(30) DEFAULT 'importado',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_nota (student_id, ano, bimestre, disciplina),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS access_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo VARCHAR(20) NOT NULL,
    referencia VARCHAR(150),
    acao VARCHAR(50) NOT NULL,
    ip VARCHAR(45),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS import_lotes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    arquivo VARCHAR(255),
    ano INT NOT NULL,
    bimestre INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','confirmado','descartado')),
    criado_por VARCHAR(150),
    total_alunos INT DEFAULT 0,
    total_nao_localizados INT DEFAULT 0,
    total_gravado INT DEFAULT 0,
    processando TINYINT(1) NOT NULL DEFAULT 0,
    erro_mensagem TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmado_em TIMESTAMP NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS grades_staging (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lote_id INT NOT NULL,
    aluno_key VARCHAR(255) NOT NULL,
    turma_pdf VARCHAR(10),
    nome_pdf VARCHAR(150),
    student_id INT,
    disciplina VARCHAR(150) NOT NULL,
    faltas INT,
    compensacoes INT,
    frequencia FLOAT,
    conceito VARCHAR(10),
    situacao_conselho VARCHAR(30),
    incluir TINYINT(1) NOT NULL DEFAULT 1,
    FOREIGN KEY (lote_id) REFERENCES import_lotes(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS historico_manual (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    serie VARCHAR(30) NOT NULL,
    disciplina VARCHAR(150) NOT NULL,
    resultado VARCHAR(30),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_historico_manual (student_id, serie, disciplina),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS configuracoes (
    chave VARCHAR(100) PRIMARY KEY,
    valor TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sptrans_turma_codigo (
    turma VARCHAR(10) PRIMARY KEY,
    codigo_curso VARCHAR(30),
    codigo_turma VARCHAR(30),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS turma_turno (
    turma VARCHAR(10) PRIMARY KEY,
    turno VARCHAR(10) NOT NULL CHECK (turno IN ('Manhã','Tarde','Integral')),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sptrans_dados_aluno (
    student_id INT PRIMARY KEY,
    cpf VARCHAR(20),
    rg_numero VARCHAR(20),
    rg_digito VARCHAR(5),
    rg_uf VARCHAR(2),
    cep VARCHAR(12),
    endereco_numero VARCHAR(20),
    endereco_complemento VARCHAR(100),
    telefone VARCHAR(20),
    email VARCHAR(150),
    nome_responsavel VARCHAR(150),
    tipo_gratuidade VARCHAR(5) NOT NULL DEFAULT '0',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contatos_responsaveis (
    student_id INT PRIMARY KEY,
    telefone_filiacao1 VARCHAR(20),
    telefone_filiacao2 VARCHAR(20),
    responsavel_legal VARCHAR(150),
    telefone_recados VARCHAR(20),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS frequencia_mensal (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    ano INT NOT NULL,
    mes INT NOT NULL,
    faltas INT,
    motivo VARCHAR(255),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_frequencia (student_id, ano, mes),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS dias_letivos_mensais (
    ano INT NOT NULL,
    mes INT NOT NULL,
    dias_letivos INT NOT NULL,
    PRIMARY KEY (ano, mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS teg_alunos (
    student_id INT PRIMARY KEY,
    turno VARCHAR(30),
    motivo_codigo INT,
    motivo_descricao VARCHAR(255),
    distancia_metros INT,
    cadeirante VARCHAR(5),
    tipo_logradouro VARCHAR(30),
    logradouro VARCHAR(150),
    numero_endereco VARCHAR(20),
    complemento VARCHAR(100),
    bairro VARCHAR(150),
    cep VARCHAR(15),
    placa_veiculo VARCHAR(15),
    nome_condutor VARCHAR(150),
    capacidade_veiculo INT,
    barreira_fisica VARCHAR(255),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS teg_condutores (
    nome_condutor VARCHAR(150) PRIMARY KEY,
    telefone VARCHAR(20),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS arquivo_morto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    letra VARCHAR(2) NOT NULL,
    numero VARCHAR(20),
    nome VARCHAR(150) NOT NULL,
    data_nascimento VARCHAR(20),
    student_id INT,
    origem VARCHAR(15) NOT NULL DEFAULT 'importado' CHECK (origem IN ('importado', 'transferencia', 'manual')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL,
    INDEX idx_arquivo_morto_letra (letra)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cursos_recomendados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    descricao TEXT,
    url VARCHAR(500),
    ciclo VARCHAR(20) NOT NULL CHECK (ciclo IN ('Alfabetização','Interdisciplinar','Autoral')),
    fonte VARCHAR(150),
    ativo TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS atendimentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_hora DATETIME NOT NULL,
    student_id INT,
    nome_responsavel VARCHAR(150) NOT NULL,
    telefone_contato VARCHAR(20),
    assunto VARCHAR(255) NOT NULL,
    observacoes TEXT,
    responsavel_atendimento VARCHAR(150),
    status VARCHAR(15) NOT NULL DEFAULT 'agendado' CHECK (status IN ('agendado','realizado','cancelado','faltou')),
    criado_por VARCHAR(150),
    atendido_por VARCHAR(150),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS afastamentos_saude (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE,
    motivo TEXT,
    observacoes TEXT,
    criado_por VARCHAR(150),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS atividades_afastamento (
    id INT AUTO_INCREMENT PRIMARY KEY,
    afastamento_id INT NOT NULL,
    disciplina VARCHAR(150),
    titulo VARCHAR(255) NOT NULL,
    descricao TEXT,
    data_envio DATE NOT NULL,
    enviado_por VARCHAR(150),
    status VARCHAR(15) NOT NULL DEFAULT 'enviada' CHECK (status IN ('enviada','entregue','pendente')),
    data_entrega DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (afastamento_id) REFERENCES afastamentos_saude(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS turma_turno (
    turma VARCHAR(10) PRIMARY KEY,
    turno VARCHAR(10) NOT NULL CHECK (turno IN ('Manhã','Tarde','Integral')),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

_INDICES_MYSQL = [
    "CREATE INDEX idx_students_turma ON students(turma)",
    "CREATE INDEX idx_grades_student ON grades(student_id)",
    "CREATE INDEX idx_staging_lote ON grades_staging(lote_id)",
    "CREATE INDEX idx_historico_manual_student ON historico_manual(student_id)",
    "CREATE INDEX idx_atendimentos_data ON atendimentos(data_hora)",
    "CREATE INDEX idx_atendimentos_student ON atendimentos(student_id)",
    "CREATE INDEX idx_afastamentos_student ON afastamentos_saude(student_id)",
    "CREATE INDEX idx_atividades_afastamento ON atividades_afastamento(afastamento_id)",
    "CREATE INDEX idx_frequencia_student ON frequencia_mensal(student_id)",
]


# --------------------------------------------------------- camada comum ----
class _MySQLConn:
    """Faz uma conexão pymysql se comportar como uma sqlite3.Connection o
    suficiente para o resto do código não precisar saber qual banco está
    em uso: aceita "?" como placeholder (convertido para "%s") e devolve
    linhas com acesso por chave — igual ao sqlite3.Row."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(sql.replace("?", "%s"), params)
        return cur

    def executescript(self, sql):
        cur = self._conn.cursor()
        for stmt in filter(None, (s.strip() for s in sql.split(";"))):
            cur.execute(stmt)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


@contextmanager
def get_db():
    if config.DB_BACKEND == "mysql":
        import pymysql
        import pymysql.cursors

        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        db = _MySQLConn(conn)
    else:
        Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        db = conn
    try:
        yield db
        db.commit()
    finally:
        db.close()


def _migrar_import_lotes(db):
    """Bancos criados antes do processamento em segundo plano não têm essas
    colunas — adiciona de forma idempotente, sem mexer no CHECK de status
    (evita ter que recriar a tabela em produção)."""
    if config.DB_BACKEND == "mysql":
        cols = {r["Field"] for r in db.execute("SHOW COLUMNS FROM import_lotes").fetchall()}
        if "processando" not in cols:
            db.execute("ALTER TABLE import_lotes ADD COLUMN processando TINYINT(1) NOT NULL DEFAULT 0")
        if "erro_mensagem" not in cols:
            db.execute("ALTER TABLE import_lotes ADD COLUMN erro_mensagem TEXT")
    else:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(import_lotes)")}
        if "processando" not in cols:
            db.execute("ALTER TABLE import_lotes ADD COLUMN processando INTEGER NOT NULL DEFAULT 0")
        if "erro_mensagem" not in cols:
            db.execute("ALTER TABLE import_lotes ADD COLUMN erro_mensagem TEXT")


def _migrar_students_historico(db):
    """Bancos criados antes dos campos de documento/histórico manual (e,
    depois, recomendações/pendências cadastrais/transferência/cabeçalho
    completo do histórico) não têm essas colunas — adiciona de forma
    idempotente."""
    if config.DB_BACKEND == "mysql":
        cols = {r["Field"] for r in db.execute("SHOW COLUMNS FROM students").fetchall()}
        for coluna, tipo in (
            ("rg", "VARCHAR(30)"), ("certidao_nascimento", "VARCHAR(60)"),
            ("municipio_nascimento", "VARCHAR(150)"),
            ("recomendacoes", "TEXT"), ("alteracoes_pendentes", "TEXT"),
            ("data_transferencia", "VARCHAR(20)"),
            ("estado_nascimento", "VARCHAR(60)"), ("nacionalidade", "VARCHAR(60)"),
            ("rg_data_expedicao", "VARCHAR(20)"), ("rg_orgao_expedidor", "VARCHAR(60)"),
            ("rg_estado_emissor", "VARCHAR(2)"), ("certidao_numero", "VARCHAR(60)"),
            ("certidao_folha", "VARCHAR(20)"), ("certidao_livro", "VARCHAR(20)"),
            ("certidao_distrito_municipio", "VARCHAR(150)"), ("certidao_uf", "VARCHAR(2)"),
            ("nome_social", "VARCHAR(150)"),
        ):
            if coluna not in cols:
                db.execute(f"ALTER TABLE students ADD COLUMN {coluna} {tipo}")
    else:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(students)")}
        for coluna in (
            "rg", "certidao_nascimento", "municipio_nascimento",
            "recomendacoes", "alteracoes_pendentes",
            "data_transferencia",
            "estado_nascimento", "nacionalidade", "rg_data_expedicao",
            "rg_orgao_expedidor", "rg_estado_emissor", "certidao_numero",
            "certidao_folha", "certidao_livro", "certidao_distrito_municipio",
            "certidao_uf", "nome_social",
        ):
            if coluna not in cols:
                db.execute(f"ALTER TABLE students ADD COLUMN {coluna} TEXT")


def _migrar_atendimentos(db):
    """Bancos criados antes do campo 'responsavel_atendimento' (quem da
    equipe vai conduzir o atendimento) não têm essa coluna."""
    if config.DB_BACKEND == "mysql":
        cols = {r["Field"] for r in db.execute("SHOW COLUMNS FROM atendimentos").fetchall()}
        if "responsavel_atendimento" not in cols:
            db.execute("ALTER TABLE atendimentos ADD COLUMN responsavel_atendimento VARCHAR(150)")
    else:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(atendimentos)")}
        if "responsavel_atendimento" not in cols:
            db.execute("ALTER TABLE atendimentos ADD COLUMN responsavel_atendimento TEXT")


def _migrar_students_bolsa_familia(db):
    """Bancos criados antes da aba Bolsa Família não têm 'nis'/'bolsa_familia'
    em students — adiciona de forma idempotente."""
    if config.DB_BACKEND == "mysql":
        cols = {r["Field"] for r in db.execute("SHOW COLUMNS FROM students").fetchall()}
        if "nis" not in cols:
            db.execute("ALTER TABLE students ADD COLUMN nis VARCHAR(20)")
        if "bolsa_familia" not in cols:
            db.execute("ALTER TABLE students ADD COLUMN bolsa_familia TINYINT(1) NOT NULL DEFAULT 0")
    else:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(students)")}
        if "nis" not in cols:
            db.execute("ALTER TABLE students ADD COLUMN nis TEXT")
        if "bolsa_familia" not in cols:
            db.execute("ALTER TABLE students ADD COLUMN bolsa_familia INTEGER NOT NULL DEFAULT 0")


def _migrar_users_declaracao(db):
    """Bancos criados antes da aba Declaração de Matrícula não têm 'rg'/
    'nome_completo_declaracao' em users — adiciona de forma idempotente."""
    if config.DB_BACKEND == "mysql":
        cols = {r["Field"] for r in db.execute("SHOW COLUMNS FROM users").fetchall()}
        if "rg" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN rg VARCHAR(30)")
        if "nome_completo_declaracao" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN nome_completo_declaracao VARCHAR(150)")
    else:
        cols = {r["name"] for r in db.execute("PRAGMA table_info(users)")}
        if "rg" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN rg TEXT")
        if "nome_completo_declaracao" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN nome_completo_declaracao TEXT")


def _migrar_arquivo_morto_manual(db):
    """Bancos criados antes da inserção manual no Arquivo Morto têm o
    CHECK de 'origem' sem 'manual'. MySQL aceita ALTER de CHECK
    diretamente; SQLite não permite alterar CHECK via ALTER TABLE, então
    a tabela precisa ser recriada preservando os dados (idempotente: só
    mexe se o CHECK salvo ainda não incluir 'manual')."""
    if config.DB_BACKEND == "mysql":
        try:
            db.execute("ALTER TABLE arquivo_morto DROP CHECK arquivo_morto_chk_1")
        except Exception:
            pass
        try:
            db.execute(
                "ALTER TABLE arquivo_morto ADD CONSTRAINT arquivo_morto_origem_chk "
                "CHECK (origem IN ('importado', 'transferencia', 'manual'))"
            )
        except Exception:
            pass
        return

    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='arquivo_morto'"
    ).fetchone()
    if not row or not row["sql"] or "'manual'" in row["sql"]:
        return
    db.execute("ALTER TABLE arquivo_morto RENAME TO arquivo_morto_old")
    db.execute("""
        CREATE TABLE arquivo_morto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            letra TEXT NOT NULL,
            numero TEXT,
            nome TEXT NOT NULL,
            data_nascimento TEXT,
            student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
            origem TEXT NOT NULL DEFAULT 'importado' CHECK (origem IN ('importado', 'transferencia', 'manual')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    db.execute(
        """INSERT INTO arquivo_morto (id, letra, numero, nome, data_nascimento, student_id, origem, created_at)
           SELECT id, letra, numero, nome, data_nascimento, student_id, origem, created_at FROM arquivo_morto_old"""
    )
    db.execute("DROP TABLE arquivo_morto_old")
    db.execute("CREATE INDEX IF NOT EXISTS idx_arquivo_morto_letra ON arquivo_morto(letra)")


def init_db():
    with get_db() as db:
        if config.DB_BACKEND == "mysql":
            db.executescript(SCHEMA_MYSQL)
            for sql in _INDICES_MYSQL:
                try:
                    db.execute(sql)
                except Exception as e:  # índice já existe em execuções anteriores
                    if "1061" not in str(e) and "Duplicate" not in str(e):
                        raise
        else:
            db.executescript(SCHEMA_SQLITE)
        _migrar_import_lotes(db)
        _migrar_students_historico(db)
        _migrar_atendimentos(db)
        _migrar_students_bolsa_familia(db)
        _migrar_users_declaracao(db)
        _migrar_arquivo_morto_manual(db)


# ------------------------------------------------------- upserts portáveis
# MySQL e SQLite têm sintaxes diferentes de "insere ou atualiza"
# (ON DUPLICATE KEY UPDATE vs. ON CONFLICT ... DO UPDATE). Em vez de manter
# duas versões de cada query, fazemos o padrão check-then-write em Python,
# que funciona igual nos dois bancos.
def salvar_aee_info(db, student_id, eol, laudo, observacoes, deficiencia, turno):
    existente = db.execute(
        "SELECT student_id FROM aee_info WHERE student_id = ?", (student_id,)
    ).fetchone()
    if existente:
        db.execute(
            """UPDATE aee_info SET eol=?, laudo=?, observacoes=?, deficiencia=?, turno=?, updated_at=?
               WHERE student_id=?""",
            (eol, laudo, observacoes, deficiencia, turno, agora(), student_id),
        )
    else:
        db.execute(
            """INSERT INTO aee_info (student_id, eol, laudo, observacoes, deficiencia, turno, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (student_id, eol, laudo, observacoes, deficiencia, turno, agora()),
        )


def salvar_nota(db, student_id, ano, bimestre, disciplina, faltas, compensacoes,
                 frequencia, conceito, situacao_conselho, origem):
    existente = db.execute(
        "SELECT id FROM grades WHERE student_id=? AND ano=? AND bimestre=? AND disciplina=?",
        (student_id, ano, bimestre, disciplina),
    ).fetchone()
    if existente:
        db.execute(
            """UPDATE grades SET faltas=?, compensacoes=?, frequencia=?, conceito=?,
                 situacao_conselho=?, origem=?, updated_at=? WHERE id=?""",
            (faltas, compensacoes, frequencia, conceito, situacao_conselho, origem,
             agora(), existente["id"]),
        )
    else:
        db.execute(
            """INSERT INTO grades (student_id, ano, bimestre, disciplina, faltas, compensacoes,
                 frequencia, conceito, situacao_conselho, origem, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (student_id, ano, bimestre, disciplina, faltas, compensacoes, frequencia,
             conceito, situacao_conselho, origem, agora()),
        )


def salvar_frequencia_mensal(db, student_id, ano, mes, faltas, motivo):
    existente = db.execute(
        "SELECT id FROM frequencia_mensal WHERE student_id=? AND ano=? AND mes=?",
        (student_id, ano, mes),
    ).fetchone()
    if existente:
        db.execute(
            "UPDATE frequencia_mensal SET faltas=?, motivo=?, updated_at=? WHERE id=?",
            (faltas, motivo, agora(), existente["id"]),
        )
    else:
        db.execute(
            """INSERT INTO frequencia_mensal (student_id, ano, mes, faltas, motivo, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (student_id, ano, mes, faltas, motivo, agora()),
        )


def salvar_dias_letivos(db, ano, mes, dias_letivos):
    existente = db.execute(
        "SELECT ano FROM dias_letivos_mensais WHERE ano=? AND mes=?", (ano, mes)
    ).fetchone()
    if existente:
        db.execute(
            "UPDATE dias_letivos_mensais SET dias_letivos=? WHERE ano=? AND mes=?",
            (dias_letivos, ano, mes),
        )
    else:
        db.execute(
            "INSERT INTO dias_letivos_mensais (ano, mes, dias_letivos) VALUES (?,?,?)",
            (ano, mes, dias_letivos),
        )


def get_config(db, chave, padrao=None):
    row = db.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
    return row["valor"] if row and row["valor"] is not None else padrao


def set_config(db, chave, valor):
    existente = db.execute("SELECT chave FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
    if existente:
        db.execute("UPDATE configuracoes SET valor=?, updated_at=? WHERE chave=?", (valor, agora(), chave))
    else:
        db.execute("INSERT INTO configuracoes (chave, valor, updated_at) VALUES (?,?,?)", (chave, valor, agora()))


def salvar_sptrans_turma_codigo(db, turma, codigo_curso, codigo_turma):
    existente = db.execute("SELECT turma FROM sptrans_turma_codigo WHERE turma = ?", (turma,)).fetchone()
    if existente:
        db.execute(
            "UPDATE sptrans_turma_codigo SET codigo_curso=?, codigo_turma=?, updated_at=? WHERE turma=?",
            (codigo_curso, codigo_turma, agora(), turma),
        )
    else:
        db.execute(
            "INSERT INTO sptrans_turma_codigo (turma, codigo_curso, codigo_turma, updated_at) VALUES (?,?,?,?)",
            (turma, codigo_curso, codigo_turma, agora()),
        )


def salvar_turma_turno(db, turma, turno):
    """turno=None apaga a configuração (turma volta a ficar sem turno
    definido, em vez de gravar um valor inválido)."""
    if not turno:
        db.execute("DELETE FROM turma_turno WHERE turma = ?", (turma,))
        return
    existente = db.execute("SELECT turma FROM turma_turno WHERE turma = ?", (turma,)).fetchone()
    if existente:
        db.execute("UPDATE turma_turno SET turno=?, updated_at=? WHERE turma=?", (turno, agora(), turma))
    else:
        db.execute(
            "INSERT INTO turma_turno (turma, turno, updated_at) VALUES (?,?,?)", (turma, turno, agora())
        )


def salvar_turma_turno(db, turma, turno):
    """turno: 'Manhã', 'Tarde' ou 'Integral'; passe None pra apagar a
    configuração (turma volta a aparecer em 'Sem turno definido')."""
    existente = db.execute("SELECT turma FROM turma_turno WHERE turma = ?", (turma,)).fetchone()
    if not turno:
        if existente:
            db.execute("DELETE FROM turma_turno WHERE turma = ?", (turma,))
        return
    if existente:
        db.execute("UPDATE turma_turno SET turno=?, updated_at=? WHERE turma=?", (turno, agora(), turma))
    else:
        db.execute(
            "INSERT INTO turma_turno (turma, turno, updated_at) VALUES (?,?,?)", (turma, turno, agora())
        )


def salvar_sptrans_dados_aluno(db, student_id, **campos):
    """campos aceitos: cpf, rg_numero, rg_digito, rg_uf, cep, endereco_numero,
    endereco_complemento, telefone, email, nome_responsavel, tipo_gratuidade"""
    existente = db.execute(
        "SELECT student_id FROM sptrans_dados_aluno WHERE student_id = ?", (student_id,)
    ).fetchone()
    colunas = [
        "cpf", "rg_numero", "rg_digito", "rg_uf", "cep", "endereco_numero",
        "endereco_complemento", "telefone", "email", "nome_responsavel", "tipo_gratuidade",
    ]
    valores = [campos.get(c) for c in colunas]
    if valores[colunas.index("tipo_gratuidade")] is None:
        valores[colunas.index("tipo_gratuidade")] = "0"
    if existente:
        db.execute(
            f"""UPDATE sptrans_dados_aluno SET {', '.join(f'{c}=?' for c in colunas)}, updated_at=?
                WHERE student_id=?""",
            valores + [agora(), student_id],
        )
    else:
        db.execute(
            f"""INSERT INTO sptrans_dados_aluno (student_id, {', '.join(colunas)}, updated_at)
                VALUES (?, {', '.join(['?'] * len(colunas))}, ?)""",
            [student_id] + valores + [agora()],
        )


def salvar_contato_responsavel(db, student_id, **campos):
    """campos aceitos: telefone_filiacao1, telefone_filiacao2, responsavel_legal,
    telefone_recados"""
    existente = db.execute(
        "SELECT student_id FROM contatos_responsaveis WHERE student_id = ?", (student_id,)
    ).fetchone()
    colunas = ["telefone_filiacao1", "telefone_filiacao2", "responsavel_legal", "telefone_recados"]
    valores = [campos.get(c) for c in colunas]
    if existente:
        db.execute(
            f"""UPDATE contatos_responsaveis SET {', '.join(f'{c}=?' for c in colunas)}, updated_at=?
                WHERE student_id=?""",
            valores + [agora(), student_id],
        )
    else:
        db.execute(
            f"""INSERT INTO contatos_responsaveis (student_id, {', '.join(colunas)}, updated_at)
                VALUES (?, {', '.join(['?'] * len(colunas))}, ?)""",
            [student_id] + valores + [agora()],
        )


TEG_COLUNAS = [
    "turno", "motivo_codigo", "motivo_descricao", "distancia_metros", "cadeirante",
    "tipo_logradouro", "logradouro", "numero_endereco", "complemento", "bairro", "cep",
    "placa_veiculo", "nome_condutor", "capacidade_veiculo", "barreira_fisica",
]


def salvar_teg_aluno(db, student_id, **campos):
    """campos aceitos: ver TEG_COLUNAS."""
    existente = db.execute(
        "SELECT student_id FROM teg_alunos WHERE student_id = ?", (student_id,)
    ).fetchone()
    valores = [campos.get(c) for c in TEG_COLUNAS]
    if existente:
        db.execute(
            f"""UPDATE teg_alunos SET {', '.join(f'{c}=?' for c in TEG_COLUNAS)}, updated_at=?
                WHERE student_id=?""",
            valores + [agora(), student_id],
        )
    else:
        db.execute(
            f"""INSERT INTO teg_alunos (student_id, {', '.join(TEG_COLUNAS)}, updated_at)
                VALUES (?, {', '.join(['?'] * len(TEG_COLUNAS))}, ?)""",
            [student_id] + valores + [agora()],
        )


def salvar_teg_condutor_telefone(db, nome_condutor, telefone):
    existente = db.execute(
        "SELECT nome_condutor FROM teg_condutores WHERE nome_condutor = ?", (nome_condutor,)
    ).fetchone()
    if existente:
        db.execute(
            "UPDATE teg_condutores SET telefone=?, updated_at=? WHERE nome_condutor=?",
            (telefone, agora(), nome_condutor),
        )
    else:
        db.execute(
            "INSERT INTO teg_condutores (nome_condutor, telefone, updated_at) VALUES (?,?,?)",
            (nome_condutor, telefone, agora()),
        )


def _arquivo_morto_duplicado(db, letra, nome, data_nascimento):
    """Considera duplicado um registro já existente na mesma letra com o
    mesmo nome (sem diferenciar maiúscula/espaço) — e, quando alguma das
    duas datas de nascimento existir, só se elas também baterem (nome
    igual com nascimento diferente pode ser gente diferente; nome igual
    sem nascimento nos dois lados é tratado como o mesmo registro)."""
    nome_norm = nome.strip().upper()
    candidatos = db.execute(
        "SELECT data_nascimento FROM arquivo_morto WHERE letra = ? AND UPPER(TRIM(nome)) = ?",
        (letra, nome_norm),
    ).fetchall()
    for c in candidatos:
        if not c["data_nascimento"] or not data_nascimento or c["data_nascimento"] == data_nascimento:
            return True
    return False


def _proximo_numero_arquivo_morto(db, letra):
    numeros = db.execute("SELECT numero FROM arquivo_morto WHERE letra = ?", (letra,)).fetchall()
    maior_numero = 0
    for linha in numeros:
        try:
            maior_numero = max(maior_numero, int(linha["numero"]))
        except (TypeError, ValueError):
            continue
    return maior_numero + 1 if numeros else 1


def adicionar_ao_arquivo_morto(db, student_id, nome, data_nascimento):
    """Chamada quando um aluno é marcado como transferido — entra no
    arquivo morto automaticamente, no fim da letra correspondente (a
    letra vem da primeira letra do nome, igual à organização em abas
    do arquivo em planilha original). Devolve False sem inserir nada se
    esse aluno já constar no arquivo morto (ex: foi reativado e
    transferido de novo) — quem chama decide como avisar disso."""
    nome = (nome or "").strip()
    if not nome:
        return True
    letra = nome[0].upper()
    if _arquivo_morto_duplicado(db, letra, nome, data_nascimento):
        return False

    proximo_numero = _proximo_numero_arquivo_morto(db, letra)
    db.execute(
        """INSERT INTO arquivo_morto (letra, numero, nome, data_nascimento, student_id, origem)
           VALUES (?,?,?,?,?,'transferencia')""",
        (letra, str(proximo_numero), nome, data_nascimento, student_id),
    )
    return True


def inserir_arquivo_morto_manual(db, nome, data_nascimento):
    """Inserção manual pela tela "Novo registro" do Arquivo Morto — mesma
    checagem de duplicidade de adicionar_ao_arquivo_morto. Devolve False
    sem inserir se já existir um registro equivalente."""
    nome = (nome or "").strip()
    if not nome:
        return False
    letra = nome[0].upper()
    if _arquivo_morto_duplicado(db, letra, nome, data_nascimento):
        return False

    proximo_numero = _proximo_numero_arquivo_morto(db, letra)
    db.execute(
        """INSERT INTO arquivo_morto (letra, numero, nome, data_nascimento, origem)
           VALUES (?,?,?,?,'manual')""",
        (letra, str(proximo_numero), nome, data_nascimento),
    )
    return True
