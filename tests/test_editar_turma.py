"""
Testa a edição de turma do aluno (usada sobretudo pra corrigir a turma
provisória 'TEG-PROV'), incluindo a correção em lote na tela da turma e
o desaparecimento automático da TEG-PROV do painel principal assim que
ninguém mais estiver nela.
"""


def _aluno(db, codigo, nome, turma="6A", serie="6º Ano"):
    return db.execute(
        "INSERT INTO students (codigo_interno, nome, turma, serie, situacao) VALUES (?,?,?,?, 'ATIVO')",
        (codigo, nome, turma, serie),
    ).lastrowid


def test_link_editar_turma_aparece_na_pagina_do_aluno(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "ET1", "ALUNO TESTE TURMA")

    resp = client.get(f"/aluno/{aluno_id}")
    assert "Editar turma" in resp.get_data(as_text=True)


def test_corrigir_turma_de_aluno_provisorio(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "ET2", "ALUNO PROVISORIO TESTE", turma="TEG-PROV", serie="7º Ano")

    tok = pegar_csrf(f"/aluno/{aluno_id}/turma")
    resp = client.post(
        f"/aluno/{aluno_id}/turma",
        data={"csrf_token": tok, "turma": "7a", "serie": "7º Ano"},
        follow_redirects=True,
    )
    assert "atualizada" in resp.get_data(as_text=True).lower()

    with get_db() as db:
        aluno = db.execute("SELECT turma FROM students WHERE id=?", (aluno_id,)).fetchone()
    assert aluno["turma"] == "7A"  # maiuscula


def test_turma_vazia_mostra_erro(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "ET3", "ALUNO TESTE 3", turma="TEG-PROV")

    tok = pegar_csrf(f"/aluno/{aluno_id}/turma")
    resp = client.post(
        f"/aluno/{aluno_id}/turma",
        data={"csrf_token": tok, "turma": "", "serie": ""},
        follow_redirects=True,
    )
    assert "não pode ficar em branco" in resp.get_data(as_text=True)

    with get_db() as db:
        aluno = db.execute("SELECT turma FROM students WHERE id=?", (aluno_id,)).fetchone()
    assert aluno["turma"] == "TEG-PROV"


def test_teg_prov_mostra_tela_de_correcao_em_lote(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        _aluno(db, "ET4", "ALUNO LOTE UM", turma="TEG-PROV", serie="6º Ano")
        _aluno(db, "ET5", "ALUNO LOTE DOIS", turma="TEG-PROV", serie="8º Ano")

    resp = client.get("/turma/TEG-PROV")
    html = resp.get_data(as_text=True)
    assert "ALUNO LOTE UM" in html
    assert "ALUNO LOTE DOIS" in html
    assert "Nova turma" in html
    assert "Turma provisória" in html


def test_corrigir_via_tela_de_lote_redireciona_de_volta_e_remove_da_lista(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "ET6", "ALUNO LOTE TRES", turma="TEG-PROV", serie="9º Ano")
        _aluno(db, "ET7", "ALUNO LOTE QUATRO", turma="TEG-PROV", serie="5º Ano")

    tok = pegar_csrf("/turma/TEG-PROV")
    client.post(
        f"/aluno/{aluno_id}/turma",
        data={"csrf_token": tok, "turma": "9A", "serie": "9º Ano", "next": "turma_atual"},
        follow_redirects=True,
    )
    client.get("/")  # consome a flash message pendente antes de checar a lista

    resp = client.get("/turma/TEG-PROV")
    html = resp.get_data(as_text=True)
    assert "ALUNO LOTE TRES" not in html
    assert "ALUNO LOTE QUATRO" in html


def test_teg_prov_some_do_painel_quando_todos_forem_corrigidos(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "ET8", "ALUNO ULTIMO PROVISORIO", turma="TEG-PROV", serie="4º Ano")

    resp_antes = client.get("/")
    assert "TEG-PROV" in resp_antes.get_data(as_text=True)

    tok = pegar_csrf(f"/aluno/{aluno_id}/turma")
    client.post(f"/aluno/{aluno_id}/turma", data={"csrf_token": tok, "turma": "4A", "serie": "4º Ano"})

    resp_depois = client.get("/")
    assert "TEG-PROV" not in resp_depois.get_data(as_text=True)


def test_professor_nao_edita_turma(client, pegar_csrf, criar_admin):
    from models import get_db
    from auth import hash_password

    with get_db() as db:
        aluno_id = _aluno(db, "ET9", "ALUNO TESTE 9")
        db.execute(
            "INSERT INTO users (username, password_hash, nome, setor, papel) VALUES (?,?,?,?,?)",
            ("prof13", hash_password("senha-professor-999"), "Professor Treze", "Sala", "professor"),
        )
    tok = pegar_csrf("/login")
    client.post("/login", data={"username": "prof13", "senha": "senha-professor-999", "csrf_token": tok})

    resp = client.get(f"/aluno/{aluno_id}/turma")
    assert resp.status_code == 403
