import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Ponto Digital 2026", page_icon="⏰")

# 2. FUNÇÕES DE BANCO DE DATA E LÓGICA (DEVEM VIR ANTES DA INTERFACE)
def abrir_conexao():
    return sqlite3.connect('ponto_loja.db', check_same_thread=False)

def inicializar_banco():
    conn = abrir_conexao()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, data_hora TEXT)''')
    
    # Verifica se há funcionários, se não, adiciona um teste
    cursor.execute("SELECT COUNT(*) FROM funcionarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO funcionarios (nome) VALUES ('Funcionario Exemplo')")
    
    conn.commit()
    conn.close()

def registrar(nome, tipo):
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
        st.error(f"Erro ao salvar: {e}")

# INICIALIZA O BANCO
inicializar_banco()

# 3. INTERFACE DO USUÁRIO
st.title("⏰ Relógio de Ponto")
st.write("---")

# Busca lista de funcionários atualizada
conn = abrir_conexao()
df_func = pd.read_sql_query("SELECT nome FROM funcionarios", conn)
lista_func = df_func['nome'].tolist()
conn.close()

usuario = st.selectbox("Selecione seu nome para bater o ponto:", [""] + lista_func)

if usuario:
    st.subheader(f"Funcionário: {usuario}")
    
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

# 4. PAINEL LATERAL DO GERENTE
with st.sidebar:
    st.header("⚙️ Administração")
    senha = st.text_input("Senha de Acesso", type="password")
    
    if senha == "1234":  # Altere sua senha aqui
        st.divider()
        st.subheader("Cadastrar Colaborador")
        novo_nome = st.text_input("Nome Completo")
        if st.button("Salvar Novo Funcionário"):
            if novo_nome:
                try:
                    conn = abrir_conexao()
                    conn.execute("INSERT INTO funcionarios (nome) VALUES (?)", (novo_nome,))
                    conn.commit()
                    conn.close()
                    st.success("Cadastrado com sucesso! Recarregue a página.")
                except:
                    st.error("Nome já existe ou erro no banco.")
            else:
                st.warning("Digite um nome.")

        st.divider()
        st.subheader("Relatórios")
        if st.button("Gerar Planilha de Horários"):
            conn = abrir_conexao()
            df_regs = pd.read_sql_query("SELECT funcionario, tipo, data_hora FROM registros ORDER BY id DESC", conn)
            conn.close()
            
            if not df_regs.empty:
                nome_arq = "ponto_2026.xlsx"
                df_regs.to_excel(nome_arq, index=False)
                with open(nome_arq, "rb") as f:
                    st.download_button("⬇️ Baixar Excel", f, file_name=nome_arq)
            else:
                st.info("Ainda não há registros de ponto.")