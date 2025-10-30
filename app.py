import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import numpy as np
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import seaborn as sns

# Configuração da página
st.set_page_config(
    page_title="Vermicompostagem - Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Vermicompostagem nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo de emissões para resíduos orgânicos**")

# URL do Excel no GitHub
URL_EXCEL = "https://github.com/loopvinyl/vermicompostagem-ribeirao-preto/raw/main/dados_vermicompostagem.xlsx"

# =============================================================================
# FUNÇÕES DE COTAÇÃO DO CARBONO (MANTIDAS)
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
# FUNÇÕES DE CÁLCULO BASEADAS NO SCRIPT FORNECIDO
# =============================================================================

def calcular_emissoes_aterro_escolas(residuo_kg, umidade=0.85, temperatura=25, doc=0.15, dias_simulacao=365*20):
    """
    Calcula emissões de aterro para resíduos de escolas baseado no script fornecido
    """
    # Parâmetros fixos do script
    MCF = 1
    F = 0.5
    OX = 0.1
    Ri = 0.0
    k_ano = 0.06
    
    # Cálculo do DOCf baseado na temperatura
    docf_calc = 0.0147 * temperatura + 0.28
    
    # Potencial de CH4 por kg de resíduo
    potencial_CH4_por_kg = doc * docf_calc * MCF * F * (16/12) * (1 - Ri) * (1 - OX)
    potencial_CH4_total = residuo_kg * potencial_CH4_por_kg
    
    # Emissões de CH4 ao longo do tempo (modelo de decaimento)
    t = np.arange(1, dias_simulacao + 1, dtype=float)
    kernel_ch4 = np.exp(-k_ano * (t - 1) / 365.0) - np.exp(-k_ano * t / 365.0)
    emissoes_CH4 = potencial_CH4_total * kernel_ch4
    
    # Emissões de N2O (simplificado)
    fator_umid = (1 - umidade) / (1 - 0.55)
    E_medio = 2.0  # Valor médio para resíduos orgânicos
    E_medio_ajust = E_medio * fator_umid
    emissao_diaria_N2O = (E_medio_ajust * (44/28) / 1_000_000) * residuo_kg
    
    # Perfil temporal do N2O
    PERFIL_N2O = {1: 0.10, 2: 0.30, 3: 0.40, 4: 0.15, 5: 0.05}
    kernel_n2o = np.array([PERFIL_N2O.get(d, 0) for d in range(1, 6)], dtype=float)
    emissoes_N2O = emissao_diaria_N2O * kernel_n2o.sum()
    
    # GWP (IPCC AR6)
    GWP_CH4_20 = 79.7
    GWP_N2O_20 = 273
    
    # Converter para tCO₂eq
    total_ch4_tco2eq = (emissoes_CH4.sum() * GWP_CH4_20) / 1000
    total_n2o_tco2eq = (emissoes_N2O * GWP_N2O_20) / 1000
    
    total_aterro_tco2eq = total_ch4_tco2eq + total_n2o_tco2eq
    
    return total_aterro_tco2eq

def calcular_emissoes_compostagem_escolas(residuo_kg, umidade=0.85, dias_compostagem=50):
    """
    Calcula emissões de compostagem para resíduos de escolas
    """
    # Parâmetros para resíduos orgânicos de escolas (similares aos do script)
    TOC = 0.436  # Fração de carbono orgânico total
    TN = 14.2 / 1000  # Fração de nitrogênio total
    CH4_C_FRAC = 0.13 / 100  # Fração do TOC emitida como CH4-C
    N2O_N_FRAC = 0.92 / 100  # Fração do TN emitida como N2O-N
    
    fracao_ms = 1 - umidade
    
    # Emissões totais
    ch4_total = residuo_kg * (TOC * CH4_C_FRAC * (16/12) * fracao_ms)
    n2o_total = residuo_kg * (TN * N2O_N_FRAC * (44/28) * fracao_ms)
    
    # GWP (IPCC AR6)
    GWP_CH4_20 = 79.7
    GWP_N2O_20 = 273
    
    # Converter para tCO₂eq
    total_ch4_tco2eq = (ch4_total * GWP_CH4_20) / 1000
    total_n2o_tco2eq = (n2o_total * GWP_N2O_20) / 1000
    
    total_compost_tco2eq = total_ch4_tco2eq + total_n2o_tco2eq
    
    return total_compost_tco2eq

