import math
import os
import pandas as pd
import requests
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from workalendar.america import Chile

# ==============================================================================
# CONFIGURACIÓN DE TMC (Tasa Máxima Convencional)
# Actualiza estos valores mensualmente según lo publicado por la CMF.
# ==============================================================================
TMC_HASTA_50_UF = 38.50    # Tramo P02T01
TMC_HASTA_200_UF = 30.20   # Tramo P02T02
TMC_HASTA_5000_UF = 25.10  # Tramo P02T03
TMC_MAS_5000_UF = 18.00    # Tramo P02T04

# ==============================================================================
# FUNCIONES AUXILIARES (Reemplazan la Base de Datos)
# ==============================================================================

def obtener_uf(fecha_consulta: date) -> float:
    """Obtiene el valor de la UF para una fecha específica usando mindicador.cl"""
    try:
        # La API requiere formato dd-mm-yyyy
        fecha_str = fecha_consulta.strftime('%d-%m-%Y')
        url = f'https://mindicador.cl/api/uf/{fecha_str}'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get('serie'):
            return float(data['serie'][0]['valor'])
        else:
            print(f"Advertencia: No se encontró UF para {fecha_str}, usando valor por defecto.")
            return 38000.0 
    except Exception as e:
        print(f"Error consultando API UF: {e}. Usando valor por defecto.")
        return 38000.0

def ajustar_dia_habil(fecha_ven: date, calendario) -> date:
    """Avanza la fecha hasta el siguiente día hábil usando workalendar"""
    while not calendario.is_working_day(fecha_ven):
        fecha_ven += timedelta(days=1)
    return fecha_ven

def obtener_valor_plantilla(ruta_csv: str, nombre_plantilla: str, monto_bruto: float, plazo: int) -> float:
    """Busca el spread o descuento en el CSV de plantillas"""
    try:
        df = pd.read_csv(ruta_csv)
        # Filtrar equivalente al WHERE del SQL
        filtro = (
            (df['plantilla'] == nombre_plantilla) &
            (df['monto_desde'] <= monto_bruto) & (df['monto_hasta'] >= monto_bruto) &
            (df['plazo_desde'] <= plazo) & (df['plazo_hasta'] >= plazo)
        )
        resultado = df[filtro]
        if not resultado.empty:
            return float(resultado['valor'].iloc[0])
        return 0.0
    except Exception as e:
        print(f"Error leyendo {ruta_csv}: {e}")
        return 0.0

def obtener_costo_fondos(ruta_csv: str, plazo_meses: int, resguardo_cf: float) -> float:
    """Busca el costo de fondos en el CSV y lo anualiza"""
    try:
        df = pd.read_csv(ruta_csv)
        df['fecha'] = pd.to_datetime(df['fecha']).dt.date
        
        # Mapeo de meses a años según tu lógica SQL: 
        # <=24 -> 1 año, <=36 -> 2 años, <=48 -> 3 años, <=60 -> 4 años, <=72 -> 5 años
        if plazo_meses <= 24: plazo_anos = 1
        elif plazo_meses <= 36: plazo_anos = 2
        elif plazo_meses <= 48: plazo_anos = 3
        elif plazo_meses <= 60: plazo_anos = 4
        else: plazo_anos = 5
        
        # Buscar la fecha máxima (más reciente) en el CSV
        max_fecha = df['fecha'].max()
        df_reciente = df[df['fecha'] == max_fecha]
        
        # Obtener el CF para el plazo en años
        resultado = df_reciente[df_reciente['plazo'] == plazo_anos]
        if not resultado.empty:
            cf_base = float(resultado['cf'].iloc[0])
            return (cf_base * 12.0) + resguardo_cf
        return 0.0
    except Exception as e:
        print(f"Error leyendo {ruta_csv}: {e}")
        return 0.0

# ==============================================================================
# FUNCIÓN PRINCIPAL DE SIMULACIÓN
# ==============================================================================

