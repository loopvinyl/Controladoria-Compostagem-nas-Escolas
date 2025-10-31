@st.cache_data
def carregar_dados_excel(url):
    """Carrega os dados REAIS do Excel do GitHub"""
    try:
        loading_placeholder = st.empty()
        loading_placeholder.info("📥 Carregando dados do Excel...")
        
        # Primeiro, vamos listar todas as abas disponíveis para diagnóstico
        excel_file = pd.ExcelFile(url)
        st.info(f"📋 Abas disponíveis no Excel: {excel_file.sheet_names}")
        
        # Agora ler as abas específicas
        df_escolas = pd.read_excel(url, sheet_name='escolas')
        df_reatores = pd.read_excel(url, sheet_name='reatores')
        
        loading_placeholder.empty()
        st.success(f"✅ Dados carregados: {len(df_escolas)} escolas e {len(df_reatores)} reatores")
        
        # Restante do código de conversão de datas...
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
        if 'loading_placeholder' in locals():
            loading_placeholder.empty()
        st.error(f"❌ Erro ao carregar dados do Excel: {e}")
        
        # Diagnóstico mais detalhado
        try:
            excel_file = pd.ExcelFile(url)
            st.error(f"📋 Abas encontradas: {excel_file.sheet_names}")
            st.error("🔍 Procurando por 'reatores' nas abas...")
            for sheet in excel_file.sheet_names:
                if 'reator' in sheet.lower():
                    st.error(f"→ Possível match: '{sheet}'")
        except:
            st.error("❌ Não foi possível acessar o arquivo Excel")
            
        return pd.DataFrame(), pd.DataFrame()
