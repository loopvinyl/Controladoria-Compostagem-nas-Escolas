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
import yfinance as yf  # para obter cotação do carbono

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
    """Formata números no padrão brasileiro: 1.234,56"""
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
    """Formata valores monetários no padrão brasileiro: R$ 1.234,56"""
    return f"{simbolo} {formatar_br(valor, casas_decimais)}"

def formatar_tco2eq(valor):
    """Formata valores de tCO₂eq no padrão brasileiro"""
    return f"{formatar_br(valor, 3)} tCO₂eq"

# =============================================================================
# FUNÇÕES DE COTAÇÃO DO CARBONO (INTEGRADAS DO SCRIPT ORIGINAL)
# =============================================================================

def obter_cotacao_carbono():
    """
    Obtém a cotação do carbono via Yahoo Finance (ticker CO2.L).
    Em caso de falha, retorna valor de referência 85,50 €.
    """
    try:
        ticker = yf.Ticker("CO2.L")
        data = ticker.history(period="1d")
        if not data.empty:
            preco = data['Close'].iloc[-1]
            if 10 < preco < 200:   # faixa plausível
                return preco, "€", "Carbon Futures (CO2.L)", True, "Yahoo Finance (CO2.L)"
        # Fallback se dados inválidos
        return 85.50, "€", "Carbon Emissions (Referência)", False, "Referência"
    except Exception:
        return 85.50, "€", "Carbon Emissions (Referência)", False, "Referência"

def obter_cotacao_euro_real():
    """
    Obtém a cotação EUR/BRL usando APIs públicas.
    Fallback para 5,50 se falhar.
    """
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
    """Valor financeiro dos créditos de carbono."""
    return emissoes_evitadas_tco2eq * preco_carbono_por_tonelada * taxa_cambio

def exibir_cotacao_carbono():
    """Exibe na barra lateral os preços do carbono e do câmbio EUR/BRL."""
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
        preco_euro, moeda_real, _, fonte_euro = obter_cotacao_euro_real()
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
        st.markdown(f"""
        **📊 Cotações Atuais:**
        - **Fonte do Carbono:** {st.session_state.fonte_cotacao}
        - **Preço Atual:** {st.session_state.moeda_carbono} {formatar_br(st.session_state.preco_carbono)}/tCO₂eq
        - **Câmbio EUR/BRL:** 1 Euro = R$ {formatar_br(st.session_state.taxa_cambio)}
        - **Carbono em Reais:** R$ {formatar_br(preco_carbono_reais)}/tCO₂eq
        
        **🌍 Mercado de Referência:**
        - European Union Allowances (EUA)
        - European Emissions Trading System (EU ETS)
        - Contratos futuros de carbono (ICE CO2.L)
        - Preços em tempo real via Yahoo Finance
        
        **🔄 Atualização:**
        - As cotações são carregadas automaticamente ao abrir o aplicativo
        - Clique em **"Atualizar Cotações"** para obter valores mais recentes
        - Em caso de falha, são utilizados valores de referência.
        """)

# =============================================================================
# INICIALIZAÇÃO DA SESSION STATE
# =============================================================================

def inicializar_session_state():
    """Inicializa todas as variáveis de session state necessárias"""
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
        st.session_state.periodo_credito = 10  # Período de crédito padrão em anos
    if 'k_ano' not in st.session_state:
        st.session_state.k_ano = K_ANO_PADRAO  # Taxa de decaimento padrão

# =============================================================================
# FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO DOS DADOS REAIS
# =============================================================================

@st.cache_data
def carregar_dados_excel(url):
    """Carrega os dados REAIS do Excel do GitHub"""
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
        
        # =============================================================================
        # CÁLCULO DA CAPACIDADE APENAS A PARTIR DAS DIMENSÕES
        # =============================================================================
        
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
# FUNÇÕES DE CÁLCULO CIENTÍFICO - AJUSTADAS COM φ = 0,85
# =============================================================================

