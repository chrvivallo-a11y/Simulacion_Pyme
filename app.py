import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import io

# IMPORTANTE: Aquí importamos la función que creamos antes. 
# Asegúrate de guardar el código anterior en un archivo llamado 'motor_simulacion.py'
from motor_simulacion import com_simulacion, obtener_uf 

# Configuración inicial de la página
st.set_page_config(page_title="Simulador BCI - Comercial", page_icon="🏦", layout="wide")

st.title("🏦 Simulador de Créditos de Comercial")

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
            help="Máximo 6 meses de holgura desde la fecha de curse."
        )

    st.markdown("---")
    st.header("2. Datos de Simulación")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        tipo_cliente = st.selectbox("Tipo de Cliente", ["Sin Garantía", "Con Garantía (FOGAPE/etc)"])
        perfil = st.selectbox("Perfil", ["Dependiente", "Independiente", "Jubilado"])
        segmento = st.selectbox("Segmento", ["Banca Personas", "Banca Preferencial", "Banca Privada"])
        canal = st.selectbox("Canal de Curse", ["Digital (App/Web)", "Asistido (Sucursal)"])
        
    with col_d2:
        monto = st.number_input("Monto Líquido ($)", min_value=500000, value=5000000, step=500000)
        plazo = st.slider("Plazo (Cuotas)", min_value=6, max_value=72, value=36, step=1)
        resguardo_cf = st.number_input("Resguardo Costo de Fondo (%)", value=0.0, step=0.1)

    # ---------------------------------------------------------
    # LÓGICA DE NEGOCIO (Mapeo de UI a Plantillas)
    # ---------------------------------------------------------
    # Aquí debes definir cómo las selecciones del usuario se traducen
    # en los nombres exactos de las plantillas de tu CSV.
    # Esto es un ejemplo (debes ajustarlo a tu realidad comercial):
    def obtener_nombre_plantillas(segmento, canal, tipo_cliente):
        plantilla_tasa = 'FGPWGRUPO6$' # Valor por defecto
        plantilla_dscto = 'DSCTFGPG6$W' # Valor por defecto
        
        if canal == "Digital (App/Web)":
            plantilla_dscto = 'DSCT_DIGITAL_1'
        if segmento == "Banca Preferencial":
            plantilla_tasa = 'TASA_PREF_01'
            
        return plantilla_tasa, plantilla_dscto

    plantilla_tasa_seleccionada, plantilla_dscto_seleccionada = obtener_nombre_plantillas(segmento, canal, tipo_cliente)

    # Botón para simular
    if st.button("🚀 Calcular Simulación", type="primary"):
        with st.spinner("Calculando..."):
            resultado = com_simulacion(
                in_fecha_curse=fecha_curse,
                in_primer_venc=fecha_primer_pago,
                in_monto_liquido=monto,
                in_plantilla_tasa=plantilla_tasa_seleccionada,
                in_plantilla_descuento=plantilla_dscto_seleccionada,
                in_cuotas=plazo,
                in_resguardo_cf=resguardo_cf
            )
            
            st.success("¡Simulación completada!")
            
            # Mostrar resultados en tarjetas
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Valor Cuota", f"${resultado['valor_cuota']:,.0f}".replace(',', '.'))
            r2.metric("Monto Bruto", f"${resultado['monto_bruto']:,.0f}".replace(',', '.'))
            r3.metric("Tasa Aplicada", f"{resultado['tasa_aplicada']:.2f}%")
            r4.metric("CAE", f"{resultado['cae']:.2f}%")


# ==============================================================================
# MÓDULO 2: SIMULACIÓN MASIVA (BATCH POR CSV)
# ==============================================================================
with tab_masivo:
    st.header("Simulación por Lotes")
    st.write("Sube un archivo `.csv` con los casos a simular. El archivo debe contener las columnas: `fecha_curse`, `fecha_pago`, `monto`, `plazo`, `plantilla_tasa`, `plantilla_dscto`.")
    
    archivo_subido = st.file_uploader("Sube tu archivo CSV aquí", type=["csv"])
    
    if archivo_subido is not None:
        try:
            df_input = pd.read_csv(archivo_subido)
            st.write("Vista previa de los datos cargados:")
            st.dataframe(df_input.head())
            
            if st.button("▶️ Ejecutar Simulación Masiva"):
                barra_progreso = st.progress(0)
                resultados_masivos = []
                
                for index, row in df_input.iterrows():
                    # Parsear fechas del CSV
                    f_curse = pd.to_datetime(row['fecha_curse']).date()
                    f_pago = pd.to_datetime(row['fecha_pago']).date()
                    
                    # Ejecutar motor por cada fila
                    res = com_simulacion(
                        in_fecha_curse=f_curse,
                        in_primer_venc=f_pago,
                        in_monto_liquido=int(row['monto']),
                        in_plantilla_tasa=row['plantilla_tasa'],
                        in_plantilla_descuento=row['plantilla_dscto'],
                        in_cuotas=int(row['plazo']),
                        in_resguardo_cf=0.0 # O leerlo del CSV si existe
                    )
                    
                    # Agregar el resultado a la fila original para no perder el contexto
                    fila_resultado = row.to_dict()
                    fila_resultado.update(res)
                    resultados_masivos.append(fila_resultado)
                    
                    # Actualizar barra de progreso
                    barra_progreso.progress((index + 1) / len(df_input))
                
                df_resultados = pd.DataFrame(resultados_masivos)
                st.success(f"Se simularon {len(df_input)} casos exitosamente.")
                st.dataframe(df_resultados)
                
                # Convertir DF a CSV para descargar
                csv_export = df_resultados.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Resultados en CSV",
                    data=csv_export,
                    file_name='resultados_simulacion.csv',
                    mime='text/csv',
                )
                
        except Exception as e:
            st.error(f"Error procesando el archivo: {e}. Revisa que las columnas tengan los nombres correctos.")