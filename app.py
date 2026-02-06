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

# 1. CONFIGURAÇÃO DA MARCA ORBTECH
st.set_page_config(page_title="OrbTech Ponto Pro", page_icon="🛡️", layout="wide")

def abrir_conexao():
    return sqlite3.connect('ponto_loja.db', check_same_thread=False)

def inicializar_banco():
    conn = abrir_conexao()
    cursor = conn.cursor()
    # Tabelas essenciais
    cursor.execute('''CREATE TABLE IF NOT EXISTS configuracoes 
                      (id INTEGER PRIMARY KEY, nome_empresa TEXT, lat REAL, lon REAL, 
                       raio_metros REAL, ip_loja TEXT, modo_trava TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, 
                       data_hora TEXT, data_iso TEXT, foto BLOB)''')
    
    # Configuração inicial caso o banco seja novo
    cursor.execute("SELECT COUNT(*) FROM configuracoes")
    if cursor.fetchone() == 0:
        cursor.execute("INSERT INTO configuracoes VALUES (1, 'Empresa Cliente', -23.5505, -46.6333, 50.0, '0.0.0.0', 'IP')")
    
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
    return resultado > 0

# --- INICIALIZAÇÃO ---
inicializar_banco()
conn = abrir_conexao()
conf = pd.read_sql_query("SELECT * FROM configuracoes WHERE id=1", conn).iloc[0]
lista_func = pd.read_sql_query("SELECT nome FROM funcionarios ORDER BY nome", conn)['nome'].tolist()
conn.close()

# --- INTERFACE DO FUNCIONÁRIO ---
st.title(f"🏢 {conf['nome_empresa']}")
st.write(f"🔒 Segurança Ativa: *Modo {conf['modo_trava']}*")

ip_atual = get_ip_usuario()
loc = None
if conf['modo_trava'] == 'GPS':
    loc = streamlit_js_eval(js_expressions="new Promise((resolve, reject) => { navigator.geolocation.getCurrentPosition(pos => resolve({lat: pos.coords.latitude, lon: pos.coords.longitude}), err => reject(err), {enableHighAccuracy: true, timeout: 10000}) })", key="get_location")

usuario = st.selectbox("Selecione seu nome:", [""] + lista_func)

if usuario:
    autorizado = False
    # Validação de Segurança
    if conf['modo_trava'] == 'IP':
        autorizado = (ip_atual == conf['ip_loja'] or conf['ip_loja'] == '0.0.0.0')
        if not autorizado: st.error(f"❌ Bloqueado: Conecte-se ao Wi-Fi da loja. (Seu IP: {ip_atual})")
    elif conf['modo_trava'] == 'GPS':
        if loc:
            dist = geodesic((conf['lat'], conf['lon']), (loc['lat'], loc['lon'])).meters
            autorizado = (dist <= conf['raio_metros'])
            if not autorizado: st.error(f"❌ Fora do Raio! Você está a {int(dist)}m da loja.")
        else: st.warning("📡 Buscando GPS... Ative a localização e aguarde.")

    if autorizado:
        foto = st.camera_input("Foto obrigatória para validar")
        if foto:
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            fuso = pytz.timezone('America/Sao_Paulo')
            agora = datetime.now(fuso)
            
            def salvar(tipo_batida):
                conn = abrir_conexao()
                img_bin = io.BytesIO(foto.getvalue()).getvalue()
                conn.execute("INSERT INTO registros (funcionario, tipo, data_hora, data_iso, foto) VALUES (?,?,?,?,?)",
                             (usuario, tipo_batida, agora.strftime("%d/%m/%Y %H:%M:%S"), agora.date().isoformat(), img_bin))
                conn.commit()
                conn.close()
                st.success(f"{tipo_batida} OK!")
                st.rerun()

            botoes = [("🚀 Entrada", "Entrada", c1), ("☕ Saída Almoço", "Saída Almoço", c2), 
                      ("🍱 Volta Almoço", "Volta Almoço", c3), ("🏠 Saída Final", "Saída Final", c4)]
            
            for label, t, col in botoes:
                if not verificar_batida_hoje(usuario, t):
                    col.button(label, on_click=salvar, args=(t,), use_container_width=True)
                else: col.info(f"Batido")

