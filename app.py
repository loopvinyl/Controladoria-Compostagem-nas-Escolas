import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import numpy as np
from io import BytesIO
import re

# Configuração da página
st.set_page_config(
    page_title="Compostagem com Minhocas, Ribeirão Preto",
    page_icon="♻️",
    layout="wide"
)

st.title("♻️ Compostagem com Minhocas nas Escolas de Ribeirão Preto")
st.markdown("**Cálculo de créditos de carbono baseado no modelo científico de emissões para resíduos orgânicos**")

# =============================================================================
# CONFIGURAÇÕES - URL DO EXCEL
# =============================================================================

URL_EXCEL = "https://raw.githubusercontent.com/loopvinyl/Controladoria-Compostagem-nas-Escolas/main/dados_vermicompostagem_real.xlsx"

# =============================================================================
# CONFIGURAÇÕES FIXAS - DENSIDADE PADRAO
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
    if valor is None or pd.isna(valor):
        return f"{simbolo} 0,00"
    
    # Se o valor já está em formato de string com R$, converter
    if isinstance(valor, str):
        # Remover R$ e espaços, converter vírgula para ponto
        valor = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            valor = float(valor)
        except:
            valor = 0
    
    return f"{simbolo} {formatar_br(valor, casas_decimais)}"

def formatar_tco2eq(valor):
    """Formata valores de tCO₂eq no padrão brasileiro"""
    return f"{formatar_br(valor, 3)} tCO₂eq"

# =============================================================================
# NOVAS FUNÇÕES PARA CÁLCULO DE DIMENSÕES
# =============================================================================

def calcular_volume_litros(altura_cm, largura_cm, comprimento_cm):
    """Calcula volume em litros a partir das dimensões em cm"""
    if pd.isna(altura_cm) or pd.isna(largura_cm) or pd.isna(comprimento_cm):
        return None
    
    volume_cm3 = altura_cm * largura_cm * comprimento_cm
    volume_litros = volume_cm3 / 1000  # 1 litro = 1000 cm³
    return round(volume_litros, 2)

def calcular_peso_residuos(volume_litros, densidade_kg_l=DENSIDADE_PADRAO):
    """Calcula peso estimado de resíduos em kg"""
    if volume_litros is None or pd.isna(volume_litros):
        return None
    
    peso_kg = volume_litros * densidade_kg_l
    return round(peso_kg, 2)