def calcular_emissoes_evitadas_reator_detalhado(capacidade_litros, periodo_anos=10):
    """
    Calcula emissões evitadas baseado no modelo científico CORRIGIDO
    COM DISTRIBUIÇÃO TEMPORAL ADEQUADA e FATOR φ = 0,85 (UNFCCC 2024):
    - Aterro: emissões ao longo de N anos (kernel não normalizado) * φ
    - Compostagem: emissões em 50 dias
    - Usando GWP-20: CH₄=79.7, N₂O=273
    """
    
    # Massa de resíduos processada - DENSIDADE FIXA
    residuo_kg = capacidade_litros * DENSIDADE_PADRAO
    
    # =============================================================================
    # PARÂMETROS FIXOS
    # =============================================================================
    
    # Parâmetros para aterro (CH₄)
    T = 25  # Temperatura (°C)
    DOC = 0.15  # Carbono orgânico degradável
    DOCf = 0.0147 * T + 0.28  # Calculado da temperatura
    MCF = 1.0  # Fator de correção de metano (para aterros sanitários)
    F = 0.5  # Fração de metano no biogás
    OX = 0.1  # Fator de oxidação
    Ri = 0.0  # Metano recuperado
    phi = PHI_BASELINE  # Fator φ (UNFCCC 2024) – clima úmido
    
    # Parâmetros para compostagem com minhocas (Yang et al. 2017)
    TOC_YANG = 0.436  # Fração de carbono orgânico total
    TN_YANG = 14.2 / 1000  # Fração de nitrogênio total
    CH4_C_FRAC_YANG = 0.13 / 100  # 0.13%
    N2O_N_FRAC_YANG = 0.92 / 100  # 0.92%
    
    umidade = 0.85  # 85% umidade
    fracao_ms = 1 - umidade  # Fração de matéria seca
    
    # Parâmetros para N₂O do aterro (Wang et al. 2017)
    massa_exposta_kg = min(residuo_kg, 50)
    h_exposta = 8  # horas
    
    # GWP 20 anos
    GWP_CH4_20 = 79.7  # IPCC AR6 - 20 anos
    GWP_N2O_20 = 273   # IPCC AR6 - 20 anos
    
    # =============================================================================
    # 1. CÁLCULO DO CH₄ DO ATERRO - COM DISTRIBUIÇÃO TEMPORAL E FATOR φ
    # =============================================================================
    
    # Potencial TOTAL de metano do aterro (100 anos)
    potencial_CH4_por_kg_total = DOC * DOCf * MCF * F * (16/12) * (1 - Ri) * (1 - OX)
    ch4_total_aterro = residuo_kg * potencial_CH4_por_kg_total
    
    # Taxa de decaimento diária (usando session state)
    k_ano_atual = st.session_state.get('k_ano', K_ANO_PADRAO)
    k_dia = k_ano_atual / 365.0
    
    # Período em dias
    dias_simulacao = periodo_anos * 365
    
    # Kernel de decaimento NÃO NORMALIZADO (correto IPCC)
    t = np.arange(1, dias_simulacao + 1, dtype=float)
    kernel_ch4 = np.exp(-k_dia * (t - 1)) - np.exp(-k_dia * t)
    kernel_ch4 = np.maximum(kernel_ch4, 0)
    
    # CH₄ emitido no período (soma do kernel * potencial total), sem φ ainda
    ch4_emitido_aterro_bruto = ch4_total_aterro * kernel_ch4.sum()
    # Aplicação do fator φ (UNFCCC 2024) – apenas sobre o CH₄ do baseline
    ch4_emitido_aterro_periodo = ch4_emitido_aterro_bruto * phi
    
    # Fração total emitida no período (antes do φ)
    fracao_ch4_emitida = kernel_ch4.sum()
    
    # =============================================================================
    # 2. CÁLCULO DO N₂O DO ATERRO (perfil de 5 dias - normalizado)
    # =============================================================================
    
    # Cálculo das emissões diárias de N₂O no aterro
    f_aberto = (massa_exposta_kg / residuo_kg) * (h_exposta / 24)
    f_aberto = np.clip(f_aberto, 0.0, 1.0)
    
    E_aberto = 1.91  # g N₂O-N/ton
    E_fechado = 2.15  # g N₂O-N/ton
    E_medio = f_aberto * E_aberto + (1 - f_aberto) * E_fechado
    
    fator_umid = (1 - umidade) / (1 - 0.55)
    E_medio_ajust = E_medio * fator_umid
    
    # Emissão total de N₂O do aterro (kg) – sem φ, pois φ é só para CH₄
    n2o_total_aterro = (E_medio_ajust * (44/28) / 1_000_000) * residuo_kg
    
    # Perfil temporal de N₂O (5 dias - Wang et al. 2017) - NORMALIZADO
    kernel_n2o = np.array([0.10, 0.30, 0.40, 0.15, 0.05], dtype=float)
    kernel_n2o = kernel_n2o / kernel_n2o.sum()  # Normalizar
    
    # N₂O emitido no período (como ocorre no início, consideramos todo)
    n2o_emitido_aterro_periodo = n2o_total_aterro
    
    # =============================================================================
    # 3. CÁLCULO DAS EMISSÕES DA COMPOSTAGEM COM MINHOCAS (50 dias)
    # =============================================================================
    
    # CH₄ total da compostagem (ocorre em ~50 dias)
    ch4_total_compostagem = residuo_kg * (TOC_YANG * CH4_C_FRAC_YANG * (16/12) * fracao_ms)
    
    # N₂O total da compostagem (ocorre em ~50 dias)
    n2o_total_compostagem = residuo_kg * (TN_YANG * N2O_N_FRAC_YANG * (44/28) * fracao_ms)
    
    # Considerando que as emissões ocorrem no primeiro ano
    ch4_emitido_compostagem_periodo = ch4_total_compostagem
    n2o_emitido_compostagem_periodo = n2o_total_compostagem
    
    # =============================================================================
    # 4. CONVERSÃO PARA CO₂eq (GWP 20 anos)
    # =============================================================================
    
    # Emissões do aterro em CO₂eq no período (CH₄ já com φ)
    emissao_aterro_kgco2eq = (
        ch4_emitido_aterro_periodo * GWP_CH4_20 + 
        n2o_emitido_aterro_periodo * GWP_N2O_20
    )
    
    # Emissões da compostagem em CO₂eq
    emissao_compostagem_kgco2eq = (
        ch4_emitido_compostagem_periodo * GWP_CH4_20 + 
        n2o_emitido_compostagem_periodo * GWP_N2O_20
    )
    
    # =============================================================================
    # 5. EMISSÕES EVITADAS NO PERÍODO
    # =============================================================================
    
    emissões_evitadas_tco2eq = (emissao_aterro_kgco2eq - emissao_compostagem_kgco2eq) / 1000
    
    return {
        'residuo_kg': residuo_kg,
        'ch4_total_aterro': ch4_total_aterro,
        'ch4_emitido_aterro_bruto': ch4_emitido_aterro_bruto,  # sem φ
        'ch4_emitido_aterro_periodo': ch4_emitido_aterro_periodo,  # com φ
        'n2o_total_aterro': n2o_total_aterro,
        'n2o_emitido_aterro_periodo': n2o_emitido_aterro_periodo,
        'ch4_total_compostagem': ch4_total_compostagem,
        'n2o_total_compostagem': n2o_total_compostagem,
        'ch4_emitido_compostagem_periodo': ch4_emitido_compostagem_periodo,
        'n2o_emitido_compostagem_periodo': n2o_emitido_compostagem_periodo,
        'emissao_aterro_kgco2eq': emissao_aterro_kgco2eq,
        'emissao_compostagem_kgco2eq': emissao_compostagem_kgco2eq,
        'emissoes_evitadas_tco2eq': emissões_evitadas_tco2eq,
        'parametros': {
            'capacidade_litros': capacidade_litros,
            'densidade_kg_l': DENSIDADE_PADRAO,
            'periodo_anos': periodo_anos,
            'k_ano': k_ano_atual,
            'fracao_ch4_emitida': fracao_ch4_emitida,
            'phi': phi,
            'T': T,
            'DOC': DOC,
            'DOCf': DOCf,
            'TOC_YANG': TOC_YANG,
            'TN_YANG': TN_YANG,
            'CH4_C_FRAC_YANG': CH4_C_FRAC_YANG,
            'N2O_N_FRAC_YANG': N2O_N_FRAC_YANG,
            'umidade': umidade,
            'GWP_CH4_20': GWP_CH4_20,
            'GWP_N2O_20': GWP_N2O_20,
            'massa_exposta_kg': massa_exposta_kg,
            'h_exposta': h_exposta,
            'f_aberto': f_aberto,
            'E_medio': E_medio,
            'E_medio_ajust': E_medio_ajust,
            'fator_umid': fator_umid
        }
    }

