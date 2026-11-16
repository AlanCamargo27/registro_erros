from datetime import datetime
import hashlib
import json
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# Pega a URL do banco configurada de forma segura no Streamlit Cloud
DATABASE_URL = st.secrets.get("DATABASE_URL")

def get_engine():
  DATABASE_URL = st.secrets.get("DATABASE_URL")
  if not DATABASE_URL:
    st.error("⚠️ A variável DATABASE_URL não foi encontrada nas Secrets do Streamlit Cloud! Configure-a em Settings > Secrets.")
    st.stop()
  return create_engine(DATABASE_URL)

def hash_senha(senha):
  return hashlib.sha256(senha.encode()).hexdigest()

def init_db():
  engine = get_engine()
  with engine.begin() as conn:
    # Tabela de Usuários
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """))

    # Tabela de Separadores
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS separadores (
            id SERIAL PRIMARY KEY,
            nome TEXT UNIQUE NOT NULL
        )
    """))

    # Tabela de Registros de Erros
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS registros (
            id SERIAL PRIMARY KEY,
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
    """))

    # Tabela de Auditoria / Histórico de Ações
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id SERIAL PRIMARY KEY,
            data_hora TEXT,
            usuario TEXT,
            nome TEXT,
            acao TEXT,
            detalhes TEXT
        )
    """))

    # Criar Admin padrão se não existir
    res = conn.execute(text("SELECT * FROM usuarios WHERE username = 'admin'")).fetchone()
    if not res:
      conn.execute(
          text("INSERT INTO usuarios VALUES (:u, :n, :s, :r)"),
          {"u": "admin", "n": "Administrador", "s": hash_senha("admin123"), "r": "admin"}
      )

    # Criar separadores iniciais se estiver vazio
    count_seps = conn.execute(text("SELECT COUNT(*) FROM separadores")).scalar()
    if count_seps == 0:
      iniciais = [
          {"nome": "João Silva"},
          {"nome": "Pedro Santos"},
          {"nome": "Lucas Oliveira"},
          {"nome": "Fernanda Alves"},
      ]
      for item in iniciais:
        conn.execute(
            text("INSERT INTO separadores (nome) VALUES (:nome) ON CONFLICT (nome) DO NOTHING"),
            item
        )

# --- AUTENTICAÇÃO E PERFIL ---
def autenticar_usuario(username, senha):
  engine = get_engine()
  with engine.connect() as conn:
    res = conn.execute(
        text("SELECT nome, role FROM usuarios WHERE username = :u AND senha_hash = :s"),
        {"u": username, "s": hash_senha(senha)}
    ).fetchone()
  return res if res else None


def alterar_senha(username, senha_atual, nova_senha):
  engine = get_engine()
  with engine.begin() as conn:
    user = conn.execute(
        text("SELECT * FROM usuarios WHERE username = :u AND senha_hash = :s"),
        {"u": username, "s": hash_senha(senha_atual)}
    ).fetchone()
    if user:
      conn.execute(
          text("UPDATE usuarios SET senha_hash = :ns WHERE username = :u"),
          {"ns": hash_senha(nova_senha), "u": username}
      )
      return True
  return False


def atualizar_dados_usuario(username_atual, novo_username, novo_nome):
  engine = get_engine()
  novo_username = novo_username.strip().lower()

  with engine.begin() as conn:
    if novo_username != username_atual:
      existe = conn.execute(
          text("SELECT * FROM usuarios WHERE username = :u"), {"u": novo_username}
      ).fetchone()
      if existe:
        return False, "Este login (usuário) já está em uso por outra conta."

      conn.execute(
          text("UPDATE usuarios SET username = :nu, nome = :nn WHERE username = :ua"),
          {"nu": novo_username, "nn": novo_nome, "ua": username_atual}
      )
      conn.execute(
          text("UPDATE registros SET conferente_user = :nu, conferente_nome = :nn WHERE conferente_user = :ua"),
          {"nu": novo_username, "nn": novo_nome, "ua": username_atual}
      )
    else:
      conn.execute(
          text("UPDATE usuarios SET nome = :nn WHERE username = :ua"),
          {"nn": novo_nome, "ua": username_atual}
      )
      conn.execute(
          text("UPDATE registros SET conferente_nome = :nn WHERE conferente_user = :ua"),
          {"nn": novo_nome, "ua": username_atual}
      )
  return True, "Dados atualizados com sucesso!"


# --- SEPARADORES ---
def get_separadores():
  engine = get_engine()
  df = pd.read_sql("SELECT nome FROM separadores ORDER BY nome", engine)
  return df["nome"].tolist()


def adicionar_separador(nome):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(text("INSERT INTO separadores (nome) VALUES (:n)"), {"n": nome})