def calcular_residuos_cozinha(num_alunos, dias_uteis=20, geracao_per_capita=0.15):
    """
    Calcula estimativa de resíduos gerados na cozinha da escola
    Parâmetros:
    - num_alunos: número de alunos na escola
    - dias_uteis: dias úteis no mês (padrão 20)
    - geracao_per_capita: geração per capita de resíduos pré-preparo (kg/aluno/dia)
    """
    res_diario = num_alunos * geracao_per_capita
    res_mensal = res_diario * dias_uteis
    return {
        'diario_kg': round(res_diario, 2),
        'mensal_kg': round(res_mensal, 2),
        'anual_kg': round(res_mensal * 10, 2)  # 10 meses letivos
    }

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
        # Usar um placeholder para a mensagem de carregamento
        loading_placeholder = st.empty()
        loading_placeholder.info("📥 Carregando dados do Excel...")
        
        # Primeiro, vamos diagnosticar as abas disponíveis
        excel_file = pd.ExcelFile(url)
        st.info(f"📋 Abas disponíveis no Excel: {excel_file.sheet_names}")
        
        # Ler as abas com os nomes corretos
        df_escolas = pd.read_excel(url, sheet_name='escolas')
        df_reatores = pd.read_excel(url, sheet_name='reatores')
        df_gastos = pd.read_excel(url, sheet_name='gastos')
        
        # Limpar a mensagem de carregamento
        loading_placeholder.empty()
        
        # Mostrar mensagem de sucesso
        st.success(f"✅ Dados carregados: {len(df_escolas)} escolas, {len(df_reatores)} reatores, {len(df_gastos)} gastos")
        
        # Converter colunas de data
        colunas_data_escolas = ['data_implantacao', 'ultima_visita']
        for col in colunas_data_escolas:
            if col in df_escolas.columns:
                df_escolas[col] = pd.to_datetime(df_escolas[col], errors='coerce')
                
        colunas_data_reatores = ['data_ativacao', 'data_encheu', 'data_colheita']
        for col in colunas_data_reatores:
            if col in df_reatores.columns:
                df_reatores[col] = pd.to_datetime(df_reatores[col], errors='coerce')
        
        # Converter coluna de data de gastos
        if 'data_compra' in df_gastos.columns:
            df_gastos['data_compra'] = pd.to_datetime(df_gastos['data_compra'], errors='coerce')
        
        # Converter valor de gastos para numérico
        if 'valor' in df_gastos.columns:
            df_gastos['valor_numerico'] = df_gastos['valor'].apply(lambda x: 
                float(str(x).replace('R$', '').replace(' ', '').replace(',', '.').replace('.', '', 1).replace(',', '.')) 
                if pd.notna(x) else 0)
        
        # Calcular volume e peso para reatores com dimensões
        df_reatores = calcular_volume_peso_reatores(df_reatores)
        
        return df_escolas, df_reatores, df_gastos
        
    except Exception as e:
        # Limpar mensagem de carregamento em caso de erro
        if 'loading_placeholder' in locals():
            loading_placeholder.empty()
        st.error(f"❌ Erro ao carregar dados do Excel: {e}")
        
        # Diagnóstico detalhado
        try:
            excel_file = pd.ExcelFile(url)
            st.error(f"📋 Abas encontradas: {excel_file.sheet_names}")
        except Exception as diag_error:
            st.error(f"❌ Erro no diagnóstico: {diag_error}")
            
        st.error("📋 Verifique se o arquivo Excel existe no repositório GitHub")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def calcular_volume_peso_reatores(df_reatores):
    """Calcula volume e peso para reatores com dimensões"""
    df = df_reatores.copy()
    
    # Verificar se temos todas as colunas de dimensões
    colunas_dimensoes = ['altura_cm', 'largura_cm', 'comprimento_cm']
    
    # Converter vírgulas para pontos nas colunas numéricas
    for col in colunas_dimensoes:
        if col in df.columns:
            # Converter para string, substituir vírgula por ponto, depois para float
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    
    if all(col in df.columns for col in colunas_dimensoes):
        # Calcular volume para linhas com todas as dimensões
        mask_dimensoes = df['altura_cm'].notna() & df['largura_cm'].notna() & df['comprimento_cm'].notna()
        
        if mask_dimensoes.any():
            # Calcular volume em litros
            df.loc[mask_dimensoes, 'volume_calculado_litros'] = (
                df.loc[mask_dimensoes, 'altura_cm'] * 
                df.loc[mask_dimensoes, 'largura_cm'] * 
                df.loc[mask_dimensoes, 'comprimento_cm']
            ) / 1000
            
            # Calcular peso estimado
            df.loc[mask_dimensoes, 'peso_estimado_kg'] = (
                df.loc[mask_dimensoes, 'volume_calculado_litros'] * DENSIDADE_PADRAO
            )
            
            # Se capacidade_litros for "???", usar o volume calculado
            if 'capacidade_litros' in df.columns:
                # Converter "???" para NaN
                df['capacidade_litros'] = df['capacidade_litros'].replace('???', np.nan)
                
                # Para reatores sem capacidade mas com dimensões, usar volume calculado
                mask_sem_capacidade = df['capacidade_litros'].isna() & mask_dimensoes
                df.loc[mask_sem_capacidade, 'capacidade_litros'] = df.loc[mask_sem_capacidade, 'volume_calculado_litros']
                
                # Converter para numérico
                df['capacidade_litros'] = pd.to_numeric(df['capacidade_litros'], errors='coerce')
    
    return df

# =============================================================================
# FUNÇÕES DE CÁLCULO CIENTÍFICO COM DENSIDADE FIXA
# =============================================================================

