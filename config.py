import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _carregar_dotenv(caminho):
    """Loader simples de .env (evita depender do pacote python-dotenv)."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip())


_carregar_dotenv(BASE_DIR / ".env")

# Nunca comite o arquivo .env nem a pasta data/ com dados reais - veja README.md
SECRET_KEY = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")

# Chave exigida para criar um novo usuário ADMINISTRADOR pela tela de login
# (/login/criar-admin). Só quem tem acesso ao servidor (arquivo .env) consegue
# criar um admin — não existe cadastro público. Por padrão usa a própria
# SECRET_KEY para não exigir configuração extra, mas o recomendado em
# produção é definir ADMIN_SETUP_KEY com um valor PRÓPRIO e diferente da
# SECRET_KEY (que também assina a sessão de login) — assim é possível trocar
# uma sem invalidar a outra.
ADMIN_SETUP_KEY = os.environ.get("ADMIN_SETUP_KEY", SECRET_KEY)


# Em hospedagem na nuvem, o disco do próprio código costuma ser APAGADO a
# cada novo deploy/reinício — então o banco de dados e as fotos NÃO podem
# morar dentro da pasta do projeto nesse cenário. Configure ESCOLA_DATA_DIR
# apontando para um disco persistente (ex: Render Persistent Disk, volume do
# Railway/Fly.io) e tudo abaixo passa a morar lá automaticamente. Sem essa
# variável, continua tudo dentro do projeto — ótimo para uso local.
DATA_DIR = Path(os.environ.get("ESCOLA_DATA_DIR", str(BASE_DIR / "instance")))

# ------------------------------------------------------------- banco de dados
# DB_BACKEND = "sqlite" (padrão — zero configuração, ótimo para rodar local
# e para os testes automatizados) ou "mysql" (para o banco relacional do
# projeto integrador). Trocar de banco NÃO exige mudar nenhuma rota nem
# script — toda a diferença de sintaxe fica isolada em models.py.
DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").strip().lower()

DB_PATH = os.environ.get("ESCOLA_DB_PATH", str(DATA_DIR / "sistema_escolar.db"))

MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "sistema_escolar")

DATA_RAW_DIR = BASE_DIR / "data" / "raw"
TEMPLATES_DIR = BASE_DIR / "data" / "templates"
PHOTOS_DIR = DATA_DIR / "photos"
EXPORTS_DIR = DATA_DIR / "exports"
UPLOADS_DIR = DATA_DIR / "uploads"

ANO_LETIVO = int(os.environ.get("ESCOLA_ANO_LETIVO", "2026"))

# Papeis que podem ver o detalhe (laudo/observacoes) do cadastro AEE.
# Todos os papeis de staff veem o badge "AEE" no card do aluno; apenas estes
# veem o detalhe do laudo/diagnostico.
PAPEIS_COM_ACESSO_AEE_DETALHE = {"admin", "aee"}

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))            # fotos de alunos
MAX_PDF_UPLOAD_MB = int(os.environ.get("MAX_PDF_UPLOAD_MB", "150"))   # Atas Bimestrais em PDF (podem ter 150+ páginas e pesar bem mais que os arquivos de teste)

# Ligue isso (ESCOLA_FORCE_HTTPS=1) quando o sistema estiver atrás de HTTPS
# de verdade (qualquer hospedagem séria na internet). Isso faz o cookie de
# sessão só trafegar criptografado. Em desenvolvimento local (http://
# 127.0.0.1) deixe desligado, senão o login não funciona.
FORCE_HTTPS = os.environ.get("ESCOLA_FORCE_HTTPS", "0") == "1"

# Series/turmas disponiveis para importacao (usado no formulario de upload).
# Ajuste se a nomenclatura de turmas da sua rede for diferente.
SERIES_EF = [
    "1º Ano", "2º Ano", "3º Ano", "4º Ano", "5º Ano",
    "6º Ano", "7º Ano", "8º Ano", "9º Ano",
]

# Itens da barra lateral (menu) e seus rótulos — a ORDEM aqui é a
# ordem padrão de fábrica; admin pode reordenar em "Ordem do menu
# lateral" (fica salvo na tabela configuracoes, chave 'ordem_sidebar').
ORDEM_PADRAO_SIDEBAR = [
    "inicio", "importar_notas", "importar_alunos", "arquivo_morto",
]
ROTULOS_SIDEBAR = {
    "inicio": "Início",
    "importar_notas": "Importar notas",
    "importar_alunos": "Importar alunos",
    "arquivo_morto": "Arquivo Morto",
}
