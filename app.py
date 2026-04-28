# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import numpy as np
from io import BytesIO
import math
import yfinance as yf

# =============================================================================
# CONFIGURAÇÕES INICIAIS
# =============================================================================

st.set_page_config(
    page_title="Compostagem com Minhocas, Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Compostagem com Minhocas nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo científico de emissões para resíduos orgânicos**")

# =============================================================================
# CONFIGURAÇÕES FIXAS
# =============================================================================

URL_EXCEL = "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem_real.xlsx"
DENSIDADE_PADRAO = 0.6  # kg/L - para resíduos de vegetais, frutas e borra de café
K_ANO_PADRAO = 0.06     # Taxa de decaimento anual padrão (IPCC para resíduos alimentares)
PHI_BASELINE = 0.85     # Fator φ (UNFCCC 2024) para clima úmido

# =============================================================================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# =============================================================================

def formatar_br(numero, casas_decimais=2):
    if numero is None or pd.isna(numero):
        return "N/A"
    try:
        numero = round(float(numero), casas_decimais)
        if casas_decimais == 0:
            return f"{numero:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            formato = f"{{:,.{casas_decimais}f}}"
            return formato.format(numero).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "N/A"

def formatar_moeda_br(valor, simbolo="R$", casas_decimais=2):
    return f"{simbolo} {formatar_br(valor, casas_decimais)}"

def formatar_tco2eq(valor):
    return f"{formatar_br(valor, 3)} tCO₂eq"

# =============================================================================
# FUNÇÕES DE COTAÇÃO DO CARBONO (YAHOO FINANCE + FALLBACK)
# =============================================================================

def obter_cotacao_carbono():
    try:
        ticker = yf.Ticker("CO2.L")
        data = ticker.history(period="1d")
        if not data.empty:
            preco = data['Close'].iloc[-1]
            if 10 < preco < 200:
                return preco, "€", "Carbon Futures (CO2.L)", True, "Yahoo Finance (CO2.L)"
        return 85.50, "€", "Carbon Emissions (Referência)", False, "Referência"
    except Exception:
        return 85.50, "€", "Carbon Emissions (Referência)", False, "Referência"

def obter_cotacao_euro_real():
    try:
        url = "https://economia.awesomeapi.com.br/last/EUR-BRL"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return float(data['EURBRL']['bid']), "R$", True, "AwesomeAPI"
    except:
        pass
    try:
        url = "https://api.exchangerate-api.com/v4/latest/EUR"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data['rates']['BRL'], "R$", True, "ExchangeRate-API"
    except:
        pass
    return 5.50, "R$", False, "Referência"

def calcular_valor_creditos(emissoes_evitadas_tco2eq, preco_carbono_por_tonelada, moeda, taxa_cambio=1):
    return emissoes_evitadas_tco2eq * preco_carbono_por_tonelada * taxa_cambio

def exibir_cotacao_carbono():
    st.sidebar.header("💰 Mercado de Carbono e Câmbio")
    if not st.session_state.get('cotacao_carregada', False):
        st.session_state.mostrar_atualizacao = True
        st.session_state.cotacao_carregada = True
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        if st.button("🔄 Atualizar Cotações", key="atualizar_cotacoes"):
            st.session_state.cotacao_atualizada = True
            st.session_state.mostrar_atualizacao = True
    if st.session_state.get('mostrar_atualizacao', False):
        st.sidebar.info("🔄 Atualizando cotações...")
        preco_carbono, moeda, _, _, fonte_carbono = obter_cotacao_carbono()
        preco_euro, moeda_real, _, _ = obter_cotacao_euro_real()
        st.session_state.preco_carbono = preco_carbono
        st.session_state.moeda_carbono = moeda
        st.session_state.taxa_cambio = preco_euro
        st.session_state.moeda_real = moeda_real
        st.session_state.fonte_cotacao = fonte_carbono
        st.session_state.mostrar_atualizacao = False
        st.session_state.cotacao_atualizada = False
        st.rerun()
    st.sidebar.metric(
        label="Preço do Carbono (tCO₂eq)",
        value=f"{st.session_state.moeda_carbono} {formatar_br(st.session_state.preco_carbono)}",
        help=f"Fonte: {st.session_state.fonte_cotacao}"
    )
    st.sidebar.metric(
        label="Euro (EUR/BRL)",
        value=f"{st.session_state.moeda_real} {formatar_br(st.session_state.taxa_cambio)}",
        help="Cotação do Euro em Reais Brasileiros"
    )
    preco_carbono_reais = st.session_state.preco_carbono * st.session_state.taxa_cambio
    st.sidebar.metric(
        label="Carbono em Reais (tCO₂eq)",
        value=f"R$ {formatar_br(preco_carbono_reais)}",
        help="Preço do carbono convertido para Reais Brasileiros"
    )
    with st.sidebar.expander("ℹ️ Informações do Mercado de Carbono"):
        st.markdown("""
        **📊 Cotações Atuais:**
        - **Fonte do Carbono:** {fonte}
        - **Preço Atual:** {moeda} {preco}/tCO₂eq
        - **Câmbio EUR/BRL:** 1 Euro = R$ {cambio}
        - **Carbono em Reais:** R$ {precoreais}/tCO₂eq
        
        **🌍 Mercado de Referência:**
        - European Union Allowances (EUA)
        - European Emissions Trading System (EU ETS)
        - Contratos futuros de carbono (ICE CO2.L)
        - Preços em tempo real via Yahoo Finance
        
        **🔄 Atualização:**
        - As cotações são carregadas automaticamente ao abrir o aplicativo
        - Clique em **"Atualizar Cotações"** para obter valores mais recentes
        - Em caso de falha, são utilizados valores de referência.
        """.format(
            fonte=st.session_state.fonte_cotacao,
            moeda=st.session_state.moeda_carbono,
            preco=formatar_br(st.session_state.preco_carbono),
            cambio=formatar_br(st.session_state.taxa_cambio),
            precoreais=formatar_br(preco_carbono_reais)
        ))

