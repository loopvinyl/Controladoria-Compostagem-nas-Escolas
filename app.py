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
    page_title="Compostagem com Minhocas - Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Compostagem com Minhocas nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo científico de emissões para resíduos orgânicos**")

# =============================================================================
# CONFIGURAÇÕES - URLS ALTERNATIVAS PARA O EXCEL
# =============================================================================

# URLs alternativas para o Excel (tentará em ordem)
URLS_EXCEL = [
    "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem.xlsx",
    "https://github.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/raw/main/dados_vermicompostagem.xlsx"
]

# =============================================================================
# CONFIGURAÇÕES FIXAS - DENSIDADE PADRÃO
# =============================================================================

DENSIDADE_PADRAO = 0.6  # kg/L - para resíduos de vegetais, frutas e borra de café

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
# FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO DOS DADOS REAIS - MELHORADA
# =============================================================================

@st.cache_data
def carregar_dados_excel(_urls):
    """Carrega os dados REAIS do Excel do GitHub - tenta múltiplas URLs"""
    df_escolas = pd.DataFrame()
    df_reatores = pd.DataFrame()
    url_sucesso = None
    
    loading_placeholder = st.empty()
    
    for i, url in enumerate(_urls):
        try:
            loading_placeholder.info(f"📥 Tentando carregar dados... (URL {i+1}/{len(_urls)})")
            
            # Ler as abas
            df_escolas = pd.read_excel(url, sheet_name='escolas')
            df_reatores = pd.read_excel(url, sheet_name='reatores')
            
            loading_placeholder.empty()
            st.success(f"✅ Dados carregados com sucesso!")
            st.success(f"📊 {len(df_escolas)} escolas e {len(df_reatores)} reatores carregados")
            
            url_sucesso = url
            break
            
        except Exception as e:
            loading_placeholder.empty()
            st.warning(f"⚠️ Não foi possível carregar da URL {i+1}")
            continue
    
    if df_escolas.empty or df_reatores.empty:
        st.error("❌ Não foi possível carregar os dados de nenhuma das URLs fornecidas.")
        st.error("📋 Por favor, verifique:")
        st.error("   - Se o arquivo Excel existe no repositório")
        st.error("   - Se as abas 'escolas' e 'reatores' existem no arquivo")
        st.error("   - Se o repositório é público")
        return pd.DataFrame(), pd.DataFrame()
    
    # Converter colunas de data
    try:
        colunas_data_escolas = ['data_implantacao', 'ultima_visita']
        for col in colunas_data_escolas:
            if col in df_escolas.columns:
                df_escolas[col] = pd.to_datetime(df_escolas[col], errors='coerce')
                
        colunas_data_reatores = ['data_ativacao', 'data_encheu', 'data_colheita']
        for col in colunas_data_reatores:
            if col in df_reatores.columns:
                df_reatores[col] = pd.to_datetime(df_reatores[col], errors='coerce')
    except Exception as e:
        st.warning(f"⚠️ Aviso ao converter datas: {e}")
    
    return df_escolas, df_reatores

# =============================================================================
# FUNÇÕES DE CÁLCULO CIENTÍFICO COM DENSIDADE FIXA
# =============================================================================

