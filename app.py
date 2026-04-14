import streamlit as st
import pandas as pd
import time
from datetime import date
from dateutil.relativedelta import relativedelta

# Importamos el motor de simulación y utilidades
from motor_simulacion import com_simulacion_pyme, obtener_uf 

# ==============================================================================
# CONFIGURACIÓN DE PÁGINA
# ==============================================================================
st.set_page_config(page_title="Simulador Pyme BCI", page_icon="🏦", layout="wide")

st.title("🏦 Simulador Créditos Comerciales (Pyme) - BCI")
st.markdown("Este simulador aplica la cascada de precios: Spread Base -> Desc. Perfil -> Desc. Segmento -> % Canal -> % Seguro.")

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
            max_value=fecha_maxima_pago,
            help="Día hábil y mes de primer pago (Holgura de hasta 6 meses)."
        )

    st.markdown("---")
    st.header("2. Datos de la Operación")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        monto = st.number_input("Monto Líquido ($)", min_value=100000, value=1000000, step=1000000)
        plazo = st.number_input("Plazo (Cuotas)", min_value=3, max_value=120, value=36, step=1)
        tipo_garantia = st.selectbox("Tipo de Crédito", ["Sin Garantía (Comercial)", "Con Garantía Estatal (GGEE)"])
        
    with col_d2:
        perfil = st.selectbox("Perfil de Riesgo", ["1", "2", "3", "4", "5", "6", "7", "8"])
        segmento = st.selectbox("Segmento", ["NACE", "MEDIANA", "PEQUENA", "PYME DIGITAL", "SOCIO"])
        
    with col_d3:
        canal = st.selectbox("Canal de Curse", ["CCDD", "ASISTIDO"])
        seguro = st.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])

    es_ggee = True if "GGEE" in tipo_garantia else False

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
                
                st.success("¡Simulación completada!")
                
                # Indicadores principales
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Valor Cuota", f"${resultado['valor_cuota']:,.0f}".replace(',', '.'))
                r2.metric("Monto Bruto", f"${resultado['monto_bruto']:,.0f}".replace(',', '.'))
                r3.metric("Tasa Mensual", f"{resultado['tasa_mensual']:.4f}%")
                r4.metric("CAE (Sernac)", f"{resultado['cae_sernac']:.2f}%")
                
                st.markdown("---")

                # ==============================================================
                # CASCADA DE PRICING CON TASA MENSUAL
                # ==============================================================
                st.subheader("🪜 Detalle de Cascada de Pricing")
                
                if "detalle_cascada" in resultado:
                    datos_cascada = resultado["detalle_cascada"].copy()
                    
                    # Añadimos el paso final de conversión a mensual si no existe
                    tasa_anual = resultado['tasa_anual']
                    tasa_mensual = resultado['tasa_mensual']
                    datos_cascada.append({
                        "Concepto": "7. Conversión a Tasa Mensual (Anual / 12)", 
                        "Ajuste": None, 
                        "Spread Resultante": tasa_mensual
                    })
                    
                    df_viz = pd.DataFrame(datos_cascada)
                    
                    # Función de formateo condicional
                    def formatear_valor(fila):
                        val = fila["Spread Resultante"]
                        # Si es el último paso (Mensual), usamos 4 decimales
                        if "Mensual" in fila["Concepto"]:
                            return f"{val:.4f}%"
                        return f"{val:.2f}%"

                    def formatear_ajuste(val):
                        if val is None or val == 0: return "-"
                        return f"{val:+.2f}%"

                    df_viz["Valor Resultante"] = df_viz.apply(formatear_valor, axis=1)
                    df_viz["Ajuste"] = df_viz["Ajuste"].apply(formatear_ajuste)
                    
                    st.table(df_viz[["Concepto", "Ajuste", "Valor Resultante"]])
                    
                    st.info("💡 La **Tasa Mensual** resultante es la que se utiliza para calcular los intereses en la tabla de desarrollo.")

                st.markdown("---")
                
                # Tabla de Desarrollo
                with st.expander("📊 Ver Tabla de Desarrollo"):
                    if "tabla_desarrollo" in resultado:
                        st.dataframe(pd.DataFrame(resultado["tabla_desarrollo"]), use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Error en el cálculo: {e}")

# (El resto del código de Módulo Masivo se mantiene igual que la versión anterior)
