"""
Lista de cursos gratuitos recomendados (ex: Escola Virtual.gov/ENAP),
organizada pelos 3 ciclos oficiais do Ensino Fundamental (Alfabetização,
Interdisciplinar, Autoral). Mantida manualmente pela equipe — não é
sincronizada automaticamente com nenhuma plataforma externa, porque esses
catálogos mudam com frequência.
"""
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort

from models import get_db, agora
from auth import login_required, roles_required, current_user

cursos_bp = Blueprint("cursos", __name__, url_prefix="/cursos")

CICLOS = ["Alfabetização", "Interdisciplinar", "Autoral"]


def ciclo_da_serie(serie):
    """Converte a série do aluno (ex: '5º Ano') no ciclo correspondente,
    seguindo a mesma organização da Rede Municipal de SP usada no resto
    do sistema (Alfabetização 1º-3º, Interdisciplinar 4º-6º, Autoral
    7º-9º). Devolve None se não conseguir reconhecer o número da série
    (aluno sem série cadastrada, formato diferente, etc.)."""
    if not serie:
        return None
    m = re.match(r"\s*(\d+)", serie)
    if not m:
        return None
    numero = int(m.group(1))
    if 1 <= numero <= 3:
        return "Alfabetização"
    if 4 <= numero <= 6:
        return "Interdisciplinar"
    if 7 <= numero <= 9:
        return "Autoral"
    return None


def serie_com_turma(serie, turma):
    """Junta a série com a letra da turma (ex: serie='3º Ano', turma='3B'
    -> '3º Ano B') — a turma já traz o número da série embutido (3B = 3º
    ano, turma B), então só a letra é útil ao lado da série por extenso.
    Turmas fora do padrão número+letra (ex: 'TEG-PROV') aparecem inteiras."""
    if not serie:
        return turma or "—"
    m = re.match(r"^\d+", turma or "")
    if not m:
        return f"{serie} ({turma})" if turma else serie
    letra = (turma or "")[m.end():].strip()
    return f"{serie} {letra}".strip() if letra else serie


def _log(acao):
    with get_db() as db:
        db.execute(
            "INSERT INTO access_log (tipo, referencia, acao, ip) VALUES (?,?,?,?)",
            ("staff", session.get("nome"), acao, request.remote_addr),
        )


@cursos_bp.route("/")
@login_required
def index():
    with get_db() as db:
        linhas = db.execute(
            "SELECT * FROM cursos_recomendados WHERE ativo = 1 ORDER BY ciclo, titulo"
        ).fetchall()
    por_ciclo = {c: [] for c in CICLOS}
    for l in linhas:
        por_ciclo.setdefault(l["ciclo"], []).append(l)
    return render_template("cursos_index.html", ciclos=CICLOS, por_ciclo=por_ciclo, user=current_user())


@cursos_bp.route("/adicionar", methods=["POST"])
@roles_required("admin", "secretaria")
def adicionar():
    titulo = request.form.get("titulo", "").strip()
    ciclo = request.form.get("ciclo", "").strip()
    if not titulo or ciclo not in CICLOS:
        flash("Informe pelo menos o título e o ciclo.", "erro")
        return redirect(url_for("cursos.index"))

    with get_db() as db:
        db.execute(
            """INSERT INTO cursos_recomendados (titulo, descricao, url, ciclo, fonte, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (
                titulo,
                request.form.get("descricao", "").strip() or None,
                request.form.get("url", "").strip() or None,
                ciclo,
                request.form.get("fonte", "").strip() or None,
                agora(),
            ),
        )
    _log("curso_adicionado")
    flash("Curso adicionado.", "ok")
    return redirect(url_for("cursos.index"))


@cursos_bp.route("/<int:curso_id>/excluir", methods=["POST"])
@roles_required("admin", "secretaria")
def excluir(curso_id):
    with get_db() as db:
        curso = db.execute("SELECT id FROM cursos_recomendados WHERE id = ?", (curso_id,)).fetchone()
        if not curso:
            abort(404)
        db.execute("DELETE FROM cursos_recomendados WHERE id = ?", (curso_id,))
    _log(f"curso_excluido:{curso_id}")
    flash("Curso removido da lista.", "ok")
    return redirect(url_for("cursos.index"))
