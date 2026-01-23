import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Ponto Digital 2026", page_icon="⏰")

# 2. DEFINIÇÃO DAS FUNÇÕES (Devem vir antes de serem chamadas pelos botões)

def abrir_conexao():
    """Cria conexão com o banco de dados"""
    return sqlite3.connect('ponto_loja.db', check_same_thread=False)

def inicializar_banco():
    """Cria as tabelas se elas não existirem"""
    conn = abrir_conexao()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, data_hora TEXT)''')
    
    # Adiciona um funcionário inicial se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM funcionarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO funcionarios (nome) VALUES ('Gerente')")
    
    conn.commit()
    conn.close()

def registrar_ponto(nome, tipo):
    """Salva a batida de ponto no banco de dados"""
    try:
        conn = abrir_conexao()
        cursor = conn.cursor()
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cursor.execute("INSERT INTO registros (funcionario, tipo, data_hora) VALUES (?, ?, ?)", 
                       (nome, tipo, agora))
        conn.commit()
        conn.close()
        st.success(f"✅ {tipo} registrado para {nome} às {datetime.now().strftime('%H:%M')}!")
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")

# --- INICIALIZAÇÃO ---
inicializar_banco()

# 3. INTERFACE DO USUÁRIO (FRONT-END)
st.title("⏰ Relógio de Ponto")
st.write("Sistema de registro para funcionários")
st.divider()

# Busca lista de funcionários para o selectbox
conn = abrir_conexao()
df_func = pd.read_sql_query("SELECT nome FROM funcionarios", conn)
lista_func = df_func['nome'].tolist()
conn.close()

usuario = st.selectbox("Selecione seu nome:", [""] + lista_func)

if usuario:
    st.subheader(f"Colaborador: {usuario}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 ENTRADA", use_container_width=True):
            registrar_ponto(usuario, "Entrada")
        if st.button("☕ SAÍDA ALMOÇO", use_container_width=True):
            registrar_ponto(usuario, "Saída Almoço")
            
    with col2:
        if st.button("🍱 VOLTA ALMOÇO", use_container_width=True):
            registrar_ponto(usuario, "Volta Almoço")
        if st.button("🏠 SAÍDA FINAL", use_container_width=True):
            registrar_ponto(usuario, "Saída Final")

# 4. PAINEL DO GERENTE (LATERAL)
with st.sidebar:
    st.header("⚙️ Administração")
    senha = st.text_input("Senha de Acesso", type="password")
    
    if senha == "1234":  # Troque pela sua senha
        st.divider()
        st.subheader("Novos Funcionários")
        novo_nome = st.text_input("Nome do Colaborador")
        if st.button("Cadastrar Funcionário"):
            if novo_nome:
                try:
                    conn = abrir_conexao()
                    conn.execute("INSERT INTO funcionarios (nome) VALUES (?)", (novo_nome,))
                    conn.commit()
                    conn.close()
                    st.success("Cadastrado! Recarregue a página.")
                    st.rerun() # Atualiza a lista de nomes imediatamente
                except:
                    st.error("Erro: Nome já existe.")
            else:
                st.warning("Preencha o nome.")

        st.divider()
        st.subheader("Exportar Relatórios")
        if st.button("Gerar Planilha Excel"):
            conn = abrir_conexao()
            df_regs = pd.read_sql_query("SELECT funcionario, tipo, data_hora FROM registros ORDER BY id DESC", conn)
            conn.close()
            
            if not df_regs.empty:
                excel_nome = "ponto_registros.xlsx"
                df_regs.to_excel(excel_nome, index=False)
                with open(excel_nome, "rb") as f:
                    st.download_button("⬇️ Baixar Planilha", f, file_name=excel_nome)
            else:
                st.info("Nenhum ponto registrado ainda.")