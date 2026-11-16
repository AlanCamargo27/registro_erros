from datetime import datetime
import json
import pandas as pd
import streamlit as st
import banco
import plotly.express as px

# Configuração da página
st.set_page_config(
    page_title="Conferência Logística", page_icon="📦", layout="wide"
)

# Inicializa o banco de dados na primeira execução
banco.init_db()

# --- GERENCIAMENTO DE SESSÃO ---
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
  st.session_state.username = None
  st.session_state.nome = None
  st.session_state.role = None


def fazer_logout():
  st.session_state.logged_in = False
  st.session_state.username = None
  st.session_state.nome = None
  st.session_state.role = None


# --- CONSTANTES ---
TIPOS_ERRO = [
    "Item Faltando",
    "Item Sobrando",
    "Produto Trocado",
]

# --- BARRA LATERAL (LOGIN / NAVEGAÇÃO) ---
with st.sidebar:
  st.title("📦 Logística")

  if not st.session_state.logged_in:
    st.info("Você está no modo de **Visualização Pública**.")
    with st.expander("🔐 Acesso Restrito (Login)", expanded=True):
      with st.form("form_login"):
        user_input = st.text_input("Usuário").strip().lower()
        pass_input = st.text_input("Senha", type="password")
        btn_login = st.form_submit_button("Entrar", use_container_width=True)

        if btn_login:
          user_data = banco.autenticar_usuario(user_input, pass_input)
          if user_data:
            st.session_state.logged_in = True
            st.session_state.username = user_input
            st.session_state.nome = user_data[0]
            st.session_state.role = user_data[1]
            banco.registrar_auditoria(
                user_input, user_data[0], "LOGIN", "Usuário realizou login no sistema."
            )
            st.rerun()
          else:
            st.error("Usuário ou senha incorretos.")
  else:
    st.success(f"Olá, **{st.session_state.nome}**!")
    st.caption(f"Perfil: {st.session_state.role.upper()}")

    if st.session_state.role == "admin":
      menu = st.radio(
          "Navegação",
          [
              "📊 Painel Público",
              "⏳ Aprovações Pendentes",
              "🗂️ Todos os Registros",
              "👥 Usuários e Cadastros",
              "📜 Histórico do Sistema",
              "⚙️ Meu Perfil e Senha",
          ],
      )
    elif st.session_state.role == "gestor":
      menu = st.radio(
          "Navegação",
          [
              "📊 Painel Público",
              "⏳ Aprovações Pendentes",
              "🗂️ Todos os Registros",
              "👥 Usuários e Cadastros",
              "⚙️ Meu Perfil e Senha",
          ],
      )
    else:
      menu = st.radio(
          "Navegação",
          [
              "📝 Registrar Ocorrência",
              "📋 Meus Registros",
              "📊 Painel Público",
              "⚙️ Meu Perfil e Senha",
          ],
      )

    st.divider()
    if st.button("🚪 Sair (Logout)", use_container_width=True):
      banco.registrar_auditoria(
          st.session_state.username, st.session_state.nome, "LOGOUT", "Usuário saiu do sistema."
      )
      fazer_logout()
      st.rerun()


