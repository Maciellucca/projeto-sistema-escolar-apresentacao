"""
Testa o Arquivo Morto: importação (com idempotência), o registro
automático de alunos transferidos no fim da letra correspondente,
busca, e as gavetas por letra.
"""
import io

from openpyxl import Workbook


def _aluno(db, codigo, nome, turma="6A", serie="6º Ano", data_nascimento=None):
    return db.execute(
        "INSERT INTO students (codigo_interno, nome, turma, serie, situacao, data_nascimento) VALUES (?,?,?,?, 'ATIVO', ?)",
        (codigo, nome, turma, serie, data_nascimento),
    ).lastrowid


def _planilha_arquivo_morto(abas):
    """abas: {'A': [(numero, nome, data_nascimento), ...], ...} — sem cabeçalho."""
    wb = Workbook()
    primeira = True
    for letra, linhas in abas.items():
        ws = wb.active if primeira else wb.create_sheet()
        primeira = False
        ws.title = letra
        for numero, nome, data_nasc in linhas:
            ws.append([numero, nome, data_nasc])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_importacao_basica_por_letra(client, pegar_csrf, criar_admin):
    from models import get_db
    from datetime import datetime

    buf = _planilha_arquivo_morto({
        "A": [(1, "ANTONIO TESTE", datetime(1970, 1, 15)), (2, "ANA TESTE", datetime(1980, 6, 20))],
        "B": [(1, "BRUNO TESTE", datetime(1975, 3, 10))],
    })
    tok = pegar_csrf("/arquivo-morto/importar")
    resp = client.post(
        "/arquivo-morto/importar", data={"planilha": (buf, "am.xlsx"), "csrf_token": tok},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert "3" in resp.get_data(as_text=True)

    with get_db() as db:
        a = db.execute("SELECT * FROM arquivo_morto WHERE letra='A' AND numero='1'").fetchone()
        b = db.execute("SELECT * FROM arquivo_morto WHERE letra='B' AND numero='1'").fetchone()
    assert a["nome"] == "ANTONIO TESTE"
    assert a["data_nascimento"] == "1970-01-15"
    assert a["origem"] == "importado"
    assert b["nome"] == "BRUNO TESTE"


def test_linha_com_numero_mas_sem_nome_e_ignorada(client, pegar_csrf, criar_admin):
    from models import get_db

    wb = Workbook()
    ws = wb.active
    ws.title = "A"
    ws.append([1, "ANTONIO TESTE", None])
    ws.append([2, None, None])  # numero preenchido, nome vazio -> ignorar
    ws.append([3, "", None])  # nome so com espacos/vazio -> ignorar
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    tok = pegar_csrf("/arquivo-morto/importar")
    resp = client.post(
        "/arquivo-morto/importar", data={"planilha": (buf, "am.xlsx"), "csrf_token": tok},
        content_type="multipart/form-data",
    )
    assert "<strong>1</strong>" in resp.get_data(as_text=True)

    with get_db() as db:
        total = db.execute("SELECT COUNT(*) c FROM arquivo_morto").fetchone()["c"]
    assert total == 1


def test_importacao_e_idempotente(client, pegar_csrf, criar_admin):
    from models import get_db
    from datetime import datetime

    buf1 = _planilha_arquivo_morto({"A": [(1, "ANTONIO TESTE", datetime(1970, 1, 15))]})
    tok = pegar_csrf("/arquivo-morto/importar")
    client.post(
        "/arquivo-morto/importar", data={"planilha": (buf1, "am.xlsx"), "csrf_token": tok},
        content_type="multipart/form-data",
    )

    buf2 = _planilha_arquivo_morto({"A": [(1, "ANTONIO TESTE", datetime(1970, 1, 15))]})
    tok2 = pegar_csrf("/arquivo-morto/importar")
    resp = client.post(
        "/arquivo-morto/importar", data={"planilha": (buf2, "am.xlsx"), "csrf_token": tok2},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "<strong>0</strong>" in html
    assert "1" in html  # duplicados_ignorados

    with get_db() as db:
        total = db.execute("SELECT COUNT(*) c FROM arquivo_morto").fetchone()["c"]
    assert total == 1


def test_aluno_transferido_entra_no_fim_da_letra_correspondente(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "TR1", "CARLOS TESTE TRANSFERIDO", data_nascimento="2013-05-10")
        # já tem um registro C importado com número 30 — o novo tem que vir DEPOIS
        db.execute(
            "INSERT INTO arquivo_morto (letra, numero, nome, data_nascimento, origem) VALUES ('C','30','CAIO EXEMPLO ANTIGO','1990-01-01','importado')"
        )

    tok = pegar_csrf(f"/aluno/{aluno_id}/transferir")
    client.post(f"/aluno/{aluno_id}/transferir", data={"csrf_token": tok, "data_transferencia": "2026-09-20"})

    with get_db() as db:
        entrada = db.execute("SELECT * FROM arquivo_morto WHERE nome='CARLOS TESTE TRANSFERIDO'").fetchone()
    assert entrada is not None
    assert entrada["letra"] == "C"
    assert int(entrada["numero"]) > 30
    assert entrada["origem"] == "transferencia"
    assert entrada["student_id"] == aluno_id
    assert entrada["data_nascimento"] == "2013-05-10"


def test_primeira_letra_vazia_nao_gera_erro(client, pegar_csrf, criar_admin):
    """Reativar não deveria disparar nada no arquivo morto — só a
    transferência adiciona. Confirma que nenhum registro extra aparece
    numa letra qualquer quando não há transferência."""
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "TR2", "DANIEL TESTE NORMAL")

    with get_db() as db:
        total_antes = db.execute("SELECT COUNT(*) c FROM arquivo_morto").fetchone()["c"]
    assert total_antes == 0


def test_busca_encontra_e_abre_a_gaveta_certa(client, pegar_csrf, criar_admin):
    from models import get_db
    from datetime import datetime

    buf = _planilha_arquivo_morto({
        "A": [(1, "ANTONIO BUSCA TESTE", datetime(1970, 1, 15))],
        "B": [(1, "BRUNO OUTRO TESTE", datetime(1975, 3, 10))],
    })
    tok = pegar_csrf("/arquivo-morto/importar")
    client.post(
        "/arquivo-morto/importar", data={"planilha": (buf, "am.xlsx"), "csrf_token": tok},
        content_type="multipart/form-data",
    )

    resp = client.get("/arquivo-morto/?q=ANTONIO BUSCA")
    html = resp.get_data(as_text=True)
    assert "ANTONIO BUSCA TESTE" in html
    assert "BRUNO OUTRO TESTE" not in html


def test_index_mostra_todas_as_26_letras_com_contagem(client, pegar_csrf, criar_admin):
    from datetime import datetime

    buf = _planilha_arquivo_morto({"A": [(1, "ANTONIO TESTE", datetime(1970, 1, 15))]})
    tok = pegar_csrf("/arquivo-morto/importar")
    client.post(
        "/arquivo-morto/importar", data={"planilha": (buf, "am.xlsx"), "csrf_token": tok},
        content_type="multipart/form-data",
    )

    resp = client.get("/arquivo-morto/")
    html = resp.get_data(as_text=True)
    for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert f">{letra}<" in html
    assert "1 registro(s)" in html


def test_lista_fica_em_ordem_decrescente_por_recente(client, pegar_csrf, criar_admin):
    """Facilita achar quem entrou por último — o mais recente aparece
    primeiro na gaveta da letra, não no fim."""
    from datetime import datetime

    buf = _planilha_arquivo_morto({
        "A": [(1, "ANTONIO PRIMEIRO", datetime(1970, 1, 15)), (2, "AUGUSTO SEGUNDO", datetime(1971, 2, 16))],
    })
    tok = pegar_csrf("/arquivo-morto/importar")
    client.post(
        "/arquivo-morto/importar", data={"planilha": (buf, "am.xlsx"), "csrf_token": tok},
        content_type="multipart/form-data",
    )

    html = client.get("/arquivo-morto/").get_data(as_text=True)
    assert html.index("AUGUSTO SEGUNDO") < html.index("ANTONIO PRIMEIRO")


def test_novo_registro_manual_cria_entrada(client, pegar_csrf, criar_admin):
    from models import get_db

    tok = pegar_csrf("/arquivo-morto/novo")
    resp = client.post(
        "/arquivo-morto/novo",
        data={"csrf_token": tok, "nome": "Mariana Registro Manual", "data_nascimento": "1968-04-12"},
        follow_redirects=True,
    )
    assert "adicionado ao Arquivo Morto" in resp.get_data(as_text=True)

    with get_db() as db:
        entrada = db.execute("SELECT * FROM arquivo_morto WHERE nome='MARIANA REGISTRO MANUAL'").fetchone()
    assert entrada is not None
    assert entrada["origem"] == "manual"
    assert entrada["letra"] == "M"
    assert entrada["data_nascimento"] == "1968-04-12"


def test_novo_registro_manual_duplicado_mostra_erro(client, pegar_csrf, criar_admin):
    from models import get_db

    tok = pegar_csrf("/arquivo-morto/novo")
    client.post(
        "/arquivo-morto/novo",
        data={"csrf_token": tok, "nome": "Roberto Duplicado", "data_nascimento": "1972-09-01"},
    )

    tok2 = pegar_csrf("/arquivo-morto/novo")
    resp = client.post(
        "/arquivo-morto/novo",
        data={"csrf_token": tok2, "nome": "roberto duplicado", "data_nascimento": "1972-09-01"},
        follow_redirects=True,
    )
    assert "já consta no Arquivo Morto" in resp.get_data(as_text=True)

    with get_db() as db:
        total = db.execute("SELECT COUNT(*) c FROM arquivo_morto WHERE letra='R'").fetchone()["c"]
    assert total == 1


def test_transferir_aluno_ja_no_arquivo_morto_avisa_sem_duplicar(client, pegar_csrf, criar_admin):
    """Reativar e transferir de novo não deveria criar uma segunda
    entrada silenciosa — o usuário precisa ver que já existe."""
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "TR3", "FELIPE JA ARQUIVADO", data_nascimento="2012-03-03")
        db.execute(
            "INSERT INTO arquivo_morto (letra, numero, nome, data_nascimento, origem) "
            "VALUES ('F','1','FELIPE JA ARQUIVADO','2012-03-03','transferencia')"
        )

    tok = pegar_csrf(f"/aluno/{aluno_id}/transferir")
    resp = client.post(
        f"/aluno/{aluno_id}/transferir",
        data={"csrf_token": tok, "data_transferencia": "2026-09-20"},
        follow_redirects=True,
    )
    assert "já constava no Arquivo Morto" in resp.get_data(as_text=True)

    with get_db() as db:
        total = db.execute(
            "SELECT COUNT(*) c FROM arquivo_morto WHERE nome='FELIPE JA ARQUIVADO'"
        ).fetchone()["c"]
    assert total == 1


def test_professor_nao_acessa_arquivo_morto(client, pegar_csrf, criar_admin):
    from models import get_db
    from auth import hash_password

    with get_db() as db:
        db.execute(
            "INSERT INTO users (username, password_hash, nome, setor, papel) VALUES (?,?,?,?,?)",
            ("prof12", hash_password("senha-professor-888"), "Professor Doze", "Sala", "professor"),
        )
    tok = pegar_csrf("/login")
    client.post("/login", data={"username": "prof12", "senha": "senha-professor-888", "csrf_token": tok})

    resp = client.get("/arquivo-morto/")
    assert resp.status_code == 403
