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
    page_title="Compostagem - Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Compostagem nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo de emissões para resíduos orgânicos**")

# URL CORRIGIDA do Excel no GitHub
URL_EXCEL = "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem.xlsx"

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

    st.sidebar.metric(
        label=f"Preço do Carbono (tCO₂eq)",
        value=f"{st.session_state.moeda_carbono} {st.session_state.preco_carbono:.2f}",
        help=f"Fonte: {st.session_state.fonte_cotacao}"
    )
    
    st.sidebar.metric(
        label="Euro (EUR/BRL)",
        value=f"{st.session_state.moeda_real} {st.session_state.taxa_cambio:.2f}",
        help="Cotação do Euro em Reais Brasileiros"
    )
    
    preco_carbono_reais = st.session_state.preco_carbono * st.session_state.taxa_cambio
    
    st.sidebar.metric(
        label=f"Carbono em Reais (tCO₂eq)",
        value=f"R$ {preco_carbono_reais:.2f}",
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
        
        # Criar dados de exemplo
        df_escolas = pd.DataFrame({
            'id_escola': ['EMEI001', 'EMEI002'],
            'nome_escola': ['EMEI Joãozinho', 'EMEI Maria'],
            'data_implantacao': [datetime(2024, 3, 15), datetime(2024, 3, 20)],
            'status': ['Ativo', 'Ativo'],
            'ultima_visita': [datetime(2024, 5, 10), datetime(2024, 5, 12)]
        })
        
        df_reatores = pd.DataFrame({
            'id_reator': ['R001', 'R002', 'R003'],
            'id_escola': ['EMEI001', 'EMEI001', 'EMEI002'],
            'capacidade_litros': [100, 100, 100],
            'status_reator': ['Cheio', 'Ativo', 'Cheio'],
            'data_ativacao': [datetime(2024, 3, 15), datetime(2024, 3, 15), datetime(2024, 3, 20)],
            'data_encheu': [datetime(2024, 4, 20), None, datetime(2024, 4, 25)],
            'data_colheita': [None, None, None]
        })
        
        return df_escolas, df_reatores

# =============================================================================
# FUNÇÕES DE CÁLCULO SIMPLIFICADAS
# =============================================================================

def calcular_emissoes_evitadas_reator(capacidade_litros, densidade_kg_l=0.5):
    """
    Calcula emissões evitadas para um reator cheio (cálculo simplificado)
    """
    residuo_kg = capacidade_litros * densidade_kg_l
    
    # Fator de emissão simplificado (kg CO₂eq por kg de resíduo)
    # Baseado na diferença entre aterro e compostagem
    fator_emissao_evitada = 0.8  # kg CO₂eq/kg resíduo
    
    emissões_evitadas_kgco2eq = residuo_kg * fator_emissao_evitada
    emissões_evitadas_tco2eq = emissões_evitadas_kgco2eq / 1000
    
    return residuo_kg, emissões_evitadas_tco2eq

def processar_reatores_cheios(df_reatores, df_escolas, densidade_kg_l=0.5):
    """
    Processa os reatores cheios e calcula emissões evitadas
    """
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

# =============================================================================
# EXIBIÇÃO DOS DADOS E CÁLCULOS
# =============================================================================

st.header("📊 Dashboard de Compostagem com minhocas")

# Métricas gerais
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_escolas = len(df_escolas)
    st.metric("Total de Escolas", total_escolas)

with col2:
    total_reatores = len(df_reatores)
    st.metric("Total de Reatores", total_reatores)

with col3:
    reatores_cheios = len(df_reatores[df_reatores['data_encheu'].notna()])
    st.metric("Reatores Cheios", reatores_cheios)

with col4:
    reatores_ativos = len(df_reatores[df_reatores['status_reator'] == 'Ativo'])
    st.metric("Reatores Ativos", reatores_ativos)

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

# Exibir resultados financeiros
st.header("💰 Créditos de Carbono Computados")

if reatores_processados.empty:
    st.info("ℹ️ Nenhum reator cheio encontrado. Os créditos serão calculados quando os reatores encherem.")
else:
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Reatores Processados",
            f"{len(reatores_processados)}"
        )
    
    with col2:
        st.metric(
            "Resíduo Processado",
            f"{total_residuo:,.0f} kg"
        )
    
    with col3:
        st.metric(
            "Emissões Evitadas",
            f"{total_emissoes:.3f} tCO₂eq"
        )
    
    with col4:
        st.metric(
            "Valor dos Créditos",
            f"R$ {valor_brl:,.2f}"
        )

# Tabela de reatores
st.header("📋 Dados dos Reatores")

# Juntar com nomes das escolas
reatores_display = reatores_filtrados.merge(
    df_escolas[['id_escola', 'nome_escola']], 
    on='id_escola', 
    how='left'
)

# Selecionar colunas para mostrar
colunas_mostrar = ['nome_escola', 'id_reator', 'status_reator', 'data_ativacao', 'data_encheu']
if 'capacidade_litros' in reatores_display.columns:
    colunas_mostrar.append('capacidade_litros')

st.dataframe(reatores_display[colunas_mostrar], use_container_width=True)

# Tabela detalhada de créditos (se houver reatores processados)
if not reatores_processados.empty:
    st.header("🧮 Detalhamento dos Créditos")
    
    df_detalhes = reatores_processados[[
        'nome_escola', 'id_reator', 'data_encheu', 'capacidade_litros', 
        'residuo_kg', 'emissoes_evitadas_tco2eq'
    ]].copy()
    
    # Arredondar valores
    df_detalhes['residuo_kg'] = df_detalhes['residuo_kg'].round(1)
    df_detalhes['emissoes_evitadas_tco2eq'] = df_detalhes['emissoes_evitadas_tco2eq'].round(4)
    
    st.dataframe(df_detalhes, use_container_width=True)

# Gráfico de status dos reatores
st.header("📊 Status dos Reatores")

status_count = reatores_filtrados['status_reator'].value_counts()
fig = px.pie(
    values=status_count.values,
    names=status_count.index,
    title="Distribuição dos Status dos Reatores"
)
st.plotly_chart(fig, use_container_width=True)

# Informações adicionais
with st.expander("ℹ️ Sobre o Cálculo"):
    st.markdown("""
    **📊 Metodologia de Cálculo:**
    
    **Emissões Evitadas:**
    ```
    Emissões Evitadas (tCO₂eq) = Resíduo Processado (kg) × Fator de Emissão (kg CO₂eq/kg) ÷ 1000
    ```
    
    **Fator de Emissão:** 0,8 kg CO₂eq/kg de resíduo
    - Baseado na diferença entre emissões de aterro sanitário e compostagem
    - Considera a redução de metano (CH4) e óxido nitroso (N2O)
    
    **Valor dos Créditos:**
    ```
    Valor = Emissões Evitadas (tCO₂eq) × Preço do Carbono (€/tCO₂eq) × Taxa de Câmbio (R$/€)
    ```
    
    **💡 Próximos Passos:**
    - Atualize o Excel com as datas de enchimento dos reatores
    - Os cálculos serão atualizados automaticamente
    - Adicione a coluna 'capacidade_litros' para cálculos mais precisos
    """)

# Botão para atualizar dados
if st.button("🔄 Atualizar Dados do Excel"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")
st.markdown("""
**♻️ Sistema de Compostagem - Ribeirão Preto/SP**  
*Dados carregados de: Controladoria-Compostagem-nas-Escolas*
""")
