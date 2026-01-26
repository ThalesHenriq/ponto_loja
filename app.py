import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pytz
from PIL import Image
import io

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Ponto Pro 2026", page_icon="📸", layout="centered")

# 2. FUNÇÕES DE BANCO DE DADOS E LÓGICA
def abrir_conexao():
    return sqlite3.connect('ponto_loja.db', check_same_thread=False)

def inicializar_banco():
    conn = abrir_conexao()
    cursor = conn.cursor()
    
    # 1. Cria as tabelas básicas se não existirem
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, data_hora TEXT)''')
    
    # 2. MIGRAR COLUNAS FALTANTES (Evita erros de "no column named")
    colunas_necessarias = [
        ("data_iso", "TEXT"),
        ("foto", "BLOB")
    ]
    
    for nome_col, tipo_col in colunas_necessarias:
        try:
            cursor.execute(f"ALTER TABLE registros ADD COLUMN {nome_col} {tipo_col}")
        except sqlite3.OperationalError:
            # Se a coluna já existir, o SQLite lançará um erro e nós apenas ignoramos
            pass
        
    conn.commit()
    conn.close()

def registrar_ponto(nome, tipo, foto_capturada):
    if not foto_capturada:
        st.error("❌ Foto obrigatória para registrar o ponto!")
        return

    try:
        conn = abrir_conexao()
        cursor = conn.cursor()
        
        # Horário oficial de Brasília
        fuso_br = pytz.timezone('America/Sao_Paulo')
        agora_br = datetime.now(fuso_br)
        data_hora_txt = agora_br.strftime("%d/%m/%Y %H:%M:%S")
        data_iso = agora_br.date().isoformat()
        
        # Processar Foto
        img = Image.open(foto_capturada)
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        foto_binaria = buf.getvalue()

        cursor.execute("""INSERT INTO registros (funcionario, tipo, data_hora, data_iso, foto) 
                          VALUES (?, ?, ?, ?, ?)""", 
                       (nome, tipo, data_hora_txt, data_iso, foto_binaria))
        conn.commit()
        conn.close()
        st.success(f"✅ {tipo} registrado: {data_hora_txt}")
        st.balloons()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# 3. INTERFACE DO FUNCIONÁRIO
inicializar_banco()
st.title("⏰ Sistema de Ponto 2026")
st.write("Registre sua jornada com validação por foto.")

conn = abrir_conexao()
lista_func = pd.read_sql_query("SELECT nome FROM funcionarios ORDER BY nome", conn)['nome'].tolist()
conn.close()

usuario = st.selectbox("Selecione seu nome:", [""] + lista_func)

if usuario:
    foto = st.camera_input("Posicione seu rosto para a foto")
    
    if foto:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 ENTRADA", use_container_width=True):
                registrar_ponto(usuario, "Entrada", foto)
            if st.button("☕ SAÍDA ALMOÇO", use_container_width=True):
                registrar_ponto(usuario, "Saída Almoço", foto)
        with col2:
            if st.button("🍱 VOLTA ALMOÇO", use_container_width=True):
                registrar_ponto(usuario, "Volta Almoço", foto)
            if st.button("🏠 SAÍDA FINAL", use_container_width=True):
                registrar_ponto(usuario, "Saída Final", foto)

# 4. PAINEL DO GERENTE (SIDEBAR)
with st.sidebar:
    st.header("🔐 Painel Administrativo")
    st.write("Acesso restrito ao gerente")
    
    senha = st.text_input("Digite a Senha", type="password")
    
    if senha == "1234":  # Altere sua senha aqui
        st.success("Acesso Liberado")
        
        # --- ABA 1: CADASTRO ---
        st.divider()
        st.subheader("👤 Gestão de Equipe")
        novo_nome = st.text_input("Nome do Novo Funcionário")
        if st.button("Cadastrar Colaborador", use_container_width=True):
            if novo_nome:
                try:
                    conn = abrir_conexao()
                    conn.execute("INSERT INTO funcionarios (nome) VALUES (?)", (novo_nome,))
                    conn.commit()
                    conn.close()
                    st.success(f"{novo_nome} cadastrado!")
                    st.rerun()
                except:
                    st.error("Erro: Nome já existe ou banco travado.")
            else:
                st.warning("Insira um nome válido.")

        # --- ABA 2: RELATÓRIOS ---
        st.divider()
        st.subheader("📊 Relatórios e Horas")
        if st.button("Gerar Espelho de Ponto (Excel)", use_container_width=True):
            conn = abrir_conexao()
            df = pd.read_sql_query("SELECT funcionario, tipo, data_iso, data_hora FROM registros", conn)
            conn.close()

            if not df.empty:
                # Processamento de Horas
                df['data_hora'] = pd.to_datetime(df['data_hora'], format='%d/%m/%Y %H:%M:%S')
                espelho = df.pivot_table(index=['funcionario', 'data_iso'], 
                                         columns='tipo', 
                                         values='data_hora', 
                                         aggfunc='first').reset_index()
                
                # Criar colunas faltantes para evitar erro no cálculo
                for col in ['Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída Final']:
                    if col not in espelho: espelho[col] = pd.NaT

                def calcular_jornada(row):
                    try:
                        # Cálculo: (Almoço - Entrada) + (Saída Final - Volta)
                        manha = (row['Saída Almoço'] - row['Entrada']).total_seconds() / 3600
                        tarde = (row['Saída Final'] - row['Volta Almoço']).total_seconds() / 3600
                        total = manha + tarde
                        extra = max(0, total - 8.0) # Base de 8h diárias
                        return pd.Series([round(total, 2), round(extra, 2)])
                    except:
                        return pd.Series([0.0, 0.0])

                espelho[['Total Horas', 'Horas Extras']] = espelho.apply(calcular_jornada, axis=1)
                
                # Criar arquivo Excel em memória
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    espelho.to_excel(writer, index=False, sheet_name='Relatorio')
                
                st.download_button(
                    label="⬇️ Baixar Planilha 2026",
                    data=output.getvalue(),
                    file_name=f"ponto_geral_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("Nenhum dado para exportar.")

        # --- ABA 3: AUDITORIA VISUAL ---
        st.divider()
        st.subheader("📸 Auditoria por Foto")
        if st.button("Verificar Últimas Batidas", use_container_width=True):
            conn = abrir_conexao()
            # Busca os últimos 5 registros com foto
            registros_fotos = pd.read_sql_query(
                "SELECT funcionario, tipo, data_hora, foto FROM registros ORDER BY id DESC LIMIT 5", conn
            )
            conn.close()

            if not registros_fotos.empty:
                for _, row in registros_fotos.iterrows():
                    st.write(f"*{row['funcionario']}* ({row['tipo']})")
                    st.caption(f"🕒 {row['data_hora']}")
                    if row['foto']:
                        st.image(row['foto'], width=180)
                    st.divider()
            else:
                st.info("Nenhuma foto registrada.")

    elif senha != "":
        st.error("Senha Incorreta")
