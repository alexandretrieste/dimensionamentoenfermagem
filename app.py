import streamlit as st
import pandas as pd
import math
from processamento import carregar_dados_banco, limpar_banco, processar_planilha_e_salvar, NORMA

st.set_page_config(page_title="Auditoria EBSERH", layout="wide")

def fmt(valor):
    return f"{valor:.1f}".replace('.', ',')

st.title("Painel de Auditoria de Dimensionamento")

st.sidebar.header("Parâmetros de Auditoria")
leitos_oficiais = st.sidebar.number_input("Leitos Oficiais (CNES)", min_value=1, value=10)
enf_atual = st.sidebar.number_input("Enfermeiros/Turno (Real)", min_value=0, value=0)
tec_atual = st.sidebar.number_input("Técnicos/Turno (Real)", min_value=0, value=0)

with st.sidebar.expander("Importar Planilha"):
    mes_in = st.text_input("Mês/Ano")
    uni_in = st.text_input("Unidade")
    file_in = st.file_uploader("Arquivo", type=["csv", "xlsx"])
    if st.button("Processar Dados"):
        if file_in and uni_in: processar_planilha_e_salvar(file_in, uni_in, mes_in)

if st.sidebar.button("🗑️ Limpar Banco"):
    if limpar_banco(): st.rerun()

df = carregar_dados_banco()
if not df.empty:
    u_sel = st.selectbox("Unidade", sorted(df['Unidade'].unique()))
    df_v = df[df['Unidade'] == u_sel]
    
    # PEGA OS LEITOS DA PLANILHA. SE FOR 0, USA O CNES DA BARRA LATERAL
    leitos_plan = df_v['Leitos_Planilha'].max()
    leitos_usados = leitos_plan if leitos_plan > 0 else leitos_oficiais
    
    censo_pico = df_v.groupby(['Mes_Ano', 'Dia'])['Censo_Real'].max()
    media_censo = censo_pico.mean()
    taxa_ocupacao = (media_censo / leitos_usados) * 100 if leitos_usados > 0 else 0
    prevalencia = df_v['Prevalencia'].mode()[0]
    regra = NORMA[prevalencia]
    
    # CÁLCULOS COM TRAVA PARA NÃO DAR NEGATIVO
    total_prof_seg = math.ceil(leitos_usados / regra['ratio'])
    if total_prof_seg == 0:
        enf_seg_f, tec_seg_f = 0, 0
    else:
        enf_seg_f = math.ceil(total_prof_seg * regra['enf'])
        if enf_seg_f < 1: enf_seg_f = 1
        tec_seg_f = total_prof_seg - enf_seg_f

    st.subheader(f"{u_sel} | Ocupação Média: {fmt(taxa_ocupacao)}% ({math.ceil(media_censo)} pac.)")
    st.info(f"Capacidade Considerada: {int(leitos_usados)} leitos | Prevalência: {prevalencia} ({regra['ratio_str']}; {regra['label']})")

    st.write("#### Quadro de Necessidade para Cobertura Total (100% Leitos)")
    data_equipe = {
        "Categoria": ["Enfermeiro", "Técnico de Enfermagem"],
        "Por Plantão (12h)": [f"{enf_seg_f} prof.", f"{tec_seg_f} prof."],
        "Por Dia (24h)": [f"{enf_seg_f*2} prof.", f"{tec_seg_f*2} prof."],
        "Quadro Total (RH)": [
            f"{math.ceil(((leitos_usados*regra['horas']*7*1.15)/36)*regra['enf'])} prof.", 
            f"{math.ceil(((leitos_usados*regra['horas']*7*1.15)/36)*regra['tec'])} prof."
        ]
    }
    st.table(pd.DataFrame(data_equipe))
    
    total_prof_med = math.ceil(media_censo / regra['ratio'])
    if total_prof_med == 0:
        enf_med_f, tec_med_f = 0, 0
    else:
        enf_med_f = math.ceil(total_prof_med * regra['enf'])
        if enf_med_f < 1: enf_med_f = 1
        tec_med_f = total_prof_med - enf_med_f

    st.markdown(f"""
    <div style="line-height: 1.2;">
        <strong>Cálculo Real p/ {int(leitos_usados)} leitos:</strong> Enf {fmt((leitos_usados*regra['horas']*regra['enf'])/24)} | Tec {fmt((leitos_usados*regra['horas']*regra['tec'])/24)}<br>
        <small style="color: gray;">Nota: Ratio {regra['ratio_str']} respeitando a proporção de {regra['label']}</small><br>
        <small style="color: gray;">Mínimo p/ ocupação média ({math.ceil(media_censo)} pac.): Enf {enf_med_f} | Tec {tec_med_f}</small>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    if leitos_plan > 0 and int(leitos_plan) != int(leitos_oficiais):
        st.error(f"Divergência de Leitos: Planilha ({int(leitos_plan)}) vs CNES ({leitos_oficiais})")
    elif leitos_plan == 0:
        st.warning(f"Leitos não encontrados na planilha. Usando valor do CNES ({leitos_oficiais}).")
    
    if enf_atual > 0 or tec_atual > 0:
        c1, c2 = st.columns(2)
        with c1:
            if enf_atual == enf_seg_f: st.success(f"Enfermeiro: OK ({enf_atual})")
            elif enf_atual < enf_seg_f: st.error(f"Enfermeiro: Subdimensionado (Ideal: {enf_seg_f})")
            else: st.warning(f"Enfermeiro: Superdimensionado (Ideal: {enf_seg_f})")
        with c2:
            if tec_atual == tec_seg_f: st.success(f"Técnico: OK ({tec_atual})")
            elif tec_atual < tec_seg_f: st.error(f"Técnico: Subdimensionado (Ideal: {tec_seg_f})")
            else: st.warning(f"Técnico: Superdimensionado (Ideal: {tec_seg_f})")
else:
    st.info("Aguardando upload da planilha.")