# =============================================================================
# INICIALIZAÇÃO DA SESSION STATE
# =============================================================================

def inicializar_session_state():
    if 'preco_carbono' not in st.session_state:
        preco_carbono, moeda, _, _, fonte = obter_cotacao_carbono()
        st.session_state.preco_carbono = preco_carbono
        st.session_state.moeda_carbono = moeda
        st.session_state.fonte_cotacao = fonte
    if 'taxa_cambio' not in st.session_state:
        preco_euro, moeda_real, _, _ = obter_cotacao_euro_real()
        st.session_state.taxa_cambio = preco_euro
        st.session_state.moeda_real = moeda_real
    if 'moeda_real' not in st.session_state:
        st.session_state.moeda_real = "R$"
    if 'cotacao_atualizada' not in st.session_state:
        st.session_state.cotacao_atualizada = False
    if 'mostrar_atualizacao' not in st.session_state:
        st.session_state.mostrar_atualizacao = False
    if 'cotacao_carregada' not in st.session_state:
        st.session_state.cotacao_carregada = False
    if 'periodo_credito' not in st.session_state:
        st.session_state.periodo_credito = 10
    if 'k_ano' not in st.session_state:
        st.session_state.k_ano = K_ANO_PADRAO
    # NOVAS INICIALIZAÇÕES PARA A BOLSA DE CARBONO
    if 'carteira_r_virtual' not in st.session_state:
        st.session_state.carteira_r_virtual = 10.0  # R$10 iniciais
    if 'portfolio_creditos' not in st.session_state:
        st.session_state.portfolio_creditos = {}
    if 'historico_transacoes' not in st.session_state:
        st.session_state.historico_transacoes = []

# =============================================================================
# CARREGAMENTO DOS DADOS REAIS
# =============================================================================

