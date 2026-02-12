import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pytz
import io
import requests
from geopy.distance import geodesic
from streamlit_js_eval import streamlit_js_eval
from fpdf import FPDF  # Agora é fpdf2

# ===================== CONFIGURAÇÃO =====================
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
    
    cursor.execute("SELECT COUNT(*) FROM configuracoes")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO configuracoes VALUES (1, 'Empresa Cliente', -23.5505, -46.6333, 50.0, '0.0.0.0', 'IP')")
    
    conn.commit()
    conn.close()

def get_ip_usuario():
    try:
        return requests.get('https://api.ipify.org', timeout=5).text
    except:
        return "Indisponível"

def verificar_batida_hoje(nome, tipo):
    conn = abrir_conexao()
    hoje = datetime.now(pytz.timezone('America/Sao_Paulo')).date().isoformat()
    query = "SELECT COUNT(*) FROM registros WHERE funcionario = ? AND tipo = ? AND data_iso = ?"
    resultado = conn.execute(query, (nome, tipo, hoje)).fetchone()
    conn.close()
    return resultado[0] > 0

# ===================== INICIALIZAÇÃO =====================
inicializar_banco()

if 'conf' not in st.session_state:
    conn = abrir_conexao()
    st.session_state.conf = pd.read_sql_query("SELECT * FROM configuracoes WHERE id=1", conn).iloc[0]
    st.session_state.lista_func = pd.read_sql_query("SELECT nome FROM funcionarios ORDER BY nome", conn)['nome'].tolist()
    conn.close()

conf = st.session_state.conf
lista_func = st.session_state.lista_func

# ===================== INTERFACE FUNCIONÁRIO =====================
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
        autorizado = (ip_atual == conf['ip_loja'] or conf['ip_loja'] == '0.0.0.0')
        if not autorizado:
            st.error(f"❌ Bloqueado: Conecte-se ao Wi-Fi da loja. (Seu IP: {ip_atual})")
    elif conf['modo_trava'] == 'GPS':
        if loc:
            dist = geodesic((conf['lat'], conf['lon']), (loc['lat'], loc['lon'])).meters
            autorizado = (dist <= conf['raio_metros'])
            if not autorizado:
                st.error(f"❌ Fora do Raio! Você está a {int(dist)}m da loja.")
        else:
            st.warning("📡 Buscando GPS... Ative a localização e aguarde.")

    if autorizado:
        if 'foto_key' not in st.session_state:
            st.session_state.foto_key = 0

        foto = st.camera_input("Foto obrigatória para validar", key=f"camera_{st.session_state.foto_key}")
        if foto:
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            agora = datetime.now(pytz.timezone('America/Sao_Paulo'))
            
            def salvar(tipo_batida):
                conn = abrir_conexao()
                img_bin = foto.getvalue()
                conn.execute("INSERT INTO registros (funcionario, tipo, data_hora, data_iso, foto) VALUES (?,?,?,?,?)",
                             (usuario, tipo_batida, agora.strftime("%d/%m/%Y %H:%M:%S"), agora.date().isoformat(), img_bin))
                conn.commit()
                conn.close()
                st.success(f"✅ {tipo_batida} registrado com sucesso!")
                st.session_state.foto_key += 1

            botoes = [("🚀 Entrada", "Entrada", c1), ("☕ Saída Almoço", "Saída Almoço", c2),
                      ("🍱 Volta Almoço", "Volta Almoço", c3), ("🏠 Saída Final", "Saída Final", c4)]
            
            for label, t, col in botoes:
                if not verificar_batida_hoje(usuario, t):
                    if col.button(label, key=f"btn_{t}", use_container_width=True):
                        salvar(t)
                else:
                    col.info("✅ Batido")

