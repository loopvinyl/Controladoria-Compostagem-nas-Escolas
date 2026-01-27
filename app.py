import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import numpy as np
from io import BytesIO
import math

# =============================================================================
# CONFIGURAÇÕES INICIAIS - IDÊNTICO
# =============================================================================

st.set_page_config(
    page_title="Compostagem com Minhocas, Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Compostagem com Minhocas nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo científico de emissões para resíduos orgânicos**")

# =============================================================================
# CONFIGURAÇÕES FIXAS - MODIFICADO: Usar session state para K_ANO
# =============================================================================

URL_EXCEL = "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem_real.xlsx"
DENSIDADE_PADRAO = 0.6  # kg/L - para resíduos de vegetais, frutas e borra de café
K_ANO_PADRAO = 0.06  # Taxa de decaimento anual padrão (IPCC para resíduos alimentares)

# =============================================================================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA - IDÊNTICO
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
# FUNÇÕES DE COTAÇÃO DO CARBONO - IDÊNTICO
# =============================================================================

def obter_cotacao_carbono_investing():
    try:
        url = "https://www.investing.com/commodities/carbon-emissions"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://www.investing.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        selectores = [
            '[data-test="instrument-price-last"]',
            '.text-2xl',
            '.last-price-value',
            '.instrument-price-last',
            '.pid-1062510-last',
            '.float_lang_base_1',
            '.top.bold.inlineblock',
            '#last_last'
        ]
        
        preco = None
        fonte = "Investing.com"
        
        for seletor in selectores:
            try:
                elemento = soup.select_one(seletor)
                if elemento:
                    texto_preco = elemento.text.strip().replace(',', '')
                    texto_preco = ''.join(c for c in texto_preco if c.isdigit() or c == '.')
                    if texto_preco:
                        preco = float(texto_preco)
                        break
            except (ValueError, AttributeError):
                continue
        
        if preco is not None:
            return preco, "€", "Carbon Emissions Future", True, fonte
        
        import re
        padroes_preco = [
            r'"last":"([\d,]+)"',
            r'data-last="([\d,]+)"',
            r'last_price["\']?:\s*["\']?([\d,]+)',
            r'value["\']?:\s*["\']?([\d,]+)'
        ]
        
        html_texto = str(soup)
        for padrao in padroes_preco:
            matches = re.findall(padrao, html_texto)
            for match in matches:
                try:
                    preco_texto = match.replace(',', '')
                    preco = float(preco_texto)
                    if 50 < preco < 200:
                        return preco, "€", "Carbon Emissions Future", True, fonte
                except ValueError:
                    continue
                    
        return None, None, None, False, fonte
        
    except Exception as e:
        return None, None, None, False, f"Investing.com - Erro: {str(e)}"

def obter_cotacao_carbono():
    preco, moeda, contrato_info, sucesso, fonte = obter_cotacao_carbono_investing()
    
    if sucesso:
        return preco, moeda, f"{contrato_info}", True, fonte
    
    return 85.50, "€", "Carbon Emissions (Referência)", False, "Referência"

def obter_cotacao_euro_real():
    try:
        url = "https://economia.awesomeapi.com.br/last/EUR-BRL"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            cotacao = float(data['EURBRL']['bid'])
            return cotacao, "R$", True, "AwesomeAPI"
    except:
        pass
    
    try:
        url = "https://api.exchangerate-api.com/v4/latest/EUR"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            cotacao = data['rates']['BRL']
            return cotacao, "R$", True, "ExchangeRate-API"
    except:
        pass
    
    return 5.50, "R$", False, "Referência"

def calcular_valor_creditos(emissoes_evitadas_tco2eq, preco_carbono_por_tonelada, moeda, taxa_cambio=1):
    valor_total = emissoes_evitadas_tco2eq * preco_carbono_por_tonelada * taxa_cambio
    return valor_total

