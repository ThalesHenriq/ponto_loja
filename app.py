import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pytz
from PIL import Image
import io

st.set_page_config(page_title="Ponto Facial 2026", page_icon="📸")

def abrir_conexao():
    return sqlite3.connect('ponto_loja.db', check_same_thread=False)

# Adicionamos uma coluna para salvar a imagem (em formato texto/base64 ou binário)
def inicializar_banco():
    conn = abrir_conexao()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, data_hora TEXT, foto BLOB)''')
    conn.commit()
    conn.close()

def registrar_com_foto(nome, tipo, foto_capturada):
    if foto_capturada is None:
        st.error("❌ Você precisa tirar uma foto para confirmar sua identidade!")
        return

    try:
        conn = abrir_conexao()
        cursor = conn.cursor()
        
        # Horário de Brasília
        fuso_br = pytz.timezone('America/Sao_Paulo')
        agora_br = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
        
        # Converter foto para binário
        img = Image.open(foto_capturada)
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        foto_binaria = buf.getvalue()

        cursor.execute("INSERT INTO registros (funcionario, tipo, data_hora, foto) VALUES (?, ?, ?, ?)", 
                       (nome, tipo, agora_br, foto_binaria))
        conn.commit()
        conn.close()
        st.success(f"✅ Ponto de {tipo} batido com foto!")
    except Exception as e:
        st.error(f"Erro: {e}")

inicializar_banco()

st.title("📸 Ponto com Validação Visual")

conn = abrir_conexao()
lista_func = pd.read_sql_query("SELECT nome FROM funcionarios", conn)['nome'].tolist()
conn.close()

usuario = st.selectbox("Selecione seu nome:", [""] + lista_func)

if usuario:
    # Ativa a câmera do celular/PC
    foto = st.camera_input("Tire uma foto para confirmar")

    if foto:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 ENTRADA", use_container_width=True):
                registrar_com_foto(usuario, "Entrada", foto)
        with col2:
            if st.button("🏠 SAÍDA", use_container_width=True):
                registrar_com_foto(usuario, "Saída", foto)

# Painel do Gerente para ver as fotos
with st.sidebar:
    st.header("Área do Gerente")
    if st.text_input("Senha", type="password") == "1234":
        if st.button("Ver Últimas Fotos"):
            conn = abrir_conexao()
            df = pd.read_sql_query("SELECT funcionario, tipo, data_hora, foto FROM registros ORDER BY id DESC LIMIT 5", conn)
            for i, row in df.iterrows():
                st.write(f"{row['data_hora']} - {row['funcionario']}")
                st.image(row['foto'], width=150)
            conn.close()
