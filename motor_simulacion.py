import math
import os
import pandas as pd
import requests
import streamlit as st  # <--- Necesario para leer los secretos
import numpy_financial as npf  # <--- NUEVA LIBRERÍA FINANCIERA
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from workalendar.america import Chile

# Cache para almacenar los DataFrames en memoria y no leer los CSVs en cada clic
DATA_CACHE = {}

def cargar_datos_csv():
    """Carga y procesa todos los CSVs en memoria una sola vez al iniciar la app."""
    global DATA_CACHE
    directorio_actual = os.path.dirname(__file__)
    
    archivos = {                                       # <--- ¡DEBE TENER ESTOS 4 ESPACIOS!
        'comercial': '1. plantilla_comercial.csv',
        'ggee': '2. plantilla_ggee.csv',
        'perfiles': '3. plantilla_perfiles.csv',
        'segmentos': '4. plantilla_segmentos.csv',
        'canal': '5. plantilla_canal.csv',
        'seguros': '6. plantilla_seguros.csv',
        'cf': 'cf.csv',
        'uf': 'uf.csv',
        'desgravamen': 'desgravamen_aval.csv'
    }
    
    for clave, nombre_archivo in archivos.items():
        # 1. Intentamos buscar el archivo en la carpeta principal (raíz)
        ruta = os.path.join(directorio_actual, nombre_archivo)
        
        # 2. Si no está ahí, intentamos buscarlo dentro de una subcarpeta 'data/'
        if not os.path.exists(ruta):
            ruta = os.path.join(directorio_actual, 'data', nombre_archivo)
            
        # 3. Si ya definitivamente no está en ningún lado, avisamos por consola y lo saltamos
        if not os.path.exists(ruta):
            print(f"🚨 ALERTA: No encontré el archivo {nombre_archivo} en GitHub.")
            continue
        
        if clave in ['cf', 'uf', 'desgravamen']:
            try:
                df = pd.read_csv(ruta, sep=';', engine='python')
                if len(df.columns) < 2:
                    df = pd.read_csv(ruta, sep=',', engine='python')
            except:
                df = pd.read_csv(ruta, sep=None, engine='python')
            DATA_CACHE[clave] = df
        else:
            df = pd.read_csv(ruta, sep=None, engine='python')
            df.set_index(df.columns[0], inplace=True) 
            df = df.replace({',': '.'}, regex=True).astype(float)
            df.index = df.index.astype(str)
            DATA_CACHE[clave] = df

def obtener_tasa_desgravamen(cuotas: int) -> float:
    """Obtiene la tasa por mil del desgravamen según el plazo en meses (cuotas)."""
    try:
        df_desg = DATA_CACHE.get('desgravamen')
        if df_desg is None or df_desg.empty:
            return 0.0
        
        # Buscamos la fila correspondiente a las cuotas
        # Si las cuotas superan el máximo del archivo (227), tomamos el último valor
        plazos = df_desg['plazo'].astype(int)
        cuotas_busqueda = plazos.max() if cuotas > plazos.max() else cuotas
            
        fila = df_desg[df_desg['plazo'] == cuotas_busqueda]
        
        if not fila.empty:
            val = fila['tasaxmil'].iloc[0]
            if isinstance(val, str):
                # Limpiamos el punto de miles (si existe) y cambiamos la coma decimal
                val = float(val.replace('.', '').replace(',', '.'))
            else:
                val = float(val)
                
            # Como es "Tasa por Mil", se divide por 1000 para llevarlo a decimal
            return val / 1000.0 
            
    except Exception as e:
        print(f"Error técnico leyendo desgravamen_aval.csv: {e}")
        
    return 0.0