# ==============================================================================
# TELA 1: VISUALIZAÇÃO PÚBLICA (LIVRE ACESSO)
# ==============================================================================
def tela_publica():
  st.title("📊 Painel - Erros de Separação")
  st.caption("Painel interativo. Utilize os filtros abaixo para analisar os dados.")

  df_geral = banco.carregar_todos_registros()
  if "status_edicao" in df_geral.columns:
    df_geral = df_geral[df_geral["status_edicao"] != "Pendente_Exclusao"]

  if df_geral.empty:
    st.info("Nenhuma ocorrência registrada no sistema ainda.")
    return

  df_geral["data_obj"] = pd.to_datetime(df_geral["data_hora"])
  min_data = df_geral["data_obj"].dt.date.min()
  max_data = df_geral["data_obj"].dt.date.max()

  st.markdown("### Filtro de Dados")
  col_s1, col_s2, col_s3 = st.columns(3)

  with col_s1:
    opcao_periodo = st.selectbox(
        "Período",
        [
            "Todo o Período",
            "Hoje",
            "Últimos 7 dias",
            "Últimos 30 dias",
            "Este Mês",
            "Personalizado",
        ],
        key="filtro_periodo_atalho",
    )

    hoje = datetime.now().date()
    df_filtrado = df_geral.copy()

    if opcao_periodo == "Hoje":
      df_filtrado = df_filtrado[df_filtrado["data_obj"].dt.date == hoje]
    elif opcao_periodo == "Últimos 7 dias":
      inicio = hoje - pd.Timedelta(days=7)
      df_filtrado = df_filtrado[df_filtrado["data_obj"].dt.date >= inicio]
    elif opcao_periodo == "Últimos 30 dias":
      inicio = hoje - pd.Timedelta(days=30)
      df_filtrado = df_filtrado[df_filtrado["data_obj"].dt.date >= inicio]
    elif opcao_periodo == "Este Mês":
      df_filtrado = df_filtrado[
          (df_filtrado["data_obj"].dt.year == hoje.year)
          & (df_filtrado["data_obj"].dt.month == hoje.month)
      ]
    elif opcao_periodo == "Personalizado":
      c_ini, c_fim = st.columns(2)
      data_inicio = c_ini.date_input(
          "De:", value=min_data, min_value=min_data, max_value=max_data, format="DD/MM/YYYY", key="data_ini_pers"
      )
      data_fim = c_fim.date_input(
          "Até:", value=max_data, min_value=min_data, max_value=max_data, format="DD/MM/YYYY", key="data_fim_pers"
      )
      df_filtrado = df_filtrado[
          (df_filtrado["data_obj"].dt.date >= data_inicio)
          & (df_filtrado["data_obj"].dt.date <= data_fim)
      ]

  with col_s2:
    separadores_disponiveis = sorted(df_filtrado["separador"].unique())
    filtro_sep_multi = st.multiselect("Filtrar por Separador", options=separadores_disponiveis)

  with col_s3:
    erros_disponiveis = sorted(df_filtrado["tipo_erro"].unique())
    filtro_erro_multi = st.multiselect("Filtrar por Tipo de Erro", options=erros_disponiveis)

  if filtro_sep_multi:
    df_filtrado = df_filtrado[df_filtrado["separador"].isin(filtro_sep_multi)]
  if filtro_erro_multi:
    df_filtrado = df_filtrado[df_filtrado["tipo_erro"].isin(filtro_erro_multi)]

  st.divider()

  col_m1, col_m2, col_m3, col_m4 = st.columns(4)
  col_m1.metric("Total de Erros", len(df_filtrado))
  col_m2.metric("Separadores com erros", df_filtrado["separador"].nunique())

  separador_destaque = "-"
  if not df_filtrado.empty:
    resumo_sep = df_filtrado.groupby("separador").agg(
        total_erros=("id", "count"), total_divergentes=("qtd_divergente", "sum")
    ).reset_index()

    resumo_sep = resumo_sep.sort_values(by=["total_erros", "total_divergentes"], ascending=[False, False])

    if not resumo_sep.empty:
      lider = resumo_sep.iloc[0]
      erros_lider = lider["total_erros"]
      divergentes_lider = lider["total_divergentes"]

      empatados = resumo_sep[
          (resumo_sep["total_erros"] == erros_lider) &
          (resumo_sep["total_divergentes"] == divergentes_lider)
      ]

      if len(empatados) > 1:
        separador_destaque = ", ".join(empatados["separador"].tolist())
      else:
        separador_destaque = lider["separador"]

  col_m3.metric("Separador com + Erros", separador_destaque)
  col_m4.metric(
      "Principal Motivo",
      df_filtrado["tipo_erro"].mode()[0] if not df_filtrado.empty else "-",
  )

  st.divider()

  st.subheader("🏆 Análise Gráfica")
  col_g1, col_g2 = st.columns(2)

  with col_g1:
    with st.container():
      st.markdown("### Erros por Separador")
      todos_separadores = banco.get_separadores()
      if not todos_separadores:
        st.info("Nenhum separador cadastrado no sistema.")
      else:
        if not df_filtrado.empty:
          ranking_sep = df_filtrado.groupby("separador").agg(
              Erros=("id", "count"), Divergentes=("qtd_divergente", "sum")
          ).reset_index()
        else:
          ranking_sep = pd.DataFrame(columns=["separador", "Erros", "Divergentes"])

        df_todos_seps = pd.DataFrame({"separador": todos_separadores})
        ranking_sep = pd.merge(df_todos_seps, ranking_sep, on="separador", how="left")
        ranking_sep["Erros"] = ranking_sep["Erros"].fillna(0).astype(int)
        ranking_sep["Divergentes"] = ranking_sep["Divergentes"].fillna(0).astype(int)

        max_erros = max(ranking_sep["Erros"]) if not ranking_sep.empty else 1
        if max_erros == 0:
          max_erros = 3

        ranking_sep["erros_plot"] = ranking_sep["Erros"].apply(lambda x: 0.15 if x == 0 else x)
        ranking_sep = ranking_sep.sort_values(by=["Erros", "Divergentes"], ascending=[True, True])

        fig_sep = px.bar(
            ranking_sep, x="erros_plot", y="separador", orientation="h", text="Erros",
            color="Erros", color_continuous_scale="RdYlGn_r", range_color=[0, max_erros]
        )
        fig_sep.update_traces(textposition="outside", texttemplate="%{text}", cliponaxis=False)
        fig_sep.update_xaxes(tickmode="linear", dtick=1, range=[-0.1, max_erros + 0.8])
        fig_sep.update_layout(
            yaxis={"categoryorder": "array", "categoryarray": ranking_sep["separador"].tolist(), "title": "Separador"},
            xaxis_title="Erros", margin=dict(l=0, r=30, t=20, b=0), height=350,
        )
        st.plotly_chart(fig_sep, use_container_width=True, key="grafico_separador_pub")

  with col_g2:
    with st.container():
      st.markdown("### Tipos de Erros Mais Comuns")
      if df_filtrado.empty:
        st.info("Sem dados para exibir.")
      else:
        ranking_erro = df_filtrado["tipo_erro"].value_counts().reset_index()
        ranking_erro.columns = ["Tipo de Erro", "Erros"]
        ranking_erro = ranking_erro.sort_values(by="Erros", ascending=False)

        fig_erro = px.bar(
            ranking_erro, x="Tipo de Erro", y="Erros", text="Erros", color="Erros", color_continuous_scale="Blues"
        )
        fig_erro.update_traces(textposition="outside", texttemplate="%{text}", cliponaxis=False)
        max_erros_erro = max(ranking_erro["Erros"]) if not ranking_erro.empty else 1
        fig_erro.update_yaxes(range=[0, max_erros_erro + max_erros_erro * 0.25 if max_erros_erro > 0 else 3])
        fig_erro.update_layout(
            xaxis={"title": "Tipo de Erro", "tickangle": -20, "categoryorder": "array", "categoryarray": ranking_erro["Tipo de Erro"].tolist()},
            yaxis_title="Quantidade", margin=dict(l=0, r=0, t=30, b=0), height=350,
        )
        st.plotly_chart(fig_erro, use_container_width=True, key="grafico_erro_pub")

  st.subheader("📈 Curva de Desempenho (Evolução Diária)")
  df_filtrado["data_dia"] = df_filtrado["data_obj"].dt.date
  evolucao = df_filtrado.groupby("data_dia").size().reset_index(name="Quantidade de Erros")
  evolucao = evolucao.sort_values("data_dia")

  if not evolucao.empty:
    fig_linha = px.line(
        evolucao, x="data_dia", y="Quantidade de Erros", markers=True, line_shape="spline", color_discrete_sequence=["#FF4B4B"]
    )
    fig_linha.update_layout(xaxis_title="Data", yaxis_title="Total de Erros", margin=dict(l=0, r=0, t=20, b=0), height=300)
    st.plotly_chart(fig_linha, use_container_width=True, key="grafico_linha_pub")

  st.divider()

  st.subheader("📋 Detalhamento das Ocorrências Filtradas")
  colunas_exibir = [
      "id", "data_hora", "num_pedido", "separador", "tipo_erro", "sku_produto", "qtd_divergente", "observacao", "conferente_nome"
  ]
  df_exibir = df_filtrado[colunas_exibir].rename(
      columns={
          "id": "ID", "data_hora": "Data/Hora", "num_pedido": "Pedido", "separador": "Separador",
          "tipo_erro": "Tipo de Erro", "sku_produto": "SKU", "qtd_divergente": "Qtd",
          "observacao": "Observação", "conferente_nome": "Conferente",
      }
  )

  st.dataframe(df_exibir, use_container_width=True, hide_index=True)

  csv = df_exibir.to_csv(index=False, sep=";").encode("utf-8-sig")
  st.download_button(
      label="📥 Baixar Dados Filtrados (CSV/Excel)",
      data=csv,
      file_name=f"relatorio_filtrado_{datetime.now().strftime('%Y%m%d')}.csv",
      mime="text/csv",
  )


