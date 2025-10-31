import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import numpy as np
from io import BytesIO

# Configuração da página
st.set_page_config(
    page_title="Vermicompostagem - Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Vermicompostagem nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo científico de emissões para resíduos orgânicos**")

# URL do Excel no GitHub (RAW)
URL_EXCEL = "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem.xlsx"

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
# FUNÇÕES DE COTAÇÃO DO CARBONO
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
# INICIALIZAÇÃO DA SESSION STATE
# =============================================================================

def inicializar_session_state():
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

# =============================================================================
# FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO DOS DADOS REAIS
# =============================================================================

@st.cache_data
def carregar_dados_excel(url):
    """Carrega os dados REAIS do Excel do GitHub"""
    try:
        st.info("📥 Carregando dados do Excel...")
        
        # Ler as abas
        df_escolas = pd.read_excel(url, sheet_name='escolas')
        df_reatores = pd.read_excel(url, sheet_name='reatores')
        
        st.success(f"✅ Dados carregados: {len(df_escolas)} escolas e {len(df_reatores)} reatores")
        
        # Converter colunas de data
        colunas_data_escolas = ['data_implantacao', 'ultima_visita']
        for col in colunas_data_escolas:
            if col in df_escolas.columns:
                df_escolas[col] = pd.to_datetime(df_escolas[col], errors='coerce')
                
        colunas_data_reatores = ['data_ativacao', 'data_encheu', 'data_colheita']
        for col in colunas_data_reatores:
            if col in df_reatores.columns:
                df_reatores[col] = pd.to_datetime(df_reatores[col], errors='coerce')
                
        return df_escolas, df_reatores
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados do Excel: {e}")
        st.error("📋 Verifique a estrutura do Excel e tente novamente.")
        return pd.DataFrame(), pd.DataFrame()

# =============================================================================
# FUNÇÕES DE CÁLCULO CIENTÍFICO
# =============================================================================

def calcular_emissoes_evitadas_reator_detalhado(capacidade_litros, densidade_kg_l=0.5):
    """
    Calcula emissões evitadas baseado no modelo científico
    """
    # Massa de resíduos processada
    residuo_kg = capacidade_litros * densidade_kg_l
    
    # Parâmetros fixos do modelo científico
    T = 25
    DOC = 0.15
    DOCf = 0.0147 * T + 0.28
    MCF = 1
    F = 0.5
    OX = 0.1
    Ri = 0.0
    
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
    
    # Cálculo das emissões do aterro
    potencial_CH4_por_kg = DOC * DOCf * MCF * F * (16/12) * (1 - Ri) * (1 - OX)
    emissoes_CH4_aterro = residuo_kg * potencial_CH4_por_kg
    
    f_aberto = (massa_exposta_kg / residuo_kg) * (h_exposta / 24)
    f_aberto = np.clip(f_aberto, 0.0, 1.0)
    
    E_aberto = 1.91
    E_fechado = 2.15
    E_medio = f_aberto * E_aberto + (1 - f_aberto) * E_fechado
    
    fator_umid = (1 - umidade) / (1 - 0.55)
    E_medio_ajust = E_medio * fator_umid
    
    emissao_N2O_aterro = (E_medio_ajust * (44/28) / 1_000_000) * residuo_kg
    
    # Cálculo das emissões da vermicompostagem
    emissoes_CH4_vermi = residuo_kg * (TOC_YANG * CH4_C_FRAC_YANG * (16/12) * fracao_ms)
    emissoes_N2O_vermi = residuo_kg * (TN_YANG * N2O_N_FRAC_YANG * (44/28) * fracao_ms)
    
    # Cálculo das emissões evitadas
    emissao_aterro_kgco2eq = (emissoes_CH4_aterro * GWP_CH4_20 + emissao_N2O_aterro * GWP_N2O_20)
    emissao_vermi_kgco2eq = (emissoes_CH4_vermi * GWP_CH4_20 + emissoes_N2O_vermi * GWP_N2O_20)
    
    emissões_evitadas_tco2eq = (emissao_aterro_kgco2eq - emissao_vermi_kgco2eq) / 1000
    
    return {
        'residuo_kg': residuo_kg,
        'emissoes_evitadas_tco2eq': emissões_evitadas_tco2eq,
        'parametros': {
            'capacidade_litros': capacidade_litros,
            'densidade_kg_l': densidade_kg_l
        }
    }

def calcular_emissoes_evitadas_reator(capacidade_litros, densidade_kg_l=0.5):
    """Versão simplificada para uso geral"""
    resultado = calcular_emissoes_evitadas_reator_detalhado(capacidade_litros, densidade_kg_l)
    return resultado['residuo_kg'], resultado['emissoes_evitadas_tco2eq']

