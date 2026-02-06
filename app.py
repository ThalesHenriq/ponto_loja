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
    cursor.execute('''CREATE TABLE IF NOT EXISTS configuracoes 
                      (id INTEGER PRIMARY KEY, nome_empresa TEXT, lat REAL, lon REAL, 
                       raio_metros REAL, ip_loja TEXT, modo_trava TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS funcionarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS registros 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, funcionario TEXT, tipo TEXT, 
                       data_hora TEXT, data_iso TEXT, foto BLOB)''')
    if cursor.execute("SELECT COUNT(*) FROM configuracoes").fetchone() == 0:
        cursor.execute("INSERT INTO configuracoes VALUES (1, 'OrbTech Cliente', -23.5505, -46.6333, 50.0, '0.0.0.0', 'IP')")
    conn.commit()
    conn.close()

def get_ip_usuario():
    try: return requests.get('https://api.ipify.org', timeout=5).text
    except: return "Indisponível"

def verificar_batida_hoje(nome, tipo):
    conn = abrir_conexao()
    hoje = datetime.now(pytz.timezone('America/Sao_Paulo')).date().isoformat()
    res = conn.execute("SELECT COUNT(*) FROM registros WHERE funcionario=? AND tipo=? AND data_iso=?", (nome, tipo, hoje)).fetchone()
    conn.close()
    return res[0] > 0

# --- INICIALIZAÇÃO ---
inicializar_banco()
conn = abrir_conexao()
conf = pd.read_sql_query("SELECT * FROM configuracoes WHERE id=1", conn).iloc[0]
lista_func = pd.read_sql_query("SELECT nome FROM funcionarios ORDER BY nome", conn)['nome'].tolist()
conn.close()

st.title(f"🏢 {conf['nome_empresa']}")
st.write(f"🔒 Segurança Ativa: **Modo {conf['modo_trava']}**")

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
            st.write("---")
            c1, c2, c3, c4 = st.columns(4)
            agora = datetime.now(pytz.timezone('America/Sao_Paulo'))
            
            def salvar(tipo):
                conn = abrir_conexao()
                img_bin = io.BytesIO(foto.getvalue()).getvalue()
                conn.execute("INSERT INTO registros (funcionario, tipo, data_hora, data_iso, foto) VALUES (?,?,?,?,?)",
                             (usuario, tipo, agora.strftime("%d/%m/%Y %H:%M:%S"), agora.date().isoformat(), img_bin))
                conn.commit(); conn.close()
                st.success(f"{tipo} OK!"); st.rerun()

            btn_map = [("🚀 Entrada", "Entrada", c1), ("☕ Saída Almoço", "Saída Almoço", c2), 
                       ("🍱 Volta Almoço", "Volta Almoço", c3), ("🏠 Saída Final", "Saída Final", c4)]
            
            for label, t, col in btn_map:
                if not verificar_batida_hoje(usuario, t):
                    col.button(label, on_click=salvar, args=(t,), use_container_width=True)
                else: col.info(f"Registrado")
    else: st.error("❌ Acesso bloqueado. Saia da rede privada ou aproxime-se da loja.")

# --- PAINEL DO GERENTE (SIDEBAR) ---
with st.sidebar:
    st.header("🔐 Admin OrbTech")
    if st.text_input("Senha", type="password") == "1234":
        
        # ABA: CONFIGURAÇÕES DE TRAVA
        with st.expander("🛠️ Modo de Segurança"):
            modo = st.radio("Método:", ["GPS", "IP"], index=0 if conf['modo_trava'] == 'GPS' else 1)
            n_ip = st.text_input("IP Loja", value=conf['ip_loja'])
            if st.button("Definir meu IP atual"): n_ip = ip_atual
            n_lat = st.number_input("Lat", value=conf['lat'], format="%.6f")
            n_lon = st.number_input("Lon", value=conf['lon'], format="%.6f")
            n_raio = st.number_input("Raio (m)", value=float(conf['raio_metros']))
            if st.button("Salvar Configurações"):
                c = abrir_conexao(); c.execute("UPDATE configuracoes SET lat=?, lon=?, raio_metros=?, ip_loja=?, modo_trava=? WHERE id=1", (n_lat, n_lon, n_raio, n_ip, modo)); c.commit(); c.close(); st.rerun()

        # ABA: FOTOS (10 PRINCIPAIS)
        with st.expander("📸 Auditoria: Últimas 10 Fotos"):
            c = abrir_conexao()
            f_df = pd.read_sql_query("SELECT funcionario, tipo, data_hora, foto FROM registros ORDER BY id DESC LIMIT 10", c)
            c.close()
            for _, r in f_df.iterrows():
                ca, cb = st.columns([1, 2])
                if r['foto']: ca.image(r['foto'], width=80)
                cb.write(f"**{r['funcionario']}**"); cb.caption(f"{r['tipo']} | {r['data_hora']}")
                st.divider()

        # ABA: RELATÓRIO INDIVIDUAL E CÁLCULO
        with st.expander("📊 Relatório e Horas"):
            filtro = st.selectbox("Funcionário:", ["Todos"] + lista_func)
            c = abrir_conexao(); query = "SELECT funcionario, tipo, data_iso, data_hora FROM registros"
            if filtro != "Todos": query += f" WHERE funcionario = '{filtro}'"
            df = pd.read_sql_query(query, c); c.close()

            if not df.empty:
                df['data_hora'] = pd.to_datetime(df['data_hora'], format='%d/%m/%Y %H:%M:%S')
                esp = df.pivot_table(index=['funcionario', 'data_iso'], columns='tipo', values='data_hora', aggfunc='first').reset_index()
                for col in ['Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída Final']:
                    if col not in esp: esp[col] = pd.NaT

                def calc_h(row):
                    try:
                        t = (row['Saída Almoço'] - row['Entrada']) + (row['Saída Final'] - row['Volta Almoço'])
                        h = t.total_seconds() / 3600
                        return f"{int(h)}h {int((h%1)*60)}m"
                    except: return "Incompleto"

                esp['Carga Total'] = esp.apply(calc_h, axis=1)
                st.dataframe(esp[['funcionario', 'data_iso', 'Carga Total']], hide_index=True)
                
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='openpyxl') as wr:
                    esp.to_excel(wr, index=False, sheet_name='Ponto', startrow=2)
                    ws = wr.sheets['Ponto']; ws['A1'] = f"RELATÓRIO: {conf['nome_empresa'].upper()}"
                st.download_button("⬇️ Baixar Excel", out.getvalue(), f"ponto_{filtro}.xlsx")
        
        # ABA: GESTÃO DE EQUIPE
        with st.expander("👤 Equipe"):
            nf = st.text_input("Novo nome")
            if st.button("Cadastrar"):
                c = abrir_conexao(); c.execute("INSERT INTO funcionarios (nome) VALUES (?)", (nf,)); c.commit(); c.close(); st.rerun()
