import streamlit as st
import pandas as pd
import time
from datetime import date
from dateutil.relativedelta import relativedelta

# Importamos las funciones desde el motor de simulación
from motor_simulacion import com_simulacion_pyme, obtener_uf 

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Simulador Pyme BCI", 
    page_icon="🏦", 
    layout="wide"
)

# Estilos CSS personalizados para mejorar la visualización de la tabla
st.markdown("""
    <style>
    .stTable { font-size: 14px !important; }
    .main-metric { background-color: #f0f2f6; padding: 20px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏦 Simulador Créditos Comerciales (Pyme) - BCI")
st.markdown("""
**Configuración de Pricing:**
- **Cascada:** Spread Base → + Costo Fondo (Paso a Tasa) → Descuentos (Segmento, Perfil, Canal, Seguro).
- **Política de Plazo:** Para plazos ≥ 24 meses, se utiliza automáticamente el Costo de Fondo del tramo anterior.
- **Visualización:** Todos los valores se muestran en formato **Mensual**.
""")

# Crear las dos pestañas principales
tab_individual, tab_masivo = st.tabs(["👤 Simulación Individual", "📁 Simulación Masiva (Batch)"])

# ==============================================================================
# MÓDULO 1: SIMULACIÓN INDIVIDUAL
# ==============================================================================
with tab_individual:
    st.header("1. Parámetros Generales y de Operación")
    
    with st.container():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fecha_curse = st.date_input("Fecha de Curse", value=date.today())
            monto = st.number_input("Monto Líquido ($)", min_value=100000, value=10000000, step=1000000)
            plazo = st.number_input("Plazo (Cuotas)", min_value=3, max_value=120, value=24, step=1)
        
        with col2:
            valor_uf_actual = obtener_uf(fecha_curse)
            st.metric(label=f"Valor UF al {fecha_curse.strftime('%d-%m-%Y')}", 
                      value=f"${valor_uf_actual:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
            
            segmento = st.selectbox("Segmento Cliente", ["NACE", "MEDIANA", "PEQUENA", "PYME DIGITAL", "SOCIO"])
            perfil = st.selectbox("Perfil de Riesgo", ["1", "2", "3", "4", "5", "6", "7", "8"])
            
        with col3:
            fecha_primer_pago = st.date_input("Fecha Primer Vencimiento", value=fecha_curse + relativedelta(months=1))
            canal = st.selectbox("Canal de Venta", ["CCDD", "ASISTIDO"])
            seguro = st.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])
            es_ggee = st.checkbox("¿Es Crédito con Garantía Estatal (GGEE)?")

    if st.button("🚀 Ejecutar Simulación", type="primary", use_container_width=True):
        try:
            # Ejecución del motor corregido
            res = com_simulacion_pyme(
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
            
            st.success("Simulación calculada exitosamente.")
            
            # --- SECCIÓN DE MÉTRICAS ---
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Cuota Mensual", f"${res['valor_cuota']:,.0f}".replace(',', '.'))
            with m2:
                st.metric("Tasa Mensual Final", f"{res['tasa_mensual']:.4f}%")
            with m3:
                st.metric("Monto Bruto", f"${res['monto_bruto']:,.0f}".replace(',', '.'))
            with m4:
                st.metric("CAE Anual", f"{res['cae_sernac']:.2f}%")

            st.markdown("---")

            # --- CASCADA DE PRICING ---
            st.subheader("🪜 Cascada de Pricing (Tasas Mensuales)")
            
            df_cascada = pd.DataFrame(res["detalle_cascada"])
            
            # Formatear la visualización
            df_viz = df_cascada.copy()
            df_viz["Variación (Mes)"] = df_viz["Ajuste"].apply(
                lambda x: f"{x:+.4f}%" if x and x != 0 else "-"
            )
            df_viz["Tasa Paso (Mes)"] = df_viz["Valor Mensual"].apply(
                lambda x: f"**{x:.4f}%**"
            )
            
            # Mostrar tabla
            st.table(df_viz[["Concepto", "Variación (Mes)", "Tasa Paso (Mes)"]])
            
            # Alerta de política de plazo
            if plazo >= 24:
                st.info(f"💡 **Nota de Política:** Para el plazo de {plazo} meses, el sistema aplicó el Costo de Fondo del tramo anterior para mejorar la tasa del cliente.")

            # --- TABLA DE DESARROLLO ---
            with st.expander("📊 Ver Tabla de Amortización Completa"):
                df_tabla = pd.DataFrame(res["tabla_desarrollo"])
                df_tabla["fec_ven"] = pd.to_datetime(df_tabla["fec_ven"]).dt.strftime('%d-%m-%Y')
                st.dataframe(df_tabla, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Se produjo un error en el cálculo: {e}")

# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA (BATCH)
# ==============================================================================
with tab_masivo:
    st.header("Procesamiento por Lotes")
    st.write("Sube un archivo CSV para simular múltiples operaciones.")
    
    archivo_csv = st.file_uploader("Cargar archivo CSV", type=["csv"])
    
    if archivo_csv is not None:
        try:
            df_input = pd.read_csv(archivo_csv, sep=None, engine='python')
            st.write("Vista previa de entrada:", df_input.head(3))
            
            if st.button("▶️ Iniciar Procesamiento Masivo"):
                resultados_batch = []
                progreso = st.progress(0)
                
                for i, fila in df_input.iterrows():
                    # Llamada al motor para cada fila
                    r = com_simulacion_pyme(
                        in_fecha_curse=pd.to_datetime(fila['fecha_curse']).date(),
                        in_primer_venc=pd.to_datetime(fila['fecha_pago']).date(),
                        in_monto_liquido=int(fila['monto']),
                        in_cuotas=int(fila['plazo']),
                        in_garantia_estatal=str(fila['es_ggee']).upper() in ['TRUE', '1', 'V'],
                        in_perfil=str(fila['perfil']),
                        in_segmento=str(fila['segmento']).upper(),
                        in_canal=str(fila['canal']).upper(),
                        in_seguro=str(fila['seguro']).upper()
                    )
                    
                    # Consolidar resultados
                    res_fila = fila.to_dict()
                    res_fila.update({
                        "monto_bruto": r["monto_bruto"],
                        "valor_cuota": r["valor_cuota"],
                        "tasa_mensual": r["tasa_mensual"],
                        "cae": r["cae_sernac"]
                    })
                    resultados_batch.append(res_fila)
                    progreso.progress((i + 1) / len(df_input))
                
                df_final = pd.DataFrame(resultados_batch)
                st.success(f"✅ Procesados {len(df_final)} registros correctamente.")
                st.dataframe(df_final)
                
                # Descarga de resultados
                csv_bytes = df_final.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar Resultados",
                    data=csv_bytes,
                    file_name=f"simulacion_masiva_{date.today()}.csv",
                    mime="text/csv"
                )
                
        except Exception as e:
            st.error(f"Error procesando el archivo: {e}")
