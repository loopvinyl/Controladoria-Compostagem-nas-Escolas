""")

# =============================================================================
# GRÁFICOS COM DADOS REAIS
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
- Wang et al. (2017). N₂O emissions from landfills  
- **Fator φ = 0,85 (UNFCCC, 2024) para baseline em clima úmido**  
- GWP 20 anos: CH₄=79.7, N₂O=273 (IPCC AR6)

**✅ Cálculo Corrigido:** Distribuição temporal com kernel não normalizado no aterro, acrescido do fator φ.
""")