def calcular_emissoes_evitadas_reator_detalhado(capacidade_litros):
    """
    Calcula emissões evitadas baseado no modelo científico
    COM DENSIDADE FIXA de 0,6 kg/L para resíduos escolares
    """
    # Se capacidade_litros for None ou NaN, retornar zeros
    if pd.isna(capacidade_litros):
        capacidade_litros = 0
    
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
        capacidade = reator['capacidade_litros'] if 'capacidade_litros' in reator and pd.notna(reator['capacidade_litros']) else 0
        
        # Se não tem capacidade, tentar usar volume calculado
        if capacidade == 0 and 'volume_calculado_litros' in reator and pd.notna(reator['volume_calculado_litros']):
            capacidade = reator['volume_calculado_litros']
        
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
# ANÁLISE DE ESCOLAS ATIVAS COM REATORES ATIVOS
# =============================================================================

def analisar_escolas_ativas_com_reatores_ativos(df_escolas, df_reatores):
    """Analisa escolas ativas que possuem reatores ativos"""
    
    # Filtrar escolas ativas
    if 'status' in df_escolas.columns:
        escolas_ativas = df_escolas[df_escolas['status'].notna()].copy()
    else:
        escolas_ativas = df_escolas.copy()
    
    # Filtrar reatores ativos (qualquer texto na coluna status_reator)
    if 'status_reator' in df_reatores.columns:
        reatores_ativos = df_reatores[df_reatores['status_reator'].notna()].copy()
    else:
        reatores_ativos = pd.DataFrame()
    
    # Contar reatores ativos por escola
    if not reatores_ativos.empty and 'id_escola' in reatores_ativos.columns:
        contagem_reatores_por_escola = reatores_ativos.groupby('id_escola').size().reset_index(name='reatores_ativos')
        
        # Juntar com informações das escolas
        escolas_com_reatores_ativos = escolas_ativas.merge(
            contagem_reatores_por_escola, 
            on='id_escola', 
            how='left'
        )
        
        # Preencher NaN com 0 para escolas sem reatores ativos
        escolas_com_reatores_ativos['reatores_ativos'] = escolas_com_reatores_ativos['reatores_ativos'].fillna(0)
        
        return escolas_com_reatores_ativos
    else:
        # Se não há reatores ativos, retornar escolas com contagem zero
        escolas_ativas['reatores_ativos'] = 0
        return escolas_ativas

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

# Inicializar session state
inicializar_session_state()

# Carregar dados REAIS
df_escolas, df_reatores, df_gastos = carregar_dados_excel(URL_EXCEL)

# Verificar se os dados foram carregados
if df_escolas.empty or df_reatores.empty:
    st.error("❌ Não foi possível carregar os dados. Verifique se o arquivo Excel existe no repositório GitHub.")
    st.stop()

# Sidebar
exibir_cotacao_carbono()

with st.sidebar:
    st.header("🔍 Filtros")
    
    escolas_options = ["Todas as escolas"] + df_escolas['id_escola'].astype(str).tolist()
    escola_selecionada = st.selectbox("Selecionar escola", escolas_options)

# =============================================================================
# NOVA SEÇÃO: CALCULADORA DE CAIXAS E RESÍDUOS
# =============================================================================

st.header("📏 Calculadora de Caixas Composteiras")

tab1, tab2, tab3 = st.tabs(["📐 Calcular Volume da Caixa", "🍎 Estimar Resíduos da Cozinha", "📊 Registrar Medições"])