# ==============================================================================
# TELAS DO CONFERENTE
# ==============================================================================
def tela_registrar_ocorrencia():
  with st.container():
    st.title("📝 Registrar Nova Ocorrência")
    separadores_brutos = banco.get_separadores()

    if not separadores_brutos:
      st.warning("Nenhum separador cadastrado. Solicite ao Administrador.")
      return

    separadores = ["-- Selecione o Separador --"] + separadores_brutos
    tipos_erro_opcoes = ["-- Selecione o Tipo de Erro --"] + TIPOS_ERRO

    with st.form("form_novo_erro_conf", clear_on_submit=True):
      col1, col2 = st.columns(2)
      with col1:
        num_pedido = st.text_input(
            "Número do Pedido *", placeholder="Ex: PED-1045", key="input_num_pedido_reg"
        )
        separador = st.selectbox("Separador *", separadores, index=0, key="select_separador_reg")
        sku_produto = st.text_input(
            "Código/SKU do Produto", placeholder="Ex: 78912345", key="input_sku_reg"
        )

      with col2:
        st.text_input(
            "Conferente Responsável", value=st.session_state.nome, disabled=True, key="input_conf_resp"
        )
        tipo_erro = st.selectbox("Tipo de Erro *", tipos_erro_opcoes, index=0, key="select_tipo_erro_reg")
        qtd_divergente = st.number_input(
            "Quantidade Divergente *", min_value=0, value=0, step=1, key="num_qtd_div_reg"
        )

      observacao = st.text_area("Observações adicionais", key="text_obs_reg")

      if st.form_submit_button("💾 Salvar Ocorrência", use_container_width=True):
        erros_validacao = []

        if not num_pedido.strip():
          erros_validacao.append("O **Número do Pedido** é obrigatório.")
        if separador == "-- Selecione o Separador --":
          erros_validacao.append(
              "Você deve **selecionar o separador** responsável pelo erro."
          )
        if tipo_erro == "-- Selecione o Tipo de Erro --":
          erros_validacao.append(
              "Você deve **selecionar o tipo de erro** ocorrido."
          )
        if qtd_divergente <= 0:
          erros_validacao.append(
              "A **Quantidade Divergente** deve ser maior que zero (0)."
          )

        if erros_validacao:
          for err in erros_validacao:
            st.error(f"⚠️ {err}")
        else:
          banco.inserir_registro(
              num_pedido.strip().upper(),
              st.session_state.username,
              st.session_state.nome,
              separador,
              tipo_erro,
              sku_produto.strip().upper(),
              qtd_divergente,
              observacao,
          )
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "REGISTRAR_OCORRENCIA", f"Registrou divergência no pedido {num_pedido.strip().upper()}."
          )
          st.success("✅ Ocorrência registrada com sucesso!")


