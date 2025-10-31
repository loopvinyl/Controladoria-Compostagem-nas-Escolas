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

# URL do Excel no GitHub
URL_EXCEL = "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem.xlsx"

# =============================================================================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# =============================================================================

def formatar_br(numero, casas_decimais=2):
    """
    Formata números no padrão brasileiro: 1.234,56
    """
    if numero is None or pd.isna(numero):
        return "N/A"
    
    try:
        # Arredonda para o número de casas decimais especificado
        numero = round(float(numero), casas_decimais)
        
        # Formata como string e substitui o ponto pela vírgula
        if casas_decimais == 0:
            return f"{numero:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            formato = f"{{:,.{casas_decimais}f}}"
            return formato.format(numero).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "N/A"

def formatar_moeda_br(valor, simbolo="R$", casas_decimais=2):
    """
    Formata valores monetários no padrão brasileiro: R$ 1.234,56
    """
    return f"{simbolo} {formatar_br(valor, casas_decimais)}"

def formatar_tco2eq(valor):
    """
    Formata valores de tCO₂eq no padrão brasileiro
    """
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

    # Formatar valores no padrão brasileiro
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
# FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO
# =============================================================================

@st.cache_data
def carregar_dados_excel(url):
    """Carrega os dados do Excel do GitHub"""
    try:
        # Tentar carregar o arquivo
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
        
        # Criar dados de exemplo para demonstração
        st.warning("🔄 Usando dados de exemplo para demonstração...")
        
        # Criar dados de exemplo com informações do sistema
        df_escolas = pd.DataFrame({
            'id_escola': ['EMEI001', 'EMEI002'],
            'nome_escola': ['EMEI Joãozinho', 'EMEI Maria'],
            'data_implantacao': [datetime(2024, 3, 15), datetime(2024, 3, 20)],
            'status': ['Ativo', 'Ativo'],
            'ultima_visita': [datetime(2024, 5, 10), datetime(2024, 5, 12)],
            'capacidade_total_sistema_litros': [200, 200],  # 4 caixas de 50L cada
            'num_caixas_processamento': [3, 3],  # 3 caixas para processamento
            'num_caixas_biofertilizante': [1, 1]  # 1 caixa para biofertilizante
        })
        
        df_reatores = pd.DataFrame({
            'id_reator': ['R001', 'R002', 'R003', 'R004', 'R005', 'R006', 'R007', 'R008'],
            'id_escola': ['EMEI001', 'EMEI001', 'EMEI001', 'EMEI001', 'EMEI002', 'EMEI002', 'EMEI002', 'EMEI002'],
            'capacidade_litros': [50, 50, 50, 50, 50, 50, 50, 50],
            'tipo_caixa': ['Processamento', 'Processamento', 'Processamento', 'Biofertilizante', 
                          'Processamento', 'Processamento', 'Processamento', 'Biofertilizante'],
            'status_reator': ['Cheio', 'Cheio', 'Ativo', 'Coletando', 'Cheio', 'Cheio', 'Ativo', 'Coletando'],
            'data_ativacao': [datetime(2024, 3, 15), datetime(2024, 3, 15), datetime(2024, 3, 15), datetime(2024, 3, 15),
                             datetime(2024, 3, 20), datetime(2024, 3, 20), datetime(2024, 3, 20), datetime(2024, 3, 20)],
            'data_encheu': [datetime(2024, 4, 20), datetime(2024, 4, 25), None, None,
                           datetime(2024, 4, 22), datetime(2024, 4, 28), None, None],
            'data_colheita': [None, None, None, None, None, None, None, None]
        })
        
        return df_escolas, df_reatores

# =============================================================================
# FUNÇÕES DE CÁLCULO CIENTÍFICO (BASEADAS NO SCRIPT ANEXO)
# =============================================================================

