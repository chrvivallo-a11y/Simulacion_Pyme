import math
import os
import pandas as pd
import numpy_financial as npf
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from workalendar.america import Chile

DATA_CACHE = {}

def cargar_datos_csv():
    global DATA_CACHE
    dir_actual = os.path.dirname(__file__)
    archivos = {
        'comercial': '1. plantilla_comercial.csv', 'ggee': '2. plantilla_ggee.csv',
        'perfiles': '3. plantilla_perfiles.csv', 'segmentos': '4. plantilla_segmentos.csv',
        'canal': '5. plantilla_canal.csv', 'seguros': '6. plantilla_seguros.csv',
        'cf': 'cf.csv', 'uf': 'uf.csv', 'desgravamen': 'desgravamen_aval.csv'
    }
    for clave, nombre in archivos.items():
        ruta = os.path.join(dir_actual, nombre)
        if not os.path.exists(ruta):
            ruta = os.path.join(dir_actual, 'data', nombre)
        if not os.path.exists(ruta): continue
        try:
            df = pd.read_csv(ruta, sep=None, engine='python')
            if clave not in ['cf', 'uf', 'desgravamen']:
                df.set_index(df.columns[0], inplace=True)
                df = df.replace({',': '.'}, regex=True).astype(float)
                df.index = df.index.astype(str)
            DATA_CACHE[clave] = df
        except: pass

def obtener_tasa_desgravamen(cuotas):
    try:
        df = DATA_CACHE.get('desgravamen')
        if df is None: return 0.0
        c = min(cuotas, df['plazo'].astype(int).max())
        val = df[df['plazo'] == c]['tasaxmil'].iloc[0]
        return float(str(val).replace(',', '.')) / 1000.0
    except: return 0.0

def obtener_valor_matriz(tipo, fila_val, monto, es_plazo=False):
    if tipo not in DATA_CACHE: return 0.0
    df = DATA_CACHE[tipo]
    m_millones = monto / 1_000_000.0
    cols = sorted([int(c) for c in df.columns])
    col = str(next((c for c in cols if m_millones <= c), cols[-1]))
    if es_plazo:
        idxs = sorted([int(float(r)) for r in df.index])
        idx = str(next((r for r in idxs if float(fila_val) <= r), idxs[-1]))
    else:
        idx = str(fila_val).upper().strip()
    return float(df.loc[idx, col]) if idx in df.index else 0.0

def obtener_uf(fecha_consulta):
    if not DATA_CACHE: cargar_datos_csv()
    try:
        df = DATA_CACHE.get('uf')
        df['fecha'] = pd.to_datetime(df['fecha']).dt.date
        f_val = df[df['fecha'] <= fecha_consulta].sort_values(by='fecha').iloc[-1]['valor']
        return float(str(f_val).replace(',', '.'))
    except: return 39800.0