def obtener_valor_matriz(tipo_plantilla: str, valor_fila: str, monto: float, es_plazo=False) -> float:
    """Cruza Fila (Plazo o String) vs Columna (Monto) para obtener el valor del CSV"""
    df = DATA_CACHE[tipo_plantilla]
    
    # 1. Determinar la Columna (Monto en Millones)
    monto_millones = monto / 1_000_000.0
    columnas_monto = sorted([int(c) for c in df.columns])
    
    col_seleccionada = str(columnas_monto[-1]) # Asume la columna mayor por defecto
    for c in columnas_monto:
        if monto_millones <= c:
            col_seleccionada = str(c)
            break
            
    # 2. Determinar la Fila
    if es_plazo:
        # Busca el tramo de plazo "hasta" el cual es válido (<=)
        filas_plazo = sorted([int(float(r)) for r in df.index])
        fila_seleccionada = str(filas_plazo[-1])
        for r in filas_plazo:
            if float(valor_fila) <= r:
                fila_seleccionada = str(r)
                break
    else:
        # Busca por texto exacto (Ej: 'PYME DIGITAL', 'CCDD', '1')
        fila_seleccionada = str(valor_fila).upper().strip()
        if fila_seleccionada not in df.index:
            return 0.0 # Si el perfil o segmento no existe/no tiene descuento, retorna 0
            
    return float(df.loc[fila_seleccionada, col_seleccionada])

def obtener_costo_fondo_historico(plazo_meses: int) -> float:
    """Busca el costo de fondo y le suma un colchón de liquidez a partir del tramo de 24 meses."""
    try:
        df_cf = DATA_CACHE['cf']
        periodo_reciente = df_cf['periodo'].max()
        df_reciente = df_cf[df_cf['periodo'] == periodo_reciente].copy()
        
        # 1. Ordenamos la tabla de menor a mayor plazo para asegurar la secuencia de tramos
        df_reciente = df_reciente.sort_values(by='plazo_hasta').reset_index(drop=True)
        
        # 2. Buscamos el tramo donde cae el plazo del cliente
        filtro = (df_reciente['plazo_desde'] <= plazo_meses) & (df_reciente['plazo_hasta'] >= plazo_meses)
        fila_actual = df_reciente[filtro]
        
        if not fila_actual.empty:
            # Obtenemos el índice (la posición de la fila) y el CF actual
            idx_actual = fila_actual.index[0]
            val_str = fila_actual['cf'].iloc[0]
            cf_actual = float(str(val_str).replace(',', '.'))
            
            # 3. Lógica del Colchón (Solo aplica si el límite del tramo es 24 meses o más)
            colchon = 0.0
            plazo_hasta_actual = fila_actual['plazo_hasta'].iloc[0]
            
            # Verificamos que sea el tramo 24+ y que exista un tramo anterior (idx_actual > 0)
            if plazo_hasta_actual >= 24 and idx_actual > 0:
                # Obtenemos el CF del tramo inmediatamente anterior
                val_ant_str = df_reciente.loc[idx_actual - 1, 'cf']
                cf_anterior = float(str(val_ant_str).replace(',', '.'))
                
                # El colchón es el delta. Usamos max(0.0, ...) por si la curva de tasas se invierte.
                diferencia = cf_actual - cf_anterior
                colchon = max(0.0, diferencia)
                
            # Retornamos el Costo de Fondo original + el Colchón calculado
            return cf_actual + colchon
            
    except Exception as e:
        print(f"Error técnico calculando Costo de Fondo: {e}")
        
    return 0.0

def obtener_uf(fecha_consulta: date) -> float:
    """Obtiene el valor de la UF desde el archivo uf.csv en memoria."""
    
    # --- NUEVAS LÍNEAS: Si la memoria está vacía, carga los CSVs ---
    if not DATA_CACHE:
        cargar_datos_csv()
    # ---------------------------------------------------------------
        
    try:
        df_uf = DATA_CACHE.get('uf')
        if df_uf is None or df_uf.empty:
            return 38000.0

        # Convertir la columna fecha a formato Date nativo
        df_uf['fecha'] = pd.to_datetime(df_uf['fecha']).dt.date
        
        # Buscar la fecha solicitada o la última válida hacia atrás
        df_ordenado = df_uf.sort_values(by='fecha')
        filas_validas = df_ordenado[df_ordenado['fecha'] <= fecha_consulta]
        
        if not filas_validas.empty:
            val = filas_validas.iloc[-1]['valor']
            # Limpiar por si viene con coma decimal en vez de punto
            if isinstance(val, str):
                val = float(val.replace(',', '.'))
            return float(val)
            
    except Exception as e:
        print(f"Error técnico leyendo uf.csv: {e}")
        
    return 39800.0 # Salvavidas si algo falla