with tab1:
    st.subheader("Medir Dimensões da Caixa Composteira")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        altura = st.number_input("Altura (cm)", min_value=0.0, value=45.0, step=0.1, format="%.1f", key="calc_altura")
    with col2:
        largura = st.number_input("Largura (cm)", min_value=0.0, value=35.5, step=0.1, format="%.1f", key="calc_largura")
    with col3:
        comprimento = st.number_input("Comprimento (cm)", min_value=0.0, value=43.0, step=0.1, format="%.1f", key="calc_comprimento")
    
    # Calcular resultados
    volume_litros = calcular_volume_litros(altura, largura, comprimento)
    peso_estimado = calcular_peso_residuos(volume_litros)
    
    # Exibir resultados
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📦 Volume da Caixa", f"{formatar_br(volume_litros, 1)} L")
    with col2:
        st.metric("⚖️ Peso Estimado", f"{formatar_br(peso_estimado, 1)} kg")
    with col3:
        st.metric("📊 Densidade Usada", f"{DENSIDADE_PADRAO} kg/L")
    
    # Informações adicionais
    st.info(f"""
    **📝 Informações do cálculo:**
    - **Dimensões:** {altura} cm (altura) × {largura} cm (largura) × {comprimento} cm (comprimento)
    - **Fórmula do volume:** (altura × largura × comprimento) ÷ 1000 = {volume_litros} L
    - **Fórmula do peso:** volume × densidade = {volume_litros} L × {DENSIDADE_PADRAO} kg/L = {peso_estimado} kg
    """)
    
    # Botão para adicionar ao Excel
    if st.button("💾 Gerar Código para Excel", key="gerar_codigo"):
        st.code(f"""
        Colunas para adicionar no Excel (aba 'reatores'):
        
        altura_cm: {altura}
        largura_cm: {largura}
        comprimento_cm: {comprimento}
        volume_calculado_litros: {volume_litros}
        peso_estimado_kg: {peso_estimado}
        capacidade_litros: {volume_litros}
        """, language="text")

with tab2:
    st.subheader("Estimativa de Resíduos da Cozinha Escolar")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        num_alunos = st.number_input("Número de alunos", min_value=1, value=300, step=10, key="num_alunos")
    with col2:
        dias_uteis = st.number_input("Dias úteis/mês", min_value=1, max_value=31, value=20, step=1, key="dias_uteis")
    with col3:
        geracao_pp = st.number_input("Geração per capita (kg/aluno/dia)", 
                                     min_value=0.01, max_value=1.0, value=0.15, step=0.01,
                                     help="Estimativa: 150g por aluno por dia", key="geracao_pp")
    
    # Calcular estimativas
    estimativas = calcular_residuos_cozinha(num_alunos, dias_uteis, geracao_pp)
    
    st.markdown("---")
    st.subheader("📊 Estimativas de Resíduos Gerados")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📅 Resíduo Diário", f"{formatar_br(estimativas['diario_kg'], 1)} kg")
        st.caption(f"Por dia letivo")
    with col2:
        st.metric("📆 Resíduo Mensal", f"{formatar_br(estimativas['mensal_kg'], 1)} kg")
        st.caption(f"Por mês ({dias_uteis} dias úteis)")
    with col3:
        st.metric("🎓 Resíduo Anual", f"{formatar_br(estimativas['anual_kg'], 1)} kg")
        st.caption(f"Ano letivo (10 meses)")
    
    # Comparação com capacidade das caixas
    st.markdown("---")
    st.subheader("🔍 Comparação com Caixas Composteiras")
    
    # Calcular baseado nas dimensões comuns
    altura_padrao = 45.0
    largura_padrao = 35.5
    comprimento_padrao = 43.0
    
    volume_padrao = calcular_volume_litros(altura_padrao, largura_padrao, comprimento_padrao)
    capacidade_kg = calcular_peso_residuos(volume_padrao)
    
    if capacidade_kg and capacidade_kg > 0:
        caixas_diarias = estimativas['diario_kg'] / capacidade_kg
        caixas_mensais = estimativas['mensal_kg'] / capacidade_kg
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("📦 Caixas/dia", f"{formatar_br(caixas_diarias, 1)}")
            st.caption(f"Baseado em caixa padrão ({formatar_br(capacidade_kg, 1)} kg por caixa)")
        with col2:
            st.metric("📦 Caixas/mês", f"{formatar_br(caixas_mensais, 1)}")
            st.caption(f"Para processar todos os resíduos")
    
    # Recomendações
    st.markdown("---")
    st.subheader("💡 Recomendações Práticas")
    
    if 'diario_kg' in estimativas:
        if estimativas['diario_kg'] <= 20:
            st.success("✅ **Baixa geração:** 1-2 caixas médias são suficientes")
        elif estimativas['diario_kg'] <= 50:
            st.warning("⚠️ **Média geração:** Considere 3-4 caixas médias ou 2 grandes")
        else:
            st.error("🔴 **Alta geração:** Necessário sistema com 5+ caixas ou caixas grandes")

