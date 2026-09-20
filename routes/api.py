"""
API JSON interna, consumida pelo próprio front-end via JavaScript
(fetch). Não é uma API pública — exige a mesma sessão de login da equipe
escolar que as telas HTML usam.
"""
from flask import Blueprint, jsonify, request, session, abort

import config
from models import get_db
from auth import login_required

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/alunos")
@login_required
def alunos_busca():
    """Busca ao vivo de alunos em qualquer turma (usada em várias telas
    pra vincular um registro a um aluno, e na busca do painel principal).
    Exige pelo menos 2 caracteres — nunca devolve a lista inteira de uma
    vez. Busca por nome de registro OU nome social; o campo "nome" da
    resposta já vem como o nome de EXIBIÇÃO (nome social, se tiver)."""
    termo = request.args.get("q", "").strip()
    if len(termo) < 2:
        return jsonify([])
    with get_db() as db:
        linhas = db.execute(
            """SELECT id, nome, nome_social, turma FROM students
               WHERE nome LIKE ? OR nome_social LIKE ? ORDER BY nome LIMIT 20""",
            (f"%{termo}%", f"%{termo}%"),
        ).fetchall()
    return jsonify([
        {"id": a["id"], "nome": a["nome_social"] or a["nome"], "turma": a["turma"]} for a in linhas
    ])


@api_bp.route("/turma/<turma>/alunos")
@login_required
def alunos_turma(turma):
    """Busca ao vivo de alunos dentro de uma turma (usada pelo campo de
    busca da tela de turma). ?q=<termo> filtra por nome (de registro ou
    social). O campo "nome" da resposta já vem como o nome de EXIBIÇÃO
    (nome social, se tiver; senão o de registro) — quem consome esse
    JSON não precisa saber da distinção."""
    termo = request.args.get("q", "").strip()
    with get_db() as db:
        if termo:
            linhas = db.execute(
                """SELECT id, nome, nome_social, foto_path, aee, situacao FROM students
                   WHERE turma = ? AND (nome LIKE ? OR nome_social LIKE ?) ORDER BY nome""",
                (turma, f"%{termo}%", f"%{termo}%"),
            ).fetchall()
        else:
            linhas = db.execute(
                "SELECT id, nome, nome_social, foto_path, aee, situacao FROM students WHERE turma = ? ORDER BY nome",
                (turma,),
            ).fetchall()
    return jsonify([
        {
            "id": a["id"],
            "nome": a["nome_social"] or a["nome"],
            "foto_url": f"/fotos/{a['foto_path']}" if a["foto_path"] else None,
            "aee": bool(a["aee"]),
            "situacao": a["situacao"],
        }
        for a in linhas
    ])


@api_bp.route("/turma/<turma>/estatisticas")
@login_required
def estatisticas_turma(turma):
    """Estatísticas agregadas da turma a partir das notas já importadas:
    frequência média por bimestre e distribuição de conceitos/notas.
    Usado pelo painel de análise de dados da tela de turma."""
    with get_db() as db:
        existe = db.execute("SELECT 1 FROM students WHERE turma = ? LIMIT 1", (turma,)).fetchone()
        if not existe:
            abort(404)

        freq_por_bimestre = db.execute(
            """SELECT g.ano, g.bimestre, ROUND(AVG(g.frequencia), 1) AS media
               FROM grades g JOIN students s ON s.id = g.student_id
               WHERE s.turma = ? AND s.situacao = 'ATIVO' AND g.frequencia IS NOT NULL
               GROUP BY g.ano, g.bimestre ORDER BY g.ano, g.bimestre""",
            (turma,),
        ).fetchall()

        distrib_conceito = db.execute(
            """SELECT g.conceito, COUNT(*) AS total
               FROM grades g JOIN students s ON s.id = g.student_id
               WHERE s.turma = ? AND s.situacao = 'ATIVO' AND g.conceito IS NOT NULL AND g.conceito != ''
               GROUP BY g.conceito ORDER BY total DESC""",
            (turma,),
        ).fetchall()

        total_alunos = db.execute(
            "SELECT COUNT(*) c FROM students WHERE turma = ? AND situacao = 'ATIVO'", (turma,)
        ).fetchone()["c"]
        total_aee = db.execute(
            "SELECT COUNT(*) c FROM students WHERE turma = ? AND situacao = 'ATIVO' AND aee = 1", (turma,)
        ).fetchone()["c"]

    return jsonify({
        "turma": turma,
        "total_alunos": total_alunos,
        "total_aee": total_aee,
        "frequencia_por_bimestre": [
            {"ano": r["ano"], "bimestre": r["bimestre"], "media": r["media"]} for r in freq_por_bimestre
        ],
        "distribuicao_conceito": [
            {"conceito": r["conceito"], "total": r["total"]} for r in distrib_conceito
        ],
    })