def calcular_emissoes_evitadas_reator(capacidade_litros):
    """Versão simplificada para uso geral"""
    resultado = calcular_emissoes_evitadas_reator_detalhado(capacidade_litros)
    return resultado['residuo_kg'], resultado['emissoes_evitadas_tco2eq']

def processar_reatores_cheios(df_reatores, df_escolas):
    """Processa os reatores cheios e calcula emissões evitadas"""
    reatores_cheios = df_reatores[df_reatores['data_encheu'].notna()].copy()
    
    if reatores_cheios.empty:
        return pd.DataFrame(), 0, 0, []
    
    resultados = []
    total_residuo = 0
    total_emissoes_evitadas = 0
    detalhes_calculo = []
    
    for _, reator in reatores_cheios.iterrows():
        capacidade = reator['capacidade_litros'] if pd.notna(reator['capacidade_litros']) else 100
        resultado_detalhado = calcular_emissoes_evitadas_reator_detalhado(
            capacidade, 
            st.session_state.periodo_credito
        )
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
        df_resultados = df_resultados.merge(
            df_escolas[['id_escola', 'nome_escola']], 
            on='id_escola', 
            how='left'
        )
    
    return df_resultados, total_residuo, total_emissoes_evitadas, detalhes_calculo

# =============================================================================
# ANÁLISE DE ESCOLAS ATIVAS COM REATORES ATIVOS
# =============================================================================

