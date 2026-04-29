# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import requests
import numpy as np
import yfinance as yf

# =============================================================================
# CONFIGURAÇÕES INICIAIS
# =============================================================================

st.set_page_config(
    page_title="Compostagem Escolar - Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

# Estilo para melhorar a visualização
st.markdown("""
    <style>
    .main { opacity: 0.95; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("♻️ Compostagem com Minhocas nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo científico de emissões para resíduos orgânicos** [cite: 1]")

# =============================================================================
# CONFIGURAÇÕES E PARÂMETROS [cite: 1, 2]
# =============================================================================

URL_EXCEL = "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem_real.xlsx"
DENSIDADE_PADRAO = 0.6  # kg/L [cite: 1]
K_ANO_PADRAO = 0.06     # Taxa de decaimento anual padrão (IPCC) [cite: 1, 2]
PHI_BASELINE = 0.85     # Fator φ (UNFCCC 2024) para clima úmido [cite: 2]

# =============================================================================
# FUNÇÕES DE UTILIDADE E FORMATAÇÃO [cite: 2, 3]
# =============================================================================

def formatar_br(numero, casas_decimais=2):
    if numero is None or pd.isna(numero): return "N/A"
    try:
        numero = round(float(numero), casas_decimais)
        formato = f"{{:,.{casas_decimais}f}}"
        return formato.format(numero).replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "N/A"

def formatar_moeda_br(valor, simbolo="R$"):
    return f"{simbolo} {formatar_br(valor, 2)}"

def formatar_tco2eq(valor):
    return f"{formatar_br(valor, 3)} tCO₂eq"

# =============================================================================
# MERCADO DE CARBONO E CÂMBIO [cite: 4, 5, 6]
# =============================================================================

def obter_cotacoes():
    # Carbono via Yahoo Finance
    try:
        ticker = yf.Ticker("CO2.L")
        data = ticker.history(period="1d")
        preco_c = data['Close'].iloc[-1] if not data.empty else 85.50
        fonte_c = "Yahoo Finance (CO2.L)" if not data.empty else "Referência"
    except:
        preco_c, fonte_c = 85.50, "Referência"

    # Euro via AwesomeAPI
    try:
        req = requests.get("https://economia.awesomeapi.com.br/last/EUR-BRL", timeout=5)
        taxa_e = float(req.json()['EURBRL']['bid'])
    except:
        taxa_e = 5.50
        
    return preco_c, taxa_e, fonte_c

# =============================================================================
# CARREGAMENTO DOS DADOS (Com Cache de 1 hora) [cite: 16, 17, 18]
# =============================================================================

@st.cache_data(ttl=3600)
def carregar_dados_reais(url):
    try:
        df_escolas = pd.read_excel(url, sheet_name='escolas').dropna(how='all')
        df_reatores = pd.read_excel(url, sheet_name='reatores').dropna(how='all')
        df_gastos = pd.read_excel(url, sheet_name='gastos').dropna(how='all')
        
        # Limpeza básica de IDs [cite: 18]
        if 'id_reator' in df_reatores.columns:
            df_reatores = df_reatores.dropna(subset=['id_reator']).drop_duplicates(subset=['id_reator'])
            
        # Conversão de datas [cite: 19, 20, 21]
        for df, colunas in [(df_escolas, ['data_implantacao', 'ultima_visita']), 
                            (df_reatores, ['data_ativacao', 'data_encheu', 'data_colheita']),
                            (df_gastos, ['data_compra'])]:
            for col in colunas:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

        # Cálculo de volume/capacidade [cite: 25, 26, 27, 28]
        if 'altura_cm' in df_reatores.columns and 'largura_cm' in df_reatores.columns:
            vol_calc = (df_reatores['altura_cm'] * df_reatores['largura_cm'] * df_reatores['comprimento_cm']) / 1000
            df_reatores['capacidade_litros'] = df_reatores.get('volume_calculado_litros', vol_calc).fillna(100)
        else:
            df_reatores['capacidade_litros'] = 100

        return df_escolas, df_reatores, df_gastos
    except Exception as e:
        st.error(f"Erro ao carregar Excel: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# =============================================================================
# LÓGICA CIENTÍFICA [cite: 30, 31, 32, 33, 34]
# =============================================================================

def calcular_impacto(capacidade_l, periodo, k_ano, ox_fator):
    residuo_kg = capacidade_l * DENSIDADE_PADRAO
    GWP_CH4, GWP_N2O = 79.7, 273 # IPCC AR6 20 anos [cite: 31]
    
    # Simplificação do modelo Yang/IPCC contido no app original [cite: 30, 32, 34]
    potencial_ch4 = 0.15 * 0.5 * (16/12) * (1 - ox_fator) 
    emissoes_aterro = (residuo_kg * potencial_ch4 * PHI_BASELINE * GWP_CH4) / 1000
    
    # Emissões na compostagem são significativamente menores [cite: 34]
    emissoes_comp = (residuo_kg * 0.005 * GWP_CH4) / 1000 
    
    evitadas = emissoes_aterro - emissoes_comp
    return residuo_kg, max(evitadas, 0)

# =============================================================================
# INTERFACE STREAMLIT
# =============================================================================

# Inicialização de Estado [cite: 14, 15, 16]
if 'carteira' not in st.session_state: st.session_state.carteira = 50.0
if 'portfolio' not in st.session_state: st.session_state.portfolio = {}

# Sidebar - Parâmetros e Filtros [cite: 45, 46]
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2590/2590510.png", width=100)
st.sidebar.header("⚙️ Configurações Técnicas")

with st.sidebar.expander("🔬 Parâmetros Científicos", expanded=False):
    periodo = st.slider("Período (anos)", 1, 30, 10)
    k_decaimento = st.slider("Taxa k (ano⁻¹)", 0.01, 0.50, K_ANO_PADRAO)
    fator_ox = st.slider("Fator Oxidação (OX)", 0.0, 0.2, 0.1)

# Cotações [cite: 7, 8, 9, 10]
preco_carb, taxa_eur, fonte_c = obter_cotacoes()
preco_brl = preco_carb * taxa_eur

st.sidebar.metric("Preço Carbono", f"€ {formatar_br(preco_carb)}", help=f"Fonte: {fonte_c}")
st.sidebar.metric("Câmbio EUR/BRL", f"R$ {formatar_br(taxa_eur)}")

# Carregar Dados
df_escolas, df_reatores, df_gastos = carregar_dados_reais(URL_EXCEL)

# Filtro de Escola [cite: 46]
escola_sel = st.sidebar.selectbox("Selecionar Escola", ["Todas"] + list(df_escolas['id_escola'].unique()))
df_reat_filtrado = df_reatores if escola_sel == "Todas" else df_reatores[df_reatores['id_escola'] == escola_sel]

# Processamento [cite: 38, 39, 40]
reatores_cheios = df_reat_filtrado[df_reat_filtrado['data_encheu'].notna()].copy()
total_kg, total_tco2 = 0, 0
lista_resultados = []

for _, r in reatores_cheios.iterrows():
    kg, tco2 = calcular_impacto(r['capacidade_litros'], periodo, k_decaimento, fator_ox)
    total_kg += kg
    total_tco2 += tco2
    lista_resultados.append({**r, 'kg': kg, 'tco2': tco2, 'valor_r': tco2 * preco_brl})

# Dashboard Principal [cite: 47, 48]
col1, col2, col3 = st.columns(3)
col1.metric("Resíduo Processado", f"{formatar_br(total_kg, 1)} kg")
col2.metric("Créditos Gerados", formatar_tco2eq(total_tco2))
col3.metric("Valor Estimado", formatar_moeda_br(total_tco2 * preco_brl))

# Bolsa de Valores Virtual [cite: 58, 60, 61, 62]
st.divider()
st.header("🏦 Mercado de Créditos das Escolas")
c1, c2 = st.columns(2)
c1.metric("💰 Seu Saldo Virtual", formatar_moeda_br(st.session_state.carteira))
c2.info(f"Cada 100 kWh de energia emitem ~0,0046 tCO₂eq. [cite: 59]")

if lista_resultados:
    st.subheader("Ativos Disponíveis")
    for res in lista_resultados[:5]: # Mostrar top 5 para teste
        col_n, col_v, col_btn = st.columns([3, 2, 2])
        col_n.write(f"**Escola:** {res.get('id_escola')} | Reator: {res['id_reator']}")
        col_v.write(f"{formatar_tco2eq(res['tco2'])} → {formatar_moeda_br(res['valor_r'])}")
        
        if col_btn.button(f"🛒 Comprar", key=res['id_reator']):
            if st.session_state.carteira >= res['valor_r']:
                st.session_state.carteira -= res['valor_r']
                st.balloons()
                st.success(f"Sucesso! Você neutralizou emissões da escola {res['id_escola']}!")
                # Lógica simplificada de portfólio
                st.session_state.portfolio[res['id_reator']] = res['tco2']
            else:
                st.error("Saldo insuficiente na carteira virtual.")

# Tabelas de Dados [cite: 52, 53]
with st.expander("📋 Ver detalhamento dos reatores"):
    if not reatores_cheios.empty:
        st.dataframe(pd.DataFrame(lista_resultados)[['id_escola', 'id_reator', 'data_encheu', 'kg', 'tco2', 'valor_r']])
    else:
        st.warning("Nenhum reator cheio encontrado para os filtros selecionados.")

st.markdown("---")
st.caption("Sistema Experimental - Ribeirão Preto 2026. Referências: IPCC (2006) e UNFCCC (2024). [cite: 86, 88]")
