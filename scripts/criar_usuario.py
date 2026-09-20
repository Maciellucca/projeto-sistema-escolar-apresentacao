"""
Cria ou atualiza um usuário da equipe (staff) para login no sistema.
Não existe tela pública de cadastro por segurança — usuários são criados
por quem já tem acesso ao servidor/terminal.

Uso:
    python scripts/criar_usuario.py admin "Nome Completo" admin
    python scripts/criar_usuario.py jsilva "Janaina Silvestre Cruz" secretaria

Papéis válidos: admin, professor, aee, secretaria
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import get_db, init_db
from auth import hash_password

PAPEIS = {"admin", "professor", "aee", "secretaria"}


def criar(username, nome, papel, setor=None):
    if papel not in PAPEIS:
        raise SystemExit(f"Papel inválido: {papel}. Use um de: {', '.join(sorted(PAPEIS))}")

    senha = getpass.getpass("Senha: ")
    confirma = getpass.getpass("Confirme a senha: ")
    if senha != confirma:
        raise SystemExit("As senhas não conferem.")
    if len(senha) < 8:
        raise SystemExit("Use uma senha com pelo menos 8 caracteres.")

    init_db()
    with get_db() as db:
        existente = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existente:
            db.execute(
                "UPDATE users SET password_hash=?, nome=?, papel=?, setor=?, ativo=1 WHERE username=?",
                (hash_password(senha), nome, papel, setor, username),
            )
            print(f"Usuário '{username}' atualizado.")
        else:
            db.execute(
                "INSERT INTO users (username, password_hash, nome, papel, setor) VALUES (?,?,?,?,?)",
                (username, hash_password(senha), nome, papel, setor),
            )
            print(f"Usuário '{username}' criado com papel '{papel}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("nome")
    parser.add_argument("papel", choices=sorted(PAPEIS))
    parser.add_argument("--setor", default=None, help="Ex: Secretaria, Direção, Coordenação (opcional)")
    args = parser.parse_args()
    criar(args.username, args.nome, args.papel, args.setor)