def analisar_escolas_ativas_com_reatores_ativos(df_escolas, df_reatores):
    """Analisa escolas ativas que possuem reatores ativos"""
    
    if 'status' in df_escolas.columns:
        escolas_ativas = df_escolas[df_escolas['status'] == 'Ativo'].copy()
    else:
        escolas_ativas = df_escolas.copy()
    
    if 'status_reator' in df_reatores.columns:
        reatores_ativos = df_reatores[df_reatores['status_reator'].notna()].copy()
    else:
        reatores_ativos = pd.DataFrame()
    
    if not reatores_ativos.empty and 'id_escola' in reatores_ativos.columns:
        contagem_reatores_por_escola = reatores_ativos.groupby('id_escola').size().reset_index(name='reatores_ativos')
        
        escolas_com_reatores_ativos = escolas_ativas.merge(
            contagem_reatores_por_escola, 
            on='id_escola', 
            how='left'
        )
        
        escolas_com_reatores_ativos['reatores_ativos'] = escolas_com_reatores_ativos['reatores_ativos'].fillna(0)
        
        return escolas_com_reatores_ativos
    else:
        escolas_ativas['reatores_ativos'] = 0
        return escolas_ativas

# =============================================================================
# ANÁLISE DE GASTOS
# =============================================================================

def analisar_gastos(df_gastos):
    """Analisa os gastos registrados"""
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

# Inicializar session state
inicializar_session_state()

# Carregar dados REAIS
df_escolas, df_reatores, df_gastos = carregar_dados_excel(URL_EXCEL)

if df_escolas.empty or df_reatores.empty:
    st.error("❌ Não foi possível carregar os dados. Verifique se o arquivo Excel existe no repositório GitHub.")
    st.stop()

# Sidebar com controles adicionais
exibir_cotacao_carbono()

with st.sidebar:
    st.header("⚙️ Parâmetros de Cálculo")
    
    # Controle para período de crédito
    periodo_credito = st.slider(
        "Período de crédito (anos)", 
        1, 30, st.session_state.periodo_credito, 1,
        help="Período em anos para o qual as emissões são calculadas"
    )
    st.session_state.periodo_credito = periodo_credito
    
    # Controle para taxa de decaimento
    k_ano = st.slider(
        "Taxa de decaimento (k) [ano⁻¹]", 
        0.01, 0.50, st.session_state.k_ano, 0.01,
        help="Taxa de decaimento anual do metano no aterro (IPCC: 0.06 para resíduos alimentares)"
    )
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