@st.cache_data
def carregar_dados_excel(url):
    try:
        loading_placeholder = st.empty()
        loading_placeholder.info("📥 Carregando dados do Excel...")
        excel_file = pd.ExcelFile(url)
        df_escolas = pd.read_excel(url, sheet_name='escolas')
        df_reatores = pd.read_excel(url, sheet_name='reatores')
        df_gastos = pd.read_excel(url, sheet_name='gastos')
        df_reatores = df_reatores.dropna(how='all')
        df_escolas = df_escolas.dropna(how='all')
        df_gastos = df_gastos.dropna(how='all')
        if 'id_reator' in df_reatores.columns:
            df_reatores = df_reatores.dropna(subset=['id_reator'])
            df_reatores = df_reatores[df_reatores['id_reator'].astype(str).str.strip() != '']
        loading_placeholder.empty()
        colunas_data_escolas = ['data_implantacao', 'ultima_visita']
        for col in colunas_data_escolas:
            if col in df_escolas.columns:
                try:
                    df_escolas[col] = pd.to_datetime(df_escolas[col], dayfirst=True, errors='coerce')
                except:
                    df_escolas[col] = pd.to_datetime(df_escolas[col], errors='coerce')
        colunas_data_reatores = ['data_ativacao', 'data_encheu', 'data_colheita']
        for col in colunas_data_reatores:
            if col in df_reatores.columns:
                try:
                    df_reatores[col] = pd.to_datetime(df_reatores[col], dayfirst=True, errors='coerce')
                except:
                    df_reatores[col] = pd.to_datetime(df_reatores[col], errors='coerce')
        if 'data_compra' in df_gastos.columns:
            try:
                df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'], dayfirst=True, errors='coerce')
            except:
                df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'], errors='coerce')
        if 'capacidade_total_sistema_litros' in df_escolas.columns:
            df_escolas['capacidade_total_sistema_litros'] = pd.to_numeric(df_escolas['capacidade_total_sistema_litros'], errors='coerce')
        dimensoes_cols = ['altura_cm', 'largura_cm', 'comprimento_cm']
        if all(col in df_reatores.columns for col in dimensoes_cols):
            for col in dimensoes_cols:
                df_reatores[col] = pd.to_numeric(df_reatores[col], errors='coerce')
            df_reatores['capacidade_litros'] = (df_reatores['altura_cm'] * 
                                               df_reatores['largura_cm'] * 
                                               df_reatores['comprimento_cm']) / 1000
            df_reatores['capacidade_litros'] = df_reatores['capacidade_litros'].round(2)
            df_reatores['capacidade_litros'] = df_reatores['capacidade_litros'].fillna(100)
            df_reatores['residuo_kg_estimado'] = df_reatores['capacidade_litros'] * DENSIDADE_PADRAO
            df_reatores['residuo_kg_estimado'] = df_reatores['residuo_kg_estimado'].round(1)
        else:
            st.warning("⚠️ Colunas de dimensões não encontradas. Usando capacidade padrão de 100L para todos os reatores.")
            df_reatores['capacidade_litros'] = 100
            df_reatores['residuo_kg_estimado'] = 100 * DENSIDADE_PADRAO
        return df_escolas, df_reatores, df_gastos
    except Exception as e:
        if 'loading_placeholder' in locals():
            loading_placeholder.empty()
        st.error(f"❌ Erro ao carregar dados do Excel: {e}")
        try:
            excel_file = pd.ExcelFile(url)
            st.error(f"📋 Abas encontradas: {excel_file.sheet_names}")
        except Exception as diag_error:
            st.error(f"❌ Erro no diagnóstico: {diag_error}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# =============================================================================
# FUNÇÕES DE CÁLCULO CIENTÍFICO – COM FATOR φ = 0,85
# =============================================================================

def calcular_emissoes_evitadas_reator_detalhado(capacidade_litros, periodo_anos=10):
    residuo_kg = capacidade_litros * DENSIDADE_PADRAO
    T = 25
    DOC = 0.15
    DOCf = 0.0147 * T + 0.28
    MCF = 1.0
    F = 0.5
    OX = 0.1
    Ri = 0.0
    phi = PHI_BASELINE
    TOC_YANG = 0.436
    TN_YANG = 14.2 / 1000
    CH4_C_FRAC_YANG = 0.13 / 100
    N2O_N_FRAC_YANG = 0.92 / 100
    umidade = 0.85
    fracao_ms = 1 - umidade
    massa_exposta_kg = min(residuo_kg, 50)
    h_exposta = 8
    GWP_CH4_20 = 79.7
    GWP_N2O_20 = 273

    potencial_CH4_por_kg_total = DOC * DOCf * MCF * F * (16/12) * (1 - Ri) * (1 - OX)
    ch4_total_aterro = residuo_kg * potencial_CH4_por_kg_total

    k_ano_atual = st.session_state.get('k_ano', K_ANO_PADRAO)
    k_dia = k_ano_atual / 365.0
    dias_simulacao = periodo_anos * 365
    t = np.arange(1, dias_simulacao + 1, dtype=float)
    kernel_ch4 = np.exp(-k_dia * (t - 1)) - np.exp(-k_dia * t)
    kernel_ch4 = np.maximum(kernel_ch4, 0)
    ch4_emitido_aterro_bruto = ch4_total_aterro * kernel_ch4.sum()
    ch4_emitido_aterro_periodo = ch4_emitido_aterro_bruto * phi
    fracao_ch4_emitida = kernel_ch4.sum()

    f_aberto = (massa_exposta_kg / residuo_kg) * (h_exposta / 24)
    f_aberto = np.clip(f_aberto, 0.0, 1.0)
    E_aberto = 1.91
    E_fechado = 2.15
    E_medio = f_aberto * E_aberto + (1 - f_aberto) * E_fechado
    fator_umid = (1 - umidade) / (1 - 0.55)
    E_medio_ajust = E_medio * fator_umid
    n2o_total_aterro = (E_medio_ajust * (44/28) / 1_000_000) * residuo_kg
    kernel_n2o = np.array([0.10, 0.30, 0.40, 0.15, 0.05], dtype=float)
    kernel_n2o = kernel_n2o / kernel_n2o.sum()
    n2o_emitido_aterro_periodo = n2o_total_aterro

    ch4_total_compostagem = residuo_kg * (TOC_YANG * CH4_C_FRAC_YANG * (16/12) * fracao_ms)
    n2o_total_compostagem = residuo_kg * (TN_YANG * N2O_N_FRAC_YANG * (44/28) * fracao_ms)
    ch4_emitido_compostagem_periodo = ch4_total_compostagem
    n2o_emitido_compostagem_periodo = n2o_total_compostagem

    emissao_aterro_kgco2eq = (ch4_emitido_aterro_periodo * GWP_CH4_20 + 
                              n2o_emitido_aterro_periodo * GWP_N2O_20)
    emissao_compostagem_kgco2eq = (ch4_emitido_compostagem_periodo * GWP_CH4_20 + 
                                   n2o_emitido_compostagem_periodo * GWP_N2O_20)

    emissoes_evitadas_tco2eq = (emissao_aterro_kgco2eq - emissao_compostagem_kgco2eq) / 1000

    return {
        'residuo_kg': residuo_kg,
        'ch4_total_aterro': ch4_total_aterro,
        'ch4_emitido_aterro_bruto': ch4_emitido_aterro_bruto,
        'ch4_emitido_aterro_periodo': ch4_emitido_aterro_periodo,
        'n2o_total_aterro': n2o_total_aterro,
        'n2o_emitido_aterro_periodo': n2o_emitido_aterro_periodo,
        'ch4_total_compostagem': ch4_total_compostagem,
        'n2o_total_compostagem': n2o_total_compostagem,
        'ch4_emitido_compostagem_periodo': ch4_emitido_compostagem_periodo,
        'n2o_emitido_compostagem_periodo': n2o_emitido_compostagem_periodo,
        'emissao_aterro_kgco2eq': emissao_aterro_kgco2eq,
        'emissao_compostagem_kgco2eq': emissao_compostagem_kgco2eq,
        'emissoes_evitadas_tco2eq': emissoes_evitadas_tco2eq,
        'parametros': {
            'capacidade_litros': capacidade_litros,
            'densidade_kg_l': DENSIDADE_PADRAO,
            'periodo_anos': periodo_anos,
            'k_ano': k_ano_atual,
            'fracao_ch4_emitida': fracao_ch4_emitida,
            'phi': phi,
            'T': T, 'DOC': DOC, 'DOCf': DOCf,
            'TOC_YANG': TOC_YANG, 'TN_YANG': TN_YANG,
            'CH4_C_FRAC_YANG': CH4_C_FRAC_YANG, 'N2O_N_FRAC_YANG': N2O_N_FRAC_YANG,
            'umidade': umidade,
            'GWP_CH4_20': GWP_CH4_20, 'GWP_N2O_20': GWP_N2O_20,
            'massa_exposta_kg': massa_exposta_kg, 'h_exposta': h_exposta,
            'f_aberto': f_aberto, 'E_medio': E_medio,
            'E_medio_ajust': E_medio_ajust, 'fator_umid': fator_umid
        }
    }

def calcular_emissoes_evitadas_reator(capacidade_litros):
    resultado = calcular_emissoes_evitadas_reator_detalhado(capacidade_litros)
    return resultado['residuo_kg'], resultado['emissoes_evitadas_tco2eq']

def processar_reatores_cheios(df_reatores, df_escolas):
    reatores_cheios = df_reatores[df_reatores['data_encheu'].notna()].copy()
    if reatores_cheios.empty:
        return pd.DataFrame(), 0, 0, []
    resultados = []
    total_residuo = 0
    total_emissoes_evitadas = 0
    detalhes_calculo = []
    for _, reator in reatores_cheios.iterrows():
        capacidade = reator['capacidade_litros'] if pd.notna(reator['capacidade_litros']) else 100
        resultado_detalhado = calcular_emissoes_evitadas_reator_detalhado(capacidade, st.session_state.periodo_credito)
        residuo_kg = resultado_detalhado['residuo_kg']
        emissoes_evitadas = resultado_detalhado['emissoes_evitadas_tco2eq']
        detalhes_calculo.append({
            'id_reator': reator['id_reator'],
            'id_escola': reator['id_escola'],
            'capacidade_litros': capacidade,
            'residuo_kg': residuo_kg,
            'emissoes_evitadas_tco2eq': emissoes_evitadas,
            'calculo_detalhado': resultado_detalhado,
            'altura_cm': reator.get('altura_cm', 'N/A'),
            'largura_cm': reator.get('largura_cm', 'N/A'),
            'comprimento_cm': reator.get('comprimento_cm', 'N/A')
        })
        resultados.append({
            'id_reator': reator['id_reator'],
            'id_escola': reator['id_escola'],
            'data_encheu': reator['data_encheu'],
            'capacidade_litros': capacidade,
            'residuo_kg': residuo_kg,
            'emissoes_evitadas_tco2eq': emissoes_evitadas,
            'altura_cm': reator.get('altura_cm', 'N/A'),
            'largura_cm': reator.get('largura_cm', 'N/A'),
            'comprimento_cm': reator.get('comprimento_cm', 'N/A')
        })
        total_residuo += residuo_kg
        total_emissoes_evitadas += emissoes_evitadas
    df_resultados = pd.DataFrame(resultados)
    if 'nome_escola' in df_escolas.columns and 'id_escola' in df_resultados.columns:
        df_resultados = df_resultados.merge(df_escolas[['id_escola', 'nome_escola']], on='id_escola', how='left')
    return df_resultados, total_residuo, total_emissoes_evitadas, detalhes_calculo

def analisar_escolas_ativas_com_reatores_ativos(df_escolas, df_reatores):
    if 'status' in df_escolas.columns:
        escolas_ativas = df_escolas[df_escolas['status'] == 'Ativo'].copy()
    else:
        escolas_ativas = df_escolas.copy()
    if 'status_reator' in df_reatores.columns:
        reatores_ativos = df_reatores[df_reatores['status_reator'].notna()].copy()
    else:
        reatores_ativos = pd.DataFrame()
    if not reatores_ativos.empty and 'id_escola' in reatores_ativos.columns:
        contagem = reatores_ativos.groupby('id_escola').size().reset_index(name='reatores_ativos')
        escolas_com = escolas_ativas.merge(contagem, on='id_escola', how='left')
        escolas_com['reatores_ativos'] = escolas_com['reatores_ativos'].fillna(0)
        return escolas_com
    else:
        escolas_ativas['reatores_ativos'] = 0
        return escolas_ativas

def analisar_gastos(df_gastos):
    if df_gastos.empty:
        return pd.DataFrame(), 0
    if 'valor' in df_gastos.columns:
        df_gastos['valor_numerico'] = df_gastos['valor'].astype(str).str.replace('R\$', '', regex=True).str.replace(',', '.').str.strip()
        df_gastos['valor_numerico'] = pd.to_numeric(df_gastos['valor_numerico'], errors='coerce')
        total_gastos = df_gastos['valor_numerico'].sum()
        return df_gastos, total_gastos
    return df_gastos, 0

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

inicializar_session_state()
df_escolas, df_reatores, df_gastos = carregar_dados_excel(URL_EXCEL)
if df_escolas.empty or df_reatores.empty:
    st.error("❌ Não foi possível carregar os dados. Verifique se o arquivo Excel existe no repositório GitHub.")
    st.stop()

exibir_cotacao_carbono()

with st.sidebar:
    st.header("⚙️ Parâmetros de Cálculo")
    periodo_credito = st.slider("Período de crédito (anos)", 1, 30, st.session_state.periodo_credito, 1)
    st.session_state.periodo_credito = periodo_credito
    k_ano = st.slider("Taxa de decaimento (k) [ano⁻¹]", 0.01, 0.50, st.session_state.k_ano, 0.01)
    st.session_state.k_ano = k_ano
    st.info(f"""
    **📊 Parâmetros de cálculo:**
    - Período: **{periodo_credito} anos**
    - Taxa de decaimento (k): **{formatar_br(k_ano, 3)} ano⁻¹**
    - GWP: **20 anos** (CH₄=79.7, N₂O=273)
    - φ (UNFCCC 2024): **{PHI_BASELINE}** (clima úmido)
    """)
    st.header("🔍 Filtros")
    escolas_options = ["Todas as escolas"] + df_escolas['id_escola'].tolist()
    escola_selecionada = st.selectbox("Selecionar escola", escolas_options)

if escola_selecionada != "Todas as escolas":
    reatores_filtrados = df_reatores[df_reatores['id_escola'] == escola_selecionada]
    escolas_filtradas = df_escolas[df_escolas['id_escola'] == escola_selecionada]
else:
    reatores_filtrados = df_reatores
    escolas_filtradas = df_escolas

reatores_processados, total_residuo, total_emissoes, detalhes_calculo = processar_reatores_cheios(reatores_filtrados, escolas_filtradas)
preco_carbono_eur = st.session_state.preco_carbono
taxa_cambio = st.session_state.taxa_cambio
valor_eur = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "€")
valor_brl = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "R$", taxa_cambio)
df_gastos_analisados, total_gastos = analisar_gastos(df_gastos)