with tab3:
    st.subheader("📝 Registrar Novas Medições")
    
    with st.form("registro_medicoes"):
        col1, col2 = st.columns(2)
        
        with col1:
            id_reator = st.text_input("ID do Reator (ex: R003)", value="R003")
            id_escola = st.selectbox("Escola", df_escolas['id_escola'].unique())
            tipo_caixa = st.selectbox("Tipo de Caixa", ["Processamento", "Líquido"])
            status_reator = st.selectbox("Status", ["Enchendo", "Cheio", "Vazio", "Manutenção"])
        
        with col2:
            altura = st.number_input("Altura (cm)", min_value=0.0, value=45.0, step=0.1, format="%.1f", key="reg_altura")
            largura = st.number_input("Largura (cm)", min_value=0.0, value=35.5, step=0.1, format="%.1f", key="reg_largura")
            comprimento = st.number_input("Comprimento (cm)", min_value=0.0, value=43.0, step=0.1, format="%.1f", key="reg_comprimento")
            data_ativacao = st.date_input("Data de Ativação", value=datetime.now())
        
        observacoes = st.text_area("Observações", placeholder="Ex: Caixa nova, material utilizado, etc.")
        
        submitted = st.form_submit_button("📋 Registrar Medição")
        
        if submitted:
            # Calcular valores
            volume = calcular_volume_litros(altura, largura, comprimento)
            peso = calcular_peso_residuos(volume)
            
            st.success(f"""
            ✅ **Medição registrada com sucesso!**
            
            **Dados da caixa:**
            - ID: {id_reator}
            - Escola: {id_escola}
            - Tipo: {tipo_caixa}
            - Status: {status_reator}
            
            **Medições:**
            - Dimensões: {altura}cm × {largura}cm × {comprimento}cm
            - Volume: {formatar_br(volume, 1)} L
            - Peso estimado: {formatar_br(peso, 1)} kg
            
            **Para adicionar no Excel (aba 'reatores'):**
            ```
            id_reator: {id_reator}
            id_escola: {id_escola}
            altura_cm: {altura}
            largura_cm: {largura}
            comprimento_cm: {comprimento}
            volume_calculado_litros: {volume}
            peso_estimado_kg: {peso}
            capacidade_litros: {volume}
            tipo_caixa: {tipo_caixa}
            status_reator: {status_reator}
            data_ativacao: {data_ativacao.strftime('%d/%m/%Y')}
            observacoes: {observacoes}
            ```
            """)

# =============================================================================
# PROCESSAMENTO DOS CÁLCULOS - ANTES DA EXIBIÇÃO
# =============================================================================

# Processar cálculos ANTES de exibir
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

# Calcular total de gastos
total_gastos = df_gastos['valor_numerico'].sum() if 'valor_numerico' in df_gastos.columns else 0

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
    reatores_ativos = len(df_reatores[df_reatores['status_reator'].notna()])
    st.metric("Reatores Ativos", formatar_br(reatores_ativos, 0))

# =============================================================================
# RESULTADOS FINANCEIROS REAIS
# =============================================================================

st.header("💰 Análise Financeira e de Créditos de Carbono")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if reatores_processados.empty:
        st.metric("Reatores Processados", formatar_br(0, 0))
    else:
        st.metric("Reatores Processados", formatar_br(len(reatores_processados), 0))

with col2:
    if reatores_processados.empty:
        st.metric("Resíduo Processado", f"{formatar_br(0, 1)} kg")
    else:
        st.metric("Resíduo Processado", f"{formatar_br(total_residuo, 1)} kg")