def processar_reatores_cheios(df_reatores, df_escolas, densidade_kg_l=0.5):
    """Processa os reatores cheios e calcula emissões evitadas"""
    # Filtrar reatores que já encheram
    reatores_cheios = df_reatores[df_reatores['data_encheu'].notna()].copy()
    
    if reatores_cheios.empty:
        return pd.DataFrame(), 0, 0
    
    # Calcular para cada reator
    resultados = []
    total_residuo = 0
    total_emissoes_evitadas = 0
    
    for _, reator in reatores_cheios.iterrows():
        capacidade = reator['capacidade_litros'] if 'capacidade_litros' in reator else 100
        residuo_kg, emissoes_evitadas = calcular_emissoes_evitadas_reator(capacidade, densidade_kg_l)
        
        resultados.append({
            'id_reator': reator['id_reator'],
            'id_escola': reator['id_escola'],
            'data_encheu': reator['data_encheu'],
            'capacidade_litros': capacidade,
            'residuo_kg': residuo_kg,
            'emissoes_evitadas_tco2eq': emissoes_evitadas
        })
        
        total_residuo += residuo_kg
        total_emissoes_evitadas += emissoes_evitadas
    
    df_resultados = pd.DataFrame(resultados)
    
    # Juntar com informações da escola
    if 'nome_escola' in df_escolas.columns:
        df_resultados = df_resultados.merge(
            df_escolas[['id_escola', 'nome_escola']], 
            on='id_escola', 
            how='left'
        )
    
    return df_resultados, total_residuo, total_emissoes_evitadas

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

# Inicializar session state
inicializar_session_state()

# Carregar dados REAIS
df_escolas, df_reatores = carregar_dados_excel(URL_EXCEL)

# Verificar se os dados foram carregados
if df_escolas.empty or df_reatores.empty:
    st.stop()

# Sidebar
exibir_cotacao_carbono()

with st.sidebar:
    st.header("⚙️ Parâmetros de Cálculo")
    
    densidade_residuo = st.slider(
        "Densidade do resíduo (kg/litro)",
        min_value=0.3,
        max_value=0.8,
        value=0.5,
        step=0.05,
        help="Densidade média dos resíduos orgânicos"
    )
    
    escolas_options = ["Todas as escolas"] + df_escolas['id_escola'].tolist()
    escola_selecionada = st.selectbox("Selecionar escola", escolas_options)
    
    st.header("🧮 Cálculo de Exemplo")
    capacidade_exemplo = st.slider(
        "Capacidade por reator (litros)",
        min_value=25,
        max_value=200,
        value=100,
        step=5,
        help="Capacidade de cada reator de processamento"
    )

# =============================================================================
# EXIBIÇÃO DOS DADOS REAIS
# =============================================================================

st.header("📊 Dashboard de Vermicompostagem - Dados Reais")

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
    reatores_ativos = len(df_reatores[df_reatores['status_reator'] == 'Ativo'])
    st.metric("Reatores Ativos", formatar_br(reatores_ativos, 0))

# Processar cálculos
if escola_selecionada != "Todas as escolas":
    reatores_filtrados = df_reatores[df_reatores['id_escola'] == escola_selecionada]
    escolas_filtradas = df_escolas[df_escolas['id_escola'] == escola_selecionada]
else:
    reatores_filtrados = df_reatores
    escolas_filtradas = df_escolas

reatores_processados, total_residuo, total_emissoes = processar_reatores_cheios(
    reatores_filtrados, escolas_filtradas, densidade_residuo
)

# Calcular valores financeiros
preco_carbono_eur = st.session_state.preco_carbono
taxa_cambio = st.session_state.taxa_cambio

valor_eur = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "€")
valor_brl = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "R$", taxa_cambio)

# =============================================================================
# SEÇÃO DE CÁLCULO DETALHADO
# =============================================================================

st.header("🧮 Detalhamento do Cálculo")

# Calcular exemplo detalhado
resultado_detalhado = calcular_emissoes_evitadas_reator_detalhado(capacidade_exemplo, densidade_residuo)

col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 Parâmetros do Cálculo")
    st.write(f"**Capacidade do reator:** {formatar_br(capacidade_exemplo, 0)} L")
    st.write(f"**Densidade do resíduo:** {formatar_br(densidade_residuo, 2)} kg/L")
    st.write(f"**Massa de resíduos:** {formatar_br(resultado_detalhado['residuo_kg'], 1)} kg")

with col2:
    st.subheader("📊 Resultado do Cálculo")
    st.metric(
        "Emissões Evitadas", 
        formatar_tco2eq(resultado_detalhado['emissoes_evitadas_tco2eq'])
    )
    
    valor_exemplo_brl = calcular_valor_creditos(
        resultado_detalhado['emissoes_evitadas_tco2eq'], 
        preco_carbono_eur, 
        "R$", 
        taxa_cambio
    )
    
    st.metric(
        "Valor dos Créditos", 
        formatar_moeda_br(valor_exemplo_brl)
    )

# =============================================================================
# RESULTADOS FINANCEIROS REAIS
# =============================================================================

st.header("💰 Créditos de Carbono Computados - Sistema Real")

if reatores_processados.empty:
    st.info("ℹ️ Nenhum reator cheio encontrado. Os créditos serão calculados quando os reatores encherem.")
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
# TABELAS COM DADOS REAIS
# =============================================================================

st.header("📋 Dados das Escolas")

