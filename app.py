import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from motor_simulacion import com_simulacion_pyme, obtener_uf 

st.set_page_config(page_title="Simulador Pyme BCI", page_icon="🏦", layout="wide")

st.title("🏦 Simulador Créditos Comerciales (Pyme) - BCI")
st.markdown("Política: Uso de CF tramo anterior para plazos $\ge$ 24 meses.")

tab_individual, tab_masivo = st.tabs(["👤 Simulación Individual", "📁 Simulación Masiva (Batch)"])

with tab_individual:
    st.header("1. Datos de la Operación")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        f_curse = st.date_input("Fecha de Curse", value=date.today())
        monto = st.number_input("Monto Líquido ($)", min_value=100000, value=10000000, step=1000000)
    
    with col2:
        plazo = st.number_input("Plazo (Cuotas)", min_value=3, value=24)
        segmento = st.selectbox("Segmento", ["NACE", "MEDIANA", "PEQUENA", "PYME DIGITAL", "SOCIO"])
        
    with col3:
        f_pago = st.date_input("Fecha Primer Pago", value=f_curse + relativedelta(months=1))
        perfil = st.selectbox("Perfil de Riesgo", ["1", "2", "3", "4", "5", "6", "7", "8"])

    es_ggee = st.checkbox("Garantía Estatal (GGEE)")
    seguro = st.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])

    if st.button("🚀 Calcular Simulación", type="primary", use_container_width=True):
        try:
            res = com_simulacion_pyme(f_curse, f_pago, monto, plazo, es_ggee, perfil, segmento, "CCDD", seguro)
            
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Valor Cuota", f"${res['valor_cuota']:,.0f}".replace(',', '.'))
            r2.metric("Tasa Mensual", f"{res['tasa_mensual']:.4f}%")
            r3.metric("Monto Bruto", f"${res['monto_bruto']:,.0f}".replace(',', '.'))
            r4.metric("CAE Anual", f"{res['cae_sernac']:.2f}%")

            st.subheader("🪜 Detalle de Cascada (Pricing Mensual)")
            df_c = pd.DataFrame(res["detalle_cascada"])
            df_c["Variación (Mes)"] = df_c["Ajuste"].apply(lambda x: f"{x:+.4f}%" if x and x != 0 else "-")
            df_c["Tasa Paso (Mes)"] = df_c["Valor Mensual"].apply(lambda x: f"**{x:.4f}%**")
            st.table(df_c[["Concepto", "Variación (Mes)", "Tasa Paso (Mes)"]])
            
            if plazo >= 24:
                st.success(f"✅ Política Aplicada: Se utiliza CF del tramo anterior (mes 23) para plazo de {plazo} meses.")

            with st.expander("📊 Ver Tabla de Amortización"):
                st.dataframe(pd.DataFrame(res["tabla_desarrollo"]), use_container_width=True)

        except Exception as e:
            st.error(f"Error en el cálculo: {e}")

with tab_masivo:
    st.header("Simulación por Lotes")
    up = st.file_uploader("Sube tu CSV", type="csv")
    if up:
        df_in = pd.read_csv(up, sep=None, engine='python')
        if st.button("▶️ Procesar Lote"):
            results = []
            bar = st.progress(0)
            for i, row in df_in.iterrows():
                r = com_simulacion_pyme(pd.to_datetime(row['fecha_curse']).date(), pd.to_datetime(row['fecha_pago']).date(), 
                                        int(row['monto']), int(row['plazo']), str(row['es_ggee']).upper()=='TRUE', 
                                        str(row['perfil']), str(row['segmento']), "CCDD", str(row['seguro']))
                fila = row.to_dict()
                fila.update({"cuota": r["valor_cuota"], "tasa_mensual": r["tasa_mensual"]})
                results.append(fila)
                bar.progress((i+1)/len(df_in))
            df_out = pd.DataFrame(results)
            st.dataframe(df_out)
            st.download_button("📥 Descargar Resultados", df_out.to_csv(index=False, sep=';').encode('utf-8'), "batch_pyme.csv")