# =============================================================================
# EXIBIÇÃO
# =============================================================================

st.info(f"""
**⚙️ Parâmetros de Cálculo CORRIGIDOS - DISTRIBUIÇÃO TEMPORAL COM φ:**
- **Densidade do resíduo:** {DENSIDADE_PADRAO} kg/L
- **Período de cálculo:** {periodo_credito} anos
- **Taxa de decaimento (k):** {formatar_br(k_ano, 3)} ano⁻¹
- **GWP:** 20 anos (CH₄=79.7, N₂O=273)
- ***Fator φ (UNFCCC 2024):** {PHI_BASELINE}* (aplicado apenas ao CH₄ do aterro)
""")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total de Escolas", formatar_br(len(df_escolas), 0))
with col2:
    st.metric("Total de Reatores", formatar_br(len(df_reatores), 0))
with col3:
    st.metric("Reatores Cheios", formatar_br(len(df_reatores[df_reatores['data_encheu'].notna()]), 0))
with col4:
    st.metric("Reatores Ativos", formatar_br(len(df_reatores[df_reatores['status_reator'].notna()]), 0))

st.header("💰 Créditos de Carbono Computados - Sistema Real")
if reatores_processados.empty:
    st.info("ℹ️ Nenhum reator cheio encontrado.")
else:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Reatores Processados", formatar_br(len(reatores_processados), 0))
    with col2:
        st.metric("Resíduo Processado", f"{formatar_br(total_residuo, 1)} kg")
    with col3:
        st.metric("Emissões Evitadas", formatar_tco2eq(total_emissoes))
    with col4:
        st.metric("Valor dos Créditos", formatar_moeda_br(valor_brl))

st.header("💰 Análise de Gastos")
if not df_gastos.empty:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Gastos", formatar_moeda_br(total_gastos))
    with col2:
        st.metric("Total de Itens", formatar_br(len(df_gastos), 0))
    with col3:
        if total_gastos > 0 and total_emissoes > 0:
            st.metric("Custo por tCO₂eq", formatar_moeda_br(total_gastos / total_emissoes))
        else:
            st.metric("Custo por tCO₂eq", formatar_moeda_br(0))
    st.subheader("📋 Detalhamento dos Gastos")
    df_gastos_display = df_gastos[['id_gasto', 'nome_gasto', 'data_compra', 'valor']].copy()
    if 'data_compra' in df_gastos_display.columns:
        df_gastos_display['data_compra'] = pd.to_datetime(df_gastos_display['data_compra'], errors='coerce').dt.strftime('%d/%m/%Y')
    if 'valor' in df_gastos_display.columns:
        df_gastos_display['valor_formatado'] = df_gastos_display['valor'].astype(str).apply(
            lambda x: formatar_moeda_br(float(x.replace('R$', '').replace(',', '.').strip())) if pd.notna(x) and x != '' else formatar_moeda_br(0)
        )
        df_gastos_display['valor'] = df_gastos_display['valor_formatado']
        df_gastos_display = df_gastos_display.drop('valor_formatado', axis=1)
    st.dataframe(df_gastos_display, use_container_width=True)