with col3:
    if reatores_processados.empty:
        st.metric("Emissões Evitadas", formatar_tco2eq(0))
    else:
        st.metric("Emissões Evitadas", formatar_tco2eq(total_emissoes))

with col4:
    if reatores_processados.empty:
        st.metric("Valor dos Créditos", formatar_moeda_br(0))
    else:
        st.metric("Valor dos Créditos", formatar_moeda_br(valor_brl))

# Gastos
st.subheader("💰 Gastos do Projeto")

if not df_gastos.empty and 'valor_numerico' in df_gastos.columns:
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Gastos", formatar_moeda_br(total_gastos))
    
    with col2:
        if not reatores_processados.empty:
            custo_por_kg = total_gastos / total_residuo if total_residuo > 0 else 0
            st.metric("Custo por kg processado", formatar_moeda_br(custo_por_kg, casas_decimais=3))
        else:
            st.metric("Custo por kg processado", formatar_moeda_br(0))

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

# =============================================================================
# TABELAS COM DADOS REAIS
# =============================================================================

tab_escolas, tab_reatores, tab_gastos = st.tabs(["🏫 Escolas", "📦 Reatores", "💰 Gastos"])

with tab_escolas:
    st.header("📋 Dados das Escolas")
    
    # Criar cópia para formatação
    df_escolas_display = df_escolas.copy()
    
    # Formatar colunas de data para o padrão brasileiro DD/MM/YYYY
    colunas_data = ['data_implantacao', 'ultima_visita']
    for col in colunas_data:
        if col in df_escolas_display.columns:
            df_escolas_display[col] = df_escolas_display[col].dt.strftime('%d/%m/%Y')
    
    # Ordenar por data de implantação (mais recente primeiro)
    if 'data_implantacao' in df_escolas_display.columns:
        df_escolas_display = df_escolas_display.sort_values('data_implantacao', ascending=False)
    
    st.dataframe(df_escolas_display, use_container_width=True)

with tab_reatores:
    st.header("📋 Dados dos Reatores (com Dimensões)")
    
    if not df_reatores.empty:
        # Selecionar colunas para exibição
        colunas_exibicao = [
            'id_reator', 'id_escola', 'altura_cm', 'largura_cm', 'comprimento_cm',
            'volume_calculado_litros', 'peso_estimado_kg', 'capacidade_litros',
            'tipo_caixa', 'status_reator', 'data_ativacao', 'data_encheu', 
            'data_colheita', 'sólido_kg', 'líquido_litros', 'observacoes'
        ]
        
        # Filtrar apenas colunas que existem
        colunas_disponiveis = [col for col in colunas_exibicao if col in df_reatores.columns]
        df_reatores_display = df_reatores[colunas_disponiveis].copy()
        
        # Formatar datas
        colunas_data = ['data_ativacao', 'data_encheu', 'data_colheita']
        for col in colunas_data:
            if col in df_reatores_display.columns:
                df_reatores_display[col] = df_reatores_display[col].dt.strftime('%d/%m/%Y')
        
        # Formatar números
        colunas_numericas = ['altura_cm', 'largura_cm', 'comprimento_cm', 
                            'volume_calculado_litros', 'peso_estimado_kg', 
                            'capacidade_litros', 'sólido_kg', 'líquido_litros']
        
        for col in colunas_numericas:
            if col in df_reatores_display.columns:
                df_reatores_display[col] = df_reatores_display[col].apply(
                    lambda x: formatar_br(x, 1) if pd.notna(x) else "N/A"
                )
        
        # Destacar reatores com dimensões completas
        def highlight_complete(row):
            if (pd.notna(row.get('altura_cm', np.nan)) and 
                pd.notna(row.get('largura_cm', np.nan)) and 
                pd.notna(row.get('comprimento_cm', np.nan))):
                return ['background-color: #e6ffe6'] * len(row)
            return [''] * len(row)
        
        styled_df = df_reatores_display.style.apply(highlight_complete, axis=1)
        
        st.dataframe(styled_df, use_container_width=True)
        
        # Estatísticas das dimensões
        st.subheader("📊 Estatísticas das Dimensões")
        
        reatores_com_dimensoes = df_reatores.dropna(subset=['altura_cm', 'largura_cm', 'comprimento_cm'])
        
        if not reatores_com_dimensoes.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Reatores Medidos", formatar_br(len(reatores_com_dimensoes), 0))
            
            with col2:
                if 'volume_calculado_litros' in reatores_com_dimensoes.columns:
                    media_volume = reatores_com_dimensoes['volume_calculado_litros'].mean()
                    st.metric("Volume Médio", f"{formatar_br(media_volume, 1)} L")
            
            with col3:
                if 'peso_estimado_kg' in reatores_com_dimensoes.columns:
                    media_peso = reatores_com_dimensoes['peso_estimado_kg'].mean()
                    st.metric("Peso Médio Estimado", f"{formatar_br(media_peso, 1)} kg")
            
            with col4:
                # Calcular volume total
                volume_total = reatores_com_dimensoes['volume_calculado_litros'].sum() if 'volume_calculado_litros' in reatores_com_dimensoes.columns else 0
                st.metric("Volume Total", f"{formatar_br(volume_total, 1)} L")

