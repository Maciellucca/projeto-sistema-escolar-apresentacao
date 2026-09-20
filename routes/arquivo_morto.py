"""
Arquivo morto: registro permanente de todo aluno que já passou pela
escola, organizado em gavetas por letra (A-Z) — igual à organização em
abas da planilha original. Aluno transferido entra aqui automaticamente
(ver models.adicionar_ao_arquivo_morto, chamada em
staff.transferir_aluno).
"""
import string
import time

import config
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from models import get_db, inserir_arquivo_morto_manual
from auth import roles_required, current_user
from scripts.import_arquivo_morto import importar as _importar_arquivo_morto

arquivo_morto_bp = Blueprint("arquivo_morto", __name__, url_prefix="/arquivo-morto")

LETRAS = list(string.ascii_uppercase)


def _log(acao):
    with get_db() as db:
        db.execute(
            "INSERT INTO access_log (tipo, referencia, acao, ip) VALUES (?,?,?,?)",
            ("staff", session.get("nome"), acao, request.remote_addr),
        )


@arquivo_morto_bp.route("/")
@roles_required("admin", "secretaria")
def index():
    busca = request.args.get("q", "").strip()

    with get_db() as db:
        if busca:
            registros = db.execute(
                "SELECT * FROM arquivo_morto WHERE nome LIKE ? ORDER BY letra, id DESC",
                (f"%{busca}%",),
            ).fetchall()
        else:
            registros = db.execute("SELECT * FROM arquivo_morto ORDER BY letra, id DESC").fetchall()

    por_letra = {letra: [] for letra in LETRAS}
    for r in registros:
        if r["letra"] in por_letra:
            por_letra[r["letra"]].append(r)

    return render_template(
        "arquivo_morto_index.html", letras=LETRAS, por_letra=por_letra, busca=busca, user=current_user()
    )


@arquivo_morto_bp.route("/importar", methods=["GET", "POST"])
@roles_required("admin", "secretaria")
def importar():
    if request.method == "GET":
        return render_template("arquivo_morto_importar.html", user=current_user())

    file = request.files.get("planilha")
    if not file or file.filename == "" or not file.filename.lower().endswith(".xlsx"):
        flash("Selecione um arquivo .xlsx (converta de .xls pelo Excel/LibreOffice, se precisar).", "erro")
        return redirect(url_for("arquivo_morto.importar"))

    filename = f"{int(time.time())}_{file.filename}"
    caminho = config.UPLOADS_DIR / filename
    file.save(caminho)
    try:
        resultado = _importar_arquivo_morto(str(caminho))
    except Exception as exc:
        flash(f"Não foi possível importar a planilha: {exc}", "erro")
        return redirect(url_for("arquivo_morto.importar"))
    finally:
        caminho.unlink(missing_ok=True)

    _log(f"importar_arquivo_morto:{resultado['importados']}")
    return render_template("arquivo_morto_importar_resultado.html", resultado=resultado, user=current_user())


@arquivo_morto_bp.route("/novo", methods=["GET", "POST"])
@roles_required("admin", "secretaria")
def novo():
    if request.method == "GET":
        return render_template("arquivo_morto_novo.html", user=current_user())

    nome = request.form.get("nome", "").strip().upper()
    data_nascimento = request.form.get("data_nascimento", "").strip() or None
    if not nome:
        flash("Informe o nome do aluno.", "erro")
        return redirect(url_for("arquivo_morto.novo"))

    with get_db() as db:
        inserido = inserir_arquivo_morto_manual(db, nome, data_nascimento)

    if not inserido:
        flash(f"{nome} já consta no Arquivo Morto — nenhum registro duplicado foi criado.", "erro")
        return redirect(url_for("arquivo_morto.novo"))

    _log(f"criar_arquivo_morto_manual:{nome}")
    flash(f"{nome} adicionado ao Arquivo Morto.", "ok")
    return redirect(url_for("arquivo_morto.index"))
