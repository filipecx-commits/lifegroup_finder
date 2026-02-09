import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import re
import requests # Nova biblioteca para falar com o n8n
import json
from datetime import datetime

# --- CONFIGURAÇÃO ---
URL_CSV = "Cadastro dos Lifegroups.csv"

# ⚠️ IMPORTANTE: Você vai colar aqui o link de TESTE do seu n8n (Webhook)
# Enquanto não tiver o link, o botão vai dar um aviso.
WEBHOOK_URL = "" 

# Configuração da Página
st.set_page_config(page_title="LifeGroups | Paz São Paulo", page_icon="💙", layout="centered")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    div.stButton > button:first-child {
        width: 100%;
        background-color: #1C355E;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    .filter-label { font-weight: 600; color: #1C355E; }
    h1 { color: #1C355E; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; color: #1C355E; font-weight: bold; }
    .stTabs [aria-selected="true"] { background-color: #1C355E; color: white; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES ---
def extrair_zap(texto):
    if pd.isna(texto): return None
    limpo = str(texto).replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    encontrado = re.search(r'\d{10,13}', limpo)
    if encontrado:
        num = encontrado.group()
        return '55' + num if not num.startswith('55') else num
    return None

def limpar_endereco_visual(location):
    try:
        end = location.raw.get('address', {})
        rua = end.get('road', '')
        numero = end.get('house_number', '')
        bairro = end.get('suburb', end.get('neighbourhood', ''))
        cidade = end.get('city', end.get('town', end.get('municipality', '')))
        
        partes = []
        if rua: partes.append(rua)
        if numero: partes.append(numero)
        if bairro: partes.append(bairro)
        
        texto_final = ", ".join(partes)
        if cidade: texto_final += f" - {cidade}"
        if len(texto_final) < 5: return location.address.split(',')[0]
        return texto_final
    except:
        return location.address.split(',')[0]

def enviar_para_n8n(dados):
    """Envia os dados para o Webhook do n8n"""
    if not WEBHOOK_URL:
        return False, "Link do n8n não configurado no código."
    
    try:
        headers = {"Content-Type": "application/json"}
        response = requests.post(WEBHOOK_URL, data=json.dumps(dados), headers=headers)
        
        if response.status_code == 200:
            return True, "Sucesso"
        else:
            return False, f"Erro {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

@st.cache_data(ttl=600)
def carregar_dados():
    try:
        df = pd.read_csv(URL_CSV)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['Nome do Life'])
        
        geolocator = Nominatim(user_agent="app_paz_v2_auto")
        latitudes = []
        longitudes = []
        
        for endereco in df['Endereço']:
            if not isinstance(endereco, str) or endereco.strip() == "":
                latitudes.append(None); longitudes.append(None)
                continue
            try:
                # Otimização: Cache simples manual se o endereço repetir
                query = f"{endereco}, Brasil"
                loc = geolocator.geocode(query, timeout=10)
                if loc:
                    latitudes.append(loc.latitude); longitudes.append(loc.longitude)
                else:
                    latitudes.append(None); longitudes.append(None)
            except:
                latitudes.append(None); longitudes.append(None)
        
        df['lat'] = latitudes
        df['lon'] = longitudes
        return df.dropna(subset=['lat', 'lon'])
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def obter_lat_lon_usuario(endereco):
    geolocator = Nominatim(user_agent="app_paz_user_v2")
    try:
        query = f"{endereco}, São Paulo, Brasil"
        loc = geolocator.geocode(query)
        if not loc: loc = geolocator.geocode(f"{endereco}, Brasil")
        if loc:
            endereco_bonito = limpar_endereco_visual(loc)
            return loc.latitude, loc.longitude, endereco_bonito
        return None, None, None
    except:
        return None, None, None

def exibir_cartoes(dataframe, nome_user, zap_user, is_online=False):
    for index, row in dataframe.iterrows():
        with st.container():
            st.markdown("---")
            c1, c2 = st.columns([1.5, 1])
            
            bairro = row['Bairro'] if 'Bairro' in row else "Região não informada"
            
            with c1:
                st.markdown(f"### 💙 {row['Nome do Life']}")
                if is_online:
                    st.write("📍 **Life Online** (Sem fronteiras 🌎)")
                else:
                    st.write(f"📍 **{bairro}** ({row['distancia']:.1f} km)")
                st.caption(f"{row['Tipo de Life']} | {row['Modo']}")
                st.write(f"📅 {row['Dia da Semana']} às {row['Horário de Início']}")
            
            with c2:
                # Botão de Solicitação Automática
                # Precisamos de uma chave única para cada botão
                btn_key = f"btn_solicitar_{index}"
                
                if st.button("🚀 Quero Participar", key=btn_key):
                    if not nome_user or not zap_user:
                        st.error("Preencha seu Nome e WhatsApp lá em cima primeiro!")
                    else:
                        with st.spinner("Enviando solicitação..."):
                            # Prepara o pacote de dados
                            dados_lead = {
                                "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "visitante_nome": nome_user,
                                "visitante_zap": zap_user,
                                "life_nome": row['Nome do Life'],
                                "lider_nome": row['Líderes'],
                                "lider_zap": extrair_zap(row['Telefone']),
                                "modo": row['Modo']
                            }
                            
                            # Dispara para o n8n
                            sucesso, msg = enviar_para_n8n(dados_lead)
                            
                            if sucesso:
                                st.success("✅ Solicitação Enviada! O líder recebeu seu contato e vai te chamar em breve.")
                                st.balloons()
                            else:
                                st.error(f"Erro no envio: {msg}")

# --- INÍCIO DO APP ---
try: st.image("logo_menor.png", width=150)
except: pass

st.title("Encontre seu LifeGroup")
st.markdown("**Paz Church São Paulo**")

df_geral = carregar_dados()

opcoes_tipo = sorted(df_geral['Tipo de Life'].unique().tolist()) if not df_geral.empty else []
opcoes_dia = sorted(df_geral['Dia da Semana'].unique().tolist()) if not df_geral.empty else []
opcoes_modo = sorted(df_geral['Modo'].unique().tolist()) if not df_geral.empty else []

with st.form("form_busca"):
    st.markdown("### 1. Seus Dados")
    c1, c2 = st.columns(2)
    with c1: nome = st.text_input("Nome")
    with c2: whatsapp = st.text_input("WhatsApp (com DDD)")
    endereco_usuario = st.text_input("Endereço ou Bairro", placeholder="Ex: Rua Henrique Felipe da Costa, Vila Guilherme")
    
    st.markdown("---")
    st.markdown("### 2. Preferências")
    f1, f2, f3 = st.columns(3)
    with f1: filtro_tipo = st.multiselect("Público", options=opcoes_tipo, default=opcoes_tipo)
    with f2: filtro_dia = st.multiselect("Dias", options=opcoes_dia, default=opcoes_dia)
    with f3: filtro_modo = st.multiselect("Modo", options=opcoes_modo, default=opcoes_modo)
    
    buscar = st.form_submit_button("🔍 BUSCAR DISPONÍVEIS")

# --- LÓGICA DE EXIBIÇÃO ---
if buscar:
    if not nome or not whatsapp or not endereco_usuario:
        st.warning("⚠️ Preencha todos os campos acima para buscar.")
    elif df_geral.empty:
        st.error("Base vazia.")
    else:
        df_filtrado = df_geral[
            (df_geral['Tipo de Life'].isin(filtro_tipo)) &
            (df_geral['Dia da Semana'].isin(filtro_dia)) &
            (df_geral['Modo'].isin(filtro_modo))
        ]
        
        if df_filtrado.empty:
            st.warning("Nenhum life encontrado com esses filtros.")
        else:
            lat_user, lon_user, endereco_bonito = obter_lat_lon_usuario(endereco_usuario)
            
            if lat_user:
                st.info(f"📍 **Referência:** {endereco_bonito}")
                
                df_online = df_filtrado[df_filtrado['Modo'].astype(str).str.contains("Online", case=False)]
                df_presencial = df_filtrado[~df_filtrado['Modo'].astype(str).str.contains("Online", case=False)]
                
                # Renderiza Presenciais
                if not df_presencial.empty:
                    user_loc = (lat_user, lon_user)
                    df_presencial['distancia'] = df_presencial.apply(
                        lambda row: geodesic(user_loc, (row['lat'], row['lon'])).km, axis=1
                    )
                    df_sorted = df_presencial.sort_values(by='distancia')
                    
                    st.markdown("### 📍 Presenciais Próximos")
                    exibir_cartoes(df_sorted.head(3), nome, whatsapp, is_online=False)
                    
                    if len(df_sorted) > 3:
                        with st.expander(f"➕ Ver mais {len(df_sorted)-3} presenciais..."):
                            exibir_cartoes(df_sorted.iloc[3:], nome, whatsapp, is_online=False)
                
                # Renderiza Online
                if not df_online.empty:
                    st.markdown("### 💻 Opções Online")
                    exibir_cartoes(df_online, nome, whatsapp, is_online=True)
            else:
                st.error("Endereço não encontrado.")
