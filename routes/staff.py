import hmac
import re
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, request, redirect, url_for, session,
    flash, send_from_directory, abort
)
from werkzeug.utils import secure_filename

import config
from models import get_db, agora, salvar_turma_turno, get_config, set_config, adicionar_ao_arquivo_morto
from auth import (
    login_required, roles_required, verify_password, hash_password, current_user,
    new_guardian_token,
)

staff_bp = Blueprint("staff", __name__)

ALLOWED_PHOTO_EXT = {"jpg", "jpeg", "png", "webp"}


def _log(tipo, referencia, acao):
    with get_db() as db:
        db.execute(
            "INSERT INTO access_log (tipo, referencia, acao, ip) VALUES (?,?,?,?)",
            (tipo, referencia, acao, request.remote_addr),
        )


# --------------------------------------------------------------- login -----
LOGIN_MAX_TENTATIVAS = 5
LOGIN_JANELA_MINUTOS = 15


def _tentativas_recentes(username, ip):
    corte = (datetime.now(timezone.utc) - timedelta(minutes=LOGIN_JANELA_MINUTOS)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as db:
        row = db.execute(
            """SELECT COUNT(*) c FROM access_log
               WHERE tipo='staff' AND acao='login_falhou'
                 AND (referencia = ? OR ip = ?)
                 AND created_at > ?""",
            (username, ip, corte),
        ).fetchone()
    return row["c"]


@staff_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        senha = request.form.get("senha", "")

        if _tentativas_recentes(username, request.remote_addr) >= LOGIN_MAX_TENTATIVAS:
            flash(
                f"Muitas tentativas de login. Aguarde {LOGIN_JANELA_MINUTOS} minutos e tente novamente.",
                "erro",
            )
            return render_template("login.html")

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE username = ? AND ativo = 1", (username,)
            ).fetchone()
        if user and verify_password(senha, user["password_hash"]):
            session.clear()
            session["user_id"] = user["id"]
            session["papel"] = user["papel"]
            session["nome"] = user["nome"]
            _log("staff", username, "login")
            return redirect(request.args.get("next") or url_for("staff.dashboard"))
        _log("staff", username, "login_falhou")
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")


@staff_bp.route("/logout")
def logout():
    if session.get("user_id"):
        _log("staff", session.get("nome"), "logout")
    session.clear()
    return redirect(url_for("staff.login"))


