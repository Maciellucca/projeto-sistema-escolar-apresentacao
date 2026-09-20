"""
Testa o envio de fotos em lote: cada arquivo casado com o aluno certo
pelo nome do arquivo (ignorando maiúsculas/minúsculas, acentos, "_"/"-").
"""
import io

from PIL import Image


def _imagem(fmt="JPEG"):
    img = Image.new("RGB", (10, 10), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def _aluno(db, codigo, nome, turma="1A"):
    return db.execute(
        "INSERT INTO students (codigo_interno, nome, turma, serie, situacao) VALUES (?,?,?, '1º Ano', 'ATIVO')",
        (codigo, nome, turma),
    ).lastrowid


def test_tela_de_upload_carrega(client, pegar_csrf, criar_admin):
    resp = client.get("/importar/fotos")
    assert resp.status_code == 200
    assert "Enviar fotos em lote" in resp.get_data(as_text=True)


def test_foto_casa_com_aluno_por_nome_exato(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "F1", "MARIA EDUARDA SANTOS")

    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={"turma": "", "csrf_token": tok, "fotos": [(_imagem("JPEG"), "MARIA EDUARDA SANTOS.jpg")]},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "MARIA EDUARDA SANTOS.jpg" in html
    assert "Casadas com sucesso" in html

    from models import get_db
    with get_db() as db:
        aluno = db.execute("SELECT foto_path FROM students WHERE id=?", (aluno_id,)).fetchone()
    assert aluno["foto_path"] == f"aluno_{aluno_id}.jpg"


def test_nome_do_arquivo_normaliza_underscore_e_minuscula(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        aluno_id = _aluno(db, "F2", "JOAO PEDRO ALVES")

    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={"turma": "", "csrf_token": tok, "fotos": [(_imagem("PNG"), "joao_pedro_alves.png")]},
        content_type="multipart/form-data",
    )
    assert "joao_pedro_alves.png" in resp.get_data(as_text=True)

    with get_db() as db:
        aluno = db.execute("SELECT foto_path FROM students WHERE id=?", (aluno_id,)).fetchone()
    assert aluno["foto_path"] == f"aluno_{aluno_id}.png"


def test_nome_ambiguo_entre_turmas_fica_pendente(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        _aluno(db, "F3", "PEDRO HENRIQUE LIMA", turma="1A")
        _aluno(db, "F4", "PEDRO HENRIQUE LIMA", turma="2A")

    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={"turma": "", "csrf_token": tok, "fotos": [(_imagem("JPEG"), "PEDRO HENRIQUE LIMA.jpg")]},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "mais de um aluno com esse nome" in html


def test_filtro_de_turma_resolve_nome_ambiguo(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        _aluno(db, "F5", "CARLA MENDES", turma="1A")
        aluno_2a = _aluno(db, "F6", "CARLA MENDES", turma="2A")

    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={"turma": "2A", "csrf_token": tok, "fotos": [(_imagem("JPEG"), "CARLA MENDES.jpg")]},
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "Casadas com sucesso" in html
    assert "2A" in html

    with get_db() as db:
        aluno = db.execute("SELECT foto_path FROM students WHERE id=?", (aluno_2a,)).fetchone()
    assert aluno["foto_path"] is not None


def test_nome_nao_encontrado_fica_pendente(client, pegar_csrf, criar_admin):
    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={"turma": "", "csrf_token": tok, "fotos": [(_imagem("JPEG"), "ALUNO QUE NAO EXISTE.jpg")]},
        content_type="multipart/form-data",
    )
    assert "nenhum aluno com esse nome encontrado" in resp.get_data(as_text=True)


def test_extensao_invalida_fica_pendente(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        _aluno(db, "F7", "TESTE EXTENSAO")

    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={"turma": "", "csrf_token": tok, "fotos": [(io.BytesIO(b"nao e imagem"), "TESTE EXTENSAO.txt")]},
        content_type="multipart/form-data",
    )
    assert "formato inválido" in resp.get_data(as_text=True)


def test_upload_sem_arquivos_mostra_erro(client, pegar_csrf, criar_admin):
    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={"turma": "", "csrf_token": tok},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "Selecione pelo menos um arquivo" in resp.get_data(as_text=True)


def test_varias_fotos_de_uma_vez(client, pegar_csrf, criar_admin):
    from models import get_db

    with get_db() as db:
        _aluno(db, "F8", "ALUNO UM")
        _aluno(db, "F9", "ALUNO DOIS")

    tok = pegar_csrf("/importar/fotos")
    resp = client.post(
        "/importar/fotos/upload",
        data={
            "turma": "", "csrf_token": tok,
            "fotos": [
                (_imagem("JPEG"), "ALUNO UM.jpg"),
                (_imagem("PNG"), "ALUNO DOIS.png"),
                (_imagem("JPEG"), "NAO EXISTE.jpg"),
            ],
        },
        content_type="multipart/form-data",
    )
    html = resp.get_data(as_text=True)
    assert "ALUNO UM.jpg" in html
    assert "ALUNO DOIS.png" in html
    assert "NAO EXISTE.jpg" in html
