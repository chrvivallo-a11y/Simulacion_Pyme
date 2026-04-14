import math
import os
import pandas as pd
import requests
import streamlit as st
import numpy_financial as npf
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from workalendar.america import Chile

DATA_CACHE = {}

def cargar_datos_csv():
    global DATA_CACHE
    directorio_actual = os.path.dirname(__file__)
    archivos = {
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
        ruta = os.path.join(directorio_actual, nombre_archivo)
        if not os.path.exists(ruta):
            ruta = os.path.join(directorio_actual, 'data', nombre_archivo)
        if not os.path.exists(ruta):
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
    try:
        df_desg = DATA_CACHE.get('desgravamen')
        if df_desg is None or df_desg.empty: return 0.0
        plazos = df_desg['plazo'].astype(int)
        cuotas_busqueda = plazos.max() if cuotas > plazos.max() else cuotas
        fila = df_desg[df_desg['plazo'] == cuotas_busqueda]
        if not fila.empty:
            val = fila['tasaxmil'].iloc[0]
            if isinstance(val, str):
                val = float(val.replace('.', '').replace(',', '.'))
            else:
                val = float(val)
            return val / 1000.0 
    except: return 0.0
    return 0.0

def obtener_valor_matriz(tipo_plantilla: str, valor_fila: str, monto: float, es_plazo=False) -> float:
    df = DATA_CACHE[tipo_plantilla]
    monto_millones = monto / 1_000_000.0
    columnas_monto = sorted([int(c) for c in df.columns])
    col_seleccionada = str(columnas_monto[-1])
    for c in columnas_monto:
        if monto_millones <= c:
            col_seleccionada = str(c)
            break
    if es_plazo:
        filas_plazo = sorted([int(float(r)) for r in df.index])
        fila_seleccionada = str(filas_plazo[-1])
        for r in filas_plazo:
            if float(valor_fila) <= r:
                fila_seleccionada = str(r)
                break
    else:
        fila_seleccionada = str(valor_fila).upper().strip()
        if fila_seleccionada not in df.index: return 0.0
    return float(df.loc[fila_seleccionada, col_seleccionada])

def obtener_costo_fondo_historico(plazo_meses: int) -> float:
    try:
        df_cf = DATA_CACHE['cf']
        periodo_reciente = df_cf['periodo'].max()
        df_reciente = df_cf[df_cf['periodo'] == periodo_reciente].copy()
        df_reciente = df_reciente.sort_values(by='plazo_hasta').reset_index(drop=True)
        filtro = (df_reciente['plazo_desde'] <= plazo_meses) & (df_reciente['plazo_hasta'] >= plazo_meses)
        fila_actual = df_reciente[filtro]
        if not fila_actual.empty:
            idx_actual = fila_actual.index[0]
            val_str = fila_actual['cf'].iloc[0]
            cf_actual = float(str(val_str).replace(',', '.'))
            colchon = 0.0
            plazo_hasta_actual = fila_actual['plazo_hasta'].iloc[0]
            if plazo_hasta_actual >= 24 and idx_actual > 0:
                val_ant_str = df_reciente.loc[idx_actual - 1, 'cf']
                cf_anterior = float(str(val_ant_str).replace(',', '.'))
                diferencia = cf_actual - cf_anterior
                colchon = max(0.0, diferencia)
            return cf_actual - colchon
    except: return 0.0
    return 0.0

def obtener_uf(fecha_consulta: date) -> float:
    if not DATA_CACHE: cargar_datos_csv()
    try:
        df_uf = DATA_CACHE.get('uf')
        df_uf['fecha'] = pd.to_datetime(df_uf['fecha']).dt.date
        df_ordenado = df_uf.sort_values(by='fecha')
        filas_validas = df_ordenado[df_ordenado['fecha'] <= fecha_consulta]
        if not filas_validas.empty:
            val = filas_validas.iloc[-1]['valor']
            if isinstance(val, str): val = float(val.replace(',', '.'))
            return float(val)
    except: return 39800.0
    return 39800.0

# ==============================================================================
# MOTOR CENTRAL ACTUALIZADO
# ==============================================================================
def com_simulacion_pyme(in_fecha_curse, in_primer_venc, in_monto_liquido, in_cuotas, in_garantia_estatal, in_perfil, in_segmento, in_canal, in_seguro):
    if not DATA_CACHE: cargar_datos_csv()

    cal_chile = Chile()
    notario = 2640
    tasa_impuesto_plazo = 0.066
    tasa_impuesto_max = 0.8
    
    tasa_desg = obtener_tasa_desgravamen(in_cuotas) if in_seguro == 'DESGRAVAMEN' else 0.0
    tasa_impuesto = min(in_cuotas * tasa_impuesto_plazo, tasa_impuesto_max)
    monto_bruto = math.ceil((in_monto_liquido + notario) / (1.0 - tasa_impuesto/100.0 - tasa_desg))

    monto_impuesto = math.ceil(monto_bruto * (tasa_impuesto / 100.0))
    monto_seguro = math.ceil(monto_bruto * tasa_desg)

    # --- CASCADA DE PRICING ---
    tipo_base = 'ggee' if in_garantia_estatal else 'comercial'
    spread_base = obtener_valor_matriz(tipo_base, in_cuotas, monto_bruto, es_plazo=True)
    
    desc_perfil = obtener_valor_matriz('perfiles', in_perfil, monto_bruto)
    spread_tras_perfil = spread_base + desc_perfil
    
    desc_segmento = obtener_valor_matriz('segmentos', in_segmento, monto_bruto)
    spread_tras_segmento = spread_tras_perfil + desc_segmento
    
    pct_canal = obtener_valor_matriz('canal', in_canal, monto_bruto)
    spread_tras_canal = spread_tras_segmento * (1.0 - (pct_canal / 100.0))
    
    pct_seguro = obtener_valor_matriz('seguros', in_seguro, monto_bruto)
    spread_resultante = spread_tras_canal * (1.0 - (pct_seguro / 100.0))
    
    cf_mensual = obtener_costo_fondo_historico(in_cuotas)
    cf_anual = cf_mensual * 12.0
    tasa_anual = spread_resultante + cf_anual
    
    # DEFINICIÓN CRÍTICA DE LA VARIABLE QUE FALTABA
    tasa_mensual_aplicada = min(tasa_anual / 12.0, 25.10 / 12.0) 

    # --- TABLA AMORTIZACIÓN ---
    tabla = []
    fecha_ven = in_fecha_curse
    for cuota in range(in_cuotas + 1):
        if cuota == 1: fecha_ven = in_primer_venc
        elif cuota > 1: fecha_ven = in_primer_venc + relativedelta(months=cuota-1)
        while not cal_chile.is_working_day(fecha_ven): fecha_ven += timedelta(days=1)
        tabla.append({'cuota': cuota, 'fec_ven': fecha_ven, 'dias': 0, 'tasa_diaria': 0.0, 'calc_cuota1': 1.0 if cuota == 0 else 0.0, 'calc_cuota2': 0.0})

    calc_cuota1_acum = 1.0
    calc_cuota2_acum = 0.0
    for i in range(1, len(tabla)):
        dias = (tabla[i]['fec_ven'] - tabla[i-1]['fec_ven']).days
        tabla[i]['dias'] = dias
        tabla[i]['tasa_diaria'] = dias * tasa_mensual_aplicada / 3000.0
        calc_cuota1_acum *= (1.0 + tabla[i]['tasa_diaria'])
        calc_cuota2_acum += (1.0 / calc_cuota1_acum)
        tabla[i]['calc_cuota2'] = calc_cuota2_acum

    valor_cuota = math.ceil(monto_bruto / tabla[-1]['calc_cuota2'])

    # --- CAE Y OTROS ---
    out_ctc = in_cuotas * valor_cuota
    flujo_caja = [in_monto_liquido] + [0] * max(0, ((in_primer_venc.year - in_fecha_curse.year) * 12 + in_primer_venc.month - in_fecha_curse.month) - 1) + [-valor_cuota] * in_cuotas
    tir = npf.irr(flujo_caja)
    cae_sernac = (tir * 12.0) * 100.0 if not math.isnan(tir) else 0.0

    return {
        "monto_liquido": in_monto_liquido,
        "monto_bruto": monto_bruto,
        "valor_cuota": valor_cuota,
        "tasa_mensual": tasa_mensual_aplicada,
        "tasa_anual": tasa_anual,
        "spread_resultante": spread_resultante,
        "costo_fondo_historico": cf_mensual,
        "cae_sernac": cae_sernac,
        "costo_total_credito": out_ctc,
        "tabla_desarrollo": tabla,
        "detalle_cascada": [
            {"Concepto": "1. Spread Base (Matriz)", "Ajuste": 0, "Spread Resultante": spread_base},
            {"Concepto": "2. Descuento Perfil", "Ajuste": desc_perfil, "Spread Resultante": spread_tras_perfil},
            {"Concepto": "3. Descuento Segmento", "Ajuste": desc_segmento, "Spread Resultante": spread_tras_segmento},
            {"Concepto": f"4. Descuento Canal ({pct_canal}%)", "Ajuste": -(spread_tras_segmento - spread_tras_canal), "Spread Resultante": spread_tras_canal},
            {"Concepto": f"5. Descuento Seguro ({pct_seguro}%)", "Ajuste": -(spread_tras_canal - spread_resultante), "Spread Resultante": spread_resultante},
            {"Concepto": "6. Costo de Fondo (Anual)", "Ajuste": cf_anual, "Spread Resultante": tasa_anual}
        ]
    }