# ===================== PAINEL ADMIN =====================
with st.sidebar:
    st.header("🔐 Admin OrbTech")
    if st.text_input("Senha Admin", type="password") == "1234":
        
        with st.expander("🛠️ Configurações & Trava"):
            n_emp = st.text_input("Nome da Loja", value=conf['nome_empresa'])
            modo = st.radio("Modo Segurança", ["GPS", "IP"], index=0 if conf['modo_trava'] == 'GPS' else 1)
            n_lat = st.number_input("Lat", value=conf['lat'], format="%.6f")
            n_lon = st.number_input("Lon", value=conf['lon'], format="%.6f")
            n_raio = st.number_input("Raio (m)", value=float(conf['raio_metros']))
            n_ip = conf['ip_loja']
            if st.button("Definir meu IP como o da Loja"):
                n_ip = ip_atual
            
            if st.button("Salvar Mudanças"):
                conn = abrir_conexao()
                conn.execute("UPDATE configuracoes SET nome_empresa=?, lat=?, lon=?, raio_metros=?, ip_loja=?, modo_trava=? WHERE id=1",
                             (n_emp, n_lat, n_lon, n_raio, n_ip, modo))
                conn.commit()
                conn.close()
                st.session_state.conf = pd.Series({'nome_empresa': n_emp, 'lat': n_lat, 'lon': n_lon,
                                                   'raio_metros': n_raio, 'ip_loja': n_ip, 'modo_trava': modo})
                st.success("Configurações salvas com sucesso!")

        with st.expander("👤 Gerenciar Equipe"):
            n_f = st.text_input("Novo Nome")
            if st.button("Adicionar"):
                try:
                    conn = abrir_conexao()
                    conn.execute("INSERT INTO funcionarios (nome) VALUES (?)", (n_f,))
                    conn.commit()
                    conn.close()
                    st.session_state.lista_func.append(n_f)
                    st.session_state.lista_func.sort()
                    st.success("Funcionário adicionado!")
                except sqlite3.IntegrityError:
                    st.error("Nome já existe!")

        with st.expander("📊 Relatórios"):
            filtro = st.selectbox("Filtrar Funcionário", ["Todos"] + lista_func)
            data_inicio = st.date_input("Data Início", value=datetime.now(pytz.timezone('America/Sao_Paulo')) - pd.Timedelta(days=30))
            data_fim = st.date_input("Data Fim", value=datetime.now(pytz.timezone('America/Sao_Paulo')))
            
            conn = abrir_conexao()
            q = "SELECT funcionario, tipo, data_iso, data_hora FROM registros WHERE data_iso BETWEEN ? AND ?"
            params = (data_inicio.isoformat(), data_fim.isoformat())
            if filtro != "Todos":
                q += " AND funcionario = ?"
                params += (filtro,)
            df = pd.read_sql_query(q, conn, params=params)
            conn.close()

            if not df.empty:
                df['data_hora'] = pd.to_datetime(df['data_hora'], format='%d/%m/%Y %H:%M:%S')
                esp = df.pivot_table(index=['funcionario', 'data_iso'], columns='tipo', values='data_hora', aggfunc='first').reset_index()
                
                for c in ['Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída Final']:
                    if c not in esp.columns:
                        esp[c] = pd.NaT

                def calc_horas(row):
                    try:
                        manha = row['Saída Almoço'] - row['Entrada']
                        tarde = row['Saída Final'] - row['Volta Almoço']
                        total = (manha + tarde).total_seconds() / 3600
                        h = int(total)
                        m = int((total % 1) * 60)
                        return f"{h:02d}h {m:02d}min"
                    except:
                        return "Incompleto"

                esp['Total Dia'] = esp.apply(calc_horas, axis=1)

                st.dataframe(esp if filtro == "Todos" else esp[['data_iso', 'Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída Final', 'Total Dia']], hide_index=True)

                # ===================== PDF ESPELHO =====================
                def gerar_espelho_pdf(esp, nome_empresa, funcionario, data_inicio, data_fim):
                    pdf = FPDF(orientation='L', unit='mm', format='A4')
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)

                    pdf.cell(0, 10, f"Espelho de Ponto - {nome_empresa}", ln=1, align='C')
                    pdf.cell(0, 10, f"Funcionário: {funcionario}", ln=1, align='C')
                    pdf.cell(0, 10, f"Período: {data_inicio} a {data_fim}", ln=1, align='C')
                    pdf.ln(10)

                    col_widths = [30, 40, 40, 40, 40, 40]
                    headers = ["Data", "Entrada", "Saída Almoço", "Volta Almoço", "Saída Final", "Total Horas"]
                    for i, header in enumerate(headers):
                        pdf.cell(col_widths[i], 10, header, 1, 0, 'C')
                    pdf.ln()

                    for _, row in esp.iterrows():
                        pdf.cell(col_widths[0], 10, str(row['data_iso']), 1, 0, 'C')
                        pdf.cell(col_widths[1], 10, row['Entrada'].strftime('%H:%M') if pd.notna(row['Entrada']) else '-', 1, 0, 'C')
                        pdf.cell(col_widths[2], 10, row['Saída Almoço'].strftime('%H:%M') if pd.notna(row['Saída Almoço']) else '-', 1, 0, 'C')
                        pdf.cell(col_widths[3], 10, row['Volta Almoço'].strftime('%H:%M') if pd.notna(row['Volta Almoço']) else '-', 1, 0, 'C')
                        pdf.cell(col_widths[4], 10, row['Saída Final'].strftime('%H:%M') if pd.notna(row['Saída Final']) else '-', 1, 0, 'C')
                        pdf.cell(col_widths[5], 10, row['Total Dia'], 1, 0, 'C')
                        pdf.ln()

                    # Total geral
                    total_horas = esp['Total Dia'].apply(lambda x: 0 if x == "Incompleto" else int(x.split('h')[0]) + int(x.split('min')[0])/60).sum()
                    h_total = int(total_horas)
                    m_total = int((total_horas - h_total) * 60)
                    pdf.ln(10)
                    pdf.cell(0, 10, f"Total de Horas no Período: {h_total:02d}h {m_total:02d}min", ln=1, align='C')

                    # Assinatura
                    pdf.ln(20)
                    pdf.cell(0, 10, "___________________________________________          ________________", ln=1, align='C')
                    pdf.cell(0, 10, "Assinatura do Funcionário                                   Data", ln=1, align='C')

                    return bytes(pdf.output())   # ← Correção principal com fpdf2

                if filtro != "Todos":
                    pdf_data = gerar_espelho_pdf(
                        esp[['data_iso', 'Entrada', 'Saída Almoço', 'Volta Almoço', 'Saída Final', 'Total Dia']],
                        conf['nome_empresa'], filtro, data_inicio, data_fim
                    )
                    st.download_button(
                        "⬇️ Baixar Espelho de Ponto PDF",
                        pdf_data,
                        f"espelho_ponto_{filtro.replace(' ', '_')}.pdf",
                        "application/pdf"
                    )

        with st.expander("📸 Últimas 10 Fotos"):
            conn = abrir_conexao()
            fotos = pd.read_sql_query("SELECT funcionario, tipo, data_hora, foto FROM registros ORDER BY id DESC LIMIT 10", conn)
            conn.close()
            for _, r in fotos.iterrows():
                col_a, col_b = st.columns([1, 2])
                if r['foto']:
                    col_a.image(io.BytesIO(r['foto']), width=120)
                col_b.write(f"**{r['funcionario']}** - {r['tipo']}")
                col_b.caption(r['data_hora'])
                st.divider()