def tela_meus_registros():
  with st.container():
    st.title("📋 Meus Registros")
    df = banco.carregar_registros_por_conferente(st.session_state.username)

    if df.empty:
      st.info("Você ainda não registrou nenhuma ocorrência.")
      return

    st.dataframe(
        df[["id", "data_hora", "num_pedido", "separador", "tipo_erro", "sku_produto", "qtd_divergente", "status_edicao"]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("✏️ Solicitar Edição de Registro")
    st.caption("A alteração ficará com status 'Pendente' e só entrará em vigor após aprovação do Administrador ou Gestor.")

    id_selecionado = st.selectbox("Selecione o ID do registro para editar", df["id"], key="select_id_edicao_conf")
    reg_atual = df[df["id"] == id_selecionado].iloc[0]

    if reg_atual["status_edicao"] == "Pendente":
      st.warning("⚠️ Este registro já possui uma edição aguardando aprovação.")
    else:
      separadores = banco.get_separadores()
      idx_sep = separadores.index(reg_atual["separador"]) if reg_atual["separador"] in separadores else 0
      idx_erro = TIPOS_ERRO.index(reg_atual["tipo_erro"]) if reg_atual["tipo_erro"] in TIPOS_ERRO else 0

      with st.form("form_editar_conferente_unico"):
        c1, c2 = st.columns(2)
        novo_pedido = c1.text_input("Número do Pedido", value=reg_atual["num_pedido"], key="edit_num_pedido")
        novo_sep = c1.selectbox("Separador", separadores, index=idx_sep, key="edit_separador")
        novo_sku = c1.text_input("SKU", value=reg_atual["sku_produto"], key="edit_sku")

        novo_erro = c2.selectbox("Tipo de Erro", TIPOS_ERRO, index=idx_erro, key="edit_tipo_erro")
        nova_qtd = c2.number_input("Quantidade", min_value=0, value=int(reg_atual["qtd_divergente"]), key="edit_qtd")
        nova_obs = st.text_area("Observação", value=reg_atual["observacao"], key="edit_obs")

        if st.form_submit_button("📤 Enviar Edição para Aprovação"):
          dados_novos = {
              "num_pedido": novo_pedido.strip().upper(),
              "separador": novo_sep,
              "sku_produto": novo_sku.strip().upper(),
              "tipo_erro": novo_erro,
              "qtd_divergente": nova_qtd,
              "observacao": nova_obs,
          }
          banco.solicitar_edicao_registro(id_selecionado, dados_novos)
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "SOLICITAR_EDICAO", f"Solicitou edição do registro ID #{id_selecionado}."
          )
          st.success("Solicitação enviada! Aguarde a aprovação.")
          st.rerun()


# ==============================================================================
# TELA DE PERFIL
# ==============================================================================
def tela_meu_perfil():
  if st.session_state.role == "admin":
    st.title("⚙️ Meu Perfil e Credenciais (Administrador)")
    tab1, tab2 = st.tabs(["👤 Alterar Login e Nome", "🔑 Alterar Senha"])

    with tab1:
      st.subheader("Alterar Dados do Administrador")
      with st.form("form_dados_admin"):
        novo_login = st.text_input("Login de Acesso", value=st.session_state.username)
        novo_nome = st.text_input("Nome de Exibição", value=st.session_state.nome)

        if st.form_submit_button("Salvar Alterações"):
          if not novo_login.strip() or not novo_nome.strip():
            st.error("Preencha todos os campos.")
          else:
            sucesso, msg = banco.atualizar_dados_usuario(st.session_state.username, novo_login, novo_nome)
            if sucesso:
              old_user = st.session_state.username
              st.session_state.username = novo_login.strip().lower()
              st.session_state.nome = novo_nome.strip()
              banco.registrar_auditoria(
                  st.session_state.username, st.session_state.nome,
                  "ATUALIZAR_PERFIL", f"Administrador atualizou seus dados de login ({old_user} -> {novo_login})."
              )
              st.success(msg)
              st.rerun()
            else:
              st.error(msg)

    with tab2:
      st.subheader("Alterar Senha do Administrador")
      with st.form("form_senha_admin"):
        senha_atual = st.text_input("Senha Atual", type="password")
        nova_senha = st.text_input("Nova Senha", type="password")
        confirma_senha = st.text_input("Confirme a Nova Senha", type="password")

        if st.form_submit_button("Atualizar Senha"):
          if nova_senha != confirma_senha:
            st.error("As novas senhas não coincidem.")
          elif len(nova_senha) < 4:
            st.error("A senha deve ter pelo menos 4 caracteres.")
          else:
            sucesso = banco.alterar_senha(st.session_state.username, senha_atual, nova_senha)
            if sucesso:
              banco.registrar_auditoria(
                  st.session_state.username, st.session_state.nome,
                  "ALTERAR_SENHA", "Administrador alterou sua senha."
              )
              st.success("Senha alterada com sucesso!")
            else:
              st.error("Senha atual incorreta.")
  else:
    with st.container():
      st.title("🔑 Alterar Minha Senha")
      st.caption(f"Usuário logado: **{st.session_state.username}** ({st.session_state.nome}) - Perfil: **{st.session_state.role.upper()}**")
      
      with st.form("form_senha_gestor_conf_unico"):
        senha_atual = st.text_input("Senha Atual", type="password", key="pwd_atual_g")
        nova_senha = st.text_input("Nova Senha", type="password", key="pwd_nova_g")
        confirma_senha = st.text_input("Confirme a Nova Senha", type="password", key="pwd_confirma_g")

        if st.form_submit_button("Atualizar Senha"):
          if nova_senha != confirma_senha:
            st.error("As novas senhas não coincidem.")
          elif len(nova_senha) < 4:
            st.error("A senha deve ter pelo menos 4 caracteres.")
          else:
            sucesso = banco.alterar_senha(st.session_state.username, senha_atual, nova_senha)
            if sucesso:
              banco.registrar_auditoria(
                  st.session_state.username, st.session_state.nome,
                  "ALTERAR_SENHA", f"Usuário ({st.session_state.role}) alterou sua senha."
              )
              st.success("Senha alterada com sucesso!")
            else:
              st.error("Senha atual incorreta.")


# ==============================================================================
# TELAS DO ADMINISTRADOR E GESTOR
# ==============================================================================
def tela_aprovacoes():
  st.title("⏳ Aprovação de Solicitações Pendentes")
  df_todos = banco.carregar_todos_registros()
  
  df_pend_edicao = df_todos[df_todos["status_edicao"] == "Pendente"]
  df_pend_exclusao = df_todos[df_todos["status_edicao"] == "Pendente_Exclusao"]

  if df_pend_edicao.empty and df_pend_exclusao.empty:
    st.success("🎉 Nenhuma solicitação pendente no momento!")
    return

  if not df_pend_edicao.empty:
    st.subheader("✏️ Edições de Registros Pendentes")
    for _, row in df_pend_edicao.iterrows():
      novos = json.loads(row["dados_pendentes"])
      with st.expander(f"ID #{row['id']} - Pedido: {row['num_pedido']} (Solicitado por: {row['conferente_nome']})", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
          st.markdown("**📌 Dados Atuais:**")
          st.write(f"**Pedido:** {row['num_pedido']}")
          st.write(f"**Separador:** {row['separador']}")
          st.write(f"**Erro:** {row['tipo_erro']}")
          st.write(f"**SKU:** {row['sku_produto']} | **Qtd:** {row['qtd_divergente']}")
          st.write(f"**Obs:** {row['observacao']}")

        with c2:
          st.markdown("**📝 Alteração Solicitada:**")
          st.write(f"**Pedido:** {novos['num_pedido']}")
          st.write(f"**Separador:** {novos['separador']}")
          st.write(f"**Erro:** {novos['tipo_erro']}")
          st.write(f"**SKU:** {novos['sku_produto']} | **Qtd:** {novos['qtd_divergente']}")
          st.write(f"**Obs:** {novos['observacao']}")

        col_b1, col_b2, _ = st.columns([1, 1, 3])
        if col_b1.button("✅ Aprovar", key=f"apr_{row['id']}", use_container_width=True):
          banco.aprovar_edicao(row["id"], novos)
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "APROVAR_EDICAO", f"Aprovou a edição do registro ID #{row['id']}."
          )
          st.success("Edição aprovada!")
          st.rerun()

        if col_b2.button("❌ Rejeitar", key=f"rej_{row['id']}", use_container_width=True):
          banco.rejeitar_edicao(row["id"])
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "REJEITAR_EDICAO", f"Rejeitou a edição do registro ID #{row['id']}."
          )
          st.warning("Edição rejeitada.")
          st.rerun()

  if not df_pend_exclusao.empty:
    st.divider()
    st.subheader("🗑️ Solicitações de Exclusão em Massa (Enviadas por Gestores)")
    for _, row in df_pend_exclusao.iterrows():
      ids_solicitados = json.loads(row["dados_pendentes"])
      with st.expander(f"Solicitação ID #{row['id']} - Solicitado por: {row['conferente_nome']} ({row['data_hora']})", expanded=True):
        st.warning(f"O gestor **{row['conferente_nome']}** solicitou a exclusão dos seguintes IDs de registros: `{ids_solicitados}`")
        
        col_b1, col_b2, _ = st.columns([1, 1, 3])
        if col_b1.button("✅ Aprovar Exclusão", key=f"apr_exc_{row['id']}", use_container_width=True):
          banco.excluir_multiplos_registros(ids_solicitados)
          banco.excluir_registro(row["id"])
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "APROVAR_EXCLUSAO", f"Aprovou exclusão em massa dos IDs: {ids_solicitados}"
          )
          st.success("Exclusão em massa aprovada e executada!")
          st.rerun()

        if col_b2.button("❌ Rejeitar Exclusão", key=f"rej_exc_{row['id']}", use_container_width=True):
          banco.excluir_registro(row["id"])
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "REJEITAR_EXCLUSAO", f"Rejeitou a solicitação de exclusão IDs: {ids_solicitados}"
          )
          st.warning("Solicitação de exclusão rejeitada.")
          st.rerun()