def exibir_cotacao_carbono():
    st.sidebar.header("💰 Mercado de Carbono")
    
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
        
        preco_carbono, moeda, contrato_info, sucesso_carbono, fonte_carbono = obter_cotacao_carbono()
        preco_euro, moeda_real, sucesso_euro, fonte_euro = obter_cotacao_euro_real()
        
        st.session_state.preco_carbono = preco_carbono
        st.session_state.moeda_carbono = moeda
        st.session_state.taxa_cambio = preco_euro
        st.session_state.moeda_real = moeda_real
        st.session_state.fonte_cotacao = fonte_carbono
        
        st.session_state.mostrar_atualizacao = False
        st.session_state.cotacao_atualizada = False
        
        st.rerun()

    preco_carbono_formatado = formatar_br(st.session_state.preco_carbono, 2)
    taxa_cambio_formatada = formatar_br(st.session_state.taxa_cambio, 2)
    preco_carbono_reais = st.session_state.preco_carbono * st.session_state.taxa_cambio
    preco_carbono_reais_formatado = formatar_br(preco_carbono_reais, 2)

    st.sidebar.metric(
        label=f"Preço do Carbono (tCO₂eq)",
        value=f"{st.session_state.moeda_carbono} {preco_carbono_formatado}",
        help=f"Fonte: {st.session_state.fonte_cotacao}"
    )
    
    st.sidebar.metric(
        label="Euro (EUR/BRL)",
        value=f"{st.session_state.moeda_real} {taxa_cambio_formatada}",
        help="Cotação do Euro em Reais Brasileiros"
    )
    
    st.sidebar.metric(
        label=f"Carbono em Reais (tCO₂eq)",
        value=f"R$ {preco_carbono_reais_formatado}",
        help="Preço do carbono convertido para Reais Brasileiros"
    )

# =============================================================================
# INICIALIZAÇÃO DA SESSION STATE - MODIFICADO: Removida declaração global
# =============================================================================

def inicializar_session_state():
    """Inicializa todas as variáveis de session state necessárias"""
    if 'preco_carbono' not in st.session_state:
        preco_carbono, moeda, contrato_info, sucesso, fonte = obter_cotacao_carbono()
        st.session_state.preco_carbono = preco_carbono
        st.session_state.moeda_carbono = moeda
        st.session_state.fonte_cotacao = fonte
        
    if 'taxa_cambio' not in st.session_state:
        preco_euro, moeda_real, sucesso_euro, fonte_euro = obter_cotacao_euro_real()
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
# FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO DOS DADOS REAIS - IDÊNTICO
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
        # CÁLCULO DA CAPACIDADE APENAS A PARTIR DAS DIMENSÕES - IDÊNTICO
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
# FUNÇÕES DE CÁLCULO CIENTÍFICO - MODIFICADO: Incluir E_medio_ajust
# =============================================================================

