import streamlit as st
import pandas as pd
import time
from datetime import date
from dateutil.relativedelta import relativedelta

# Importación de funciones desde el motor
from motor_simulacion import com_simulacion_pyme, obtener_uf 

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Simulador Pyme BCI", page_icon="🏦", layout="wide")

st.title("🏦 Simulador Créditos Comerciales (Pyme) - BCI")
st.markdown("Configuración: CF tramo anterior para Plazos $\ge$ 24 meses. Cascada de pricing 100% mensualizada.")

# Pestañas
tab_individual, tab_masivo = st.tabs(["👤 Simulación Individual", "📁 Simulación Masiva (Batch)"])

# ==============================================================================
# MÓDULO 1: SIMULACIÓN INDIVIDUAL
# ==============================================================================
with tab_individual:
    st.header("1. Parámetros de la Operación")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        f_curse = st.date_input("Fecha de Curse", value=date.today())
        monto = st.number_input("Monto Líquido ($)", min_value=100000, value=10000000, step=1000000)
    
    with c2:
        val_uf = obtener_uf(f_curse)
        st.metric(f"UF al {f_curse.strftime('%d-%m-%Y')}", f"${val_uf:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        plazo = st.number_input("Plazo (Cuotas)", min_value=3, value=36)
        
    with c3:
        f_pago = st.date_input("Fecha Primer Pago", value=f_curse + relativedelta(months=1))
        es_ggee = st.checkbox("Garantía Estatal (GGEE)")

    st.markdown("---")
    st.header("2. Segmentación y Descuentos")
    d1, d2, d3 = st.columns(3)
    perfil = d1.selectbox("Perfil de Riesgo", ["1", "2", "3", "4", "5", "6", "7", "8"])
    segmento = d2.selectbox("Segmento", ["NACE", "MEDIANA", "PEQUENA", "PYME DIGITAL", "SOCIO"])
    seguro = d3.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])

    if st.button("🚀 Calcular Simulación", type="primary", use_container_width=True):
        try:
            res = com_simulacion_pyme(f_curse, f_pago, monto, plazo, es_ggee, perfil, segmento, "CCDD", seguro)
            
            # Métricas
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Valor Cuota", f"${res['valor_cuota']:,.0f}".replace(',', '.'))
            r2.metric("Monto Bruto", f"${res['monto_bruto']:,.0f}".replace(',', '.'))
            r3.metric("Tasa Mensual", f"{res['tasa_mensual']:.4f}%")
            r4.metric("CAE Anual", f"{res['cae_sernac']:.2f}%")

            # Tabla Cascada
            st.subheader("🪜 Cascada de Pricing Mensualizada")
            df_c = pd.DataFrame(res["detalle_cascada"])
            df_c["Variación (Mes)"] = df_c["Ajuste"].apply(lambda x: f"{x:+.4f}%" if x and x != 0 else "-")
            df_c["Tasa Paso (Mes)"] = df_c["Valor Mensual"].apply(lambda x: f"**{x:.4f}%**")
            st.table(df_c[["Concepto", "Variación (Mes)", "Tasa Paso (Mes)"]])
            
            if plazo >= 24:
                st.info("ℹ️ Nota: Costo de fondo aplicado del tramo anterior.")

            with st.expander("📊 Ver Tabla de Amortización"):
                st.dataframe(pd.DataFrame(res["tabla_desarrollo"]), use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")

# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA
# ==============================================================================
with tab_masivo:
    st.header("Simulación por Lotes")
    up = st.file_uploader("Sube CSV con columnas: fecha_curse, fecha_pago, monto, plazo, es_ggee, perfil, segmento, canal, seguro", type="csv")
    
    if up:
        df_in = pd.read_csv(up, sep=None, engine='python')
        if st.button("▶️ Procesar Batch"):
            results = []
            bar = st.progress(0)
            for i, row in df_in.iterrows():
                r = com_simulacion_pyme(pd.to_datetime(row['fecha_curse']).date(), pd.to_datetime(row['fecha_pago']).date(), 
                                        int(row['monto']), int(row['plazo']), str(row['es_ggee']).upper()=='TRUE', 
                                        str(row['perfil']), str(row['segmento']), str(row['canal']), str(row['seguro']))
                row_res = row.to_dict()
                row_res.update({"monto_bruto": r["monto_bruto"], "cuota": r["valor_cuota"], "tasa_mes": r["tasa_mensual"]})
                results.append(row_res)
                bar.progress((i+1)/len(df_in))
            
            df_out = pd.DataFrame(results)
            st.dataframe(df_out)
            st.download_button("📥 Descargar CSV", df_out.to_csv(index=False, sep=';').encode('utf-8'), "simulacion_batch.csv")