def tela_admin_registros():
  st.title("🗂️ Gestão Total de Registros")
  df = banco.carregar_todos_registros()
  if "status_edicao" in df.columns:
    df = df[df["status_edicao"] != "Pendente_Exclusao"]

  if df.empty:
    st.info("Nenhum registro encontrado no sistema.")
    return

  st.markdown("### 🗑️ Exclusão em Massa por Seleção")
  st.caption("Marque a caixa na coluna **'Excluir?'** nos registros que deseja apagar e clique no botão.")

  df_edit = df.drop(columns=["dados_pendentes"], errors="ignore").copy()
  df_edit = df_edit.reset_index(drop=True)  # <--- CORREÇÃO DO ERRO REMOVECHILD APLICADA AQUI
  df_edit.insert(0, "Excluir", False)

  df_resultado = st.data_editor(
      df_edit,
      column_config={
          "Excluir": st.column_config.CheckboxColumn(
              "Excluir?", help="Marque para selecionar este registro", default=False
          )
      },
      disabled=[col for col in df_edit.columns if col != "Excluir"],
      hide_index=True,
      use_container_width=True,
      key="tabela_exclusao_massa",
  )

  ids_para_excluir = df_resultado[df_resultado["Excluir"] == True]["id"].tolist()

  col_b1, col_b2 = st.columns([2, 4])
  with col_b1:
    if ids_para_excluir:
      st.warning(f"⚠️ {len(ids_para_excluir)} registro(s) selecionado(s).")
      
      if st.session_state.role == "admin":
        if st.button("🗑️ Excluir Selecionados", type="primary", use_container_width=True):
          banco.excluir_multiplos_registros(ids_para_excluir)
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "EXCLUIR_REGISTROS", f"Administrador excluiu os IDs: {ids_para_excluir}"
          )
          st.success(f"{len(ids_para_excluir)} registro(s) excluído(s) com sucesso!")
          st.rerun()
      else:
        if st.button("📤 Solicitar Exclusão ao Administrador", type="primary", use_container_width=True):
          banco.solicitar_exclusao_registros(
              ids_para_excluir, st.session_state.username, st.session_state.nome
          )
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "SOLICITAR_EXCLUSAO", f"Gestor solicitou exclusão dos IDs: {ids_para_excluir}"
          )
          st.success("Solicitação de exclusão enviada para aprovação do Administrador!")
          st.rerun()
    else:
      st.info("Nenhum registro selecionado.")

  if st.session_state.role == "admin":
    st.divider()
    st.markdown("### ⚠️ Zona de Perigo (Apenas Administrador)")
    with st.expander("🗑️ Zerar Base de Registros e Reiniciar IDs"):
      st.warning("Isso apagará **todos** os registros de erros do sistema permanentemente e reiniciará a contagem dos IDs do zero.")
      confirma_zerar = st.text_input("Digite 'ZERAR' para confirmar:", key="input_confirma_zerar")
      if st.button("🚨 Zerar Todos os Registros e IDs", type="primary"):
        if confirma_zerar == "ZERAR":
          banco.zerar_registros_e_ids()
          banco.registrar_auditoria(
              st.session_state.username, st.session_state.nome,
              "ZERAR_BASE", "O administrador limpou todos os registros e resetou os IDs."
          )
          st.success("Base de dados limpa com sucesso!")
          st.rerun()
        else:
          st.error("Digite exatamente 'ZERAR' para prosseguir.")

  st.divider()
  csv = df.drop(columns=["dados_pendentes"], errors="ignore").to_csv(index=False, sep=";").encode("utf-8-sig")
  st.download_button(
      "📥 Baixar Base Completa (CSV)",
      data=csv,
      file_name=f"relatorio_geral_{datetime.now().strftime('%Y%m%d')}.csv",
      mime="text/csv",
  )


