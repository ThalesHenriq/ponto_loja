import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pytz
from PIL import Image
import io
import requests
from geopy.distance import geodesic
from streamlit_js_eval import streamlit_js_eval

# 1. CONFIGURAÇÃO ORBTECH
st.set_page_config(page_title="OrbTech Ponto Pro", page_icon="🛡️", layout="wide")

def abrir_conexao():
    return sqlite3.connect('ponto_loja.db', check_same_thread=False)

def inicializar_banco():
    conn = abrir_conexao()
    cursor = conn.cursor()
    # Criar tabelas
    cursor.execute('''CREATE TABLE IF NOT EXISTS configuracoes 
                      (id INTEGER PRIMARY KEY, nome_empresa TEXT, lat REAL, lon REAL, 
                       raio_metros REAL, ip_loja TEXT, modo_trava TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, 
                       data_hora TEXT, data_iso TEXT, foto BLOB)''')
    
    # Garantir que existe a linha de configuração ID=1
    cursor.execute("SELECT COUNT(*) FROM configuracoes WHERE id=1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""INSERT INTO configuracoes (id, nome_empresa, lat, lon, raio_metros, ip_loja, modo_trava) 
                          VALUES (1, 'OrbTech Cliente', -23.5505, -46.6333, 50.0, '0.0.0.0', 'IP')""")
    
    conn.commit()
    conn.close()

def get_ip_usuario():
    try: return requests.get('https://api.ipify.org', timeout=5).text
    except: return "Indisponível"

def verificar_batida_hoje(nome, tipo):
    conn = abrir_conexao()
    hoje = datetime.now(pytz.timezone('America/Sao_Paulo')).date().isoformat()
    query = "SELECT COUNT(*) FROM registros WHERE funcionario = ? AND tipo = ? AND data_iso = ?"
    resultado = conn.execute(query, (nome, tipo, hoje)).fetchone()
    conn.close()
    return resultado[0] > 0

# --- INICIALIZAÇÃO CRÍTICA ---
inicializar_banco()
conn = abrir_conexao()

# Leitura segura das configurações
df_conf = pd.read_sql_query("SELECT * FROM configuracoes WHERE id=1", conn)
conf = df_conf.iloc[0] # Agora garantido que existe

# Leitura de funcionários
df_func = pd.read_sql_query("SELECT nome FROM funcionarios ORDER BY nome", conn)
lista_func = df_func['nome'].tolist()
conn.close()

# --- INTERFACE DO FUNCIONÁRIO ---
st.title(f"🏢 {conf['nome_empresa']}")
st.write(f"🔒 Segurança OrbTech: *Modo {conf['modo_trava']} Ativo*")

ip_atual = get_ip_usuario()
loc = None
if conf['modo_trava'] == 'GPS':
    loc = streamlit_js_eval(js_expressions="new Promise((resolve, reject) => { navigator.geolocation.getCurrentPosition(pos => resolve({lat: pos.coords.latitude, lon: pos.coords.longitude}), err => reject(err), {enableHighAccuracy: true, timeout: 10000}) })", key="get_location")

usuario = st.selectbox("Selecione seu nome:", [""] + lista_func)

if usuario:
    autorizado = False
    if conf['modo_trava'] == 'IP':
        autorizado = (ip_atual == conf['ip_lo_ja'] or conf['ip_loja'] == '0.0.0.0')
    elif conf['modo_trava'] == 'GPS' and loc:
        dist = geodesic((conf['lat'], conf['lon']), (loc['lat'], loc['lon'])).meters
        autorizado = (dist <= conf['raio_metros'])
    
    if autorizado:
        foto = st.camera_input("Foto de Verificação")
        if foto:
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            agora = datetime.now(pytz.timezone('America/Sao_Paulo'))
            
            def salvar_ponto(tipo_b):
                conn = abrir_conexao()
                img_bin = io.BytesIO(foto.getvalue()).getvalue()
                conn.execute("INSERT INTO registros (funcionario, tipo, data_hora, data_iso, foto) VALUES (?,?,?,?,?)",
                             (usuario, tipo_b, agora.strftime("%d/%m/%Y %H:%M:%S"), agora.date().isoformat(), img_bin))
                conn.commit()
                conn.close()
                st.success(f"{tipo_b} registrado!")
                st.rerun()

            botoes = [("🚀 Entrada", "Entrada", c1), ("☕ Almoço (Saída)", "Saída Almoço", c2), 
                      ("🍱 Almoço (Volta)", "Volta Almoço", c3), ("🏠 Saída Final", "Saída Final", c4)]
            
            for label, t, col in botoes:
                if not verificar_batida_hoje(usuario, t):
                    col.button(label, on_click=salvar_ponto, args=(t,), use_container_width=True)
                else: col.info(f"Registrado")
    else:
        st.error("❌ Acesso bloqueado. Verifique sua rede ou localização.")

# --- PAINEL DO GERENTE ---
with st.sidebar:
    st.header("🔐 Gerência OrbTech")
    senha_admin = st.text_input("Senha", type="password")
    
    if senha_admin == "1234":
        # Aba de Configurações
        with st.expander("🛠️ Configurações & Trava"):
            n_emp = st.text_input("Nome da Loja", value=conf['nome_empresa'])
            m_trava = st.radio("Modo Segurança", ["GPS", "IP"], index=0 if conf['modo_trava'] == 'GPS' else 1)
            n_lat = st.number_input("Lat", value=conf['lat'], format="%.6f")
            n_lon = st.number_input("Lon", value=conf['lon'], format="%.6f")
            n_raio = st.number_input("Raio (m)", value=float(conf['raio_metros']))
            if st.button("Definir meu IP atual como da Loja"):
                n_ip = ip_atual
            else: n_ip = conf['ip_loja']
            
            if st.button("Salvar Tudo"):
                conn = abrir_conexao()
                conn.execute("UPDATE configuracoes SET nome_empresa=?, lat=?, lon=?, raio_metros=?, ip_loja=?, modo_trava=? WHERE id=1",
                             (n_emp, n_lat, n_lon, n_raio, n_ip, m_trava))
                conn.commit(); conn.close(); st.rerun()

        # Aba de Funcionários
        with st.expander("👤 Gerenciar Equipe"):
            n_f = st.text_input("Novo Nome")
            if st.button("Cadastrar"):
                conn = abrir_conexao()
                conn.execute("INSERT INTO funcionarios (nome) VALUES (?)", (n_f,))
                conn.commit(); conn.close(); st.rerun()
            
            st.write("Lista atual:")
            st.write(lista_func)

        # Relatórios
        with st.expander("📊 Relatórios"):
            if st.button("Gerar Planilha"):
                conn = abrir_conexao()
                df_rel = pd.read_sql_query("SELECT funcionario, tipo, data_iso, data_hora FROM registros", conn)
                conn.close()
                if not df_rel.empty:
                    st.dataframe(df_rel)
                    output = io.BytesIO()
                    df_rel.to_excel(output, index=False)
                    st.download_button("Download Excel", output.getvalue(), "relatorio.xlsx")

        # Fotos
        with st.expander("📸 Últimas Fotos"):
            conn = abrir_conexao()
            fotos_df = pd.read_sql_query("SELECT funcionario, tipo, data_hora, foto FROM registros ORDER BY id DESC LIMIT 10", conn)
            conn.close()
            for _, r in fotos_df.iterrows():
                st.write(f"*{r['funcionario']}* - {r['tipo']}")
                if r['foto']: st.image(r['foto'], width=150)
                st.divider()