with tab_gastos:
    st.header("💰 Registro de Gastos")
    
    if not df_gastos.empty:
        # Criar cópia para formatação
        df_gastos_display = df_gastos.copy()
        
        # Formatar data
        if 'data_compra' in df_gastos_display.columns:
            df_gastos_display['data_compra'] = df_gastos_display['data_compra'].dt.strftime('%d/%m/%Y')
        
        # Ordenar por data (mais recente primeiro)
        if 'data_compra' in df_gastos_display.columns:
            df_gastos_display = df_gastos_display.sort_values('data_compra', ascending=False)
        
        # Formatar valor
        if 'valor' in df_gastos_display.columns:
            # Já está formatado como R$
            pass
        
        st.dataframe(df_gastos_display, use_container_width=True)
        
        # Gráfico de gastos por item
        if len(df_gastos) > 1:
            st.subheader("📈 Distribuição de Gastos")
            
            # Criar DataFrame para gráfico
            df_gastos_grafico = df_gastos.copy()
            
            if 'valor_numerico' in df_gastos_grafico.columns and 'nome_gasto' in df_gastos_grafico.columns:
                fig = px.pie(
                    df_gastos_grafico, 
                    values='valor_numerico',
                    names='nome_gasto',
                    title="Distribuição dos Gastos por Item"
                )
                st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# GRÁFICOS COM DADOS REAIS
# =============================================================================

st.header("📈 Análises Gráficas")

col1, col2 = st.columns(2)

with col1:
    if 'status_reator' in df_reatores.columns:
        status_count = df_reatores['status_reator'].value_counts()
        
        labels_formatados = []
        for status, count in status_count.items():
            labels_formatados.append(f"{status} ({formatar_br(count, 0)})")

        fig = px.pie(
            values=status_count.values,
            names=labels_formatados,
            title="Status dos Reatores"
        )
        st.plotly_chart(fig, use_container_width=True)

with col2:
    if 'tipo_caixa' in df_reatores.columns:
        tipo_count = df_reatores['tipo_caixa'].value_counts()
        
        labels_tipo = []
        for tipo, count in tipo_count.items():
            labels_tipo.append(f"{tipo} ({formatar_br(count, 0)})")

        fig2 = px.pie(
            values=tipo_count.values,
            names=labels_tipo,
            title="Distribuição por Tipo de Caixa"
        )
        st.plotly_chart(fig2, use_container_width=True)

# =============================================================================
# INSTRUÇÕES PARA IMPLEMENTAÇÃO
# =============================================================================