def tela_admin_usuarios():
  st.title("👥 Gestão de Usuários e Separadores")
  tab1, tab2 = st.tabs(["🔐 Usuários (Conferentes e Gestores)", "👷 Separadores"])

  with tab1:
    col1, col2 = st.columns([1, 1.5])
    with col1:
      st.subheader("Novo Usuário")
      with st.form("form_novo_user", clear_on_submit=True):
        novo_nome = st.text_input("Nome Completo (Ex: Ana Souza)")
        novo_user = st.text_input("Login de Acesso (Ex: ana.souza)").strip().lower()
        novo_role = st.selectbox("Perfil de Acesso", ["conferente", "gestor"])
        st.caption("A senha inicial será definida automaticamente como: **123456**")
        
        if st.form_submit_button("Criar Usuário", use_container_width=True):
          if novo_nome and novo_user:
            try:
              banco.criar_usuario(novo_user, novo_nome, novo_role)
              banco.registrar_auditoria(
                  st.session_state.username, st.session_state.nome,
                  "CRIAR_USUARIO", f"Criou usuário '{novo_user}' com perfil '{novo_role}'."
              )
              st.success(f"Usuário '{novo_user}' ({novo_role}) criado!")
              st.rerun()
            except Exception:
              st.error("Este login já existe ou ocorreu um erro.")
          else:
            st.error("Preencha todos os campos.")

    with col2:
      st.subheader("Usuários Cadastrados")
      df_users = banco.listar_usuarios()

      if df_users.empty:
        st.info("Nenhum usuário cadastrado.")
      else:
        st.dataframe(df_users, use_container_width=True, hide_index=True)

        if st.session_state.role == "admin":
          user_acao = st.selectbox("Selecione o usuário para gerenciar:", df_users["username"], key="select_user_acao")
          nome_atual_user = df_users[df_users["username"] == user_acao]["nome"].values[0]

          with st.expander("✏️ Editar Nome e Login do Usuário"):
            with st.form(f"form_edit_user_{user_acao}"):
              edit_nome = st.text_input("Novo Nome Completo", value=nome_atual_user)
              edit_login = st.text_input("Novo Login de Acesso", value=user_acao).strip().lower()

              if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                if not edit_nome.strip() or not edit_login.strip():
                  st.error("Nome e login não podem ficar vazios.")
                else:
                  sucesso, msg = banco.atualizar_dados_usuario(user_acao, edit_login, edit_nome.strip())
                  if sucesso:
                    banco.registrar_auditoria(
                        st.session_state.username, st.session_state.nome,
                        "EDITAR_USUARIO", f"Alterou dados do usuário '{user_acao}' para '{edit_login}'."
                    )
                    st.success(msg)
                    st.rerun()
                  else:
                    st.error(msg)

          st.write("")
          c_b1, c_b2 = st.columns(2)

          if c_b1.button("🔄 Resetar Senha (123456)", key=f"reset_{user_acao}", use_container_width=True):
            banco.resetar_senha_usuario(user_acao)
            banco.registrar_auditoria(
                st.session_state.username, st.session_state.nome,
                "RESETAR_SENHA", f"Resetou a senha do usuário '{user_acao}'."
            )
            st.success(f"Senha de '{user_acao}' resetada para 123456.")

          if c_b2.button("🗑️ Excluir Usuário", key=f"del_user_{user_acao}", use_container_width=True):
            banco.excluir_usuario(user_acao)
            banco.registrar_auditoria(
                st.session_state.username, st.session_state.nome,
                "EXCLUIR_USUARIO", f"Excluiu o usuário '{user_acao}'."
            )
            st.warning(f"Usuário '{user_acao}' excluído.")
            st.rerun()
        else:
          st.info("ℹ️ Gestores podem cadastrar novos conferentes e separadores, mas a edição de logins, redefinição de senhas e exclusão de contas são restritas ao Administrador.")

  with tab2:
    st.subheader("Cadastro de Separadores")
    with st.form("form_sep", clear_on_submit=True):
      nome_sep = st.text_input("Nome do Separador")
      if st.form_submit_button("Adicionar Separador"):
        if nome_sep.strip():
          try:
            banco.adicionar_separador(nome_sep.strip())
            banco.registrar_auditoria(
                st.session_state.username, st.session_state.nome,
                "CRIAR_SEPARADOR", f"Adicionou o separador '{nome_sep.strip()}'."
            )
            st.success(f"Separador '{nome_sep.strip()}' adicionado!")
            st.rerun()
          except Exception:
            st.error("Separador já cadastrado.")

    seps = banco.get_separadores()
    if seps:
      sep_del = st.selectbox("Remover Separador", seps, key="select_del_sep")
      if st.button("Remover", key="btn_del_sep"):
        banco.remover_separador(sep_del)
        banco.registrar_auditoria(
            st.session_state.username, st.session_state.nome,
            "REMOVER_SEPARADOR", f"Removeu o separador '{sep_del}'."
        )
        st.success(f"Separador '{sep_del}' removido.")
        st.rerun()