def com_simulacion_pyme(in_fecha_curse, in_primer_venc, in_monto_liquido, in_cuotas, in_garantia_estatal, in_perfil, in_segmento, in_canal, in_seguro):
    if not DATA_CACHE: cargar_datos_csv()
    cal = Chile()

    # 1. Gastos Iniciales y Monto Bruto
    t_desg = obtener_tasa_desgravamen(in_cuotas) if in_seguro == 'DESGRAVAMEN' else 0.0
    t_imp = min(in_cuotas * 0.066, 0.8)
    monto_bruto = math.ceil((in_monto_liquido + 2640) / (1.0 - t_imp/100.0 - t_desg))

    # 2. Lógica de Colchón CF
    cf_anual_puro, colchon_anual = 0.0, 0.0
    try:
        df_cf = DATA_CACHE['cf']
        per = df_cf['periodo'].max()
        df_r = df_cf[df_cf['periodo'] == per].sort_values(by='plazo_hasta').reset_index(drop=True)
        f = df_r[(df_r['plazo_desde'] <= in_cuotas) & (df_r['plazo_hasta'] >= in_cuotas)]
        if not f.empty:
            idx = f.index[0]
            cf_m = float(str(f['cf'].iloc[0]).replace(',', '.'))
            cf_anual_puro = cf_m * 12.0
            if f['plazo_hasta'].iloc[0] >= 24 and idx > 0:
                cf_ant = float(str(df_r.loc[idx - 1, 'cf']).replace(',', '.'))
                colchon_anual = max(0.0, (cf_m - cf_ant) * 12.0)
    except: cf_anual_puro = 5.40

    # 3. Cascada de Pricing (Colchón Positivo al inicio)
    tipo_b = 'ggee' if in_garantia_estatal else 'comercial'
    sp_matriz = obtener_valor_matriz(tipo_b, in_cuotas, monto_bruto, True)
    sp_base = sp_matriz + colchon_anual 
    
    d_perf = obtener_valor_matriz('perfiles', in_perfil, monto_bruto)
    sp_perf = sp_base + d_perf
    d_segm = obtener_valor_matriz('segmentos', in_segmento, monto_bruto)
    sp_segm = sp_perf + d_segm
    p_can = obtener_valor_matriz('canal', in_canal, monto_bruto)
    sp_can = sp_segm * (1.0 - p_can/100.0)
    p_seg = obtener_valor_matriz('seguros', in_seguro, monto_bruto)
    sp_fin = sp_can * (1.0 - p_seg/100.0)
    
    tasa_anual = sp_fin + (cf_anual_puro - colchon_anual)
    tasa_mensual = tasa_anual / 12.0

    # 4. Tabla de Desarrollo y Valor Cuota
    tabla = []
    fecha_v = in_fecha_curse
    for c in range(in_cuotas + 1):
        if c == 1: fecha_v = in_primer_venc
        elif c > 1: fecha_v = in_primer_venc + relativedelta(months=c-1)
        while not cal.is_working_day(fecha_v): fecha_v += timedelta(days=1)
        tabla.append({'cuota': c, 'fec_ven': fecha_v, 'dias': 0, 'tasa_diaria': 0.0, 'calc_cuota1': 1.0 if c==0 else 0.0})

    c1_ac, c2_ac = 1.0, 0.0
    for i in range(1, len(tabla)):
        dias = (tabla[i]['fec_ven'] - tabla[i-1]['fec_ven']).days
        tabla[i]['dias'] = dias
        tabla[i]['tasa_diaria'] = (dias * tasa_mensual) / 3000.0
        c1_ac *= (1.0 + tabla[i]['tasa_diaria'])
        c2_ac += (1.0 / c1_ac)
    
    valor_cuota = math.ceil(monto_bruto / c2_ac)

    # 5. CAE
    flujo = [in_monto_liquido] + [0]*((in_primer_venc.year-in_fecha_curse.year)*12 + in_primer_venc.month-in_fecha_curse.month-1) + [-valor_cuota]*in_cuotas
    tir = npf.irr(flujo)
    cae = (tir * 12.0 * 100.0) if not math.isnan(tir) else 0.0

    return {
        "monto_bruto": monto_bruto, "valor_cuota": valor_cuota, "tasa_mensual": tasa_mensual,
        "tasa_anual": tasa_anual, "cae_sernac": cae, "tabla_desarrollo": tabla,
        "detalle_cascada": [
            {"Concepto": "1. Spread Base (Matriz)", "Ajuste": 0, "Spread Resultante": sp_matriz},
            {"Concepto": "2. Ajuste Colchón (+) Política", "Ajuste": colchon_anual, "Spread Resultante": sp_base},
            {"Concepto": "3. Descuento Perfil", "Ajuste": d_perf, "Spread Resultante": sp_perf},
            {"Concepto": "4. Descuento Segmento", "Ajuste": d_segm, "Spread Resultante": sp_segm},
            {"Concepto": f"5. Descuento Canal ({p_can}%)", "Ajuste": -(sp_segm - sp_can), "Spread Resultante": sp_can},
            {"Concepto": f"6. Descuento Seguro ({p_seg}%)", "Ajuste": -(sp_can - sp_fin), "Spread Resultante": sp_fin},
            {"Concepto": "7. Costo Fondo Neto (Anual)", "Ajuste": cf_anual_puro - colchon_anual, "Spread Resultante": tasa_anual}
        ]
    }
