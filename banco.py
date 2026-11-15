from datetime import datetime
import hashlib
import json
import sqlite3
import pandas as pd

DB_NAME = "erros_separacao_v2.db"


def hash_senha(senha):
  return hashlib.sha256(senha.encode()).hexdigest()


def get_conn():
  return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
  conn = get_conn()
  c = conn.cursor()

  # Tabela de Usuários
  c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

  # Tabela de Separadores
  c.execute("""
        CREATE TABLE IF NOT EXISTS separadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        )
    """)

  # Tabela de Registros de Erros
  c.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            num_pedido TEXT,
            conferente_user TEXT,
            conferente_nome TEXT,
            separador TEXT,
            tipo_erro TEXT,
            sku_produto TEXT,
            qtd_divergente INTEGER,
            observacao TEXT,
            status_edicao TEXT DEFAULT 'Aprovado',
            dados_pendentes TEXT
        )
    """)

  # Tabela de Auditoria / Histórico de Ações
  c.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            usuario TEXT,
            nome TEXT,
            acao TEXT,
            detalhes TEXT
        )
    """)

  # Criar Admin padrão se não existir
  c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
  if not c.fetchone():
    c.execute(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
        ("admin", "Administrador", hash_senha("admin123"), "admin"),
    )

  # Criar separadores iniciais se estiver vazio
  c.execute("SELECT COUNT(*) FROM separadores")
  if c.fetchone()[0] == 0:
    iniciais = [
        ("João Silva",),
        ("Pedro Santos",),
        ("Lucas Oliveira",),
        ("Fernanda Alves",),
    ]
    c.executemany("INSERT INTO separadores (nome) VALUES (?)", iniciais)

  conn.commit()
  conn.close()


# --- AUTENTICAÇÃO E PERFIL ---
def autenticar_usuario(username, senha):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      "SELECT nome, role FROM usuarios WHERE username = ? AND senha_hash = ?",
      (username, hash_senha(senha)),
  )
  user = c.fetchone()
  conn.close()
  return user  # Retorna (nome, role) ou None


def alterar_senha(username, senha_atual, nova_senha):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      "SELECT * FROM usuarios WHERE username = ? AND senha_hash = ?",
      (username, hash_senha(senha_atual)),
  )
  if c.fetchone():
    c.execute(
        "UPDATE usuarios SET senha_hash = ? WHERE username = ?",
        (hash_senha(nova_senha), username),
    )
    conn.commit()
    conn.close()
    return True
  conn.close()
  return False


def atualizar_dados_usuario(username_atual, novo_username, novo_nome):
  conn = get_conn()
  c = conn.cursor()
  novo_username = novo_username.strip().lower()

  if novo_username != username_atual:
    c.execute("SELECT * FROM usuarios WHERE username = ?", (novo_username,))
    if c.fetchone():
      conn.close()
      return (
          False,
          "Este login (usuário) já está em uso por outra conta.",
      )

    c.execute(
        "UPDATE usuarios SET username = ?, nome = ? WHERE username = ?",
        (novo_username, novo_nome, username_atual),
    )
    c.execute(
        "UPDATE registros SET conferente_user = ?, conferente_nome = ? WHERE conferente_user = ?",
        (novo_username, novo_nome, username_atual),
    )
  else:
    c.execute(
        "UPDATE usuarios SET nome = ? WHERE username = ?",
        (novo_nome, username_atual),
    )
    c.execute(
        "UPDATE registros SET conferente_nome = ? WHERE conferente_user = ?",
        (novo_nome, username_atual),
    )

  conn.commit()
  conn.close()
  return True, "Dados atualizados com sucesso!"


# --- SEPARADORES ---
def get_separadores():
  conn = get_conn()
  df = pd.read_sql_query("SELECT nome FROM separadores ORDER BY nome", conn)
  conn.close()
  return df["nome"].tolist()


def adicionar_separador(nome):
  conn = get_conn()
  c = conn.cursor()
  c.execute("INSERT INTO separadores (nome) VALUES (?)", (nome,))
  conn.commit()
  conn.close()


def remover_separador(nome):
  conn = get_conn()
  c = conn.cursor()
  c.execute("DELETE FROM separadores WHERE nome = ?", (nome,))
  conn.commit()
  conn.close()


# --- REGISTROS DE ERROS ---
def inserir_registro(
    num_pedido,
    conferente_user,
    conferente_nome,
    separador,
    tipo_erro,
    sku_produto,
    qtd_divergente,
    observacao,
):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      """
        INSERT INTO registros (data_hora, num_pedido, conferente_user, conferente_nome, separador, tipo_erro, sku_produto, qtd_divergente, observacao, status_edicao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Aprovado')
    """,
      (
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          num_pedido,
          conferente_user,
          conferente_nome,
          separador,
          tipo_erro,
          sku_produto,
          qtd_divergente,
          observacao,
      ),
  )
  conn.commit()
  conn.close()