def com_simulacion(in_fecha_curse: date, in_primer_venc: date, in_monto_liquido: int, 
                   in_plantilla_tasa: str, in_plantilla_descuento: str, 
                   in_cuotas: int, in_resguardo_cf: float) -> dict:
    
    # 1. Rutas relativas a los CSV en el repositorio
    # os.path.dirname(__file__) obtiene la ruta donde está guardado este script
    directorio_actual = os.path.dirname(__file__)
    ruta_plantillas = os.path.join(directorio_actual, 'data', 'plantillas.csv')
    ruta_cf = os.path.join(directorio_actual, 'data', 'cf.csv')
    
    # Instanciar calendario chileno
    cal_chile = Chile()

    # Variables iniciales fijas
    plazo = in_cuotas
    notario = 2640
    tasa_impuesto_plazo = 0.066
    tasa_impuesto_max = 0.8
    tasa_desg = 0.0
    
    tabla = []
    
    # ---------------------------------------------------------
    # Generación de Fechas y Cuotas
    # ---------------------------------------------------------
    for cuota in range(plazo + 1):
        if cuota == 0:
            fecha_ven = in_fecha_curse
        elif cuota == 1:
            fecha_ven = in_primer_venc
        else:
            fecha_ven = in_primer_venc + relativedelta(months=cuota-1)
            
        # Ajuste de día hábil
        fecha_ven = ajustar_dia_habil(fecha_ven, cal_chile)
        
        tabla.append({
            'cuota': cuota, 'fec_ven': fecha_ven,
            'dias': 0, 'dias_acum': 0, 'tasa_diaria': 0.0,
            'calc_cuota1': 1.0 if cuota == 0 else 0.0,
            'calc_cuota2': 0.0,
            'saldo_insoluto': 0.0, 'amortizacion': 0.0, 'intereses': 0.0
        })

    # Cálculo de plazo en meses
    fecha_final = tabla[-1]['fec_ven'] - relativedelta(months=1)
    out_plazo = (fecha_final.year - in_fecha_curse.year) * 12 + (fecha_final.month - in_fecha_curse.month)
    
    # ---------------------------------------------------------
    # Impuestos y Monto Bruto
    # ---------------------------------------------------------
    tasa_impuesto = min(out_plazo * tasa_impuesto_plazo, tasa_impuesto_max)
    monto_bruto = math.ceil((in_monto_liquido + notario) / (1.0 - tasa_impuesto/100.0 - tasa_desg))
    
    # ---------------------------------------------------------
    # Obtención de Datos Externos (API, CSV, TMC)
    # ---------------------------------------------------------
    valor_uf = obtener_uf(in_fecha_curse)
    monto_bruto_uf = monto_bruto / valor_uf
    
    # Selección de TMC según tramos
    if monto_bruto_uf <= 50: tmc = TMC_HASTA_50_UF
    elif monto_bruto_uf <= 200: tmc = TMC_HASTA_200_UF
    elif monto_bruto_uf <= 5000: tmc = TMC_HASTA_5000_UF
    else: tmc = TMC_MAS_5000_UF

    # Lectura de CSVs
    spread = obtener_valor_plantilla(ruta_plantillas, in_plantilla_tasa, monto_bruto, plazo)
    descuento_df = obtener_valor_plantilla(ruta_plantillas, in_plantilla_descuento, monto_bruto, plazo)
    cf = obtener_costo_fondos(ruta_cf, plazo, in_resguardo_cf)
    
    # Cálculo de tasas
    tasa_pizarra = (spread + cf) / 12.0
    if tasa_pizarra >= tmc / 12.0:
        tasa_pizarra = tmc / 12.0
        
    tasa = tasa_pizarra * (1.0 - descuento_df / 100.0)

    # ---------------------------------------------------------
    # Días, Tasa Diaria y Factores de Cuota
    # ---------------------------------------------------------
    calc_cuota1_acum = 1.0
    calc_cuota2_acum = 0.0
    
    for i in range(1, len(tabla)):
        diferencia_dias = (tabla[i]['fec_ven'] - tabla[i-1]['fec_ven']).days
        tabla[i]['dias'] = diferencia_dias
        tabla[i]['tasa_diaria'] = diferencia_dias * tasa / 3000.0
        
        # Factores
        calc_cuota1_acum = (1.0 + tabla[i]['tasa_diaria']) * calc_cuota1_acum
        calc_cuota2_acum = calc_cuota2_acum + (1.0 / calc_cuota1_acum)
        tabla[i]['calc_cuota1'] = calc_cuota1_acum
        tabla[i]['calc_cuota2'] = calc_cuota2_acum

    valor_cuota = math.ceil(monto_bruto / tabla[-1]['calc_cuota2'])

    # ---------------------------------------------------------
    # Tabla de Amortización
    # ---------------------------------------------------------
    saldo_insoluto = float(monto_bruto)
    dias_acum = 0
    
    for i in range(1, len(tabla)):
        intereses = round(saldo_insoluto * tasa / 100.0, 0)
        dias_acum += tabla[i]['dias']
        
        if tabla[i]['cuota'] < plazo:
            amortizacion = valor_cuota - intereses
            saldo_insoluto -= amortizacion
        else:
            amortizacion = saldo_insoluto
            saldo_insoluto = 0.0
            
        tabla[i]['intereses'] = intereses
        tabla[i]['amortizacion'] = amortizacion
        tabla[i]['saldo_insoluto'] = saldo_insoluto
        tabla[i]['dias_acum'] = dias_acum

    # ---------------------------------------------------------
    # Indicadores Finales (CTC, CAE, etc.)
    # ---------------------------------------------------------
    out_impuestos = math.ceil(monto_bruto * tasa_impuesto / 100.0)
    out_seg_desgravamen = math.ceil(monto_bruto * tasa_desg)
    out_ctc = math.ceil(in_cuotas * valor_cuota)
    
    sum_dias_amort = sum(row['dias_acum'] * row['amortizacion'] for row in tabla[1:])
    sum_amort = sum(row['amortizacion'] for row in tabla[1:])
    out_duration = (sum_dias_amort / sum_amort / 360.0) if sum_amort else 0
    
    out_cae = 100.0 * (out_ctc - in_monto_liquido) / (in_monto_liquido * out_duration) if out_duration else 0

    return {
        "valor_cuota": valor_cuota,
        "monto_bruto": monto_bruto,
        "tasa_aplicada": tasa,
        "cae": out_cae,
        "costo_total_credito": out_ctc,
        "tmc_aplicada": tmc,
        "valor_uf_hoy": valor_uf
    }