# --------------------------------------------------- criação de admin ------
@staff_bp.route("/login/criar-admin", methods=["GET", "POST"])
def criar_admin():
    """Provisiona um usuário ADMINISTRADOR. Não é um cadastro público: só
    segue em frente quem digitar a chave de configuração do servidor
    (ADMIN_SETUP_KEY / SECRET_KEY no .env) — quem não tem acesso ao
    servidor não consegue criar um acesso admin por aqui."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        nome = request.form.get("nome", "").strip()
        setor = request.form.get("setor", "").strip()
        senha = request.form.get("senha", "")
        senha2 = request.form.get("senha2", "")
        chave = request.form.get("chave", "")

        erro = None
        if not hmac.compare_digest(chave, config.ADMIN_SETUP_KEY):
            erro = "Chave de configuração inválida."
        elif not username or not nome or not setor:
            erro = "Preencha usuário, nome e setor."
        elif len(senha) < 8:
            erro = "A senha deve ter pelo menos 8 caracteres."
        elif senha != senha2:
            erro = "As senhas não conferem."

        if not erro:
            with get_db() as db:
                existe = db.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()
                if existe:
                    erro = "Já existe um usuário com esse nome de login."
                else:
                    db.execute(
                        """INSERT INTO users (username, password_hash, nome, setor, papel)
                           VALUES (?,?,?,?, 'admin')""",
                        (username, hash_password(senha), nome, setor),
                    )
            if not erro:
                _log("staff", username, "criar_admin")

        if erro:
            flash(erro, "erro")
            return render_template("criar_admin.html", username=username, nome=nome, setor=setor)

        flash(f"Usuário administrador '{username}' criado. Faça login normalmente.", "ok")
        return redirect(url_for("staff.login"))

    return render_template("criar_admin.html")


# ------------------------------------------------------- minha conta -------
@staff_bp.route("/minha-conta/senha", methods=["GET", "POST"])
@login_required
def alterar_senha():
    if request.method == "POST":
        atual = request.form.get("senha_atual", "")
        nova = request.form.get("nova_senha", "")
        nova2 = request.form.get("nova_senha2", "")

        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()

        erro = None
        if not verify_password(atual, user["password_hash"]):
            erro = "Senha atual incorreta."
        elif len(nova) < 8:
            erro = "A nova senha deve ter pelo menos 8 caracteres."
        elif nova != nova2:
            erro = "As senhas não conferem."

        if erro:
            flash(erro, "erro")
            return render_template("alterar_senha.html", user=current_user())

        with get_db() as db:
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(nova), session["user_id"]),
            )
        _log("staff", session.get("nome"), "alterar_senha")
        flash("Senha alterada com sucesso.", "ok")
        return redirect(url_for("staff.dashboard"))

    return render_template("alterar_senha.html", user=current_user())


def _ordem_atual_sidebar(db):
    """Lê a ordem salva (se houver) e devolve validada: só ids que ainda
    existem, com qualquer item novo (de uma funcionalidade adicionada
    depois de alguém configurar a ordem) entrando no fim."""
    salva = get_config(db, "ordem_sidebar")
    ordem = [i for i in salva.split(",") if i in config.ORDEM_PADRAO_SIDEBAR] if salva else list(config.ORDEM_PADRAO_SIDEBAR)
    faltando = [i for i in config.ORDEM_PADRAO_SIDEBAR if i not in ordem]
    return ordem + faltando


@staff_bp.route("/configuracoes/menu-lateral", methods=["GET", "POST"])
@roles_required("admin")
def ordenar_sidebar():
    """Ordem do menu lateral — configuração única, vale pra todo mundo
    que usa o sistema (não é por usuário)."""
    with get_db() as db:
        if request.method == "POST":
            item = request.form.get("item", "")
            direcao = request.form.get("direcao", "")
            ordem = _ordem_atual_sidebar(db)
            if item in ordem:
                idx = ordem.index(item)
                if direcao == "subir" and idx > 0:
                    ordem[idx - 1], ordem[idx] = ordem[idx], ordem[idx - 1]
                elif direcao == "descer" and idx < len(ordem) - 1:
                    ordem[idx + 1], ordem[idx] = ordem[idx], ordem[idx + 1]
            set_config(db, "ordem_sidebar", ",".join(ordem))
            atualizado = True
        else:
            atualizado = False
            ordem = _ordem_atual_sidebar(db)

    if atualizado:
        _log("staff", session.get("nome"), f"ordenar_sidebar:{item}:{direcao}")
        return redirect(url_for("staff.ordenar_sidebar"))

    itens = [(i, config.ROTULOS_SIDEBAR[i]) for i in ordem]
    return render_template("ordenar_sidebar.html", itens=itens, user=current_user())


# ----------------------------------------------------------- dashboard -----
ORDEM_TURNOS = ["Manhã", "Integral", "Tarde"]


@staff_bp.route("/")
@login_required
def dashboard():
    with get_db() as db:
        turmas = db.execute(
            """SELECT s.turma, s.serie, COUNT(*) AS total, SUM(s.aee) AS total_aee, tt.turno
               FROM students s
               LEFT JOIN turma_turno tt ON tt.turma = s.turma
               WHERE s.situacao = 'ATIVO'
               GROUP BY s.turma
               ORDER BY s.serie, s.turma"""
        ).fetchall()
        total_alunos = db.execute(
            "SELECT COUNT(*) c FROM students WHERE situacao = 'ATIVO'"
        ).fetchone()["c"]
        total_aee = db.execute(
            "SELECT COUNT(*) c FROM students WHERE situacao = 'ATIVO' AND aee = 1"
        ).fetchone()["c"]
        turmas_com_notas = db.execute(
            """SELECT COUNT(DISTINCT s.turma) c FROM grades g
               JOIN students s ON s.id = g.student_id
               WHERE g.ano = ?""",
            (config.ANO_LETIVO,),
        ).fetchone()["c"]

    total_turmas = len(turmas)
    pct_notas = round((turmas_com_notas / total_turmas) * 100) if total_turmas else 0

    # turno -> {serie: [turmas]} ; turmas sem turno ficam num grupo à parte,
    # mas ainda separadas por série. Resumo (contagem) por turno é
    # calculado aqui pra aparecer fechado na gaveta, sem precisar abrir.
    turmas_por_turno = {turno: {} for turno in ORDEM_TURNOS}
    resumo_turno = {turno: {"turmas": 0, "alunos": 0} for turno in ORDEM_TURNOS}
    turmas_sem_turno = {}
    resumo_sem_turno = {"turmas": 0, "alunos": 0}
    for t in turmas:
        if t["turno"] in turmas_por_turno:
            destino, resumo = turmas_por_turno[t["turno"]], resumo_turno[t["turno"]]
        else:
            destino, resumo = turmas_sem_turno, resumo_sem_turno
        destino.setdefault(t["serie"] or "Série não definida", []).append(t)
        resumo["turmas"] += 1
        resumo["alunos"] += t["total"]

    return render_template(
        "dashboard.html", user=current_user(),
        ordem_turnos=ORDEM_TURNOS, turmas_por_turno=turmas_por_turno, turmas_sem_turno=turmas_sem_turno,
        resumo_turno=resumo_turno, resumo_sem_turno=resumo_sem_turno,
        total_alunos=total_alunos, total_aee=total_aee,
        total_turmas=total_turmas, turmas_com_notas=turmas_com_notas, pct_notas=pct_notas,
    )


@staff_bp.route("/turmas/turnos", methods=["GET", "POST"])
@roles_required("admin", "secretaria")
def configurar_turnos():
    with get_db() as db:
        if request.method == "POST":
            for turma in request.form.getlist("turma"):
                turno = request.form.get(f"turno::{turma}", "").strip()
                salvar_turma_turno(db, turma, turno or None)
            atualizado = True
        else:
            atualizado = False
            turmas = db.execute(
                """SELECT s.turma, COUNT(*) total, tt.turno
                   FROM students s
                   LEFT JOIN turma_turno tt ON tt.turma = s.turma
                   WHERE s.situacao = 'ATIVO'
                   GROUP BY s.turma
                   ORDER BY s.turma"""
            ).fetchall()

    if atualizado:
        _log("staff", session.get("nome"), "configurar_turnos")
        flash("Turnos atualizados.", "ok")
        return redirect(url_for("staff.dashboard"))

    return render_template(
        "configurar_turnos.html", turmas=turmas, ordem_turnos=ORDEM_TURNOS, user=current_user()
    )


@staff_bp.route("/turma/<turma>")
@login_required
def turma_view(turma):
    with get_db() as db:
        alunos = db.execute(
            """SELECT id, nome, nome_social, foto_path, aee, situacao, serie
               FROM students WHERE turma = ? AND situacao = 'ATIVO' ORDER BY nome""",
            (turma,),
        ).fetchall()
    if not alunos:
        abort(404)
    return render_template("turma.html", turma=turma, alunos=alunos, user=current_user())


# --------------------------------------------------------- aluno detail ----
@staff_bp.route("/aluno/<int:student_id>")
@login_required
def aluno_detail(student_id):
    with get_db() as db:
        aluno = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not aluno:
            abort(404)
        grades = db.execute(
            """SELECT * FROM grades WHERE student_id = ?
               ORDER BY ano, bimestre, disciplina""",
            (student_id,),
        ).fetchall()
        aee_detalhe = None
        if aluno["aee"] and session.get("papel") in config.PAPEIS_COM_ACESSO_AEE_DETALHE:
            aee_detalhe = db.execute(
                "SELECT * FROM aee_info WHERE student_id = ?", (student_id,)
            ).fetchone()

    # agrupa notas por ano e depois por bimestre, para renderizar em abas
    # (ano mais recente primeiro; dentro do ano, bimestre 1..4)
    boletim_por_ano = {}
    for g in grades:
        boletim_por_ano.setdefault(g["ano"], {}).setdefault(g["bimestre"], []).append(g)
    boletim = {ano: boletim_por_ano[ano] for ano in sorted(boletim_por_ano, reverse=True)}

    return render_template(
        "aluno.html",
        aluno=aluno,
        boletim=boletim,
        aee_detalhe=aee_detalhe,
        user=current_user(),
    )


@staff_bp.route("/aluno/<int:student_id>/foto", methods=["POST"])
@login_required
def upload_foto(student_id):
    file = request.files.get("foto")
    if not file or file.filename == "":
        flash("Selecione um arquivo de imagem.", "erro")
        return redirect(url_for("staff.aluno_detail", student_id=student_id))

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_PHOTO_EXT:
        flash("Formato inválido. Use JPG, PNG ou WEBP.", "erro")
        return redirect(url_for("staff.aluno_detail", student_id=student_id))

    filename = secure_filename(f"aluno_{student_id}.{ext}")
    dest = config.PHOTOS_DIR / filename
    file.save(dest)

    with get_db() as db:
        db.execute(
            "UPDATE students SET foto_path = ?, updated_at = ? WHERE id = ?",
            (filename, agora(), student_id),
        )
    _log("staff", session.get("nome"), f"upload_foto:{student_id}")
    flash("Foto atualizada.", "ok")
    return redirect(url_for("staff.aluno_detail", student_id=student_id))


_FOTO_ALUNO_RE = re.compile(r"^aluno_(\d+)\.")


@staff_bp.route("/fotos/<path:filename>")
def foto(filename):
    """Serve as fotos de alunos fora da pasta static/ (para funcionar com
    disco persistente em hospedagem na nuvem) e só libera para quem tem
    motivo: a equipe logada, ou o responsável logado pelo token — e, nesse
    caso, só a foto do próprio aluno dele."""
    m = _FOTO_ALUNO_RE.match(filename)
    student_id = int(m.group(1)) if m else None

    autorizado = bool(session.get("user_id"))
    if not autorizado and student_id and session.get("guardian_student_id") == student_id:
        autorizado = True
    if not autorizado:
        abort(403)

    return send_from_directory(config.PHOTOS_DIR, filename)


# ---------------------------------------------------- token responsavel ----
@staff_bp.route("/aluno/<int:student_id>/gerar-token", methods=["POST"])
@roles_required("admin", "secretaria")
def gerar_token(student_id):
    token, token_hash = new_guardian_token()
    with get_db() as db:
        db.execute(
            "UPDATE students SET guardian_token_hash = ?, updated_at = ? WHERE id = ?",
            (token_hash, agora(), student_id),
        )
    _log("staff", session.get("nome"), f"gerar_token:{student_id}")
    flash(
        f"Token gerado para o responsável (mostrado apenas agora, copie e "
        f"entregue com segurança): {token}",
        "token",
    )
    return redirect(url_for("staff.aluno_detail", student_id=student_id))


@staff_bp.route("/aluno/<int:student_id>/area-do-aluno", methods=["GET", "POST"])
@roles_required("admin", "secretaria", "professor")
def editar_area_do_aluno(student_id):
    """Recomendações da escola e pendências cadastrais (ex: telefone
    desatualizado, documento faltando) — aparecem para o responsável na
    Área do aluno. Nada aqui é dado de saúde/diagnóstico."""
    with get_db() as db:
        aluno = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not aluno:
            abort(404)

        if request.method == "POST":
            db.execute(
                "UPDATE students SET recomendacoes=?, alteracoes_pendentes=?, updated_at=? WHERE id=?",
                (
                    request.form.get("recomendacoes", "").strip() or None,
                    request.form.get("alteracoes_pendentes", "").strip() or None,
                    agora(), student_id,
                ),
            )
            atualizado = True
        else:
            atualizado = False

    if atualizado:
        _log("staff", session.get("nome"), f"editar_area_do_aluno:{student_id}")
        flash("Área do aluno atualizada.", "ok")
        return redirect(url_for("staff.aluno_detail", student_id=student_id))

    return render_template("editar_area_do_aluno.html", aluno=aluno, user=current_user())


# ------------------------------------------------------------ transferência --
@staff_bp.route("/aluno/<int:student_id>/nome", methods=["GET", "POST"])
@roles_required("admin", "secretaria")
def editar_nome(student_id):
    """Corrige o nome de registro (acento, erro de digitação vindo da
    importação etc.) e/ou registra o nome social do aluno — usado no
    dia a dia do sistema (listagens, busca, área do aluno), mas nunca
    substitui o nome de registro civil nos documentos oficiais
    (histórico escolar, planilha da SPTrans), que precisam bater com a
    identidade legal do aluno."""
    with get_db() as db:
        aluno = db.execute("SELECT id, nome, nome_social FROM students WHERE id = ?", (student_id,)).fetchone()
        if not aluno:
            abort(404)

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            if not nome:
                flash("O nome de registro não pode ficar em branco.", "erro")
                return redirect(url_for("staff.editar_nome", student_id=student_id))
            db.execute(
                "UPDATE students SET nome=?, nome_social=?, updated_at=? WHERE id=?",
                (nome, request.form.get("nome_social", "").strip() or None, agora(), student_id),
            )
            atualizado = True
        else:
            atualizado = False

    if atualizado:
        _log("staff", session.get("nome"), f"editar_nome:{student_id}")
        flash("Nome atualizado.", "ok")
        return redirect(url_for("staff.aluno_detail", student_id=student_id))

    return render_template("editar_nome.html", aluno=aluno, user=current_user())


@staff_bp.route("/aluno/<int:student_id>/turma", methods=["GET", "POST"])
@roles_required("admin", "secretaria")
def editar_turma(student_id):
    """Corrige a turma (e opcionalmente a série) do aluno — usada
    sobretudo pra corrigir a turma provisória 'TEG-PROV' que fica em
    quem é criado automaticamente na importação do TEG (essa planilha
    não traz a turma específica, só a série). Assim que a turma vira
    uma turma de verdade, o aluno passa a contar no turno certo
    (a turma provisória some sozinha do painel principal quando
    ninguém mais estiver nela)."""
    with get_db() as db:
        aluno = db.execute("SELECT id, nome, nome_social, turma, serie FROM students WHERE id = ?", (student_id,)).fetchone()
        if not aluno:
            abort(404)

        if request.method == "POST":
            turma = request.form.get("turma", "").strip().upper()
            if not turma:
                flash("A turma não pode ficar em branco.", "erro")
                return redirect(url_for("staff.editar_turma", student_id=student_id))
            db.execute(
                "UPDATE students SET turma=?, serie=?, updated_at=? WHERE id=?",
                (turma, request.form.get("serie", "").strip() or aluno["serie"], agora(), student_id),
            )
            proxima = request.form.get("next", "").strip()
            atualizado = True
        else:
            atualizado = False
            proxima = request.args.get("next", "").strip()

    if atualizado:
        _log("staff", session.get("nome"), f"editar_turma:{student_id}")
        flash(f"Turma de {aluno['nome_social'] or aluno['nome']} atualizada.", "ok")
        if proxima == "turma_atual":
            return redirect(url_for("staff.turma_view", turma=aluno["turma"]))
        return redirect(url_for("staff.aluno_detail", student_id=student_id))

    return render_template("editar_turma.html", aluno=aluno, proxima=proxima, user=current_user())


@staff_bp.route("/aluno/<int:student_id>/transferir", methods=["GET", "POST"])
@roles_required("admin", "secretaria")
def transferir_aluno(student_id):
    """Marca o aluno como transferido pra outra escola durante o ano
    letivo. Ele deixa de contar como 'ativo' (some das turmas, contagens
    do painel, exportação da SPTrans etc.) mas o cadastro continua
    intacto — dá pra reverter em 'Reativar matrícula' se for engano."""
    with get_db() as db:
        aluno = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not aluno:
            abort(404)

        if request.method == "POST":
            data_transferencia = request.form.get("data_transferencia", "").strip()
            if not data_transferencia:
                flash("Informe a data da transferência.", "erro")
                return redirect(url_for("staff.transferir_aluno", student_id=student_id))
            db.execute(
                "UPDATE students SET situacao='TRANSFERIDO', data_transferencia=?, updated_at=? WHERE id=?",
                (data_transferencia, agora(), student_id),
            )
            entrou_no_arquivo_morto = adicionar_ao_arquivo_morto(
                db, student_id, aluno["nome"], aluno["data_nascimento"]
            )
            atualizado = True
        else:
            atualizado = False

    if atualizado:
        _log("staff", session.get("nome"), f"transferir_aluno:{student_id}")
        flash(f"{aluno['nome']} foi marcado(a) como transferido(a).", "ok")
        if not entrou_no_arquivo_morto:
            flash(
                f"{aluno['nome']} já constava no Arquivo Morto — nenhum registro duplicado foi criado.",
                "erro",
            )
        return redirect(url_for("staff.aluno_detail", student_id=student_id))

    return render_template("transferir_aluno.html", aluno=aluno, user=current_user())


@staff_bp.route("/aluno/<int:student_id>/reativar", methods=["POST"])
@roles_required("admin", "secretaria")
def reativar_aluno(student_id):
    with get_db() as db:
        aluno = db.execute("SELECT id, nome FROM students WHERE id = ?", (student_id,)).fetchone()
        if not aluno:
            abort(404)
        db.execute(
            "UPDATE students SET situacao='ATIVO', data_transferencia=NULL, updated_at=? WHERE id=?",
            (agora(), student_id),
        )
    _log("staff", session.get("nome"), f"reativar_aluno:{student_id}")
    flash(f"{aluno['nome']} voltou a ser considerado(a) ativo(a).", "ok")
    return redirect(url_for("staff.aluno_detail", student_id=student_id))