def calcular_emissoes_evitadas_reator(capacidade_litros, densidade_kg_l=0.5, umidade=0.85, temperatura=25):
    """
    Calcula emissões evitadas para um reator cheio usando a metodologia do script
    """
    residuo_kg = capacidade_litros * densidade_kg_l
    
    # Emissões do cenário base (aterro)
    emissões_aterro = calcular_emissoes_aterro_escolas(residuo_kg, umidade, temperatura)
    
    # Emissões do cenário projeto (compostagem)
    emissões_compostagem = calcular_emissoes_compostagem_escolas(residuo_kg, umidade)
    
    # Emissões evitadas
    emissões_evitadas = emissões_aterro - emissões_compostagem
    
    return residuo_kg, emissões_evitadas

# =============================================================================
# FUNÇÕES DE CARREGAMENTO E PROCESSAMENTO
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

@st.cache_data
def carregar_dados_excel(url):
    """Carrega os dados do Excel do GitHub"""
    try:
        # Ler as abas
        df_escolas = pd.read_excel(url, sheet_name='escolas')
        df_reatores = pd.read_excel(url, sheet_name='reatores')
        
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
        return None, None

def processar_reatores_cheios(df_reatores, df_escolas, densidade_kg_l=0.5, umidade=0.85, temperatura=25):
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
        residuo_kg, emissoes_evitadas = calcular_emissoes_evitadas_reator(
            capacidade, densidade_kg_l, umidade, temperatura
        )
        
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

def criar_serie_temporal(df_reatores_processados):
    """
    Cria série temporal acumulada das emissões evitadas
    """
    if df_reatores_processados.empty:
        return pd.DataFrame()
    
    # Agrupar por mês
    df_reatores_processados['mes_ano'] = df_reatores_processados['data_encheu'].dt.to_period('M')
    
    serie_mensal = df_reatores_processados.groupby('mes_ano').agg({
        'emissoes_evitadas_tco2eq': 'sum'
    }).reset_index()
    
    serie_mensal['mes_ano'] = serie_mensal['mes_ano'].dt.to_timestamp()
    serie_mensal['emissoes_acumuladas'] = serie_mensal['emissoes_evitadas_tco2eq'].cumsum()
    
    return serie_mensal

# =============================================================================
# FUNÇÕES DE FORMATAÇÃO
# =============================================================================

def formatar_br(numero):
    """Formata números no padrão brasileiro"""
    if pd.isna(numero):
        return "N/A"
    numero = round(numero, 2)
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def br_format(x, pos):
    """Formatação para eixos de gráficos"""
    if x == 0:
        return "0"
    if abs(x) < 0.01:
        return f"{x:.1e}".replace(".", ",")
    if abs(x) >= 1000:
        return f"{x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

# Inicializar e carregar
inicializar_session_state()
df_escolas, df_reatores = carregar_dados_excel(URL_EXCEL)

if df_escolas is None or df_reatores is None:
    st.error("Não foi possível carregar os dados do Excel")
    st.stop()

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
    
    umidade = st.slider(
        "Umidade do resíduo (%)",
        min_value=70,
        max_value=95,
        value=85,
        step=1,
        help="Teor de umidade dos resíduos"
    ) / 100.0
    
    temperatura = st.slider(
        "Temperatura média (°C)",
        min_value=15,
        max_value=35,
        value=25,
        step=1,
        help="Temperatura ambiente para cálculo das emissões"
    )
    
    # Seleção de escola
    escolas_options = ["Todas as escolas"] + df_escolas['id_escola'].tolist()
    escola_selecionada = st.selectbox("Selecionar escola", escolas_options)
    
    if st.button("🧮 Calcular Créditos de Carbono", type="primary"):
        st.session_state.calcular_creditos = True

# =============================================================================
# CÁLCULOS E EXIBIÇÃO
# =============================================================================