else:
    st.info("ℹ️ Nenhum gasto registrado.")

st.header("🏫 Análise de Escolas Ativas com Reatores Ativos")
escolas_com_reatores_ativos = analisar_escolas_ativas_com_reatores_ativos(df_escolas, df_reatores)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Escolas Ativas", formatar_br(len(escolas_com_reatores_ativos), 0))
with col2:
    esc_com_reat = len(escolas_com_reatores_ativos[escolas_com_reatores_ativos['reatores_ativos'] > 0])
    st.metric("Escolas com Reatores Ativos", formatar_br(esc_com_reat, 0))
with col3:
    st.metric("Total de Reatores Ativos", formatar_br(escolas_com_reatores_ativos['reatores_ativos'].sum(), 0))

if not reatores_processados.empty:
    st.header("📊 Detalhamento dos Créditos por Reator")
    preco_carbono_reais_por_tonelada = st.session_state.preco_carbono * st.session_state.taxa_cambio
    df_detalhes = reatores_processados[['nome_escola', 'id_reator', 'data_encheu', 'altura_cm', 'largura_cm', 'comprimento_cm',
                                        'capacidade_litros', 'residuo_kg', 'emissoes_evitadas_tco2eq']].copy()
    df_detalhes['valor_creditos_reais'] = df_detalhes['emissoes_evitadas_tco2eq'] * preco_carbono_reais_por_tonelada
    for col in ['altura_cm', 'largura_cm', 'comprimento_cm']:
        df_detalhes[col] = df_detalhes[col].apply(lambda x: formatar_br(x, 0) if pd.notna(x) else "N/A")
    df_detalhes['residuo_kg'] = df_detalhes['residuo_kg'].apply(lambda x: formatar_br(x, 1))
    df_detalhes['emissoes_evitadas_tco2eq'] = df_detalhes['emissoes_evitadas_tco2eq'].apply(formatar_tco2eq)
    df_detalhes['capacidade_litros'] = df_detalhes['capacidade_litros'].apply(lambda x: formatar_br(x, 0))
    df_detalhes['data_encheu'] = pd.to_datetime(df_detalhes['data_encheu']).dt.strftime('%d/%m/%Y')
    df_detalhes['valor_creditos_reais'] = df_detalhes['valor_creditos_reais'].apply(lambda x: formatar_moeda_br(x))
    st.dataframe(df_detalhes, use_container_width=True)

    st.header("🧮 Detalhamento Completo dos Cálculos")
    primeiro_reator = detalhes_calculo[0]
    calc = primeiro_reator['calculo_detalhado']
    st.subheader(f"📋 Cálculo Detalhado para o Reator {primeiro_reator['id_reator']}")
    st.info(f"**Período de cálculo:** {periodo_credito} anos | **Taxa de decaimento (k):** {formatar_br(k_ano, 3)} ano⁻¹ | **φ = {PHI_BASELINE}**")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Dimensões e Massa:**")
        st.write(f"- Altura: {formatar_br(primeiro_reator.get('altura_cm', 'N/A'), 0)} cm")
        st.write(f"- Largura: {formatar_br(primeiro_reator.get('largura_cm', 'N/A'), 0)} cm")
        st.write(f"- Comprimento: {formatar_br(primeiro_reator.get('comprimento_cm', 'N/A'), 0)} cm")
        st.write(f"- Capacidade: {formatar_br(calc['parametros']['capacidade_litros'], 0)} L")
        st.write(f"- Densidade: {formatar_br(calc['parametros']['densidade_kg_l'], 2)} kg/L")
        st.write(f"- Massa: {formatar_br(calc['residuo_kg'], 1)} kg")
    with col2:
        st.write("**Emissões Aterro (com φ):**")
        st.write(f"- CH₄ emitido: {formatar_br(calc['ch4_emitido_aterro_periodo'], 3)} kg")
        st.write(f"- N₂O emitido: {formatar_br(calc['n2o_emitido_aterro_periodo'], 6)} kg")
        st.write(f"- CO₂eq Aterro: {formatar_br(calc['emissao_aterro_kgco2eq'], 1)} kg")
        st.write("**Emissões Compostagem:**")
        st.write(f"- CH₄: {formatar_br(calc['ch4_emitido_compostagem_periodo'], 5)} kg")
        st.write(f"- N₂O: {formatar_br(calc['n2o_emitido_compostagem_periodo'], 5)} kg")
        st.write(f"- CO₂eq Compostagem: {formatar_br(calc['emissao_compostagem_kgco2eq'], 3)} kg")
        st.metric("Emissões Evitadas", formatar_tco2eq(calc['emissoes_evitadas_tco2eq']))

