import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Configuração da Página
st.set_page_config(page_title="Ponto Digital 2026", page_icon="⏰")

# Função para conectar ao banco SQLite
def abrir_conexao():
    conn = sqlite3.connect('ponto_loja.db', check_same_thread=False)
    return conn

# Criação das tabelas caso não existam
def inicializar_banco():
    conn = abrir_conexao()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, data_hora TEXT)''')
    # Cadastra um funcionário padrão se estiver vazio
    cursor.execute("SELECT COUNT(*) FROM funcionarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO funcionarios (nome) VALUES ('Usuario Exemplo')")
    conn.commit()
    conn.close()

inicializar_banco()

# --- INTERFACE ---
st.title("⏰ Relógio de Ponto")

# Busca funcionários
conn = abrir_conexao()
lista_func = pd.read_sql_query("SELECT nome FROM funcionarios", conn)['nome'].tolist()
conn.close()

usuario = st.selectbox("Selecione seu nome:", [""] + lista_func)

if usuario:
    st.write(f"Olá, *{usuario}*!")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🚀 ENTRADA", use_container_width=True):
            registrar(usuario, "Entrada")
        if st.button("☕ SAÍDA ALMOÇO", use_container_width=True):
            registrar(usuario, "Saída Almoço")
            
    with col2:
        if st.button("🍱 VOLTA ALMOÇO", use_container_width=True):
            registrar(usuario, "Volta Almoço")
        if st.button("🏠 SAÍDA FINAL", use_container_width=True):
            registrar(usuario, "Saída Final")

def registrar(nome, tipo):
    conn = abrir_conexao()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cursor.execute("INSERT INTO registros (funcionario, tipo, data_hora) VALUES (?, ?, ?)", (nome, tipo, agora))
    conn.commit()
    conn.close()
    st.toast(f"Ponto de {tipo} registrado!", icon='✅')

# --- PAINEL DO GERENTE ---
with st.sidebar:
    st.header("Administração")
    senha = st.text_input("Senha do Gerente", type="password")
    
    if senha == "1234": # Altere sua senha aqui
        st.divider()
        st.subheader("Novo Funcionário")
        novo_nome = st.text_input("Nome completo")
        if st.button("Cadastrar"):
            try:
                conn = abrir_conexao()
                conn.execute("INSERT INTO funcionarios (nome) VALUES (?)", (novo_nome,))
                conn.commit()
                conn.close()
                st.success("Cadastrado! Atualize a página.")
            except:
                st.error("Erro ou nome já existe.")

        st.divider()
        st.subheader("Relatórios")
        if st.button("Gerar Planilha Excel"):
            conn = abrir_conexao()
            df = pd.read_sql_query("SELECT * FROM registros", conn)
            conn.close()
            df.to_excel("ponto.xlsx", index=False)
            with open("ponto.xlsx", "rb") as f:

                st.download_button("Baixar Arquivo Excel", f, file_name="ponto_2026.xlsx")