def tela_historico():
  st.title("📜 Histórico de Ações do Sistema (Auditoria)")
  st.caption("Registro detalhado de todas as ações executadas por conferentes, gestores e administradores.")

  df_audit = banco.carregar_auditoria()
  if df_audit.empty:
    st.info("Nenhum evento registrado na auditoria ainda.")
    return

  st.dataframe(
      df_audit.rename(
          columns={
              "id": "ID",
              "data_hora": "Data/Hora",
              "usuario": "Usuário",
              "nome": "Nome",
              "acao": "Ação",
              "detalhes": "Detalhes",
          }
      ),
      use_container_width=True,
      hide_index=True,
  )

  csv = df_audit.to_csv(index=False, sep=";").encode("utf-8-sig")
  st.download_button(
      "📥 Baixar Relatório de Auditoria (CSV)",
      data=csv,
      file_name=f"auditoria_{datetime.now().strftime('%Y%m%d')}.csv",
      mime="text/csv",
  )


# ==============================================================================
# ROTEAMENTO PRINCIPAL
# ==============================================================================
container_principal = st.container()

with container_principal:
  if not st.session_state.logged_in:
    tela_publica()
  else:
    if menu == "📊 Painel Público":
      tela_publica()
    elif menu == "📝 Registrar Ocorrência":
      tela_registrar_ocorrencia()
    elif menu == "📋 Meus Registros":
      tela_meus_registros()
    elif menu == "⚙️ Meu Perfil e Senha":
      tela_meu_perfil()
    elif menu == "⏳ Aprovações Pendentes":
      tela_aprovacoes()
    elif menu == "🗂️ Todos os Registros":
      tela_admin_registros()
    elif menu == "👥 Usuários e Cadastros":
      tela_admin_usuarios()
    elif menu == "📜 Histórico do Sistema" and st.session_state.role == "admin":
      tela_historico()