def calcular_emissoes_evitadas_reator_detalhado(capacidade_litros):
    """
    Calcula emissões evitadas baseado no modelo científico
    COM DENSIDADE FIXA de 0,6 kg/L para resíduos escolares
    """
    # Massa de resíduos processada - DENSIDADE FIXA
    residuo_kg = capacidade_litros * DENSIDADE_PADRAO
    
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
    
    # Cálculo das emissões da compostagem com minhocas
    emissoes_CH4_compostagem = residuo_kg * (TOC_YANG * CH4_C_FRAC_YANG * (16/12) * fracao_ms)
    emissoes_N2O_compostagem = residuo_kg * (TN_YANG * N2O_N_FRAC_YANG * (44/28) * fracao_ms)
    
    # Cálculo das emissões evitadas
    emissao_aterro_kgco2eq = (emissoes_CH4_aterro * GWP_CH4_20 + emissao_N2O_aterro * GWP_N2O_20)
    emissao_compostagem_kgco2eq = (emissoes_CH4_compostagem * GWP_CH4_20 + emissoes_N2O_compostagem * GWP_N2O_20)
    
    emissões_evitadas_tco2eq = (emissao_aterro_kgco2eq - emissao_compostagem_kgco2eq) / 1000
    
    return {
        'residuo_kg': residuo_kg,
        'emissoes_CH4_aterro': emissoes_CH4_aterro,
        'emissoes_N2O_aterro': emissao_N2O_aterro,
        'emissoes_CH4_compostagem': emissoes_CH4_compostagem,
        'emissoes_N2O_compostagem': emissoes_N2O_compostagem,
        'emissao_aterro_kgco2eq': emissao_aterro_kgco2eq,
        'emissao_compostagem_kgco2eq': emissao_compostagem_kgco2eq,
        'emissoes_evitadas_tco2eq': emissões_evitadas_tco2eq,
        'parametros': {
            'capacidade_litros': capacidade_litros,
            'densidade_kg_l': DENSIDADE_PADRAO,
            'T': T,
            'DOC': DOC,
            'DOCf': DOCf,
            'TOC_YANG': TOC_YANG,
            'TN_YANG': TN_YANG,
            'CH4_C_FRAC_YANG': CH4_C_FRAC_YANG,
            'N2O_N_FRAC_YANG': N2O_N_FRAC_YANG,
            'umidade': umidade,
            'GWP_CH4_20': GWP_CH4_20,
            'GWP_N2O_20': GWP_N2O_20
        }
    }

def calcular_emissoes_evitadas_reator(capacidade_litros):
    """Versão simplificada para uso geral"""
    resultado = calcular_emissoes_evitadas_reator_detalhado(capacidade_litros)
    return resultado['residuo_kg'], resultado['emissoes_evitadas_tco2eq']

def processar_reatores_cheios(df_reatores, df_escolas):
    """Processa os reatores cheios e calcula emissões evitadas"""
    # Filtrar reatores que já encheram
    reatores_cheios = df_reatores[df_reatores['data_encheu'].notna()].copy()
    
    if reatores_cheios.empty:
        return pd.DataFrame(), 0, 0, []
    
    # Calcular para cada reator
    resultados = []
    total_residuo = 0
    total_emissoes_evitadas = 0
    detalhes_calculo = []
    
    for _, reator in reatores_cheios.iterrows():
        capacidade = reator['capacidade_litros'] if 'capacidade_litros' in reator else 100
        resultado_detalhado = calcular_emissoes_evitadas_reator_detalhado(capacidade)
        residuo_kg = resultado_detalhado['residuo_kg']
        emissoes_evitadas = resultado_detalhado['emissoes_evitadas_tco2eq']
        
        # Guardar detalhes do cálculo para este reator
        detalhes_calculo.append({
            'id_reator': reator['id_reator'],
            'id_escola': reator['id_escola'],
            'capacidade_litros': capacidade,
            'residuo_kg': residuo_kg,
            'emissoes_evitadas_tco2eq': emissoes_evitadas,
            'calculo_detalhado': resultado_detalhado
        })
        
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
    if 'nome_escola' in df_escolas.columns and 'id_escola' in df_resultados.columns:
        df_resultados = df_resultados.merge(
            df_escolas[['id_escola', 'nome_escola']], 
            on='id_escola', 
            how='left'
        )
    
    return df_resultados, total_residuo, total_emissoes_evitadas, detalhes_calculo

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

# Inicializar session state
inicializar_session_state()

# Sidebar
exibir_cotacao_carbono()

with st.sidebar:
    st.header("🎯 Configurações")
    
    # Carregar dados REAIS
    st.info("📥 Clique para carregar dados")
    if st.button("🔄 Carregar Dados do Excel"):
        st.session_state.dados_carregados = False
        st.rerun()

