import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# Importamos el nuevo motor de simulación pyme
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
        # Mostramos la UF de la fecha seleccionada
        valor_uf_actual = obtener_uf(fecha_curse)
        st.metric(label=f"Valor UF al {fecha_curse.strftime('%d-%m-%Y')}", value=f"${valor_uf_actual:,.2f}".replace(',', '.'))
        
    with col3:
        # Holgura de hasta 6 meses para el primer pago
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
        # Los valores de estos selectbox corresponden EXACTAMENTE a los índices de tus CSV
        perfil = st.selectbox("Perfil de Riesgo", ["1", "2", "3", "4", "5", "6", "7", "8"])
        segmento = st.selectbox("Segmento", ["NACE", "MEDIANA", "PEQUENA", "PYME DIGITAL", "SOCIO"])
        
    with col_d3:
        canal = st.selectbox("Canal de Curse", ["CCDD", "ASISTIDO"])
        seguro = st.selectbox("Seguro", ["DESGRAVAMEN", "SINSEGURO"])

    # Transformar la selección del usuario a booleano para el motor
    es_ggee = True if "GGEE" in tipo_garantia else False

    # Botón de ejecución
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚀 Calcular Simulación", type="primary", use_container_width=True):
        with st.spinner("Procesando cascada de precios y matriz de amortización..."):
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
                
                # Mostrar resultados en tarjetas destacadas
                st.subheader("Resultados Financieros")
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("Valor Cuota Mensual", f"${resultado['valor_cuota']:,.0f}".replace(',', '.'))
                r2.metric("Monto Bruto Financiado", f"${resultado['monto_bruto']:,.0f}".replace(',', '.'))
                r3.metric("Costo Total del Crédito", f"${resultado['costo_total_credito']:,.0f}".replace(',', '.'))
                r4.metric("CAE", f"{resultado['cae']:.2f}%")
                
                st.markdown("---")
                st.subheader("Desglose de Tasas (Pricing)")
                t1, t2, t3, t4 = st.columns(4)
                t1.metric("Spread Resultante (bps)", f"{resultado['spread_resultante']:.2f}")
                t2.metric("Costo de Fondo Histórico", f"{resultado['costo_fondo_historico']:.4f}%")
                t3.metric("Tasa de Interés Anual", f"{resultado['tasa_anual']:.4f}%")
                t4.metric("Tasa de Interés Mensual", f"{resultado['tasa_mensual']:.4f}%")
                
                st.markdown("---")
                
                # ==========================================
                # MEJORA 1: EXPANDER CON TABLA DE DESARROLLO
                # ==========================================
                with st.expander("📊 Ver Tabla de Desarrollo (Amortización)"):
                    if "tabla_desarrollo" in resultado:
                        # Convertimos la lista de diccionarios en un DataFrame para que se vea lindo
                        df_tabla = pd.DataFrame(resultado["tabla_desarrollo"])
                        
                        # Formateamos las columnas para la vista web
                        df_tabla.rename(columns={
                            'cuota': 'N° Cuota', 'fec_ven': 'Fecha Vencimiento', 
                            'dias': 'Días', 'tasa_diaria': 'Tasa Diaria',
                            'calc_cuota1': 'Factor 1', 'calc_cuota2': 'Factor 2'
                        }, inplace=True)
                        
                        st.dataframe(df_tabla, use_container_width=True, hide_index=True)
                    else:
                        st.warning("La tabla de desarrollo no está disponible.")

                # ==========================================
                # MEJORA 2: BOTÓN DE DESCARGA DE COTIZACIÓN
                # ==========================================
                # Armamos un texto ordenado simulando un comprobante o voucher
                cotizacion_txt = f"""
=========================================
       COTIZACION COMERCIAL PYME
=========================================
Fecha de Simulación : {date.today().strftime('%d-%m-%Y')}
Fecha de Curse      : {fecha_curse.strftime('%d-%m-%Y')}
Primer Vencimiento  : {fecha_primer_pago.strftime('%d-%m-%Y')}

--- DATOS DEL CREDITO ---
Monto Líquido       : ${monto:,.0f}
Plazo               : {plazo} cuotas
Tipo de Garantía    : {tipo_garantia}
Perfil / Segmento   : {perfil} / {segmento}
Canal de Curse      : {canal}
Seguro Asociado     : {seguro}

--- RESULTADOS FINANCIEROS ---
Valor Cuota Mensual : ${resultado['valor_cuota']:,.0f}
Monto Bruto Total   : ${resultado['monto_bruto']:,.0f}
Costo Total Credito : ${resultado['costo_total_credito']:,.0f}
C.A.E.              : {resultado['cae']:.2f}%
Tasa Mensual        : {resultado['tasa_mensual']:.4f}%

* Documento referencial generado por Simulador Pyme.
=========================================
"""
                # Generamos el botón de descarga en formato .txt
                st.download_button(
                    label="📄 Descargar Cotización para el Cliente",
                    data=cotizacion_txt,
                    file_name=f"Cotizacion_Pyme_${monto:,.0f}_{plazo}M.txt".replace(',', '.'),
                    mime="text/plain",
                    type="secondary"
                )

            except Exception as e:
                st.error(f"Ocurrió un error en el cálculo. Verifica las matrices: {e}")

# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA (BATCH POR CSV)
# ==============================================================================
with tab_masivo:
    st.header("Simulación por Lotes")
    st.info("Sube un archivo `.csv` con los casos a simular. Puedes incluir columnas identificadoras como `rut` o `nombre`. \n\n **Columnas obligatorias:** `rut`, `fecha_curse`, `fecha_pago`, `monto`, `plazo`, `es_ggee` (V/F), `perfil`, `segmento`, `canal`, `seguro`.")
    
    # ==========================================
    # MEJORA 4: BOTÓN PARA DESCARGAR PLANTILLA
    # ==========================================
    csv_plantilla = "rut;fecha_curse;fecha_pago;monto;plazo;es_ggee;perfil;segmento;canal;seguro\n76123456-K;2026-04-01;2026-05-01;15000000;36;V;3;MEDIANA;CCDD;DESGRAVAMEN\n"
    st.download_button(
        label="📥 Descargar Plantilla CSV de Ejemplo",
        data=csv_plantilla.encode('utf-8-sig'),
        file_name='plantilla_masiva_pyme.csv',
        mime='text/csv',
        help="Descarga un archivo con las columnas correctas listas para llenar."
    )
    
    st.markdown("---") # Una línea divisoria visual
    archivo_subido = st.file_uploader("Sube tu archivo de entrada CSV aquí", type=["csv"])
    
    if archivo_subido is not None:
        try:
            df_input = pd.read_csv(archivo_subido, sep=None, engine='python')
            st.write("Vista previa de los datos cargados:")
            st.dataframe(df_input.head())
            
            if st.button("▶️ Ejecutar Simulación Masiva", type="primary"):
                barra_progreso = st.progress(0)
                resultados_masivos = []
                
                for index, row in df_input.iterrows():
                    f_curse = pd.to_datetime(row['fecha_curse']).date()
                    f_pago = pd.to_datetime(row['fecha_pago']).date()
                    
                    # Identificar si es True o False desde el CSV (Soporta 'V', 'F', 'True', 'False', 1, 0)
                    str_ggee = str(row['es_ggee']).upper().strip()
                    es_ggee_row = True if str_ggee in ['V', 'TRUE', '1', 'T'] else False
                    
                    res = com_simulacion_pyme(
                        in_fecha_curse=f_curse,
                        in_primer_venc=f_pago,
                        in_monto_liquido=int(row['monto']),
                        in_cuotas=int(row['plazo']),
                        in_garantia_estatal=es_ggee_row,
                        in_perfil=str(row['perfil']),
                        in_segmento=str(row['segmento']).upper().strip(),
                        in_canal=str(row['canal']).upper().strip(),
                        in_seguro=str(row['seguro']).upper().strip()
                    )
                    
                    fila_resultado = row.to_dict()
                    fila_resultado.update(res) # Combina los inputs originales con los outputs calculados
                    resultados_masivos.append(fila_resultado)
                    
                    barra_progreso.progress((index + 1) / len(df_input))
                
                df_resultados = pd.DataFrame(resultados_masivos)
                # Ocultamos la columna 'tabla_desarrollo' en el reporte masivo para no saturar el CSV
                if 'tabla_desarrollo' in df_resultados.columns:
                    df_resultados.drop(columns=['tabla_desarrollo'], inplace=True)

                st.success(f"✅ Se simularon {len(df_input)} casos exitosamente.")
                st.dataframe(df_resultados)
                
                # Botón de Descarga
                csv_export = df_resultados.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar Resultados en CSV",
                    data=csv_export,
                    file_name='resultados_batch_pyme.csv',
                    mime='text/csv',
                )
                
        except Exception as e:
            st.error(f"Error procesando el archivo masivo. Verifica el formato de las columnas. Detalle técnico: {e}")