# Verificar e mostrar colunas disponíveis
colunas_escolas = ['id_escola', 'nome_escola', 'data_implantacao', 'status', 'ultima_visita', 'observacoes']
colunas_escolas_disponiveis = [col for col in colunas_escolas if col in df_escolas.columns]

if colunas_escolas_disponiveis:
    st.dataframe(df_escolas[colunas_escolas_disponiveis], use_container_width=True)
else:
    st.warning("ℹ️ Nenhuma coluna de escolas disponível no formato esperado")

st.header("📋 Dados dos Reatores")

# Verificar e mostrar colunas disponíveis
colunas_reatores = ['id_reator', 'id_escola', 'capacidade_litros', 'status_reator', 'data_ativacao', 'data_encheu', 'data_colheita', 'residuo_kg', 'emissoes_evitadas_tco2eq', 'observacoes']
colunas_reatores_disponiveis = [col for col in colunas_reatores if col in df_reatores.columns]

if colunas_reatores_disponiveis:
    # Formatar colunas numéricas se existirem
    df_reatores_display = df_reatores[colunas_reatores_disponiveis].copy()
    
    if 'residuo_kg' in df_reatores_display.columns:
        df_reatores_display['residuo_kg'] = df_reatores_display['residuo_kg'].apply(lambda x: formatar_br(x, 1) if pd.notna(x) else "N/A")
    
    if 'emissoes_evitadas_tco2eq' in df_reatores_display.columns:
        df_reatores_display['emissoes_evitadas_tco2eq'] = df_reatores_display['emissoes_evitadas_tco2eq'].apply(lambda x: formatar_tco2eq(x) if pd.notna(x) else "N/A")
    
    if 'capacidade_litros' in df_reatores_display.columns:
        df_reatores_display['capacidade_litros'] = df_reatores_display['capacidade_litros'].apply(lambda x: formatar_br(x, 0) if pd.notna(x) else "N/A")
    
    st.dataframe(df_reatores_display, use_container_width=True)
else:
    st.warning("ℹ️ Nenhuma coluna de reatores disponível no formato esperado")

# =============================================================================
# DETALHAMENTO DOS CRÉDITOS (se houver reatores processados)
# =============================================================================

if not reatores_processados.empty:
    st.header("📊 Detalhamento dos Créditos por Reator")
    
    df_detalhes = reatores_processados[[
        'nome_escola', 'id_reator', 'data_encheu', 'capacidade_litros', 
        'residuo_kg', 'emissoes_evitadas_tco2eq'
    ]].copy()
    
    # Formatar valores
    df_detalhes['residuo_kg'] = df_detalhes['residuo_kg'].apply(lambda x: formatar_br(x, 1))
    df_detalhes['emissoes_evitadas_tco2eq'] = df_detalhes['emissoes_evitadas_tco2eq'].apply(lambda x: formatar_tco2eq(x))
    df_detalhes['capacidade_litros'] = df_detalhes['capacidade_litros'].apply(lambda x: formatar_br(x, 0))
    
    st.dataframe(df_detalhes, use_container_width=True)

# =============================================================================
# GRÁFICOS COM DADOS REAIS
# =============================================================================

st.header("📈 Status dos Reatores")

if 'status_reator' in df_reatores.columns:
    status_count = df_reatores['status_reator'].value_counts()
    
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
    st.info("ℹ️ Coluna 'status_reator' não encontrada para gerar gráfico")

# Gráfico de escolas por status
st.header("🏫 Status das Escolas")

if 'status' in df_escolas.columns:
    status_escolas_count = df_escolas['status'].value_counts()
    
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
    st.info("ℹ️ Coluna 'status' não encontrada para gerar gráfico")

# =============================================================================
# INFORMAÇÕES SOBRE OS DADOS
# =============================================================================

with st.expander("ℹ️ Informações sobre os Dados"):
    st.markdown(f"""
    **📊 Fonte dos Dados:**
    - **Excel:** [Controladoria-Compostagem-nas-Escolas]({URL_EXCEL})
    - **Escolas carregadas:** {len(df_escolas)}
    - **Reatores carregados:** {len(df_reatores)}
    - **Reatores cheios:** {reatores_cheios}
    - **Reatores ativos:** {reatores_ativos}
    
    **🧮 Cálculos Realizados:**
    - Baseado no modelo científico (IPCC, UNFCCC, Yang et al.)
    - Densidade do resíduo: {densidade_residuo} kg/L
    - Capacidade exemplo: {capacidade_exemplo} L
    - Preço do carbono: € {formatar_br(preco_carbono_eur, 2)}/tCO₂eq
    
    **💡 Próximos Passos:**
    - Atualize o Excel com novas datas de enchimento
    - Adicione observações sobre o andamento dos reatores
    - Monitore o status de cada escola
    """)

# Botão para atualizar dados
if st.button("🔄 Atualizar Dados do Excel"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")
st.markdown("""
**♻️ Sistema de Vermicompostagem - Ribeirão Preto/SP**  
*Dados carregados de: [Controladoria-Compostagem-nas-Escolas](https://github.com/loopvinyl/Controladoria-Compostagem-nas-Escolas)*
""")