# =============================================================================
# PROCESSAMENTO DOS CÁLCULOS
# =============================================================================

if escola_selecionada != "Todas as escolas":
    reatores_filtrados = df_reatores[df_reatores['id_escola'] == escola_selecionada]
    escolas_filtradas = df_escolas[df_escolas['id_escola'] == escola_selecionada]
else:
    reatores_filtrados = df_reatores
    escolas_filtradas = df_escolas

reatores_processados, total_residuo, total_emissoes, detalhes_calculo = processar_reatores_cheios(
    reatores_filtrados, escolas_filtradas
)

preco_carbono_eur = st.session_state.preco_carbono
taxa_cambio = st.session_state.taxa_cambio

valor_eur = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "€")
valor_brl = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "R$", taxa_cambio)

df_gastos_analisados, total_gastos = analisar_gastos(df_gastos)

# =============================================================================
# EXIBIÇÃO DOS DADOS REAIS
# =============================================================================

st.info(f"""
**⚙️ Parâmetros de Cálculo CORRIGIDOS - DISTRIBUIÇÃO TEMPORAL COM φ:**
- **Densidade do resíduo:** {DENSIDADE_PADRAO} kg/L
- **Período de cálculo:** {periodo_credito} anos
- **Taxa de decaimento (k):** {formatar_br(k_ano, 3)} ano⁻¹ (IPCC para resíduos alimentares)
- **GWP:** 20 anos (CH₄=79.7, N₂O=273)
- ***Fator φ (UNFCCC 2024):** {PHI_BASELINE}* (aplicado apenas ao CH₄ do aterro)
- **Metodologia:** Kernel NÃO normalizado para aterro × φ vs Compostagem (50 dias)
- **Base científica:** Valores médios da literatura para resíduos orgânicos de cozinha escolar
""")

# Métricas gerais
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_escolas = len(df_escolas)
    st.metric("Total de Escolas", formatar_br(total_escolas, 0))

with col2:
    total_reatores = len(df_reatores)
    st.metric("Total de Reatores", formatar_br(total_reatores, 0))

with col3:
    reatores_cheios = len(df_reatores[df_reatores['data_encheu'].notna()])
    st.metric("Reatores Cheios", formatar_br(reatores_cheios, 0))

with col4:
    reatores_ativos = len(df_reatores[df_reatores['status_reator'].notna()])
    st.metric("Reatores Ativos", formatar_br(reatores_ativos, 0))

# =============================================================================
# RESULTADOS FINANCEIROS REAIS
# =============================================================================

st.header("💰 Créditos de Carbono Computados - Sistema Real")

if reatores_processados.empty:
    st.info("ℹ️ Nenhum reator cheio encontrado. Os créditos serão calculados quando os reatores encherem.")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Reatores Processados", formatar_br(0, 0))
    
    with col2:
        st.metric("Resíduo Processado", f"{formatar_br(0, 1)} kg")
    
    with col3:
        st.metric("Emissões Evitadas", formatar_tco2eq(0))
    
    with col4:
        st.metric("Valor dos Créditos", formatar_moeda_br(0))
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

# =============================================================================
# ANÁLISE DE GASTOS
# =============================================================================

st.header("💰 Análise de Gastos")

if not df_gastos.empty:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_gastos_br = formatar_moeda_br(total_gastos, "R$", 2)
        st.metric("Total de Gastos", total_gastos_br)
    
    with col2:
        total_itens = len(df_gastos)
        st.metric("Total de Itens", formatar_br(total_itens, 0))
    
    with col3:
        if total_gastos > 0 and total_emissoes > 0:
            custo_por_tonelada = total_gastos / total_emissoes
            st.metric("Custo por tCO₂eq", formatar_moeda_br(custo_por_tonelada, "R$", 2))
        else:
            st.metric("Custo por tCO₂eq", formatar_moeda_br(0, "R$", 2))
    
    st.subheader("📋 Detalhamento dos Gastos")
    
    df_gastos_display = df_gastos[['id_gasto', 'nome_gasto', 'data_compra', 'valor']].copy()
    
    if 'data_compra' in df_gastos_display.columns:
        df_gastos_display['data_compra'] = pd.to_datetime(df_gastos_display['data_compra'], errors='coerce')
        df_gastos_display = df_gastos_display.sort_values('data_compra', ascending=True)
        df_gastos_display['data_compra'] = df_gastos_display['data_compra'].dt.strftime('%d/%m/%Y')
    
    if 'valor' in df_gastos_display.columns:
        df_gastos_display['valor_formatado'] = df_gastos_display['valor'].astype(str).apply(
            lambda x: formatar_moeda_br(float(x.replace('R$', '').replace(',', '.').strip()), "R$", 2) 
            if pd.notna(x) and x != '' else formatar_moeda_br(0, "R$", 2)
        )
        df_gastos_display['valor'] = df_gastos_display['valor_formatado']
        df_gastos_display = df_gastos_display.drop('valor_formatado', axis=1)
    
    st.dataframe(df_gastos_display, use_container_width=True)
