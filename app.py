import streamlit as st
import pandas as pd
import time
from datetime import date
from dateutil.relativedelta import relativedelta

# Importamos el motor de simulación actualizado y utilidades
from motor_simulacion import com_simulacion_pyme, obtener_uf

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Simulador Pyme BCI", page_icon="🏦", layout="wide")

st.title("🏦 Simulador Créditos Comerciales (Pyme) - BCI")
st.markdown("Cálculo con Cascada de Pricing: Spread Base -> **Ajuste Colchón (+)** -> Descuentos -> Costo Fondo -> Tasa Mensual.")

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
        st.metric(label=f"Valor UF al {fecha_curse.strftime('%d-%m-%Y')}", value=f"${valor_uf_actual:,.2f}".replace(',', '.'))
        
    with col3:
        fecha_maxima_pago = fecha_curse + relativedelta(months=6)
        fecha_primer_pago = st.date_input(
            "Fecha Primer Pago", 
            value=fecha_curse + relativedelta(months=1),
            min_value=fecha_curse,
            max_value=fecha_maxima_pago
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
        with st.spinner("Procesando cascada de precios..."):
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
                
                st.success("¡Simulación completada con éxito!")
                
                # --- MÉTRICAS PRINCIPALES ---
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Valor Cuota", f"${resultado['valor_cuota']:,.0f}".replace(',', '.'))
                r2.metric("Monto Bruto", f"${resultado['monto_bruto']:,.0f}".replace(',', '.'))
                r3.metric("Tasa Mensual", f"{resultado['tasa_mensual']:.4f}%")
                r4.metric("CAE (Sernac)", f"{resultado['cae_sernac']:.2f}%")
                
                st.markdown("---")

                # ==============================================================
                # VISUALIZACIÓN DE CASCADA DE PRICING
                # ==============================================================
                st.subheader("🪜 Detalle de Cascada de Pricing (Evolución de Tasa)")
                
                if "detalle_cascada" in resultado:
                    datos_cascada = resultado["detalle_cascada"].copy()
                    
                    # Añadimos manualmente el paso final de Tasa Mensual
                    datos_cascada.append({
                        "Concepto": "8. TASA MENSUAL APLICADA (Tasa Anual / 12)", 
                        "Ajuste": None, 
                        "Spread Resultante": resultado['tasa_mensual']
                    })
                    
                    df_viz = pd.DataFrame(datos_cascada)
                    
                    # Formateo de los valores de la tabla
                    def formatear_ajuste(val):
                        if val is None or val == 0: return "-"
                        return f"{val:+.2f}%"

                    def formatear_resultante(fila):
                        val = fila["Spread Resultante"]
                        # Si es el paso de tasa mensual, mostramos 4 decimales
                        if "MENSUAL" in fila["Concepto"]:
                            return f"**{val:.4f}%**"
                        return f"{val:.2f}%"

                    df_viz["Variación"] = df_viz["Ajuste"].apply(formatear_ajuste)
                    df_viz["Tasa / Spread"] = df_viz.apply(formatear_resultante, axis=1)
                    
                    # Mostrar tabla estilizada
                    st.table(df_viz[["Concepto", "Variación", "Tasa / Spread"]])
                    
                    st.info("""
                    💡 **Nota sobre el Colchón:** Para plazos ≥ 24 meses, el beneficio de política se suma al spread inicial (+). 
                    Esto compensa la reducción posterior en el Costo de Fondo Neto, manteniendo la integridad del margen comercial.
                    """)
                
                st.markdown("---")
                
                # Tabla de Desarrollo
                with st.expander("📊 Ver Tabla de Desarrollo (Amortización)"):
                    if "tabla_desarrollo" in resultado:
                        df_tabla = pd.DataFrame(resultado["tabla_desarrollo"])
                        st.dataframe(df_tabla, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Error técnico en el cálculo: {e}")

# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA (BATCH)
# ==============================================================================
with tab_masivo:
    st.header("Simulación por Lotes")
    st.info("Sube un archivo CSV con las columnas: rut, fecha_curse, fecha_pago, monto, plazo, es_ggee, perfil, segmento, canal, seguro.")
    
    archivo_subido = st.file_uploader("Sube tu archivo CSV aquí", type=["csv"])
    
    if archivo_subido is not None:
        try:
            df_input = pd.read_csv(archivo_subido, sep=None, engine='python')
            if st.button("▶️ Ejecutar Simulación Masiva", type="primary"):
                barra = st.progress(0)
                resultados_masivos = []
                
                for index, row in df_input.iterrows():
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
                    fila = row.to_dict()
                    # Excluimos objetos pesados de la exportación CSV
                    fila.update({k: v for k, v in res.items() if k not in ['tabla_desarrollo', 'detalle_cascada']})
                    resultados_masivos.append(fila)
                    barra.progress((index + 1) / len(df_input))
                
                df_res = pd.DataFrame(resultados_masivos)
                st.success(f"Procesados {len(df_res)} casos.")
                st.dataframe(df_res)
                st.download_button("📥 Descargar Resultados", df_res.to_csv(index=False, sep=';').encode('utf-8'), "resultados_simulacion.csv")
        except Exception as e:
            st.error(f"Error en proceso masivo: {e}")
