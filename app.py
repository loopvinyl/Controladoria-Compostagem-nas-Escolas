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
st.markdown("**Monitoramento do sistema de compostagem com minhocas**")

# URL do Excel no GitHub
URL_EXCEL = "https://github.com/loopvinyl/vermicompostagem-ribeirao-preto/raw/main/dados_vermicompostagem.xlsx"

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
# FUNÇÕES DE CARREGAMENTO E CÁLCULO
# =============================================================================

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

def calcular_capacidade_sistema(df_reatores, escola_selecionada=None):
    """Calcula a capacidade total do sistema baseado nos reatores"""
    if escola_selecionada and escola_selecionada != "Todas":
        reatores_filtrados = df_reatores[df_reatores['id_escola'] == escola_selecionada]
    else:
        reatores_filtrados = df_reatores
    
    # Calcular capacidade total (assumindo que cada reator tem capacidade padrão se não especificado)
    if 'capacidade_litros' not in reatores_filtrados.columns:
        # Se não houver coluna de capacidade, usar valor padrão de 100L por reator
        capacidade_total = len(reatores_filtrados) * 100
    else:
        capacidade_total = reatores_filtrados['capacidade_litros'].sum()
    
    return capacidade_total, len(reatores_filtrados)

def calcular_residuo_processado(capacidade_total_litros, ciclos_ano, densidade_kg_l=0.5):
    """Calcula a quantidade total de resíduo processado por ano"""
    residuo_por_ciclo_kg = capacidade_total_litros * densidade_kg_l
    residuo_total_kg = residuo_por_ciclo_kg * ciclos_ano
    return residuo_total_kg

def calcular_emissoes_evitadas(residuo_total_kg, fator_emissao_kgco2eq_kg=0.8):
    """Calcula emissões evitadas baseado na quantidade de resíduo processado"""
    emissões_evitadas_kgco2eq = residuo_total_kg * fator_emissao_kgco2eq_kg
    emissões_evitadas_tco2eq = emissões_evitadas_kgco2eq / 1000
    return emissões_evitadas_tco2eq

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

inicializar_session_state()

# =============================================================================
# CARREGAMENTO DOS DADOS DO EXCEL
# =============================================================================

# Carregar dados do Excel
df_escolas, df_reatores = carregar_dados_excel(URL_EXCEL)

if df_escolas is None or df_reatores is None:
    st.error("""
    ❌ **Não foi possível carregar os dados do Excel. Verifique:**
    - A URL do arquivo está correta
    - As abas 'escolas' e 'reatores' existem
    - O arquivo não está corrompido
    """)
    st.stop()

# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

# Exibir cotação de carbono
exibir_cotacao_carbono()

# Sidebar com configurações
with st.sidebar:
    st.header("⚙️ Configuração do Sistema")
    
    # Seleção da escola
    escolas_options = ["Todas"] + df_escolas['id_escola'].tolist()
    escola_selecionada = st.selectbox(
        "Selecionar Escola",
        options=escolas_options,
        help="Selecione uma escola específica ou 'Todas' para ver o consolidado"
    )
    
    # Mostrar informações da escola selecionada
    if escola_selecionada != "Todas":
        escola_info = df_escolas[df_escolas['id_escola'] == escola_selecionada].iloc[0]
        st.info(f"""
        **🏫 {escola_info['nome_escola']}**
        - Status: {escola_info.get('status', 'N/A')}
        - Implantação: {escola_info.get('data_implantacao', 'N/A')}
        """)
    
    # Parâmetros do cálculo
    st.subheader("📊 Parâmetros de Cálculo")
    
    ciclos_ano = st.slider(
        "Ciclos completos por ano",
        min_value=1,
        max_value=12,
        value=6,
        step=1,
        help="Número de vezes que os reatores são completamente processados por ano"
    )
    
    densidade_residuo = st.slider(
        "Densidade do resíduo (kg/litro)",
        min_value=0.3,
        max_value=0.8,
        value=0.5,
        step=0.05,
        help="Densidade média dos resíduos de compostagem"
    )
    
    fator_emissao = st.slider(
        "Fator de emissão evitada (kg CO₂eq/kg resíduo)",
        min_value=0.5,
        max_value=1.5,
        value=0.8,
        step=0.1,
        help="Quanto de emissão é evitada por kg de resíduo compostado vs aterro"
    )
    
    anos_projecao = st.slider(
        "Anos de projeção",
        min_value=1,
        max_value=20,
        value=5,
        step=1,
        help="Período para projeção dos créditos de carbono"
    )

# =============================================================================
# CÁLCULOS PRINCIPAIS
# =============================================================================

# Calcular capacidade do sistema
capacidade_total, num_reatores = calcular_capacidade_sistema(df_reatores, escola_selecionada)