def calcular_emissoes_evitadas_reator_detalhado(capacidade_litros, periodo_anos=10):
    """
    Calcula emissões evitadas baseado no modelo científico CORRIGIDO
    COM DISTRIBUIÇÃO TEMPORAL ADEQUADA:
    - Aterro: emissões ao longo de N anos (kernel não normalizado)
    - Compostagem: emissões em 50 dias
    - Usando GWP-20: CH₄=79.7, N₂O=273
    """
    
    # Massa de resíduos processada - DENSIDADE FIXA
    residuo_kg = capacidade_litros * DENSIDADE_PADRAO
    
    # =============================================================================
    # PARÂMETROS FIXOS - IGUAL SCRIPT INSPIRAÇÃO
    # =============================================================================
    
    # Parâmetros para aterro (CH₄)
    T = 25  # Temperatura (°C)
    DOC = 0.15  # Carbono orgânico degradável
    DOCf = 0.0147 * T + 0.28  # Calculado da temperatura
    MCF = 1.0  # Fator de correção de metano (para aterros sanitários)
    F = 0.5  # Fração de metano no biogás
    OX = 0.1  # Fator de oxidação
    Ri = 0.0  # Metano recuperado
    
    # Parâmetros para compostagem com minhocas (Yang et al. 2017)
    TOC_YANG = 0.436  # Fração de carbono orgânico total
    TN_YANG = 14.2 / 1000  # Fração de nitrogênio total
    CH4_C_FRAC_YANG = 0.13 / 100  # 0.13%
    N2O_N_FRAC_YANG = 0.92 / 100  # 0.92%
    
    umidade = 0.85  # 85% umidade
    fracao_ms = 1 - umidade  # Fração de matéria seca
    
    # Parâmetros para N₂O do aterro (Zziwa et al. adaptado)
    massa_exposta_kg = min(residuo_kg, 50)
    h_exposta = 8  # horas
    
    # GWP 20 anos (IGUAL SCRIPT INSPIRAÇÃO)
    GWP_CH4_20 = 79.7  # IPCC AR6 - 20 anos
    GWP_N2O_20 = 273   # IPCC AR6 - 20 anos
    
    # =============================================================================
    # 1. CÁLCULO DO CH₄ DO ATERRO - COM DISTRIBUIÇÃO TEMPORAL
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
    
    # CH₄ emitido no período (soma do kernel * potencial total)
    ch4_emitido_aterro_periodo = ch4_total_aterro * kernel_ch4.sum()
    
    # Fração total emitida no período
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
    E_medio_ajust = E_medio * fator_umid  # ADICIONADO: cálculo de E_medio_ajust
    
    # Emissão total de N₂O do aterro (kg)
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
    
    # Emissões do aterro em CO₂eq no período
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
        'ch4_emitido_aterro_periodo': ch4_emitido_aterro_periodo,
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
            'E_medio_ajust': E_medio_ajust,  # ADICIONADO: Esta é a chave que estava faltando
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
# ANÁLISE DE ESCOLAS ATIVAS COM REATORES ATIVOS - IDÊNTICO
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
# ANÁLISE DE GASTOS - IDÊNTICO
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
# INTERFACE PRINCIPAL - MODIFICADO: Removida declaração global
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
    """)
    
    st.header("🔍 Filtros")
    escolas_options = ["Todas as escolas"] + df_escolas['id_escola'].tolist()
    escola_selecionada = st.selectbox("Selecionar escola", escolas_options)

# =============================================================================
# PROCESSAMENTO DOS CÁLCULOS - IDÊNTICO
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
# EXIBIÇÃO DOS DADOS REAIS - MODIFICADO: Adicionado informação temporal
# =============================================================================

# Informação sobre parâmetros de cálculo
st.info(f"""
**⚙️ Parâmetros de Cálculo CORRIGIDOS - DISTRIBUIÇÃO TEMPORAL:**
- **Densidade do resíduo:** {DENSIDADE_PADRAO} kg/L
- **Período de cálculo:** {periodo_credito} anos
- **Taxa de decaimento (k):** {formatar_br(k_ano, 3)} ano⁻¹ (IPCC para resíduos alimentares)
- **GWP:** 20 anos (CH₄=79.7, N₂O=273)
- **Metodologia:** Kernel NÃO normalizado para aterro (correto IPCC) vs Compostagem (50 dias)
- **Base científica:** Valores médios da literatura para resíduos orgânicos de cozinha escolar
""")

# Métricas gerais - IDÊNTICO
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
# RESULTADOS FINANCEIROS REAIS - IDÊNTICO
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
# ANÁLISE DE GASTOS - IDÊNTICO
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
# ANÁLISE DE ESCOLAS ATIVAS COM REATORES ATIVOS - IDÊNTICO
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
# DETALHAMENTO COMPLETO DOS CÁLCULOS - MODIFICADO: Inclui distribuição temporal
# =============================================================================

if not reatores_processados.empty:
    st.header("🧮 Detalhamento Completo dos Cálculos")
    
    primeiro_reator = detalhes_calculo[0]
    calc = primeiro_reator['calculo_detalhado']
    
    st.subheader(f"📋 Cálculo Detalhado para o Reator {primeiro_reator['id_reator']}")
    st.info(f"**Período de cálculo:** {periodo_credito} anos | **Taxa de decaimento (k):** {formatar_br(k_ano, 3)} ano⁻¹")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Dimensões e Massa:**")
        st.write(f"- Altura: {formatar_br(primeiro_reator.get('altura_cm', 'N/A'), 0)} cm")
        st.write(f"- Largura: {formatar_br(primeiro_reator.get('largura_cm', 'N/A'), 0)} cm")
        st.write(f"- Comprimento: {formatar_br(primeiro_reator.get('comprimento_cm', 'N/A'), 0)} cm")
        st.write(f"- Capacidade calculada: {formatar_br(calc['parametros']['capacidade_litros'], 0)} L")
        st.write(f"- Densidade do resíduo: {formatar_br(calc['parametros']['densidade_kg_l'], 2)} kg/L")
        st.write(f"- Massa de resíduos estimada: {formatar_br(calc['residuo_kg'], 1)} kg")
        
        st.write("**Distribuição Temporal:**")
        st.write(f"- Fração CH₄ emitida ({periodo_credito} anos): {formatar_br(calc['parametros']['fracao_ch4_emitida'] * 100, 1)}%")
        st.write(f"- CH₄ total aterro: {formatar_br(calc['ch4_total_aterro'], 3)} kg")
        st.write(f"- CH₄ emitido (período): {formatar_br(calc['ch4_emitido_aterro_periodo'], 3)} kg")
        st.write(f"- N₂O emitido aterro: {formatar_br(calc['n2o_emitido_aterro_periodo'], 6)} kg")
    
    with col2:
        st.write("**Resultados Aterro (período):**")
        st.write(f"- CH₄ Aterro: {formatar_br(calc['ch4_emitido_aterro_periodo'], 3)} kg")
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

    # Fórmulas matemáticas atualizadas
    with st.expander("📝 Ver Fórmulas Matemáticas Completas (CORRIGIDAS)"):
        k_ano_atual = st.session_state.k_ano
        st.markdown(f"""
        **🧮 Fórmulas Utilizadas no Cálculo CORRIGIDO:**

        **1. Cálculo da Capacidade (Litros):**
        ```
        Capacidade (L) = Altura (cm) × Largura (cm) × Comprimento (cm) ÷ 1000
        Capacidade = {formatar_br(primeiro_reator.get('altura_cm', 0), 0)} × {formatar_br(primeiro_reator.get('largura_cm', 0), 0)} × {formatar_br(primeiro_reator.get('comprimento_cm', 0), 0)} ÷ 1000
        Capacidade = {formatar_br(calc['parametros']['capacidade_litros'], 0)} L
        ```

        **2. Massa de Resíduos:**
        ```
        Resíduo (kg) = Capacidade (L) × Densidade (kg/L)
        Resíduo = {formatar_br(calc['parametros']['capacidade_litros'], 0)} × {formatar_br(calc['parametros']['densidade_kg_l'], 2)} = {formatar_br(calc['residuo_kg'], 1)} kg
        ```

        **3. CH₄ Aterro (Potencial Total - 100 anos):**
        ```
        CH₄ Total Aterro = Resíduo × DOC × DOCf × MCF × F × (16/12) × (1-Ri) × (1-OX)
        CH₄ Total Aterro = {formatar_br(calc['residuo_kg'], 1)} × {formatar_br(calc['parametros']['DOC'], 3)} × {formatar_br(calc['parametros']['DOCf'], 3)} × 1 × 0,5 × 1,333 × 1 × 0,9
        CH₄ Total Aterro = {formatar_br(calc['ch4_total_aterro'], 3)} kg
        ```

        **4. CH₄ Aterro Emitido (Período {periodo_credito} anos):**
        ```
        k_dia = k_ano / 365 = {formatar_br(k_ano_atual, 3)} / 365 = {formatar_br(k_ano_atual/365, 6)} dia⁻¹
        Fração emitida = 1 - exp(-k_ano × T) = 1 - exp(-{formatar_br(k_ano_atual, 3)} × {periodo_credito})
        Fração emitida = {formatar_br(calc['parametros']['fracao_ch4_emitida'] * 100, 1)}%
        
        CH₄ Emitido = CH₄ Total × Fração emitida
        CH₄ Emitido = {formatar_br(calc['ch4_total_aterro'], 3)} × {formatar_br(calc['parametros']['fracao_ch4_emitida'], 3)}
        CH₄ Emitido = {formatar_br(calc['ch4_emitido_aterro_periodo'], 3)} kg
        ```

        **5. N₂O Aterro (período 5 dias):**
        ```
        f_aberto = (massa_exposta / resíduo) × (horas_expostas / 24)
        f_aberto = ({formatar_br(calc['parametros']['massa_exposta_kg'], 0)} / {formatar_br(calc['residuo_kg'], 1)}) × ({formatar_br(calc['parametros']['h_exposta'], 0)} / 24)
        f_aberto = {formatar_br(calc['parametros']['f_aberto'], 3)}
        
        E_medio = f_aberto × E_aberto + (1 - f_aberto) × E_fechado
        E_medio = {formatar_br(calc['parametros']['f_aberto'], 3)} × 1,91 + (1 - {formatar_br(calc['parametros']['f_aberto'], 3)}) × 2,15
        E_medio = {formatar_br(calc['parametros']['E_medio'], 3)}
        
        fator_umid = (1 - umidade) / (1 - 0,55)
        fator_umid = (1 - {formatar_br(calc['parametros']['umidade'], 2)}) / (1 - 0,55)
        fator_umid = {formatar_br(calc['parametros']['fator_umid'], 3)}
        
        E_medio_ajust = E_medio × fator_umid
        E_medio_ajust = {formatar_br(calc['parametros']['E_medio'], 3)} × {formatar_br(calc['parametros']['fator_umid'], 3)}
        E_medio_ajust = {formatar_br(calc['parametros']['E_medio_ajust'], 3)}
        
        N₂O Aterro = Resíduo × E_medio_ajust × (44/28) ÷ 1.000.000
        N₂O Aterro = {formatar_br(calc['residuo_kg'], 1)} × {formatar_br(calc['parametros']['E_medio_ajust'], 3)} × 1,571 ÷ 1.000.000
        N₂O Aterro = {formatar_br(calc['n2o_total_aterro'], 6)} kg
        ```

        **6. CH₄ Compostagem (período 50 dias):**
        ```
        CH₄ Compostagem = Resíduo × TOC × CH₄-C/TOC × (16/12) × (1-umidade)
        CH₄ Compostagem = {formatar_br(calc['residuo_kg'], 1)} × {formatar_br(calc['parametros']['TOC_YANG'], 3)} × {formatar_br(calc['parametros']['CH4_C_FRAC_YANG'], 4)} × 1,333 × {formatar_br(1-calc['parametros']['umidade'], 2)}
        CH₄ Compostagem = {formatar_br(calc['ch4_emitido_compostagem_periodo'], 5)} kg
        ```

        **7. N₂O Compostagem (período 50 dias):**
        ```
        N₂O Compostagem = Resíduo × TN × N₂O-N/TN × (44/28) × (1-umidade)
        N₂O Compostagem = {formatar_br(calc['residuo_kg'], 1)} × {formatar_br(calc['parametros']['TN_YANG'], 4)} × {formatar_br(calc['parametros']['N2O_N_FRAC_YANG'], 4)} × 1,571 × {formatar_br(1-calc['parametros']['umidade'], 2)}
        N₂O Compostagem = {formatar_br(calc['n2o_emitido_compostagem_periodo'], 5)} kg
        ```

        **8. Emissões em CO₂eq (GWP 20 anos):**
        ```
        CO₂eq Aterro = (CH₄ Aterro × {formatar_br(calc['parametros']['GWP_CH4_20'], 0)}) + (N₂O Aterro × {formatar_br(calc['parametros']['GWP_N2O_20'], 0)})
        CO₂eq Aterro = ({formatar_br(calc['ch4_emitido_aterro_periodo'], 3)} × {formatar_br(calc['parametros']['GWP_CH4_20'], 0)}) + ({formatar_br(calc['n2o_emitido_aterro_periodo'], 6)} × {formatar_br(calc['parametros']['GWP_N2O_20'], 0)})
        CO₂eq Aterro = {formatar_br(calc['emissao_aterro_kgco2eq'], 1)} kg CO₂eq

        CO₂eq Compostagem = (CH₄ Compostagem × {formatar_br(calc['parametros']['GWP_CH4_20'], 0)}) + (N₂O Compostagem × {formatar_br(calc['parametros']['GWP_N2O_20'], 0)})
        CO₂eq Compostagem = ({formatar_br(calc['ch4_emitido_compostagem_periodo'], 5)} × {formatar_br(calc['parametros']['GWP_CH4_20'], 0)}) + ({formatar_br(calc['n2o_emitido_compostagem_periodo'], 5)} × {formatar_br(calc['parametros']['GWP_N2O_20'], 0)})
        CO₂eq Compostagem = {formatar_br(calc['emissao_compostagem_kgco2eq'], 3)} kg CO₂eq
        ```

        **9. Emissões Evitadas:**
        ```
        Emissões Evitadas = (CO₂eq Aterro - CO₂eq Compostagem) ÷ 1000
        Emissões Evitadas = ({formatar_br(calc['emissao_aterro_kgco2eq'], 1)} - {formatar_br(calc['emissao_compostagem_kgco2eq'], 3)}) ÷ 1000
        Emissões Evitadas = {formatar_br(calc['emissoes_evitadas_tco2eq'], 3)} tCO₂eq
        ```
        """)

# =============================================================================
# DETALHAMENTO DOS CRÉDITOS - IDÊNTICO (com valor por reator)
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
# GRÁFICOS COM DADOS REAIS - IDÊNTICO
# =============================================================================

st.header("📈 Status dos Reatores")

if 'status_reator' in df_reatores.columns:
    status_count = df_reatores['status_reator'].value_counts()
    
    if not status_count.empty:
        labels_formatados = []
        for status, count in status_count.items():
            labels_formatados.append(f"{status} ({formatar_br(count, 0)})")

        fig = px.pie(
            values=status_count.values,
            names=labels_formatados,
            title="Distribuição dos Status dos Reatores"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ℹ️ Sem dados de status para reatores")
else:
    st.info("ℹ️ Coluna 'status_reator' não encontrada para gerar gráfico")

st.header("🏫 Status das Escolas")

if 'status' in df_escolas.columns:
    status_escolas_count = df_escolas['status'].value_counts()
    
    if not status_escolas_count.empty:
        labels_escolas_formatados = []
        for status, count in status_escolas_count.items():
            labels_escolas_formatados.append(f"{status} ({formatar_br(count, 0)})")

        fig2 = px.pie(
            values=status_escolas_count.values,
            names=labels_escolas_formatados,
            title="Distribuição dos Status das Escolas"
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("ℹ️ Sem dados de status para escolas")
else:
    st.info("ℹ️ Coluna 'status' não encontrada para gerar gráfico")

st.markdown("---")
st.markdown("""
**♻️ Sistema de Compostagem com Minhocas - Ribeirão Preto/SP**  
*Dados carregados de: [Controladoria-Compostagem-nas-Escolas](https://github.com/loopvinyl/Controladoria-Compostagem-nas-Escolas)*

**📚 Referências Científicas:**  
- IPCC (2006). Guidelines for National Greenhouse Gas Inventories  
- Yang et al. (2017). Greenhouse gas emissions during MSW landfilling in China  
- Zziwa et al. (adaptado). Modelo de emissões para resíduos orgânicos  
- GWP 20 anos: CH₄=79.7, N₂O=273 (IPCC AR6)

**✅ Cálculo Corrigido:** Distribuição temporal adequada com kernel não normalizado para aterro
""")
