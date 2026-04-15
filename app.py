import streamlit as st
import pandas as pd
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
- **Perfiles:** Descuentos de perfiles alineados a plantilla mensualizada.
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
    
    col_opt1, col_opt2, col_opt3 = st.columns(3)
    with col_opt1:
        canal_ind = st.selectbox("Canal de Venta", ["CCDD", "ASISTIDO"])
    with col_opt2:
        seguro_ind = st.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])
    with col_opt3:
        st.write("") # Espaciador
        es_ggee_ind = st.checkbox("Garantía Estatal (GGEE)")

    if st.button("🚀 Calcular Simulación", type="primary", use_container_width=True):
        try:
            # Llamada al motor
            res = com_simulacion_pyme(
                in_fecha_curse=f_curse,
                in_primer_venc=f_pago,
                in_monto_liquido=monto,
                in_cuotas=plazo,
                in_garantia_estatal=es_ggee_ind,
                in_perfil=perfil,
                in_segmento=segmento,
                in_canal=canal_ind,
                in_seguro=seguro_ind
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
            df_c["Variación (Mes)"] = df_c["Ajuste"].apply(lambda x: f"{x:+.4f}%" if x and x != 0 else "-")
            df_c["Tasa Paso (Mes)"] = df_c["Valor Mensual"].apply(lambda x: f"**{x:.4f}%**")
            st.table(df_c[["Concepto", "Variación (Mes)", "Tasa Paso (Mes)"]])
            
            # --- FEEDBACK DE LA POLÍTICA ---
            if plazo >= 24:
                st.success(f"✅ **Política Aplicada:** Al ser un plazo de {plazo} meses, se ha forzado el uso del Costo de Fondo del tramo anterior para beneficiar la tasa final.")
            
            with st.expander("📊 Ver Tabla de Amortización"):
                st.dataframe(pd.DataFrame(res["tabla_desarrollo"]), use_container_width=True)

        except Exception as e:
            st.error(f"Error en el cálculo: {e}")

# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA
# ==============================================================================
with tab_masivo:
    st.header("📁 Simulación por Lotes (Masiva)")
    
    # --- CARÁTULA / INSTRUCCIONES ---
    with st.expander("ℹ️ Instrucciones y Formato del Archivo CSV (Carátula)", expanded=True):
        st.markdown("""
        Para realizar simulaciones masivas, debes subir un archivo **.csv**. 
        El archivo debe contener **exactamente** las siguientes cabeceras (la primera fila) y respetar los formatos permitidos:
        """)
        
        # Tabla de Diccionario de Datos
        diccionario = pd.DataFrame({
            "Nombre Columna": ["fecha_curse", "fecha_pago", "monto", "plazo", "es_ggee", "perfil", "segmento", "canal", "seguro"],
            "Descripción": ["Fecha de otorgamiento", "Fecha del primer vencimiento", "Monto Líquido a solicitar", "Cantidad de cuotas", "¿Tiene Garantía Estatal?", "Perfil de Riesgo del cliente", "Segmento comercial", "Canal de curse", "Seguro asociado"],
            "Formato / Valores Permitidos": ["YYYY-MM-DD", "YYYY-MM-DD", "Número entero (ej: 10000000)", "Número entero (ej: 24)", "TRUE o FALSE", "1, 2, 3, 4, 5, 6, 7 u 8", "NACE, MEDIANA, PEQUENA, PYME DIGITAL, SOCIO", "CCDD o ASISTIDO", "DESGRAVAMEN o SINSEGURO"]
        })
        st.table(diccionario)
        
        # Generar botón para descargar plantilla vacía
        plantilla_df = pd.DataFrame(columns=diccionario["Nombre Columna"].tolist())
        csv_plantilla = plantilla_df.to_csv(index=False, sep=';').encode('utf-8-sig')
        st.download_button(
            label="📥 Descargar Plantilla CSV Vacía",
            data=csv_plantilla,
            file_name="plantilla_simulacion_masiva.csv",
            mime="text/csv",
            help="Descarga un archivo CSV con las cabeceras listas para ser llenadas."
        )

    st.markdown("---")
    
    # --- ZONA DE CARGA Y PROCESO ---
    up = st.file_uploader("Sube tu archivo CSV con los casos a simular", type="csv")
    
    if up:
        try:
            df_in = pd.read_csv(up, sep=None, engine='python')
            
            # Verificación rápida de cabeceras
            columnas_requeridas = ["fecha_curse", "fecha_pago", "monto", "plazo", "es_ggee", "perfil", "segmento", "canal", "seguro"]
            columnas_faltantes = [col for col in columnas_requeridas if col not in df_in.columns]
            
            if columnas_faltantes:
                st.error(f"❌ Error: El archivo no tiene el formato correcto. Faltan las columnas: {', '.join(columnas_faltantes)}")
            else:
                st.success(f"Archivo cargado correctamente con {len(df_in)} registros.")
                
                if st.button("▶️ Iniciar Procesamiento de Lote", type="primary"):
                    results = []
                    bar = st.progress(0)
                    
                    for i, row in df_in.iterrows():
                        try:
                            # Aseguramos limpieza en los booleanos y strings
                            es_ggee_val = str(row['es_ggee']).upper().strip() in ['TRUE', '1', 'V', 'SI']
                            
                            r = com_simulacion_pyme(
                                in_fecha_curse=pd.to_datetime(row['fecha_curse']).date(), 
                                in_primer_venc=pd.to_datetime(row['fecha_pago']).date(), 
                                in_monto_liquido=int(row['monto']), 
                                in_cuotas=int(row['plazo']), 
                                in_garantia_estatal=es_ggee_val, 
                                in_perfil=str(row['perfil']).strip(), 
                                in_segmento=str(row['segmento']).upper().strip(), 
                                in_canal=str(row['canal']).upper().strip(), 
                                in_seguro=str(row['seguro']).upper().strip()
                            )
                            
                            fila = row.to_dict()
                            # Añadir resultados del motor
                            fila.update({
                                "monto_bruto_res": r["monto_bruto"], 
                                "valor_cuota_res": r["valor_cuota"], 
                                "tasa_mensual_res": r["tasa_mensual"],
                                "cae_res": r["cae_sernac"]
                            })
                            results.append(fila)
                        except Exception as fila_err:
                            # Si una fila falla, la guardamos con error para no detener todo el proceso
                            fila_error = row.to_dict()
                            fila_error.update({"monto_bruto_res": "ERROR", "valor_cuota_res": str(fila_err)})
                            results.append(fila_error)
                            
                        bar.progress((i+1)/len(df_in))
                    
                    df_out = pd.DataFrame(results)
                    st.success("✅ Procesamiento masivo completado.")
                    st.dataframe(df_out)
                    
                    st.download_button(
                        label="📥 Descargar Resultados Consolidados", 
                        data=df_out.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig'), 
                        file_name=f"resultados_batch_pyme_{date.today()}.csv",
                        mime="text/csv"
                    )
        except Exception as e:
            st.error(f"Error al leer el archivo: Comprueba que sea un CSV válido. Detalle: {e}")