st.header("📈 Status dos Reatores")
if 'status_reator' in df_reatores.columns:
    status_count = df_reatores['status_reator'].value_counts()
    if not status_count.empty:
        labels_formatados = [f"{status} ({formatar_br(count, 0)})" for status, count in status_count.items()]
        fig = px.pie(values=status_count.values, names=labels_formatados, title="Distribuição dos Status dos Reatores")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Sem dados de status para reatores")
else:
    st.info("ℹ️ Coluna 'status_reator' não encontrada")

st.header("🏫 Status das Escolas")
if 'status' in df_escolas.columns:
    status_escolas_count = df_escolas['status'].value_counts()
    if not status_escolas_count.empty:
        labels_escolas_formatados = [f"{status} ({formatar_br(count, 0)})" for status, count in status_escolas_count.items()]
        fig2 = px.pie(values=status_escolas_count.values, names=labels_escolas_formatados, title="Distribuição dos Status das Escolas")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("ℹ️ Sem dados de status para escolas")
else:
    st.info("ℹ️ Coluna 'status' não encontrada")

# =============================================================================
# NOVA SEÇÃO: BOLSA DE VALORES DE CARBONO DAS ESCOLAS (R$ VIRTUAL)
# =============================================================================

st.header("🏦 Bolsa de Valores de Carbono Escolar (Simulação)")

col_saldo, col_disponivel = st.columns(2)
with col_saldo:
    st.metric("💰 Seu Saldo (R$ Virtual)", formatar_moeda_br(st.session_state.carteira_r_virtual))
with col_disponivel:
    creditos_em_carteira = sum(st.session_state.portfolio_creditos.values())
    st.metric("🎯 Créditos em Carteira", formatar_tco2eq(creditos_em_carteira))