def remover_separador(nome):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(text("DELETE FROM separadores WHERE nome = :n"), {"n": nome})


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
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("""
            INSERT INTO registros (data_hora, num_pedido, conferente_user, conferente_nome, separador, tipo_erro, sku_produto, qtd_divergente, observacao, status_edicao)
            VALUES (:dh, :np, :cu, :cn, :sep, :te, :sku, :qtd, :obs, 'Aprovado')
        """),
        {
            "dh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "np": num_pedido,
            "cu": conferente_user,
            "cn": conferente_nome,
            "sep": separador,
            "te": tipo_erro,
            "sku": sku_produto,
            "qtd": qtd_divergente,
            "obs": observacao,
        }
    )


def carregar_todos_registros():
  engine = get_engine()
  df = pd.read_sql("SELECT * FROM registros ORDER BY id DESC", engine)
  return df


def carregar_registros_por_conferente(username):
  engine = get_engine()
  df = pd.read_sql(
      text("SELECT * FROM registros WHERE conferente_user = :u ORDER BY id DESC"),
      engine,
      params={"u": username}
  )
  return df


def solicitar_edicao_registro(id_reg, dados_dict):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("UPDATE registros SET status_edicao = 'Pendente', dados_pendentes = :dp WHERE id = :id"),
        {"dp": json.dumps(dados_dict), "id": int(id_reg)}
    )


def aprovar_edicao(id_reg, novos):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("""
            UPDATE registros SET 
                num_pedido = :np, separador = :sep, tipo_erro = :te, sku_produto = :sku, 
                qtd_divergente = :qtd, observacao = :obs, status_edicao = 'Aprovado', dados_pendentes = NULL
            WHERE id = :id
        """),
        {
            "np": novos["num_pedido"],
            "sep": novos["separador"],
            "te": novos["tipo_erro"],
            "sku": novos["sku_produto"],
            "qtd": novos["qtd_divergente"],
            "obs": novos["observacao"],
            "id": id_reg,
        }
    )


def rejeitar_edicao(id_reg):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("UPDATE registros SET status_edicao = 'Rejeitado', dados_pendentes = NULL WHERE id = :id"),
        {"id": id_reg}
    )


def excluir_registro(id_reg):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(text("DELETE FROM registros WHERE id = :id"), {"id": id_reg})


def excluir_multiplos_registros(ids_lista):
  if not ids_lista:
    return
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("DELETE FROM registros WHERE id = ANY(:ids)"),
        {"ids": ids_lista}
    )


def zerar_registros_e_ids():
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(text("DELETE FROM registros"))
    try:
      conn.execute(text("ALTER SEQUENCE registros_id_seq RESTART WITH 1"))
    except Exception:
      pass


# --- SOLICITAÇÃO DE EXCLUSÃO PELO GESTOR ---
def solicitar_exclusao_registros(ids_lista, username, nome):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("""
            INSERT INTO registros (data_hora, num_pedido, conferente_user, conferente_nome, separador, tipo_erro, sku_produto, qtd_divergente, observacao, status_edicao, dados_pendentes)
            VALUES (:dh, 'EXCLUSAO_EM_MASSA', :cu, :cn, 'SISTEMA', 'EXCLUSAO', 'S/N', 0, :obs, 'Pendente_Exclusao', :dp)
        """),
        {
            "dh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cu": username,
            "cn": nome,
            "obs": f"Solicitação de exclusão de {len(ids_lista)} registro(s).",
            "dp": json.dumps(ids_lista),
        }
    )


# --- AUDITORIA ---
def registrar_auditoria(username, nome, acao, detalhes):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("""
            INSERT INTO auditoria (data_hora, usuario, nome, acao, detalhes)
            VALUES (:dh, :u, :n, :ac, :det)
        """),
        {
            "dh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "u": username,
            "n": nome,
            "ac": acao,
            "det": detalhes,
        }
    )


def carregar_auditoria():
  engine = get_engine()
  df = pd.read_sql("SELECT * FROM auditoria ORDER BY id DESC", engine)
  return df


# --- GESTÃO DE USUÁRIOS ---
def criar_usuario(username, nome, role="conferente"):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("INSERT INTO usuarios VALUES (:u, :n, :s, :r)"),
        {"u": username.strip().lower(), "n": nome, "s": hash_senha("123456"), "r": role}
    )


def listar_usuarios():
  engine = get_engine()
  df = pd.read_sql(
      "SELECT username, nome, role FROM usuarios WHERE username != 'admin'",
      engine,
  )
  return df


def resetar_senha_usuario(username):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(
        text("UPDATE usuarios SET senha_hash = :s WHERE username = :u"),
        {"s": hash_senha("123456"), "u": username}
    )


def excluir_usuario(username):
  engine = get_engine()
  with engine.begin() as conn:
    conn.execute(text("DELETE FROM usuarios WHERE username = :u"), {"u": username})