if st.session_state.get('calcular_creditos', False):
    with st.spinner('Calculando créditos de carbono...'):
        # Filtrar dados conforme seleção
        if escola_selecionada != "Todas as escolas":
            reatores_filtrados = df_reatores[df_reatores['id_escola'] == escola_selecionada]
            escolas_filtradas = df_escolas[df_escolas['id_escola'] == escola_selecionada]
        else:
            reatores_filtrados = df_reatores
            escolas_filtradas = df_escolas
        
        # Processar reatores cheios
        reatores_processados, total_residuo, total_emissoes = processar_reatores_cheios(
            reatores_filtrados, escolas_filtradas, densidade_residuo, umidade, temperatura
        )
        
        # Criar série temporal
        serie_temporal = criar_serie_temporal(reatores_processados)
        
        # Calcular valores financeiros
        preco_carbono_eur = st.session_state.preco_carbono
        taxa_cambio = st.session_state.taxa_cambio
        
        valor_eur = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "€")
        valor_brl = calcular_valor_creditos(total_emissoes, preco_carbono_eur, "R$", taxa_cambio)
        
        # =============================================================================
        # EXIBIÇÃO DOS RESULTADOS
        # =============================================================================
        
        st.header("📊 Créditos de Carbono Computados")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Reatores Processados",
                f"{len(reatores_processados)}",
                "Total de ciclos completos"
            )
        
        with col2:
            st.metric(
                "Resíduo Processado",
                f"{total_residuo:,.0f} kg",
                f"{total_residuo/1000:.1f} ton"
            )
        
        with col3:
            st.metric(
                "Emissões Evitadas",
                f"{total_emissoes:.3f} tCO₂eq",
                "Total acumulado"
            )
        
        with col4:
            st.metric(
                "Valor dos Créditos",
                f"R$ {valor_brl:,.2f}",
                f"€ {valor_eur:,.2f}"
            )
        
        # Tabela detalhada
        if not reatores_processados.empty:
            st.subheader("🧮 Detalhamento por Reator")
            
            colunas_detalhes = ['nome_escola', 'id_reator', 'data_encheu', 'capacidade_litros', 'residuo_kg', 'emissoes_evitadas_tco2eq']
            df_detalhes = reatores_processados[colunas_detalhes].copy()
            df_detalhes['residuo_kg'] = df_detalhes['residuo_kg'].round(1)
            df_detalhes['emissoes_evitadas_tco2eq'] = df_detalhes['emissoes_evitadas_tco2eq'].round(4)
            
            st.dataframe(df_detalhes, use_container_width=True)
        
        # Série temporal
        if not serie_temporal.empty:
            st.subheader("📈 Evolução das Emissões Evitadas")
            
            fig = px.area(
                serie_temporal, 
                x='mes_ano', 
                y='emissoes_acumuladas',
                title='Acumulado de Emissões Evitadas ao Longo do Tempo'
            )
            fig.update_layout(
                xaxis_title='Mês/Ano',
                yaxis_title='Emissões Evitadas Acumuladas (tCO₂eq)'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Gráfico de comparação por escola
        if not reatores_processados.empty and escola_selecionada == "Todas as escolas":
            st.subheader("🏫 Comparação por Escola")
            
            emissoes_por_escola = reatores_processados.groupby('nome_escola').agg({
                'emissoes_evitadas_tco2eq': 'sum',
                'residuo_kg': 'sum'
            }).reset_index()
            
            fig = px.bar(
                emissoes_por_escola,
                x='nome_escola',
                y='emissoes_evitadas_tco2eq',
                title='Emissões Evitadas por Escola',
                labels={'emissoes_evitadas_tco2eq': 'Emissões Evitadas (tCO₂eq)', 'nome_escola': 'Escola'}
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        # Projeção futura
        st.subheader("🔮 Projeção Futura")
        
        # Calcular capacidade total ativa
        reatores_ativos = reatores_filtrados[reatores_filtrados['status_reator'] == 'Ativo']
        capacidade_total = reatores_ativos['capacidade_litros'].sum() if 'capacidade_litros' in reatores_ativos.columns else len(reatores_ativos) * 100
        
        col1, col2 = st.columns(2)
        with col1:
            ciclos_ano_projecao = st.slider("Ciclos/ano (projeção)", 1, 12, 6, key="proj_ciclos")
        with col2:
            anos_projecao = st.slider("Anos de projeção", 1, 10, 5, key="proj_anos")
        
        # Cálculo da projeção
        residuo_anual_proj = capacidade_total * densidade_residuo * ciclos_ano_projecao
        emissoes_anual_proj = 0
        
        # Calcular emissões anuais projetadas
        if residuo_anual_proj > 0:
            _, emissoes_anual_proj = calcular_emissoes_evitadas_reator(
                capacidade_total * ciclos_ano_projecao, densidade_residuo, umidade, temperatura
            )
        
        emissoes_total_proj = emissoes_anual_proj * anos_projecao
        
        valor_eur_proj = calcular_valor_creditos(emissoes_total_proj, preco_carbono_eur, "€")
        valor_brl_proj = calcular_valor_creditos(emissoes_total_proj, preco_carbono_eur, "R$", taxa_cambio)
        
        # Exibir projeção
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Emissões Evitadas Projetadas",
                f"{emissoes_total_proj:.3f} tCO₂eq",
                f"{anos_projecao} anos"
            )
        with col2:
            st.metric(
                "Valor Projetado (€)",
                f"€ {valor_eur_proj:,.2f}",
                f"@ €{preco_carbono_eur:.2f}/tCO₂eq"
            )
        with col3:
            st.metric(
                "Valor Projetado (R$)",
                f"R$ {valor_brl_proj:,.2f}",
                f"@ R${preco_carbono_eur * taxa_cambio:.2f}/tCO₂eq"
            )
        
        # =============================================================================
        # DOWNLOAD E DETALHES
        # =============================================================================
        
        st.subheader("📥 Exportação de Dados")
        
        if not reatores_processados.empty:
            # Preparar dados para download
            download_df = reatores_processados[[
                'nome_escola', 'id_reator', 'data_encheu', 'capacidade_litros', 
                'residuo_kg', 'emissoes_evitadas_tco2eq'
            ]].copy()
            
            csv = download_df.to_csv(index=False)
            st.download_button(
                label="📊 Download dos Créditos Computados",
                data=csv,
                file_name=f"creditos_carbono_escolas_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        # Detalhamento dos cálculos
        with st.expander("🧮 Metodologia de Cálculo"):
            st.markdown(f"""
            **📊 Metodologia Baseada no Modelo Científico:**
            
            **1. Cenário Base (Aterro Sanitário):**
            - Modelo de decaimento exponencial para emissões de CH4
            - Emissões de N2O baseadas em fatores específicos
            - Considera umidade, temperatura e DOC (Carbono Orgânico Degradável)
            - Período de simulação: 20 anos
            
            **2. Cenário Projeto (Compostagem):**
            - Emissões de CH4 e N2O durante o processo de compostagem
            - Baseado em fatores de emissão específicos para resíduos orgânicos
            - Período de compostagem: 50 dias
            
            **3. Emissões Evitadas:**
            ```
            Emissões Evitadas = Emissões_Aterro - Emissões_Compostagem
            ```
            
            **4. Parâmetros Utilizados:**
            - Densidade do resíduo: {densidade_residuo} kg/L
            - Umidade: {umidade:.1%}
            - Temperatura: {temperatura}°C
            - DOC: 0.15 (valor padrão para resíduos orgânicos)
            
            **5. Valor dos Créditos:**
            ```
            Valor (€) = Emissões Evitadas (tCO₂eq) × Preço Carbono (€/tCO₂eq)
                      = {total_emissoes:.3f} × €{preco_carbono_eur:.2f}
                      = €{valor_eur:,.2f}
            ```
            
            **🌍 Referências Científicas:**
            - IPCC (2006) para metodologia de aterros
            - Yang et al. (2017) para compostagem
            - GWP do IPCC AR6 (CH4: 79.7, N2O: 273)
            """)

else:
    st.info("💡 Configure os parâmetros na barra lateral e clique em 'Calcular Créditos de Carbono' para ver os resultados.")

# =============================================================================
# INFORMAÇÕES GERAIS
# =============================================================================

st.sidebar.markdown("---")
st.sidebar.subheader("📝 Sobre o Cálculo")

with st.sidebar.expander("ℹ️ Informações"):
    st.markdown("""
    **🎯 Objetivo:**
    Calcular créditos de carbono baseado na compostagem de resíduos orgânicos nas escolas
    
    **📊 Metodologia:**
    - Comparação entre cenário base (aterro) e cenário projeto (compostagem)
    - Cálculo baseado em modelos científicos validados
    - Considera características específicas dos resíduos escolares
    
    **💡 Como usar:**
    1. Selecione a escola ou "Todas as escolas"
    2. Ajuste os parâmetros técnicos conforme necessário
    3. Clique em "Calcular Créditos de Carbono"
    4. Veja os resultados e faça o download dos dados
    """)

st.markdown("---")
st.markdown("""
**♻️ Sistema de Vermicompostagem - Ribeirão Preto/SP**  
*Cálculo científico de créditos de carbono baseado na compostagem de resíduos orgânicos*
""")