def calcular_emissoes_evitadas_reator_detalhado(capacidade_litros, densidade_kg_l=0.5):
    """
    Calcula emissões evitadas baseado no modelo científico adaptado para escolas
    Retorna um dicionário com todos os componentes do cálculo
    """
    # Massa de resíduos processada
    residuo_kg = capacidade_litros * densidade_kg_l
    
    # =============================================================================
    # PARÂMETROS FIXOS DO MODELO CIENTÍFICO
    # =============================================================================
    
    # Parâmetros para aterro (cenário base) - IPCC 2006
    T = 25  # Temperatura média (ºC)
    DOC = 0.15  # Carbono orgânico degradável (fração)
    DOCf = 0.0147 * T + 0.28
    MCF = 1  # Fator de correção de metano
    F = 0.5  # Fração de metano no biogás
    OX = 0.1  # Fator de oxidação
    Ri = 0.0  # Metano recuperado
    
    # Parâmetros para vermicompostagem (Yang et al. 2017) - cenário projeto
    TOC_YANG = 0.436  # Fração de carbono orgânico total
    TN_YANG = 14.2 / 1000  # Fração de nitrogênio total (14.2 g/kg → 0.0142)
    CH4_C_FRAC_YANG = 0.13 / 100  # Fração do TOC emitida como CH4-C (0.13%)
    N2O_N_FRAC_YANG = 0.92 / 100  # Fração do TN emitida como N2O-N (0.92%)
    
    # Umidade padrão (85% - valor típico para resíduos orgânicos)
    umidade = 0.85
    fracao_ms = 1 - umidade  # Fração de matéria seca
    
    # Parâmetros operacionais escola (valores conservadores)
    massa_exposta_kg = min(residuo_kg, 50)  # Limite de exposição
    h_exposta = 8  # Horas de exposição por dia
    
    # GWP (IPCC AR6) - 20 anos
    GWP_CH4_20 = 79.7
    GWP_N2O_20 = 273
    
    # =============================================================================
    # CÁLCULO DAS EMISSÕES DO ATERRO (CENÁRIO BASE)
    # =============================================================================
    
    # Emissões de CH4 no aterro (kg CH4) - IPCC 2006
    potencial_CH4_por_kg = DOC * DOCf * MCF * F * (16/12) * (1 - Ri) * (1 - OX)
    emissoes_CH4_aterro = residuo_kg * potencial_CH4_por_kg
    
    # Emissões de N2O no aterro (kg N2O) - Wang et al. (2017)
    f_aberto = (massa_exposta_kg / residuo_kg) * (h_exposta / 24)
    f_aberto = np.clip(f_aberto, 0.0, 1.0)  # Limitar entre 0 e 1
    
    E_aberto = 1.91   # Fator de emissão para resíduos expostos
    E_fechado = 2.15  # Fator de emissão para resíduos cobertos
    E_medio = f_aberto * E_aberto + (1 - f_aberto) * E_fechado
    
    # Ajuste por umidade
    fator_umid = (1 - umidade) / (1 - 0.55)
    E_medio_ajust = E_medio * fator_umid
    
    emissao_N2O_aterro = (E_medio_ajust * (44/28) / 1_000_000) * residuo_kg
    
    # =============================================================================
    # CÁLCULO DAS EMISSÕES DA VERMICOMPOSTAGEM (CENÁRIO PROJETO)
    # =============================================================================
    
    # Emissões totais de CH4 e N2O para vermicompostagem - Yang et al. (2017)
    emissoes_CH4_vermi = residuo_kg * (TOC_YANG * CH4_C_FRAC_YANG * (16/12) * fracao_ms)
    emissoes_N2O_vermi = residuo_kg * (TN_YANG * N2O_N_FRAC_YANG * (44/28) * fracao_ms)
    
    # =============================================================================
    # CÁLCULO DAS EMISSÕES EVITADAS
    # =============================================================================
    
    # Emissões em CO₂eq (kg)
    emissao_aterro_kgco2eq = (emissoes_CH4_aterro * GWP_CH4_20 + 
                             emissao_N2O_aterro * GWP_N2O_20)
    
    emissao_vermi_kgco2eq = (emissoes_CH4_vermi * GWP_CH4_20 + 
                            emissoes_N2O_vermi * GWP_N2O_20)
    
    # Emissões evitadas (t CO₂eq)
    emissões_evitadas_tco2eq = (emissao_aterro_kgco2eq - emissao_vermi_kgco2eq) / 1000
    
    # Retornar todos os componentes do cálculo
    return {
        'residuo_kg': residuo_kg,
        'emissoes_CH4_aterro': emissoes_CH4_aterro,
        'emissoes_N2O_aterro': emissao_N2O_aterro,
        'emissoes_CH4_vermi': emissoes_CH4_vermi,
        'emissoes_N2O_vermi': emissoes_N2O_vermi,
        'emissao_aterro_kgco2eq': emissao_aterro_kgco2eq,
        'emissao_vermi_kgco2eq': emissao_vermi_kgco2eq,
        'emissoes_evitadas_tco2eq': emissões_evitadas_tco2eq,
        'parametros': {
            'capacidade_litros': capacidade_litros,
            'densidade_kg_l': densidade_kg_l,
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

def calcular_emissoes_evitadas_reator(capacidade_litros, densidade_kg_l=0.5):
    """
    Versão simplificada para uso geral
    """
    resultado = calcular_emissoes_evitadas_reator_detalhado(capacidade_litros, densidade_kg_l)
    return resultado['residuo_kg'], resultado['emissoes_evitadas_tco2eq']

def processar_reatores_cheios(df_reatores, df_escolas, densidade_kg_l=0.5):
    """
    Processa os reatores cheios e calcula emissões evitadas usando modelo científico
    Considera APENAS caixas de processamento (exclui caixa de biofertilizante)
    """
    # Filtrar reatores que já encheram e são de processamento
    reatores_cheios = df_reatores[
        (df_reatores['data_encheu'].notna()) & 
        (df_reatores['tipo_caixa'] == 'Processamento')
    ].copy()
    
    if reatores_cheios.empty:
        return pd.DataFrame(), 0, 0, 0
    
    # Calcular para cada reator
    resultados = []
    total_residuo = 0
    total_emissoes_evitadas = 0
    total_caixas_processamento = len(reatores_cheios)
    
    for _, reator in reatores_cheios.iterrows():
        capacidade = reator['capacidade_litros'] if 'capacidade_litros' in reator else 50  # Padrão 50L por caixa
        residuo_kg, emissoes_evitadas = calcular_emissoes_evitadas_reator(capacidade, densidade_kg_l)
        
        resultados.append({
            'id_reator': reator['id_reator'],
            'id_escola': reator['id_escola'],
            'data_encheu': reator['data_encheu'],
            'capacidade_litros': capacidade,
            'tipo_caixa': reator['tipo_caixa'],
            'residuo_kg': residuo_kg,
            'emissoes_evitadas_tco2eq': emissoes_evitadas
        })
        
        total_residuo += residuo_kg
        total_emissoes_evitadas += emissoes_evitadas
    
    df_resultados = pd.DataFrame(resultados)
    
    # Juntar com informações da escola
    df_resultados = df_resultados.merge(
        df_escolas[['id_escola', 'nome_escola']], 
        on='id_escola', 
        how='left'
    )
    
    return df_resultados, total_residuo, total_emissoes_evitadas, total_caixas_processamento

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

# Inicializar session state
inicializar_session_state()

# Carregar dados
df_escolas, df_reatores = carregar_dados_excel(URL_EXCEL)

# Sidebar
exibir_cotacao_carbono()

with st.sidebar:
    st.header("⚙️ Parâmetros de Cálculo")
    
    # Parâmetros técnicos
    densidade_residuo = st.slider(
        "Densidade do resíduo (kg/litro)",
        min_value=0.3,
        max_value=0.8,
        value=0.5,
        step=0.05,
        help="Densidade média dos resíduos orgânicos"
    )
    
    # Seleção de escola
    escolas_options = ["Todas as escolas"] + df_escolas['id_escola'].tolist()
    escola_selecionada = st.selectbox("Selecionar escola", escolas_options)
    
    # Configuração do cálculo de exemplo
    st.header("🧮 Cálculo de Exemplo")
    capacidade_exemplo = st.slider(
        "Capacidade por caixa de processamento (litros)",
        min_value=25,
        max_value=100,
        value=50,
        step=5,
        help="Capacidade de cada caixa de processamento de resíduos"
    )

# =============================================================================
# EXIBIÇÃO DOS DADOS E CÁLCULOS
# =============================================================================

st.header("📊 Dashboard de Vermicompostagem")

# Informações do sistema
st.info("""
**🏗️ Sistema de Vermicompostagem:**
- Cada sistema possui **4 caixas totalizando 200L**
- **3 caixas para processamento** de resíduos (150L)
- **1 caixa coletora** de biofertilizante (50L) - *não entra no cálculo de resíduos*
- Cada caixa de processamento tem capacidade de **50 litros**
- A caixa de biofertilizante coleta o líquido fertilizante (biowash)
""")

# Métricas gerais
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_escolas = len(df_escolas)
    st.metric("Total de Escolas", formatar_br(total_escolas, 0))

with col2:
    total_reatores = len(df_reatores)
    st.metric("Total de Caixas", formatar_br(total_reatores, 0))

with col3:
    # Contar apenas caixas de processamento
    caixas_processamento = len(df_reatores[df_reatores['tipo_caixa'] == 'Processamento'])
    st.metric("Caixas de Processamento", formatar_br(caixas_processamento, 0))

with col4:
    # Contar apenas caixas de biofertilizante
    caixas_biofertilizante = len(df_reatores[df_reatores['tipo_caixa'] == 'Biofertilizante'])
    st.metric("Caixas Biofertilizante", formatar_br(caixas_biofertilizante, 0))

# Processar cálculos - APENAS CAIXAS DE PROCESSAMENTO
if escola_selecionada != "Todas as escolas":
    reatores_filtrados = df_reatores[df_reatores['id_escola'] == escola_selecionada]
    escolas_filtradas = df_escolas[df_escolas['id_escola'] == escola_selecionada]
else:
    reatores_filtrados = df_reatores
    escolas_filtradas = df_escolas

reatores_processados, total_residuo, total_emissoes, total_caixas_processamento = processar_reatores_cheios(
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

# Calcular exemplo detalhado para UMA caixa
resultado_detalhado_individual = calcular_emissoes_evitadas_reator_detalhado(capacidade_exemplo, densidade_residuo)

# Calcular exemplo detalhado para TODAS as caixas de processamento
if not reatores_processados.empty:
    capacidade_total_sistema = total_caixas_processamento * capacidade_exemplo
    residuo_total_sistema = capacidade_total_sistema * densidade_residuo
    resultado_detalhado_total = calcular_emissoes_evitadas_reator_detalhado(capacidade_total_sistema, densidade_residuo)
else:
    capacidade_total_sistema = 3 * capacidade_exemplo  # 3 caixas de processamento padrão
    residuo_total_sistema = capacidade_total_sistema * densidade_residuo
    resultado_detalhado_total = calcular_emissoes_evitadas_reator_detalhado(capacidade_total_sistema, densidade_residuo)

col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 Por Caixa Individual")
    st.write(f"**Capacidade da caixa:** {formatar_br(capacidade_exemplo, 0)} L")
    st.write(f"**Densidade do resíduo:** {formatar_br(densidade_residuo, 2)} kg/L")
    st.write(f"**Massa de resíduos por caixa:** {formatar_br(resultado_detalhado_individual['residuo_kg'], 1)} kg")
    st.write(f"**Emissões evitadas por caixa:** {formatar_tco2eq(resultado_detalhado_individual['emissoes_evitadas_tco2eq'])}")
    
    # Valor financeiro individual
    valor_individual_eur = calcular_valor_creditos(
        resultado_detalhado_individual['emissoes_evitadas_tco2eq'], 
        preco_carbono_eur, 
        "€"
    )
    valor_individual_brl = calcular_valor_creditos(
        resultado_detalhado_individual['emissoes_evitadas_tco2eq'], 
        preco_carbono_eur, 
        "R$", 
        taxa_cambio
    )
    
    st.metric(
        "Valor por caixa", 
        formatar_moeda_br(valor_individual_brl),
        help=f"Valor em Reais (€ {formatar_br(valor_individual_eur, 2)})"
    )

with col2:
    st.subheader("📊 Sistema Completo")
    st.write(f"**Nº de caixas de processamento:** {formatar_br(total_caixas_processamento, 0)}")
    st.write(f"**Capacidade total do sistema:** {formatar_br(capacidade_total_sistema, 0)} L")
    st.write(f"**Massa total de resíduos:** {formatar_br(residuo_total_sistema, 1)} kg")
    st.write(f"**Emissões evitadas totais:** {formatar_tco2eq(resultado_detalhado_total['emissoes_evitadas_tco2eq'])}")
    
    # Valor financeiro total
    valor_total_eur = calcular_valor_creditos(
        resultado_detalhado_total['emissoes_evitadas_tco2eq'], 
        preco_carbono_eur, 
        "€"
    )
    valor_total_brl = calcular_valor_creditos(
        resultado_detalhado_total['emissoes_evitadas_tco2eq'], 
        preco_carbono_eur, 
        "R$", 
        taxa_cambio
    )
    
    st.metric(
        "Valor total do sistema", 
        formatar_moeda_br(valor_total_brl),
        help=f"Valor em Reais (€ {formatar_br(valor_total_eur, 2)})"
    )

# =============================================================================
# RESULTADOS FINANCEIROS CONSISTENTES
# =============================================================================

st.header("💰 Créditos de Carbono Computados - Sistema Real")

if reatores_processados.empty:
    st.info("ℹ️ Nenhuma caixa de processamento cheia encontrada. Os créditos serão calculados quando as caixas encherem.")
else:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Caixas Processadas",
            formatar_br(len(reatores_processados), 0)
        )
    
    with col2:
        st.metric(
            "Resíduo Processado",
            f"{formatar_br(total_residuo, 1)} kg"
        )
    
    with col3:
        st.metric(
            "Emissões Evitadas",
            formatar_tco2eq(total_emissoes)
        )
    
    with col4:
        st.metric(
            "Valor dos Créditos",
            formatar_moeda_br(valor_brl)
        )

# Tabela de reatores com informações completas
st.header("📋 Detalhes das Caixas por Escola")

# Juntar com nomes das escolas
reatores_display = reatores_filtrados.merge(
    df_escolas[['id_escola', 'nome_escola']], 
    on='id_escola', 
    how='left'
)

# Selecionar colunas para mostrar
colunas_mostrar = ['nome_escola', 'id_reator', 'tipo_caixa', 'status_reator', 'data_ativacao', 'data_encheu', 'capacidade_litros']

st.dataframe(reatores_display[colunas_mostrar], use_container_width=True)

# Tabela detalhada de créditos (se houver reatores processados)
if not reatores_processados.empty:
    st.header("📊 Detalhamento dos Créditos por Caixa")
    
    df_detalhes = reatores_processados[[
        'nome_escola', 'id_reator', 'tipo_caixa', 'data_encheu', 'capacidade_litros', 
        'residuo_kg', 'emissoes_evitadas_tco2eq'
    ]].copy()
    
    # Formatar valores no padrão brasileiro
    df_detalhes_formatado = df_detalhes.copy()
    df_detalhes_formatado['residuo_kg'] = df_detalhes_formatado['residuo_kg'].apply(lambda x: formatar_br(x, 1))
    df_detalhes_formatado['emissoes_evitadas_tco2eq'] = df_detalhes_formatado['emissoes_evitadas_tco2eq'].apply(lambda x: formatar_tco2eq(x))
    df_detalhes_formatado['capacidade_litros'] = df_detalhes_formatado['capacidade_litros'].apply(lambda x: formatar_br(x, 0))
    
    st.dataframe(df_detalhes_formatado, use_container_width=True)

# Gráfico de status dos reatores
st.header("📈 Status das Caixas")

# Separar por tipo de caixa
status_count_processamento = reatores_filtrados[reatores_filtrados['tipo_caixa'] == 'Processamento']['status_reator'].value_counts()
status_count_biofertilizante = reatores_filtrados[reatores_filtrados['tipo_caixa'] == 'Biofertilizante']['status_reator'].value_counts()

col1, col2 = st.columns(2)

with col1:
    # Formatar labels com números brasileiros
    labels_formatados_processamento = []
    for status, count in status_count_processamento.items():
        labels_formatados_processamento.append(f"{status} ({formatar_br(count, 0)})")

    fig1 = px.pie(
        values=status_count_processamento.values,
        names=labels_formatados_processamento,
        title="Caixas de Processamento"
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    # Formatar labels com números brasileiros
    labels_formatados_biofertilizante = []
    for status, count in status_count_biofertilizante.items():
        labels_formatados_biofertilizante.append(f"{status} ({formatar_br(count, 0)})")

    fig2 = px.pie(
        values=status_count_biofertilizante.values,
        names=labels_formatados_biofertilizante,
        title="Caixas de Biofertilizante"
    )
    st.plotly_chart(fig2, use_container_width=True)

# Informações adicionais sobre a metodologia científica
with st.expander("🔬 Metodologia Científica de Cálculo"):
    st.markdown("""
    **📊 Metodologia de Cálculo Baseada em Referências Científicas:**
    
    **Cenário Base (Aterro Sanitário):**
    - **Metano (CH4):** IPCC (2006), UNFCCC (2016), Wang et al. (2023)
    - **Óxido Nitroso (N2O):** Wang et al. (2017)
    - **Fórmula IPCC:** DOC × DOCf × MCF × F × (16/12) × (1 - Ri) × (1 - OX)
    
    **Cenário Projeto (Vermicompostagem):**
    - **Metano e Óxido Nitroso:** Yang et al. (2017)
    - **Fatores específicos para compostagem com minhocas**
    
    **Parâmetros Utilizados:**
    - **TOC (Carbono Orgânico Total):** 43,6% (Yang et al. 2017)
    - **TN (Nitrogênio Total):** 14,2 g/kg (Yang et al. 2017)
    - **CH4-C/TOC:** 0,13% (fração do carbono emitida como metano)
    - **N2O-N/TN:** 0,92% (fração do nitrogênio emitida como óxido nitroso)
    - **GWP-20 (IPCC AR6):** CH4 = 79,7; N2O = 273
    
    **🏗️ Sistema de Vermicompostagem:**
    - Cada sistema: 4 caixas (200L total)
    - 3 caixas para processamento (150L)
    - 1 caixa para biofertilizante (50L) - não conta no cálculo
    - Capacidade por caixa: 50 litros
    - Densidade do resíduo: 0,5 kg/L
    - Massa por caixa: 25 kg
    - Massa total por sistema: 75 kg
    """)

# Botão para atualizar dados
if st.button("🔄 Atualizar Dados do Excel"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")
st.markdown("""
**♻️ Sistema de Vermicompostagem - Ribeirão Preto/SP**  
*Cálculos baseados em metodologia científica validada - Dados carregados de: Controladoria-Compostagem-nas-Escolas*
""")