# Calcular resíduo processado
residuo_anual_kg = calcular_residuo_processado(capacidade_total, ciclos_ano, densidade_residuo)
residuo_anual_ton = residuo_anual_kg / 1000

# Calcular emissões evitadas
emissoes_evitadas_ano = calcular_emissoes_evitadas(residuo_anual_kg, fator_emissao)
emissoes_totais_evitadas = emissoes_evitadas_ano * anos_projecao

# Calcular valores financeiros
preco_carbono_eur = st.session_state.preco_carbono
taxa_cambio = st.session_state.taxa_cambio

valor_eur = calcular_valor_creditos(emissoes_totais_evitadas, preco_carbono_eur, "€")
valor_brl = calcular_valor_creditos(emissoes_totais_evitadas, preco_carbono_eur, "R$", taxa_cambio)

# =============================================================================
# EXIBIÇÃO DOS RESULTADOS
# =============================================================================

st.header("💰 Projeção de Créditos de Carbono")

# Resumo do sistema
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Sistema de Reatores",
        f"{num_reatores} reatores",
        f"Capacidade: {capacidade_total:,}L"
    )

with col2:
    st.metric(
        "Resíduo Processado/Ano",
        f"{residuo_anual_ton:.1f} ton",
        f"{residuo_anual_kg:,.0f} kg"
    )

with col3:
    st.metric(
        "Emissões Evitadas/Ano",
        f"{emissoes_evitadas_ano:.2f} tCO₂eq",
        f"Fator: {fator_emissao} kg CO₂eq/kg"
    )

# Valor financeiro
st.subheader("💵 Valor Financeiro dos Créditos")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Emissões Evitadas Totais",
        f"{emissoes_totais_evitadas:.1f} tCO₂eq",
        f"Em {anos_projecao} anos"
    )

with col2:
    st.metric(
        "Valor em Euros",
        f"€ {valor_eur:,.2f}",
        f"@ €{preco_carbono_eur:.2f}/tCO₂eq"
    )

with col3:
    st.metric(
        "Valor em Reais", 
        f"R$ {valor_brl:,.2f}",
        f"@ R${preco_carbono_eur * taxa_cambio:.2f}/tCO₂eq"
    )

# Detalhamento dos dados
st.subheader("📋 Dados do Sistema")

# Mostrar reatores
if escola_selecionada != "Todas":
    reatores_escola = df_reatores[df_reatores['id_escola'] == escola_selecionada]
else:
    reatores_escola = df_reatores

# Juntar com nomes das escolas para display
reatores_display = reatores_escola.merge(
    df_escolas[['id_escola', 'nome_escola']], 
    on='id_escola',
    how='left'
)

# Selecionar colunas para mostrar
colunas_mostrar = ['nome_escola', 'id_reator', 'status_reator', 'data_ativacao', 'data_encheu']
if 'capacidade_litros' in reatores_display.columns:
    colunas_mostrar.append('capacidade_litros')

st.dataframe(reatores_display[colunas_mostrar], use_container_width=True)

# Projeção anual
st.subheader("📈 Projeção Anual de Receita")

projecao_anual = []
for ano in range(1, anos_projecao + 1):
    emissoes_acumuladas = emissoes_evitadas_ano * ano
    valor_eur_acumulado = calcular_valor_creditos(emissoes_acumuladas, preco_carbono_eur, "€")
    valor_brl_acumulado = calcular_valor_creditos(emissoes_acumuladas, preco_carbono_eur, "R$", taxa_cambio)
    
    projecao_anual.append({
        'Ano': ano,
        'Emissões Evitadas Acumuladas (tCO₂eq)': emissoes_acumuladas,
        'Valor Acumulado (€)': valor_eur_acumulado,
        'Valor Acumulado (R$)': valor_brl_acumulado
    })

projecao_df = pd.DataFrame(projecao_anual)
st.dataframe(projecao_df, use_container_width=True)

# Gráfico de projeção
fig = px.line(
    projecao_df, 
    x='Ano', 
    y='Valor Acumulado (R$)',
    title=f'Projeção de Receita com Créditos de Carbono - {anos_projecao} anos',
    markers=True
)
fig.update_layout(
    yaxis_title='Valor Acumulado (R$)',
    xaxis_title='Ano'
)
st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# DETALHAMENTO DOS CÁLCULOS
# =============================================================================