# --- PAINEL DO GERENTE (SIDEBAR) ---
with st.sidebar:
    st.header("🔐 Admin OrbTech")
    if st.text_input("Senha Admin", type="password") == "1234":
        
        # 1. CONFIGURAÇÕES DE TRAVA
        with st.expander("🛠️ Configurações & Trava"):
            n_emp = st.text_input("Nome da Loja", value=conf['nome_empresa'])
            modo = st.radio("Modo Segurança", ["GPS", "IP"], index=0 if conf['modo_trava'] == 'GPS' else 1)
            n_lat = st.number_input("Lat", value=conf['lat'], format="%.6f")
            n_lon = st.number_input("Lon", value=conf['lon'], format="%.6f")
            n_raio = st.number_input("Raio (m)", value=float(conf['raio_metros']))
            if st.button("Definir meu IP como o da Loja"): n_ip = ip_atual
            else: n_ip = conf['ip_loja']
            
            if st.button("Salvar Mudanças"):
                conn = abrir_conexao()
                conn.execute("UPDATE configuracoes SET nome_empresa=?, lat=?, lon=?, raio_metros=?, ip_loja=?, modo_trava=? WHERE id=1",
                             (n_emp, n_lat, n_lon, n_raio, n_ip, modo))
                conn.commit(); conn.close(); st.rerun()

        # 2. GESTÃO DE EQUIPE
        with st.expander("👤 Gerenciar Equipe"):
            n_f = st.text_input("Novo Nome")
            if st.button("Adicionar"):
                conn = abrir_conexao(); conn.execute("INSERT INTO funcionarios (nome) VALUES (?)", (n_f,))
                conn.commit(); conn.close(); st.rerun()

        # 3. RELATÓRIOS E CÁLCULOS
        with st.expander("📊 Relatórios"):
            filtro = st.selectbox("Filtrar Funcionário", ["Todos"] + lista_func)
            conn = abrir_conexao()
            q = "SELECT funcionario, tipo, data_iso, data_hora FROM registros"
            if filtro != "Todos": q += f" WHERE funcionario = '{filtro}'"
            df = pd.read_sql_query(q, conn)
            conn.close()

            if not df.empty:
                df['data_hora'] = pd.to_datetime(df['data_hora'], format='%d/%m/%Y %H:%M:%S')
                esp = df.pivot_table(index=['funcionario', 'data_iso'], columns='tipo', values='data_hora', aggfunc='first').reset_index()
                
                for c in ['Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída Final']:
                    if c not in esp: esp[c] = pd.NaT

                def calc_horas(row):
                    try:
                        total = (row['Saída Almoço'] - row['Entrada']) + (row['Saída Final'] - row['Volta Almoço'])
                        h = total.total_seconds() / 3600
                        return f"{int(h):02d}h {int((h%1)*60):02d}min"
                    except: return "Incompleto"

                esp['Total Dia'] = esp.apply(calc_horas, axis=1)
                st.dataframe(esp[['funcionario', 'data_iso', 'Total Dia']], hide_index=True)
                
                output = io.BytesIO()
                esp.to_excel(output, index=False)
                st.download_button("⬇️ Baixar Excel", output.getvalue(), "relatorio_orbtech.xlsx")

        # 4. AUDITORIA DE FOTOS
        with st.expander("📸 Últimas 10 Fotos"):
            conn = abrir_conexao()
            fotos = pd.read_sql_query("SELECT funcionario, tipo, data_hora, foto FROM registros ORDER BY id DESC LIMIT 10", conn)
            conn.close()
            for _, r in fotos.iterrows():
                col_a, col_b = st.columns([1, 2])
                if r['foto']: col_a.image(r['foto'], width=100)
                col_b.write(f"*{r['funcionario']}* - {r['tipo']}")
                col_b.caption(r['data_hora'])
                st.divider()
