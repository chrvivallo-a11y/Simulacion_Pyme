import streamlit as st
import pandas as pd
import time
from datetime import date
from dateutil.relativedelta import relativedelta

# Importación desde tu archivo motor_simulacion.py
from motor_simulacion import com_simulacion_pyme, obtener_uf 

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Simulador Pyme BCI", page_icon="🏦", layout="wide")

st.title("🏦 Simulador Créditos Comerciales (Pyme) - BCI")
st.markdown("""
Esta versión utiliza la **Cascada de Pricing Mensualizada**: 
1. Spread Base → 2. Ajuste Colchón (+) → 3. Inclusión CF (Paso a Tasa) → 4. Desc. Segmento → 5. Desc. Perfil → 6. % Canal → 7. % Seguro.
""")

# Crear las dos pestañas (Módulos)
tab_individual, tab_masivo = st.tabs(["👤 Simulación Individual", "📁 Simulación Masiva (Batch)"])

# ==============================================================================
# MÓDULO 1: SIMULACIÓN INDIVIDUAL
# ==============================================================================
with tab_individual:
    st.header("1. Parámetros Generales")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fecha_curse = st.date_input("Fecha de Curse", value=date.today())
    
    with col2:
        valor_uf_actual = obtener_uf(fecha_curse)
        st.metric(label=f"Valor UF al {fecha_curse.strftime('%d-%m-%Y')}", 
                  value=f"${valor_uf_actual:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        
    with col3:
        fecha_maxima_pago = fecha_curse + relativedelta(months=6)
        fecha_primer_pago = st.date_input(
            "Fecha Primer Pago", 
            value=fecha_curse + relativedelta(months=1),
            min_value=fecha_curse,
            max_value=fecha_maxima_pago,
            help="Día hábil y mes de primer pago (Holgura de hasta 6 meses)."
        )

    st.markdown("---")
    st.header("2. Datos de la Operación")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        monto = st.number_input("Monto Líquido ($)", min_value=100000, value=10000000, step=1000000)
        plazo = st.number_input("Plazo (Cuotas)", min_value=3, max_value=120, value=36, step=1)
        tipo_garantia = st.selectbox("Tipo de Crédito", ["Sin Garantía (Comercial)", "Con Garantía Estatal (GGEE)"])
        
    with col_d2:
        perfil = st.selectbox("Perfil de Riesgo", ["1", "2", "3", "4", "5", "6", "7", "8"])
        segmento = st.selectbox("Segmento", ["NACE", "MEDIANA", "PEQUENA", "PYME DIGITAL", "SOCIO"])
        
    with col_d3:
        canal = st.selectbox("Canal de Curse", ["CCDD", "ASISTIDO"])
        seguro = st.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])

    es_ggee = "GGEE" in tipo_garantia

    if st.button("🚀 Calcular Simulación", type="primary", use_container_width=True):
        with st.spinner("Procesando cascada de precios mensualizada..."):
            try:
                resultado = com_simulacion_pyme(
                    in_fecha_curse=fecha_curse,
                    in_primer_venc=fecha_primer_pago,
                    in_monto_liquido=monto,
                    in_cuotas=plazo,
                    in_garantia_estatal=es_ggee,
                    in_perfil=perfil,
                    in_segmento=segmento,
                    in_canal=canal,
                    in_seguro=seguro
                )
                
                st.success("¡Simulación completada!")
                
                # --- RESULTADOS PRINCIPALES ---
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Valor Cuota", f"${resultado['valor_cuota']:,.0f}".replace(',', '.'))
                r2.metric("Monto Bruto", f"${resultado['monto_bruto']:,.0f}".replace(',', '.'))
                r3.metric("Tasa Mensual Final", f"{resultado['tasa_mensual']:.4f}%")
                r4.metric("CAE (Sernac)", f"{resultado['cae_sernac']:.2f}%")
                
                st.markdown("---")

                # ==============================================================
                # CASCADA DE PRICING (VISUALIZACIÓN MENSUAL)
                # ==============================================================
                st.subheader("🪜 Detalle de Cascada de Pricing (Tasas Mensuales)")
                
                if "detalle_cascada" in resultado:
                    df_cascada = pd.DataFrame(resultado["detalle_cascada"])
                    
                    # Formatear columnas para la tabla
                    df_viz = df_cascada.copy()
                    
                    def formatear_variacion(x):
                        if x is None or x == 0: return "-"
                        return f"{x:+.4f}%"

                    df_viz["Variación (Mes)"] = df_viz["Ajuste"].apply(formatear_variacion)
                    df_viz["Tasa Paso (Mes)"] = df_viz["Valor Mensual"].apply(lambda x: f"**{x:.4f}%**")
                    
                    st.table(df_viz[["Concepto", "Variación (Mes)", "Tasa Paso (Mes)"]])
                    
                    st.caption("Nota: Los pasos 1 y 2 operan sobre el Spread. A partir del paso 3, el Costo de Fondo se integra y el valor se convierte en Tasa.")
                
                st.markdown("---")
                
                # --- TABLA DE DESARROLLO ---
                with st.expander("📊 Ver Tabla de Desarrollo (Amortización)"):
                    if "tabla_desarrollo" in resultado:
                        df_tabla = pd.DataFrame(resultado["tabla_desarrollo"])
                        # Formatear fechas para mejor lectura
                        df_tabla["fec_ven"] = pd.to_datetime(df_tabla["fec_ven"]).dt.strftime('%d-%m-%Y')
                        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Error en el cálculo: {e}")

# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA (BATCH)
# ==============================================================================
with tab_masivo:
    st.header("Simulación por Lotes")
    st.info("Sube un archivo .csv para procesar múltiples simulaciones simultáneamente.")
    
    archivo_subido = st.file_uploader("Sube tu archivo de entrada CSV", type=["csv"])
    
    if archivo_subido is not None:
        try:
            df_input = pd.read_csv(archivo_subido, sep=None, engine='python')
            
            if st.button("▶️ Ejecutar Simulación Masiva", type="primary"):
                barra_progreso = st.progress(0)
                resultados_masivos = []
                
                for index, row in df_input.iterrows():
                    # Ejecutar motor por cada fila
                    res = com_simulacion_pyme(
                        in_fecha_curse=pd.to_datetime(row['fecha_curse']).date(),
                        in_primer_venc=pd.to_datetime(row['fecha_pago']).date(),
                        in_monto_liquido=int(row['monto']),
                        in_cuotas=int(row['plazo']),
                        in_garantia_estatal=str(row['es_ggee']).upper() in ['V', 'TRUE', '1'],
                        in_perfil=str(row['perfil']),
                        in_segmento=str(row['segmento']).upper().strip(),
                        in_canal=str(row['canal']).upper().strip(),
                        in_seguro=str(row['seguro']).upper().strip()
                    )
                    
                    # Consolidar datos de entrada con resultados clave
                    fila_res = row.to_dict()
                    fila_res.update({
                        "monto_bruto": res["monto_bruto"],
                        "valor_cuota": res["valor_cuota"],
                        "tasa_mensual": res["tasa_mensual"],
                        "cae": res["cae_sernac"]
                    })
                    resultados_masivos.append(fila_res)
                    barra_progreso.progress((index + 1) / len(df_input))
                
                df_final = pd.DataFrame(resultados_masivos)
                st.success(f"✅ Se procesaron {len(df_final)} casos con éxito.")
                st.dataframe(df_final)
                
                # Botón de descarga
                csv_data = df_final.to_csv(index=False, sep=';').encode('utf-8')
                st.download_button(
                    label="📥 Descargar Resultados en CSV",
                    data=csv_data,
                    file_name=f"Batch_Resultados_{date.today()}.csv",
                    mime="text/csv"
                )
                
        except Exception as e:
            st.error(f"Error procesando el archivo masivo: {e}")