else:
    st.info("ℹ️ Nenhum gasto registrado no sistema.")

# =============================================================================
# ANÁLISE DE ESCOLAS ATIVAS COM REATORES ATIVOS
# =============================================================================

st.header("🏫 Análise de Escolas Ativas com Reatores Ativos")

escolas_com_reatores_ativos = analisar_escolas_ativas_com_reatores_ativos(df_escolas, df_reatores)

col1, col2, col3 = st.columns(3)

with col1:
    total_escolas_ativas = len(escolas_com_reatores_ativos)
    st.metric("Escolas Ativas", formatar_br(total_escolas_ativas, 0))

with col2:
    escolas_com_reatores = len(escolas_com_reatores_ativos[escolas_com_reatores_ativos['reatores_ativos'] > 0])
    st.metric("Escolas com Reatores Ativos", formatar_br(escolas_com_reatores, 0))

with col3:
    total_reatores_ativos_analise = escolas_com_reatores_ativos['reatores_ativos'].sum()
    st.metric("Total de Reatores Ativos (Análise)", formatar_br(total_reatores_ativos_analise, 0))

st.subheader("📋 Detalhamento por Escola")

colunas_display = ['id_escola', 'nome_escola', 'reatores_ativos']
if 'status' in escolas_com_reatores_ativos.columns:
    colunas_display.insert(2, 'status')
if 'data_implantacao' in escolas_com_reatores_ativos.columns:
    colunas_display.append('data_implantacao')

df_display = escolas_com_reatores_ativos[colunas_display].copy()

if 'data_implantacao' in df_display.columns:
    df_display['data_implantacao'] = pd.to_datetime(df_display['data_implantacao'], errors='coerce').dt.strftime('%d/%m/%Y')

if 'reatores_ativos' in df_display.columns:
    df_display['reatores_ativos'] = df_display['reatores_ativos'].apply(lambda x: formatar_br(x, 0) if pd.notna(x) else "0")

df_display = df_display.sort_values('reatores_ativos', ascending=False)

st.dataframe(df_display, use_container_width=True)

st.subheader("📈 Estatísticas da Implantação")

if not escolas_com_reatores_ativos.empty:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        percentual_com_reatores = (escolas_com_reatores / total_escolas_ativas) * 100
        st.metric("Taxa de Sucesso", f"{formatar_br(percentual_com_reatores, 1)}%")
    
    with col2:
        media_reatores_por_escola = total_reatores_ativos_analise / max(escolas_com_reatores, 1)
        st.metric("Média de Reatores/Escola", formatar_br(media_reatores_por_escola, 1))
    
    with col3:
        escolas_sem_reatores = total_escolas_ativas - escolas_com_reatores
        st.metric("Escolas sem Reatores Ativos", formatar_br(escolas_sem_reatores, 0))

# =============================================================================
# DETALHAMENTO DOS CRÉDITOS
# =============================================================================