# ==============================================================================
# MOTOR CENTRAL DE SIMULACIÓN PYME
# ==============================================================================
def com_simulacion_pyme(
    in_fecha_curse: date, 
    in_primer_venc: date, 
    in_monto_liquido: int, 
    in_cuotas: int, 
    in_garantia_estatal: bool, # True (GGEE) o False (Comercial)
    in_perfil: str,           # '1', '2', '3', '4' o '5'
    in_segmento: str,         # 'NACE', 'MEDIANA', 'PYME DIGITAL', etc.
    in_canal: str,            # 'CCDD' o 'ASISTIDO'
    in_seguro: str            # 'DESGRAVAMEN' o 'SINSEGURO'
) -> dict:
    
    # 0. Cargar plantillas si es la primera ejecución
    if not DATA_CACHE:
        cargar_datos_csv()

# =========================================================
    # Cálculos previos (Monto Bruto)
    # =========================================================
    cal_chile = Chile()
    notario = 2640
    tasa_impuesto_plazo = 0.066
    tasa_impuesto_max = 0.8
    
    # NUEVA LÓGICA: Obtener el costo real del seguro de desgravamen
    if in_seguro == 'DESGRAVAMEN':
        tasa_desg = obtener_tasa_desgravamen(in_cuotas)
    else:
        tasa_desg = 0.0
        
    out_plazo_aprox = in_cuotas
    tasa_impuesto = min(out_plazo_aprox * tasa_impuesto_plazo, tasa_impuesto_max)
    
    # Magia financiera: El denominador ahora le presta la plata al cliente para pagar su seguro
    monto_bruto = math.ceil((in_monto_liquido + notario) / (1.0 - tasa_impuesto/100.0 - tasa_desg))

    # =========================================================
    # CASCADA DE PRICING (Puntos 1 al 8)
    # =========================================================
    
    # P1. Spread Base
    tipo_base = 'ggee' if in_garantia_estatal else 'comercial'
    spread_base = obtener_valor_matriz(tipo_base, in_cuotas, monto_bruto, es_plazo=True)
    
    # P2 y P3. Descuentos Perfil y Segmento (Se suman, ya que en el CSV vienen negativos)
    desc_perfil = obtener_valor_matriz('perfiles', in_perfil, monto_bruto)
    desc_segmento = obtener_valor_matriz('segmentos', in_segmento, monto_bruto)
    spread = spread_base + desc_perfil + desc_segmento
    
    # P4 y P5. Descuentos Canal y Seguro (Porcentajes de descuento multiplicadores)
    pct_canal = obtener_valor_matriz('canal', in_canal, monto_bruto)
    pct_seguro = obtener_valor_matriz('seguros', in_seguro, monto_bruto)
    
    # P6. Spread Resultante
    spread_resultante = spread * (1.0 - (pct_canal / 100.0)) * (1.0 - (pct_seguro / 100.0))
    
    # P7. Costo de Fondo Mensual
    cf_mensual = obtener_costo_fondo_historico(in_cuotas)
    
    # P8. Construcción de Tasas Finales
    tasa_anual = spread_resultante + (cf_mensual * 12.0)
    tasa_mensual = tasa_anual / 12.0 
    
    # Validación con TMC (Asumimos P02T03 standard)
    tmc_mensual = 25.10 / 12.0 
    tasa_mensual_aplicada = min(tasa_mensual, tmc_mensual)

    # =========================================================
    # GENERACIÓN DE TABLA DE AMORTIZACIÓN (Punto 9)
    # =========================================================
    tabla = []
    fecha_ven = in_fecha_curse
    
    for cuota in range(in_cuotas + 1):
        if cuota == 1:
            fecha_ven = in_primer_venc
        elif cuota > 1:
            fecha_ven = in_primer_venc + relativedelta(months=cuota-1)
            
        while not cal_chile.is_working_day(fecha_ven):
            fecha_ven += timedelta(days=1)
            
        tabla.append({'cuota': cuota, 'fec_ven': fecha_ven, 'dias': 0, 'tasa_diaria': 0.0, 'calc_cuota1': 1.0 if cuota == 0 else 0.0, 'calc_cuota2': 0.0})

    # Días, Tasas Diarias y Factores
    calc_cuota1_acum = 1.0
    calc_cuota2_acum = 0.0
    for i in range(1, len(tabla)):
        dias = (tabla[i]['fec_ven'] - tabla[i-1]['fec_ven']).days
        tabla[i]['dias'] = dias
        tabla[i]['tasa_diaria'] = dias * tasa_mensual_aplicada / 3000.0
        
        calc_cuota1_acum = (1.0 + tabla[i]['tasa_diaria']) * calc_cuota1_acum
        calc_cuota2_acum = calc_cuota2_acum + (1.0 / calc_cuota1_acum)
        tabla[i]['calc_cuota2'] = calc_cuota2_acum

    valor_cuota = math.ceil(monto_bruto / tabla[-1]['calc_cuota2'])

    # Amortización para CAE
    saldo = float(monto_bruto)
    dias_acum = 0
    amortizacion_total = []
    
    for i in range(1, len(tabla)):
        intereses = round(saldo * tasa_mensual_aplicada / 100.0, 0)
        dias_acum += tabla[i]['dias']
        amort = (valor_cuota - intereses) if i < in_cuotas else saldo
        saldo -= amort
        amortizacion_total.append((amort, dias_acum))

    # Indicadores
    # =========================================================
    # INDICADORES Y CÁLCULO DE C.A.E.
    # =========================================================
    out_ctc = in_cuotas * valor_cuota
    sum_dias_amort = sum(d * a for a, d in amortizacion_total)
    sum_amort = sum(a for a, d in amortizacion_total)
    
    # 1. CAE TRADICIONAL (Actuarial por Duración Media)
    out_duration = (sum_dias_amort / sum_amort / 360.0) if sum_amort else 0
    cae_tradicional = 100.0 * (out_ctc - in_monto_liquido) / (in_monto_liquido * out_duration) if out_duration else 0

    # 2. CAE SERNAC (Tasa Interna de Retorno - TIR)
    # Calculamos los meses de gracia (desfase entre curse y primer pago)
    meses_diff = (in_primer_venc.year - in_fecha_curse.year) * 12 + in_primer_venc.month - in_fecha_curse.month
    meses_gracia = max(0, meses_diff - 1)
    
    # Armamos el Flujo de Caja: Monto Líquido (Positivo) y Cuotas (Negativas)
    flujo_caja = [in_monto_liquido] + [0] * meses_gracia + [-valor_cuota] * in_cuotas
    
    # Calculamos la TIR, la anualizamos (* 12) y la pasamos a porcentaje (* 100)
    tir = npf.irr(flujo_caja)
    cae_sernac = (tir * 12.0) * 100.0 if not math.isnan(tir) else 0.0

    return {
        "valor_cuota": valor_cuota,
        "monto_bruto": monto_bruto,
        "spread_resultante": spread_resultante,
        "costo_fondo_historico": cf_mensual,
        "tasa_anual": tasa_anual,
        "tasa_mensual": tasa_mensual_aplicada,
        "cae_tradicional": cae_tradicional,  # <--- Mantenemos el tuyo
        "cae_sernac": cae_sernac,            # <--- Agregamos el del SERNAC
        "costo_total_credito": out_ctc,
        "tabla_desarrollo": tabla
    }