def carregar_todos_registros():
  conn = get_conn()
  df = pd.read_sql_query("SELECT * FROM registros ORDER BY id DESC", conn)
  conn.close()
  return df


def carregar_registros_por_conferente(username):
  conn = get_conn()
  df = pd.read_sql_query(
      "SELECT * FROM registros WHERE conferente_user = ? ORDER BY id DESC",
      conn,
      params=(username,),
  )
  conn.close()
  return df


def solicitar_edicao_registro(id_reg, dados_dict):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      "UPDATE registros SET status_edicao = 'Pendente', dados_pendentes = ? WHERE id = ?",
      (json.dumps(dados_dict), int(id_reg)),
  )
  conn.commit()
  conn.close()


def aprovar_edicao(id_reg, novos):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      """
        UPDATE registros SET 
            num_pedido = ?, separador = ?, tipo_erro = ?, sku_produto = ?, 
            qtd_divergente = ?, observacao = ?, status_edicao = 'Aprovado', dados_pendentes = NULL
        WHERE id = ?
    """,
      (
          novos["num_pedido"],
          novos["separador"],
          novos["tipo_erro"],
          novos["sku_produto"],
          novos["qtd_divergente"],
          novos["observacao"],
          id_reg,
      ),
  )
  conn.commit()
  conn.close()


def rejeitar_edicao(id_reg):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      "UPDATE registros SET status_edicao = 'Rejeitado', dados_pendentes = NULL WHERE id = ?",
      (id_reg,),
  )
  conn.commit()
  conn.close()


def excluir_registro(id_reg):
  conn = get_conn()
  c = conn.cursor()
  c.execute("DELETE FROM registros WHERE id = ?", (id_reg,))
  conn.commit()
  conn.close()


def excluir_multiplos_registros(ids_lista):
  if not ids_lista:
    return
  conn = get_conn()
  c = conn.cursor()
  placeholders = ",".join(["?"] * len(ids_lista))
  c.execute(f"DELETE FROM registros WHERE id IN ({placeholders})", ids_lista)
  conn.commit()
  conn.close()


def zerar_registros_e_ids():
  conn = get_conn()
  c = conn.cursor()
  c.execute("DELETE FROM registros")
  c.execute("DELETE FROM sqlite_sequence WHERE name='registros'")
  conn.commit()
  conn.close()


# --- SOLICITAÇÃO DE EXCLUSÃO PELO GESTOR ---
def solicitar_exclusao_registros(ids_lista, username, nome):
  conn = get_conn()
  c = conn.cursor()
  dados_json = json.dumps(ids_lista)
  c.execute(
      """
        INSERT INTO registros (data_hora, num_pedido, conferente_user, conferente_nome, separador, tipo_erro, sku_produto, qtd_divergente, observacao, status_edicao, dados_pendentes)
        VALUES (?, 'EXCLUSAO_EM_MASSA', ?, ?, 'SISTEMA', 'EXCLUSAO', 'S/N', 0, ?, 'Pendente_Exclusao', ?)
    """,
      (
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          username,
          nome,
          f"Solicitação de exclusão de {len(ids_lista)} registro(s).",
          dados_json,
      ),
  )
  conn.commit()
  conn.close()


# --- AUDITORIA ---
def registrar_auditoria(username, nome, acao, detalhes):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      """
        INSERT INTO auditoria (data_hora, usuario, nome, acao, detalhes)
        VALUES (?, ?, ?, ?, ?)
    """,
      (
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          username,
          nome,
          acao,
          detalhes,
      ),
  )
  conn.commit()
  conn.close()


def carregar_auditoria():
  conn = get_conn()
  df = pd.read_sql_query("SELECT * FROM auditoria ORDER BY id DESC", conn)
  conn.close()
  return df


# --- GESTÃO DE USUÁRIOS ---
def criar_usuario(username, nome, role="conferente"):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
      (username.strip().lower(), nome, hash_senha("123456"), role),
  )
  conn.commit()
  conn.close()


def listar_usuarios():
  conn = get_conn()
  df = pd.read_sql_query(
      "SELECT username, nome, role FROM usuarios WHERE username != 'admin'",
      conn,
  )
  conn.close()
  return df


def resetar_senha_usuario(username):
  conn = get_conn()
  c = conn.cursor()
  c.execute(
      "UPDATE usuarios SET senha_hash = ? WHERE username = ?",
      (hash_senha("123456"), username),
  )
  conn.commit()
  conn.close()


def excluir_usuario(username):
  conn = get_conn()
  c = conn.cursor()
  c.execute("DELETE FROM usuarios WHERE username = ?", (username,))
  conn.commit()
  conn.close()