with st.expander("🧮 Detalhamento dos Cálculos"):
    st.markdown(f"""
    **📊 Metodologia de Cálculo:**
    
    **1. Capacidade do Sistema:**
    ```
    Capacidade Total (L) = Soma da capacidade de todos os reatores ativos
    Reatores ativos: {num_reatores}
    Capacidade total: {capacidade_total:,} litros
    ```
    
    **2. Resíduo Processado:**
    ```
    Resíduo Anual (kg) = Capacidade Total (L) × Densidade (kg/L) × Ciclos/Ano
                       = {capacidade_total:,} L × {densidade_residuo} kg/L × {ciclos_ano}
                       = {residuo_anual_kg:,.0f} kg/ano = {residuo_anual_ton:.1f} ton/ano
    ```
    
    **3. Emissões Evitadas:**
    ```
    Emissões Evitadas (tCO₂eq/ano) = Resíduo Anual (kg) × Fator Emissão (kg CO₂eq/kg) ÷ 1000
                                   = {residuo_anual_kg:,.0f} kg × {fator_emissao} kg CO₂eq/kg ÷ 1000
                                   = {emissoes_evitadas_ano:.2f} tCO₂eq/ano
    ```
    
    **4. Valor dos Créditos:**
    ```
    Valor Total (€) = Emissões Totais Evitadas (tCO₂eq) × Preço Carbono (€/tCO₂eq)
                    = {emissoes_totais_evitadas:.1f} tCO₂eq × €{preco_carbono_eur:.2f}/tCO₂eq
                    = €{valor_eur:,.2f}
                    
    Valor Total (R$) = Valor (€) × Taxa Câmbio (R$/€)
                     = €{valor_eur:,.2f} × R${taxa_cambio:.2f}/€
                     = R${valor_brl:,.2f}
    ```
    
    **📚 Pressupostos:**
    - Cada reator completa {ciclos_ano} ciclos por ano
    - Densidade do resíduo: {densidade_residuo} kg/L
    - Fator de emissão evitada: {fator_emissao} kg CO₂eq/kg resíduo
    - Projeção: {anos_projecao} anos
    - Preço do carbono: €{preco_carbono_eur:.2f}/tCO₂eq ({st.session_state.fonte_cotacao})
    - Câmbio: €1 = R${taxa_cambio:.2f}
    """)

# =============================================================================
# DOWNLOAD E EXPORTAÇÃO
# =============================================================================

st.subheader("📥 Exportação de Dados")

# Criar DataFrame para download
download_df = pd.DataFrame({
    'Ano': list(range(1, anos_projecao + 1)),
    'Emissões_Evitadas_tCO2eq': [emissoes_evitadas_ano * ano for ano in range(1, anos_projecao + 1)],
    'Valor_EUR': [calcular_valor_creditos(emissoes_evitadas_ano * ano, preco_carbono_eur, "€") for ano in range(1, anos_projecao + 1)],
    'Valor_BRL': [calcular_valor_creditos(emissoes_evitadas_ano * ano, preco_carbono_eur, "R$", taxa_cambio) for ano in range(1, anos_projecao + 1)]
})

# Botão de download
csv = download_df.to_csv(index=False)
st.download_button(
    label="📊 Download da Projeção (CSV)",
    data=csv,
    file_name=f"projecao_creditos_carbono_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv"
)

# =============================================================================
# ATUALIZAÇÃO DA ESTRUTURA DO EXCEL
# =============================================================================

st.sidebar.markdown("---")
st.sidebar.subheader("🔄 Atualizar Estrutura do Excel")

with st.sidebar.expander("📝 Modelo Recomendado"):
    st.markdown("""
    **Para melhor funcionamento, seu Excel deve ter:**
    
    **Aba 'escolas':**
    - id_escola
    - nome_escola  
    - data_implantacao
    - status
    - ultima_visita
    
    **Aba 'reatores':**
    - id_reator
    - id_escola
    - capacidade_litros
    - status_reator
    - data_ativacao
    - data_encheu
    - data_colheita
    
    **💡 Dica:** Adicione a coluna 'capacidade_litros' na aba reatores para cálculos mais precisos!
    """)
    
    # Criar modelo para download
    def criar_modelo_excel():
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # ABA escolas
            df_modelo_escolas = pd.DataFrame(columns=[
                'id_escola', 'nome_escola', 'data_implantacao', 'status', 
                'ultima_visita', 'observacoes'
            ])
            df_modelo_escolas.to_excel(writer, sheet_name='escolas', index=False)
            
            # ABA reatores
            df_modelo_reatores = pd.DataFrame(columns=[
                'id_reator', 'id_escola', 'capacidade_litros', 'status_reator',
                'data_ativacao', 'data_encheu', 'data_colheita', 'observacoes'
            ])
            df_modelo_reatores.to_excel(writer, sheet_name='reatores', index=False)
        
        return output.getvalue()

    modelo_excel = criar_modelo_excel()
    st.download_button(
        label="⬇️ Baixar Modelo do Excel",
        data=modelo_excel,
        file_name="modelo_vermicompostagem_atualizado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("---")
st.markdown("""
**♻️ Sistema de Vermicompostagem - Ribeirão Preto/SP**  
*Cálculo de créditos de carbono baseado na capacidade real dos sistemas das escolas*
""")
