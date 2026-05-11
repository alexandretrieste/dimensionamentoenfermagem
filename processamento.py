import pandas as pd
from sqlalchemy import create_engine, text
import streamlit as st
import re

NORMA = {
    'CM':  {'horas': 4,  'enf': 0.33, 'tec': 0.67, 'ratio': 6,    'label': '33% enf. 67% téc.', 'ratio_str': '1:6'},
    'CI':  {'horas': 6,  'enf': 0.33, 'tec': 0.67, 'ratio': 4,    'label': '33% enf. 67% téc.', 'ratio_str': '1:4'},
    'CAD': {'horas': 10, 'enf': 0.36, 'tec': 0.64, 'ratio': 2.4,  'label': '36% enf. 64% téc.', 'ratio_str': '1:2,4'},
    'CSI': {'horas': 10, 'enf': 0.42, 'tec': 0.58, 'ratio': 2.4,  'label': '42% enf. 58% téc.', 'ratio_str': '1:2,4'},
    'CIt': {'horas': 18, 'enf': 0.52, 'tec': 0.48, 'ratio': 1.33, 'label': '52% enf. 48% téc.', 'ratio_str': '1:1,33'}
}
CHS, DS, IST = 36, 7, 1.15

@st.cache_resource
def get_engine():
    if "DATABASE_URL" in st.secrets:
        try:
            db_url = st.secrets["DATABASE_URL"]
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            
            engine = create_engine(db_url, pool_pre_ping=True)
            
            # Força o teste de conexão agora para capturar o erro real
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
            
        except Exception as e:
            # Mostra o erro sem a censura do Streamlit
            st.error("🚨 Falha na conexão com o Supabase. O banco local (temporário) será ativado.")
            st.error(f"Motivo técnico: {e}")
            return create_engine("sqlite:///banco_local.db")
            
    return create_engine("sqlite:///banco_local.db")

engine = get_engine()

def extrair_leitos_cabecalho(file_obj):
    try:
        file_obj.seek(0)
        topo = pd.read_excel(file_obj, nrows=2, header=None) if not file_obj.name.endswith('.csv') \
            else pd.read_csv(file_obj, nrows=2, header=None, encoding='latin1')
        texto = " ".join(topo.astype(str).values.flatten()).upper()
        match = re.search(r'(\d+)\s*LEITO', texto)
        if match: return int(match.group(1))
        numeros = [int(n) for n in re.findall(r'\d+', texto) if int(n) > 5]
        return numeros[0] if numeros else 0
    except: return 0

def calcular_dimensionamento(row):
    the = sum(row.get(k, 0) * NORMA[k]['horas'] for k in NORMA)
    if the == 0: return pd.Series([0, 0, 0, 'N/A', 0, 0, 0, 0, 0, 0])
    cargas = {k: row.get(k, 0) * NORMA[k]['horas'] for k in NORMA}
    prev = max(cargas, key=cargas.get)
    regra = NORMA[prev]
    qp_total = (the * DS * IST) / CHS
    return pd.Series([
        the, qp_total, round(qp_total, 1), prev, 
        round(qp_total * regra['enf'], 1), round(qp_total * regra['tec'], 1), 
        regra['ratio_str'], regra['enf'], regra['tec'], sum(row.get(k, 0) for k in NORMA)
    ])

def processar_planilha_e_salvar(file_obj, unidade, mes_ano):
    qtd_leitos = extrair_leitos_cabecalho(file_obj)
    file_obj.seek(0)
    df = pd.read_excel(file_obj, skiprows=1) if not file_obj.name.endswith('.csv') \
        else pd.read_csv(file_obj, skiprows=1, encoding='latin1')
    df.rename(columns={df.columns[0]: 'Dia'}, inplace=True)
    df['Dia'] = df['Dia'].ffill()
    df['Unidade'], df['Mes_Ano'], df['Leitos_Planilha'] = unidade.upper(), mes_ano, qtd_leitos
    for col in NORMA.keys():
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    res_cols = ['THE', 'QP_Calculado', 'QP_Total_Mes', 'Prevalencia', 'QP_Enf_Mes', 'QP_Tec_Mes', 'Ratio_Ref', 'Perc_Enf', 'Perc_Tec', 'Censo_Real']
    df[res_cols] = df.apply(calcular_dimensionamento, axis=1)
    
    try:
        # Tenta salvar
        df.to_sql('escalas', engine, if_exists='append', index=False)
    except Exception as e:
        # Se der erro aqui, captura e não crasha a interface
        st.error(f"Erro ao salvar os dados na tabela 'escalas': {e}")

def carregar_dados_banco():
    try:
        return pd.read_sql('SELECT * FROM escalas', engine)
    except:
        return pd.DataFrame()

def limpar_banco():
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS escalas"))
        return True
    except:
        return False