if not reatores_processados.empty:
    st.header("📊 Detalhamento dos Créditos por Reator")
    
    preco_carbono_reais_por_tonelada = st.session_state.preco_carbono * st.session_state.taxa_cambio
    
    df_detalhes = reatores_processados[[
        'nome_escola', 'id_reator', 'data_encheu', 'altura_cm', 'largura_cm', 'comprimento_cm',
        'capacidade_litros', 'residuo_kg', 'emissoes_evitadas_tco2eq'
    ]].copy()
    
    df_detalhes['valor_creditos_reais'] = df_detalhes['emissoes_evitadas_tco2eq'] * preco_carbono_reais_por_tonelada
    
    df_detalhes['residuo_kg'] = df_detalhes['residuo_kg'].apply(lambda x: formatar_br(x, 1))
    df_detalhes['emissoes_evitadas_tco2eq'] = df_detalhes['emissoes_evitadas_tco2eq'].apply(lambda x: formatar_tco2eq(x))
    df_detalhes['capacidade_litros'] = df_detalhes['capacidade_litros'].apply(lambda x: formatar_br(x, 0))
    df_detalhes['data_encheu'] = pd.to_datetime(df_detalhes['data_encheu']).dt.strftime('%d/%m/%Y')
    
    df_detalhes['valor_creditos_reais'] = df_detalhes['valor_creditos_reais'].apply(
        lambda x: formatar_moeda_br(x, "R$", 2)
    )
    
    for col in ['altura_cm', 'largura_cm', 'comprimento_cm']:
        if col in df_detalhes.columns:
            df_detalhes[col] = df_detalhes[col].apply(lambda x: formatar_br(x, 0) if pd.notna(x) else "N/A")
    
    st.dataframe(df_detalhes, use_container_width=True)

# =============================================================================
# DETALHAMENTO COMPLETO DOS CÁLCULOS (COM FATOR φ)
# =============================================================================

if not reatores_processados.empty:
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
        st.write(f"- Capacidade calculada: {formatar_br(calc['parametros']['capacidade_litros'], 0)} L")
        st.write(f"- Densidade do resíduo: {formatar_br(calc['parametros']['densidade_kg_l'], 2)} kg/L")
        st.write(f"- Massa de resíduos estimada: {formatar_br(calc['residuo_kg'], 1)} kg")
        
        st.write("**Distribuição Temporal (Aterro):**")
        st.write(f"- Fração CH₄ emitida ({periodo_credito} anos): {formatar_br(calc['parametros']['fracao_ch4_emitida'] * 100, 1)}%")
        st.write(f"- CH₄ total aterro (sem φ): {formatar_br(calc['ch4_total_aterro'], 3)} kg")
        st.write(f"- CH₄ emitido bruto (sem φ): {formatar_br(calc['ch4_emitido_aterro_bruto'], 3)} kg")
        st.write(f"- CH₄ emitido (com φ = {PHI_BASELINE}): {formatar_br(calc['ch4_emitido_aterro_periodo'], 3)} kg")
        st.write(f"- N₂O emitido aterro: {formatar_br(calc['n2o_emitido_aterro_periodo'], 6)} kg")
    
    with col2:
        st.write("**Resultados Aterro (período, c/ φ):**")
        st.write(f"- CH₄ Aterro (c/ φ): {formatar_br(calc['ch4_emitido_aterro_periodo'], 3)} kg")
        st.write(f"- N₂O Aterro: {formatar_br(calc['n2o_emitido_aterro_periodo'], 6)} kg")
        st.write(f"- CO₂eq Aterro: {formatar_br(calc['emissao_aterro_kgco2eq'], 1)} kg")
        
        st.write("**Resultados Compostagem (primeiro ano):**")
        st.write(f"- CH₄ Compostagem: {formatar_br(calc['ch4_emitido_compostagem_periodo'], 5)} kg")
        st.write(f"- N₂O Compostagem: {formatar_br(calc['n2o_emitido_compostagem_periodo'], 5)} kg")
        st.write(f"- CO₂eq Compostagem: {formatar_br(calc['emissao_compostagem_kgco2eq'], 3)} kg")
        
        st.metric(
            "Emissões Evitadas", 
            formatar_tco2eq(calc['emissoes_evitadas_tco2eq']),
            f"Período: {periodo_credito} anos"
        )

    # Fórmulas matemáticas atualizadas (incluindo φ)
    with st.expander("📝 Ver Fórmulas Matemáticas Completas (COM FATOR φ)"):
        k_ano_atual = st.session_state.k_ano
        st.markdown(f"""
        **🧮 Fórmulas Utilizadas no Cálculo CORRIGIDO (φ = {PHI_BASELINE}):**

        **1. Cálculo da Capacidade (Litros):**
