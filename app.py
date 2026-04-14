import streamlit as st
import pandas as pd
import time
from datetime import date
from dateutil.relativedelta import relativedelta

# Importación de funciones desde el motor corregido
from motor_simulacion import com_simulacion_pyme, obtener_uf 

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Simulador Pyme BCI", page_icon="🏦", layout="wide")

st.title("🏦 Simulador Créditos Comerciales (Pyme) - BCI")
st.markdown("""
**Estado del Motor:** - Cascada de Pricing Mensualizada.
- **Política Activa:** Ajuste automático de Costo de Fondo al tramo anterior para plazos $\ge$ 24 meses.
""")

# Pestañas
tab_individual, tab_masivo = st.tabs(["👤 Simulación Individual", "📁 Simulación Masiva (Batch)"])

# ==============================================================================
# MÓDULO 1: SIMULACIÓN INDIVIDUAL
# ==============================================================================
with tab_individual:
    st.header("1. Datos de la Operación")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        f_curse = st.date_input("Fecha de Curse", value=date.today())
        monto = st.number_input("Monto Líquido ($)", min_value=100000, value=10000000, step=1000000)
    
    with col2:
        plazo = st.number_input("Plazo (Cuotas)", min_value=3, max_value=120, value=24, step=1)
        segmento = st.selectbox("Segmento", ["NACE", "MEDIANA", "PEQUENA", "PYME DIGITAL", "SOCIO"])
        
    with col3:
        f_pago = st.date_input("Fecha Primer Pago", value=f_curse + relativedelta(months=1))
        perfil = st.selectbox("Perfil de Riesgo", ["1", "2", "3", "4", "5", "6", "7", "8"])

    st.markdown("---")
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        seguro = st.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])
    with col_opt2:
        es_ggee = st.checkbox("Garantía Estatal (GGEE)")

    if st.button("🚀 Calcular Simulación", type="primary", use_container_width=True):
        try:
            # Llamada al motor con la lógica de búsqueda de CF blindada
            res = com_simulacion_pyme(
                in_fecha_curse=f_curse,
                in_primer_venc=f_pago,
                in_monto_liquido=monto,
                in_cuotas=plazo,
                in_garantia_estatal=es_ggee,
                in_perfil=perfil,
                in_segmento=segmento,
                in_canal="CCDD",
                in_seguro=seguro
            )
            
            # --- SECCIÓN DE RESULTADOS ---
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Valor Cuota", f"${res['valor_cuota']:,.0f}".replace(',', '.'))
            r2.metric("Tasa Mensual", f"{res['tasa_mensual']:.4f}%")
            r3.metric("Monto Bruto", f"${res['monto_bruto']:,.0f}".replace(',', '.'))
            r4.metric("CAE Anual", f"{res['cae_sernac']:.2f}%")

            # --- CASCADA VISUAL ---
            st.subheader("🪜 Detalle de Cascada (Pricing Mensual)")
            
            df_c = pd.DataFrame(res["detalle_cascada"])
            
            # Formatear columnas
            df_c["Variación (Mes)"] = df_c["Ajuste"].apply(
                lambda x: f"{x:+.4f}%" if x and x != 0 else "-"
            )
            df_c["Tasa Paso (Mes)"] = df_c["Valor Mensual"].apply(
                lambda x: f"**{x:.4f}%**"
            )
            
            st.table(df_c[["Concepto", "Variación (Mes)", "Tasa Paso (Mes)"]])
            
            # --- FEEDBACK DE LA POLÍTICA ---
            if plazo >= 24:
                st.success(f"✅ **Política Aplicada:** Al ser un plazo de {plazo} meses, se ha forzado el uso del Costo de Fondo del tramo anterior (mes 23) para beneficiar la tasa final.")
            
            with st.expander("📊 Ver Tabla de Amortización"):
                st.dataframe(pd.DataFrame(res["tabla_desarrollo"]), use_container_width=True)

        except Exception as e:
            st.error(f"Error en el cálculo: {e}")

# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA
# ==============================================================================
with tab_masivo:
    st.header("Simulación por Lotes")
    up = st.file_uploader("Sube tu CSV", type="csv")
    
    if up:
        df_in = pd.read_csv(up, sep=None, engine='python')
        if st.button("▶️ Procesar Lote"):
            results = []
            bar = st.progress(0)
            for i, row in df_in.iterrows():
                r = com_simulacion_pyme(
                    pd.to_datetime(row['fecha_curse']).date(), 
                    pd.to_datetime(row['fecha_pago']).date(), 
                    int(row['monto']), int(row['plazo']), 
                    str(row['es_ggee']).upper()=='TRUE', 
                    str(row['perfil']), str(row['segmento']), 
                    "CCDD", str(row['seguro'])
                )
                fila = row.to_dict()
                fila.update({"cuota": r["valor_cuota"], "tasa_mensual": r["tasa_mensual"]})
                results.append(fila)
                bar.progress((i+1)/len(df_in))
            
            df_out = pd.DataFrame(results)
            st.dataframe(df_out)
            st.download_button("📥 Descargar Resultados", df_out.to_csv(index=False, sep=';').encode('utf-8'), "batch_pyme.csv")