# Carregar dados REAIS
if not st.session_state.get('dados_carregados', False):
    df_escolas, df_reatores = carregar_dados_excel(URLS_EXCEL)
    
    if not df_escolas.empty and not df_reatores.empty:
        st.session_state.df_escolas = df_escolas
        st.session_state.df_reatores = df_reatores
        st.session_state.dados_carregados = True
        st.rerun()
    else:
        # Se não conseguiu carregar, mostrar opção de upload
        with st.expander("📁 Alternativa: Carregar arquivo Excel local"):
            st.info("Se as URLs online não funcionarem, você pode fazer upload do arquivo Excel localmente:")
            
            arquivo_upload = st.file_uploader("Escolha o arquivo Excel", type=['xlsx'])
            
            if arquivo_upload is not None:
                try:
                    df_escolas_upload = pd.read_excel(arquivo_upload, sheet_name='escolas')
                    df_reatores_upload = pd.read_excel(arquivo_upload, sheet_name='reatores')
                    
                    st.success(f"✅ Arquivo carregado: {len(df_escolas_upload)} escolas e {len(df_reatores_upload)} reatores")
                    
                    # Atualizar os dados na session state
                    st.session_state.df_escolas = df_escolas_upload
                    st.session_state.df_reatores = df_reatores_upload
                    st.session_state.dados_carregados = True
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erro ao carregar arquivo: {e}")
        
        st.stop()

# Usar dados da session state
df_escolas = st.session_state.df_escolas
df_reatores = st.session_state.df_reatores

# Configuração da escola na sidebar
with st.sidebar:
    escolas_options = ["Todas as escolas"] + df_escolas['id_escola'].tolist()
    escola_selecionada = st.selectbox("Selecionar escola", escolas_options)

# =============================================================================
# EXIBIÇÃO DOS DADOS REAIS
# =============================================================================

st.header("📊 Dashboard de Compostagem com Minhocas - Dados Reais")

