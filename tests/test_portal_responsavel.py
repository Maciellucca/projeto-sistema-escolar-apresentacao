import re


def _gerar_token_para(client, pegar_csrf, student_id):
    tok = pegar_csrf(f"/aluno/{student_id}")
    resp = client.post(f"/aluno/{student_id}/gerar-token", data={"csrf_token": tok}, follow_redirects=True)
    m = re.search(r"entregue com segurança\): (\S+)</div>", resp.get_data(as_text=True))
    assert m, "token não apareceu no flash message"
    return m.group(1)


def test_responsavel_com_token_valido_ve_o_boletim(client, pegar_csrf, aluno_exemplo):
    token = _gerar_token_para(client, pegar_csrf, aluno_exemplo)

    tok = pegar_csrf("/responsavel/")
    resp = client.post("/responsavel/", data={"token": token, "csrf_token": tok}, follow_redirects=True)
    assert "ALUNO DE TESTE" in resp.get_data(as_text=True)


def test_responsavel_com_token_invalido_e_recusado(client, pegar_csrf):
    tok = pegar_csrf("/responsavel/")
    resp = client.post(
        "/responsavel/", data={"token": "token-que-nao-existe", "csrf_token": tok},
        follow_redirects=True,
    )
    assert "Token inválido" in resp.get_data(as_text=True)


def test_responsavel_nao_ve_dados_de_outro_aluno(app, client, pegar_csrf, aluno_exemplo):
    from models import get_db
    with get_db() as db:
        outro_id = db.execute(
            """INSERT INTO students (codigo_interno, nome, turma, serie, situacao, aee)
               VALUES ('COD2', 'OUTRO ALUNO', '1A', '1º Ano', 'ATIVO', 0)"""
        ).lastrowid

    token = _gerar_token_para(client, pegar_csrf, aluno_exemplo)
    tok = pegar_csrf("/responsavel/")
    client.post("/responsavel/", data={"token": token, "csrf_token": tok})

    resp = client.get("/responsavel/boletim")
    html = resp.get_data(as_text=True)
    assert "ALUNO DE TESTE" in html
    assert "OUTRO ALUNO" not in html


def test_foto_exige_autorizacao(app, client, pegar_csrf, aluno_exemplo):
    from models import get_db
    with get_db() as db:
        db.execute("UPDATE students SET foto_path = 'aluno_%d.png' WHERE id = ?" % aluno_exemplo, (aluno_exemplo,))

    # staff logado acessa
    resp = client.get(f"/fotos/aluno_{aluno_exemplo}.png")
    assert resp.status_code in (200, 404)  # 404 só se o arquivo físico não existir; nunca 403 pro staff

    # cliente sem nenhuma sessão é bloqueado
    anonimo = app.test_client()
    resp2 = anonimo.get(f"/fotos/aluno_{aluno_exemplo}.png")
    assert resp2.status_code == 403