if not reatores_processados.empty:
    df_ativos = reatores_processados[['nome_escola', 'id_reator', 'emissoes_evitadas_tco2eq']].copy()
    preco_carbono_reais = st.session_state.preco_carbono * st.session_state.taxa_cambio
    df_ativos['preco_unitario'] = preco_carbono_reais
    df_ativos['valor_total'] = df_ativos['emissoes_evitadas_tco2eq'] * df_ativos['preco_unitario']
    df_ativos['disponivel'] = True

    st.subheader("📊 Ativos Disponíveis para Compra (Créditos de Carbono por Reator)")

    for idx, row in df_ativos.iterrows():
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        with col1:
            st.write(f"**{row['nome_escola']}**")
            st.caption(f"Reator: {row['id_reator']}")
        with col2:
            st.metric("Créditos", formatar_tco2eq(row['emissoes_evitadas_tco2eq']))
        with col3:
            st.metric("Preço/tCO₂eq", formatar_moeda_br(row['preco_unitario']))
        with col4:
            st.metric("Valor Total", formatar_moeda_br(row['valor_total']))
        with col5:
            quantidade_comprar = st.number_input(
                "Qtd (tCO₂eq)",
                min_value=0.0,
                max_value=float(row['emissoes_evitadas_tco2eq']),
                value=0.0,
                step=0.1,
                key=f"compra_{row['id_reator']}"
            )
            valor_compra = quantidade_comprar * row['preco_unitario']
            if st.button("🛒 Comprar", key=f"btn_{row['id_reator']}"):
                if quantidade_comprar > 0:
                    if st.session_state.carteira_r_virtual >= valor_compra:
                        st.session_state.carteira_r_virtual -= valor_compra
                        if row['id_reator'] in st.session_state.portfolio_creditos:
                            st.session_state.portfolio_creditos[row['id_reator']] += quantidade_comprar
                        else:
                            st.session_state.portfolio_creditos[row['id_reator']] = quantidade_comprar
                        st.session_state.historico_transacoes.append({
                            'data': datetime.now().strftime('%d/%m/%Y %H:%M'),
                            'id_reator': row['id_reator'],
                            'escola': row['nome_escola'],
                            'quantidade_tco2eq': quantidade_comprar,
                            'preco_unitario': row['preco_unitario'],
                            'valor_total': valor_compra,
                            'tipo': 'Compra'
                        })
                        st.success(f"✅ Compra realizada! Você adquiriu {formatar_tco2eq(quantidade_comprar)} da {row['nome_escola']}")
                        st.rerun()
                    else:
                        st.error("❌ Saldo insuficiente!")
                else:
                    st.warning("⚠️ Selecione uma quantidade maior que zero.")

    st.subheader("📂 Seu Portfólio de Créditos de Carbono")
    if st.session_state.portfolio_creditos:
        portfolio_data = []
        for id_reator, qtd in st.session_state.portfolio_creditos.items():
            info = reatores_processados[reatores_processados['id_reator'] == id_reator].iloc[0]
            portfolio_data.append({
                'Escola': info['nome_escola'],
                'Reator': id_reator,
                'Créditos (tCO₂eq)': qtd,
                'Preço Médio (R$/tCO₂eq)': preco_carbono_reais,
                'Valor Atual (R$)': qtd * preco_carbono_reais
            })
        df_portfolio = pd.DataFrame(portfolio_data)
        st.dataframe(df_portfolio, use_container_width=True)
        fig_port = px.pie(df_portfolio, values='Créditos (tCO₂eq)', names='Escola',
                          title='Distribuição da Carteira de Créditos')
        st.plotly_chart(fig_port, use_container_width=True)
    else:
        st.info("Nenhum crédito em carteira. Compre créditos das escolas acima!")

    st.subheader("📜 Histórico de Transações")
    if st.session_state.historico_transacoes:
        df_hist = pd.DataFrame(st.session_state.historico_transacoes)
        df_hist_display = df_hist.copy()
        df_hist_display['valor_total'] = df_hist_display['valor_total'].apply(lambda x: formatar_moeda_br(x))
        df_hist_display['quantidade_tco2eq'] = df_hist_display['quantidade_tco2eq'].apply(lambda x: formatar_tco2eq(x))
        st.dataframe(df_hist_display, use_container_width=True)
    else:
        st.info("Nenhuma transação realizada ainda.")

    st.subheader("📈 Mercado de Carbono - Simulação de Variação")
    datas = pd.date_range(start='2024-01-01', periods=30, freq='D')
    preco_base = preco_carbono_reais
    np.random.seed(42)
    variacao = np.random.normal(0, 0.02, 30).cumsum()
    precos_sim = preco_base * (1 + variacao)
    df_mercado = pd.DataFrame({'Data': datas, 'Preço (R$/tCO₂eq)': precos_sim})
    fig_merc = px.line(df_mercado, x='Data', y='Preço (R$/tCO₂eq)',
                       title='Simulação do Preço do Carbono nos Últimos 30 Dias',
                       markers=True)
    fig_merc.add_hline(y=preco_base, line_dash="dash", line_color="red",
                       annotation_text="Preço Atual")
    st.plotly_chart(fig_merc, use_container_width=True)

else:
    st.info("Nenhum crédito disponível para negociação. Aguarde reatores serem preenchidos.")

st.markdown("---")
st.markdown("""
**♻️ Sistema de Compostagem com Minhocas - Ribeirão Preto/SP**  
*Dados carregados de: [Controladoria-Compostagem-nas-Escolas](https://github.com/loopvinyl/Controladoria-Compostagem-nas-Escolas)*

**📚 Referências Científicas:**  
- IPCC (2006). Guidelines for National Greenhouse Gas Inventories  
- Yang et al. (2017). Greenhouse gas emissions during MSW landfilling in China  
- Wang et al. (2017). N₂O emissions from landfills  
- **Fator φ = 0,85 (UNFCCC, 2024) para baseline em clima úmido**  
- GWP 20 anos: CH₄=79.7, N₂O=273 (IPCC AR6)
""")