# Informação sobre densidade fixa
st.info(f"""
**⚙️ Parâmetros de Cálculo Fixos:**
- **Densidade do resíduo:** {DENSIDADE_PADRAO} kg/L (padrão para resíduos de vegetais, frutas e borra de café)
- **Base científica:** Valores médios da literatura para resíduos orgânicos de cozinha escolar
- **Tipo de resíduo:** Apenas pré-preparo (sem restos de pratos com carne ou laticínios)
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
    reatores_ativos = len(df_reatores[df_reatores['status_reator'] == 'Ativo'])
    st.metric("Reatores Ativos", formatar_br(reatores_ativos, 0))

# Processar cálculos
if escola_selecionada != "Todas as escolas":
    reatores_filtrados = df_reatores[df_reatores['id_escola'] == escola_selecionada]
    escolas_filtradas = df_escolas[df_escolas['id_escola'] == escola_selecionada]
else:
    reatores_filtrados = df_reatores
    escolas_filtradas = df_escolas

reatores_processados, total_residuo, total_emissoes, detalhes_calculo = processar_reatores_cheios(
    reatores_filtrados, escolas_filtradas
)

# Calcular valores financeiros
preco_carbono_eur = st.session_state.preco_carbono
taxa_cambio = st.session_state.taxa_cambio

valor_eur = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "€")
valor_brl = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "R$", taxa_cambio)

# =============================================================================
# RESULTADOS FINANCEIROS REAIS
# =============================================================================

st.header("💰 Créditos de Carbono Computados - Sistema Real")

if reatores_processados.empty:
    st.info("ℹ️ Nenhum reator cheio encontrado. Os créditos serão calculados quando os reatores encherem.")
    
    # Mostrar métricas zeradas quando não há reatores processados
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
# DETALHAMENTO COMPLETO DOS CÁLCULOS
# =============================================================================

if not reatores_processados.empty:
    st.header("🧮 Detalhamento Completo dos Cálculos")
    
    # Mostrar cálculo para o primeiro reator como exemplo
    primeiro_reator = detalhes_calculo[0]
    calc = primeiro_reator['calculo_detalhado']
    
    st.subheader(f"📋 Cálculo Detalhado para o Reator {primeiro_reator['id_reator']}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Parâmetros de Entrada:**")
        st.write(f"- Capacidade do reator: {formatar_br(calc['parametros']['capacidade_litros'], 0)} L")
        st.write(f"- Densidade do resíduo: {formatar_br(calc['parametros']['densidade_kg_l'], 2)} kg/L")
        st.write(f"- Massa de resíduos: {formatar_br(calc['residuo_kg'], 1)} kg")
        
        st.write("**Parâmetros Científicos:**")
        st.write(f"- Temperatura: {formatar_br(calc['parametros']['T'], 0)}°C")
        st.write(f"- Umidade: {formatar_br(calc['parametros']['umidade'] * 100, 0)}%")
        st.write(f"- DOC: {formatar_br(calc['parametros']['DOC'], 3)}")
        st.write(f"- TOC: {formatar_br(calc['parametros']['TOC_YANG'], 3)}")
        st.write(f"- TN: {formatar_br(calc['parametros']['TN_YANG'], 4)}")
    
    with col2:
        st.write("**Resultados Intermediários:**")
        st.write(f"- CH₄ Aterro: {formatar_br(calc['emissoes_CH4_aterro'], 3)} kg")
        st.write(f"- N₂O Aterro: {formatar_br(calc['emissoes_N2O_aterro'], 6)} kg")
        st.write(f"- CH₄ Compostagem: {formatar_br(calc['emissoes_CH4_compostagem'], 5)} kg")
        st.write(f"- N₂O Compostagem: {formatar_br(calc['emissoes_N2O_compostagem'], 5)} kg")
        
        st.write("**Resultados Finais:**")
        st.write(f"- Emissões Aterro: {formatar_br(calc['emissao_aterro_kgco2eq'], 1)} kg CO₂eq")
        st.write(f"- Emissões Compostagem: {formatar_br(calc['emissao_compostagem_kgco2eq'], 3)} kg CO₂eq")
        st.metric(
            "Emissões Evitadas", 
            formatar_tco2eq(calc['emissoes_evitadas_tco2eq'])
        )

    # Fórmulas matemáticas
    with st.expander("📝 Ver Fórmulas Matemáticas Completas"):
        st.markdown(f"""
        **🧮 Fórmulas Utilizadas no Cálculo:**

        **1. Massa de Resíduos:**
        ```
        Resíduo (kg) = Capacidade (L) × Densidade (kg/L)
        Resíduo = {formatar_br(calc['parametros']['capacidade_litros'], 0)} × {formatar_br(calc['parametros']['densidade_kg_l'], 2)} = {formatar_br(calc['residuo_kg'], 1)} kg
        ```

        **2. Emissões do Aterro (Cenário Base):**
        ```
        CH₄ Aterro = Resíduo × DOC × DOCf × MCF × F × (16/12) × (1-Ri) × (1-OX)
        CH₄ Aterro = {formatar_br(calc['residuo_kg'], 1)} × {formatar_br(calc['parametros']['DOC'], 3)} × {formatar_br(calc['parametros']['DOCf'], 3)} × 1 × 0,5 × 1,333 × 1 × 0,9
        CH₄ Aterro = {formatar_br(calc['emissoes_CH4_aterro'], 3)} kg

        N₂O Aterro = Resíduo × E_médio × (44/28) ÷ 1.000.000
        N₂O Aterro = {formatar_br(calc['residuo_kg'], 1)} × 0,69 × 1,571 ÷ 1.000.000
        N₂O Aterro = {formatar_br(calc['emissoes_N2O_aterro'], 6)} kg
        ```

        **3. Emissões da Compostagem com Minhocas (Cenário Projeto):**
        ```
        CH₄ Compostagem = Resíduo × TOC × CH₄-C/TOC × (16/12) × (1-umidade)
        CH₄ Compostagem = {formatar_br(calc['residuo_kg'], 1)} × {formatar_br(calc['parametros']['TOC_YANG'], 3)} × {formatar_br(calc['parametros']['CH4_C_FRAC_YANG'], 4)} × 1,333 × {formatar_br(1-calc['parametros']['umidade'], 2)}
        CH₄ Compostagem = {formatar_br(calc['emissoes_CH4_compostagem'], 5)} kg

        N₂O Compostagem = Resíduo × TN × N₂O-N/TN × (44/28) × (1-umidade)
        N₂O Compostagem = {formatar_br(calc['residuo_kg'], 1)} × {formatar_br(calc['parametros']['TN_YANG'], 4)} × {formatar_br(calc['parametros']['N2O_N_FRAC_YANG'], 4)} × 1,571 × {formatar_br(1-calc['parametros']['umidade'], 2)}
        N₂O Compostagem = {formatar_br(calc['emissoes_N2O_compostagem'], 5)} kg
        ```

        **4. Emissões em CO₂eq:**
        ```
        CO₂eq Aterro = (CH₄ Aterro × GWP_CH₄) + (N₂O Aterro × GWP_N₂O)
        CO₂eq Aterro = ({formatar_br(calc['emissoes_CH4_aterro'], 3)} × {formatar_br(calc['parametros']['GWP_CH4_20'], 0)}) + ({formatar_br(calc['emissoes_N2O_aterro'], 6)} × {formatar_br(calc['parametros']['GWP_N2O_20'], 0)})
        CO₂eq Aterro = {formatar_br(calc['emissao_aterro_kgco2eq'], 1)} kg CO₂eq

        CO₂eq Compostagem = (CH₄ Compostagem × GWP_CH₄) + (N₂O Compostagem × GWP_N₂O)
        CO₂eq Compostagem = ({formatar_br(calc['emissoes_CH4_compostagem'], 5)} × {formatar_br(calc['parametros']['GWP_CH4_20'], 0)}) + ({formatar_br(calc['emissoes_N2O_compostagem'], 5)} × {formatar_br(calc['parametros']['GWP_N2O_20'], 0)})
        CO₂eq Compostagem = {formatar_br(calc['emissao_compostagem_kgco2eq'], 3)} kg CO₂eq
        ```

        **5. Emissões Evitadas:**
        ```
        Emissões Evitadas = (CO₂eq Aterro - CO₂eq Compostagem) ÷ 1000
        Emissões Evitadas = ({formatar_br(calc['emissao_aterro_kgco2eq'], 1)} - {formatar_br(calc['emissao_compostagem_kgco2eq'], 3)}) ÷ 1000
        Emissões Evitadas = {formatar_br(calc['emissoes_evitadas_tco2eq'], 3)} tCO₂eq
        ```
        """)

# =============================================================================
# RESTANTE DO CÓDIGO (tabelas, gráficos, etc.)
# =============================================================================

st.header("📋 Dados das Escolas")

colunas_escolas = ['id_escola', 'nome_escola', 'data_implantacao', 'status', 'ultima_visita', 'observacoes']
colunas_escolas_disponiveis = [col for col in colunas_escolas if col in df_escolas.columns]

if colunas_escolas_disponiveis:
    st.dataframe(df_escolas[colunas_escolas_disponiveis], use_container_width=True)
else:
    st.warning("ℹ️ Nenhuma coluna de escolas disponível no formato esperado")

st.header("📋 Dados dos Reatores")

colunas_reatores = ['id_reator', 'id_escola', 'capacidade_litros', 'status_reator', 'data_ativacao', 'data_encheu', 'data_colheita', 'observacoes']
colunas_reatores_disponiveis = [col for col in colunas_reatores if col in df_reatores.columns]

if colunas_reatores_disponiveis:
    df_reatores_display = df_reatores[colunas_reatores_disponiveis].copy()
    
    if 'capacidade_litros' in df_reatores_display.columns:
        df_reatores_display['capacidade_litros'] = df_reatores_display['capacidade_litros'].apply(lambda x: formatar_br(x, 0) if pd.notna(x) else "N/A")
    
    st.dataframe(df_reatores_display, use_container_width=True)
else:
    st.warning("ℹ️ Nenhuma coluna de reatores disponível no formato esperado")

# Botão para atualizar dados
if st.button("🔄 Atualizar Dados do Excel"):
    st.cache_data.clear()
    st.session_state.dados_carregados = False
    st.rerun()

st.markdown("---")
st.markdown("""
**♻️ Sistema de Compostagem com Minhocas - Ribeirão Preto/SP**  
*Desenvolvido para acompanhamento de créditos de carbono*
""")
