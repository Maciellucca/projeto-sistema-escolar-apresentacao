"""
Testa a configuração da ordem do menu lateral (admin), incluindo o caso
de um item novo aparecer mesmo quando a ordem salva é de antes dele
existir.
"""


def test_ordem_padrao_mostra_inicio_antes_de_importar_notas(client, pegar_csrf, criar_admin):
    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert html.find(">Início<") < html.find(">Importar notas<")


def test_tela_de_configuracao_carrega(client, pegar_csrf, criar_admin):
    resp = client.get("/configuracoes/menu-lateral")
    assert resp.status_code == 200
    assert "Ordem do menu lateral" in resp.get_data(as_text=True)


def test_mover_item_para_cima_muda_a_ordem(client, pegar_csrf, criar_admin):
    from models import get_db, get_config

    tok = pegar_csrf("/configuracoes/menu-lateral")
    resp = client.post(
        "/configuracoes/menu-lateral",
        data={"csrf_token": tok, "item": "importar_notas", "direcao": "subir"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with get_db() as db:
        ordem = get_config(db, "ordem_sidebar").split(",")
    assert ordem.index("importar_notas") < ordem.index("inicio")

    resp2 = client.get("/")
    html2 = resp2.get_data(as_text=True)
    assert html2.find(">Importar notas<") < html2.find(">Início<")


def test_mover_primeiro_item_para_cima_nao_muda_nada(client, pegar_csrf, criar_admin):
    from models import get_db, get_config

    tok = pegar_csrf("/configuracoes/menu-lateral")
    client.post(
        "/configuracoes/menu-lateral",
        data={"csrf_token": tok, "item": "inicio", "direcao": "subir"},
    )
    with get_db() as db:
        ordem = get_config(db, "ordem_sidebar")
    assert ordem.split(",")[0] == "inicio"


def test_mover_ultimo_item_para_baixo_nao_muda_nada(client, pegar_csrf, criar_admin):
    """Usa o último item de config.ORDEM_PADRAO_SIDEBAR dinamicamente —
    não hardcoda qual é, porque toda vez que uma aba nova é adicionada
    ao fim da lista (o normal), um nome fixo aqui quebra à toa."""
    import config
    from models import get_db, get_config

    ultimo_item = config.ORDEM_PADRAO_SIDEBAR[-1]
    tok = pegar_csrf("/configuracoes/menu-lateral")
    client.post(
        "/configuracoes/menu-lateral",
        data={"csrf_token": tok, "item": ultimo_item, "direcao": "descer"},
    )
    with get_db() as db:
        ordem = get_config(db, "ordem_sidebar")
    assert ordem.split(",")[-1] == ultimo_item


def test_item_novo_aparece_mesmo_com_ordem_salva_antiga(client, pegar_csrf, criar_admin):
    """Simula uma ordem salva de antes de 'arquivo_morto' existir — o item
    novo tem que aparecer mesmo assim, não sumir do menu."""
    from models import get_db, set_config

    with get_db() as db:
        set_config(db, "ordem_sidebar", "importar_alunos,inicio,importar_notas")

    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert "Arquivo Morto" in html
    assert html.find("Importar alunos") < html.find(">Início<")


def test_professor_nao_acessa_configuracao_de_menu(client, pegar_csrf, criar_admin):
    from models import get_db
    from auth import hash_password

    with get_db() as db:
        db.execute(
            "INSERT INTO users (username, password_hash, nome, setor, papel) VALUES (?,?,?,?,?)",
            ("prof8", hash_password("senha-professor-333"), "Professor Oito", "Sala", "professor"),
        )
    tok = pegar_csrf("/login")
    client.post("/login", data={"username": "prof8", "senha": "senha-professor-333", "csrf_token": tok})

    resp = client.get("/configuracoes/menu-lateral")
    assert resp.status_code == 403


def test_secretaria_tambem_nao_acessa_configuracao_de_menu(client, pegar_csrf, criar_admin):
    """Diferente da maioria das configurações do sistema (SPTrans,
    turnos etc, que são admin+secretaria), a ordem do menu é só admin —
    afeta a navegação de todo mundo, decisão de só uma pessoa."""
    from models import get_db
    from auth import hash_password

    with get_db() as db:
        db.execute(
            "INSERT INTO users (username, password_hash, nome, setor, papel) VALUES (?,?,?,?,?)",
            ("sec1", hash_password("senha-secretaria-444"), "Secretaria Um", "Secretaria", "secretaria"),
        )
    tok = pegar_csrf("/login")
    client.post("/login", data={"username": "sec1", "senha": "senha-secretaria-444", "csrf_token": tok})

    resp = client.get("/configuracoes/menu-lateral")
    assert resp.status_code == 403