with st.expander("📋 Guia Prático para Implementação Amanhã"):
    st.markdown("""
    ## 🚀 **PLANO DE AÇÃO PARA AMANHÃ NA ESCOLA**
    
    ### **1. 📏 MEDIÇÃO DAS CAIXAS (IMPORTANTE!)**
    
    **Materiais necessários:**
    - Fita métrica (em centímetros)
    - Caderno para anotações
    - Calculadora ou celular
    
    **Como medir:**
    1. **Altura (cm):** Da base interna até a borda superior
    2. **Largura (cm):** Medida frontal interna (lado mais curto)
    3. **Comprimento (cm):** Medida lateral interna (lado mais longo)
    
    **Exemplo das suas caixas:**
    - Altura: 45 cm
    - Largura: 35,5 cm  
    - Comprimento: 43 cm
    - **Volume:** (45 × 35,5 × 43) ÷ 1000 = 68,7 L
    
    ### **2. 🍎 ESTIMATIVA DE RESÍDUOS DA COZINHA**
    
    **Passo a passo:**
    1. **Perguntar à cozinheira:**
       - "Quantos alunos comem na escola?"
       - "Quais são os principais alimentos preparados?"
    
    2. **Acompanhar o pré-preparo (30 minutos):**
       - Separar cascas, talos, sementes em balde
       - Pesar no final: "X kg em 30 minutos"
       - Multiplicar por 2 para 1 hora
       - Multiplicar por 4 para meio período
    
    3. **Usar a calculadora do app** para projetar:
       - Resíduos diários
       - Quantas caixas serão necessárias
    
    ### **3. 📝 REGISTRO NO EXCEL**
    
    **Para cada caixa, preencher na aba 'reatores':**
    ```
    id_reator: R001, R002, R003...
    id_escola: EEI_PN
    altura_cm: 45
    largura_cm: 35,5
    comprimento_cm: 43
    volume_calculado_litros: 68,7
    peso_estimado_kg: 41,2
    capacidade_litros: 68,7
    tipo_caixa: Processamento ou Líquido
    status_reator: Enchendo, Cheio, Vazio
    data_ativacao: 28/01/2026
    data_encheu: (deixar vazio até encher)
    ```
    
    ### **4. ⚙️ MONTAGEM DO SISTEMA**
    
    **Material por caixa (aproximado):**
    - 2 kg de minhocas californianas
    - 5 kg de serragem úmida (não encharcada)
    - 2 kg de esterco seco
    - Resíduos da cozinha (iniciar com 1 kg/dia)
    
    **Ordem de montagem:**
    1. Camada de serragem no fundo (5 cm)
    2. Mistura de esterco e minhocas
    3. Mais serragem (5 cm)
    4. Primeiros resíduos (1 kg)
    5. Cobrir com serragem seca
    
    ### **5. 📋 CHECKLIST DO DIA**
    
    ✅ [ ] Medir todas as caixas disponíveis  
    ✅ [ ] Conversar com a equipe da cozinha  
    ✅ [ ] Acompanhar pré-preparo por 30 min  
    ✅ [ ] Registrar medidas no app  
    ✅ [ ] Montar pelo menos 1 caixa completa  
    ✅ [ ] Tirar fotos para documentação  
    ✅ [ ] Explicar sistema para responsável  
    
    ### **⚠️ ATENÇÃO: RESÍDUOS PERMITIDOS**
    
    **SIM ✅**
    - Cascas de frutas e verduras
    - Talos e folhas não aproveitados
    - Borra de café com filtro de papel
    - Cascas de ovos (trituradas)
    - Restos de frutas
    
    **NÃO ❌**
    - Carnes, peixes, frutos do mar
    - Laticínios (queijo, iogurte, leite)
    - Alimentos cozidos com óleo ou sal
    - Molhos, temperos fortes
    - Fezes de animais
    
    ### **📞 EM CASO DE DÚVIDAS**
    
    1. **Minhocas paradas no fundo?** Adicionar mais serragem seca
    2. **Cheiro forte?** Menos resíduos, mais serragem
    3. **Moscas?** Cobrir sempre com serragem
    4. **Minhocas fugindo?** Muito úmido ou ácido
    """)

st.markdown("---")
st.markdown("""
**♻️ Sistema de Compostagem com Minhocas - Ribeirão Preto/SP**  
**📊 Dados atualizados em tempo real do Excel**  
**💡 Pronto para implementação amanhã na escola!**
""")
