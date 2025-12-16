import json

# Definimos los bytes de control
STX = b'\x02' # Start of Text
ETX = b'\x03' # End of Text

def calculate_lrc(data_bytes):
    """
    Calcula el Longitudinal Redundancy Check (LRC) haciendo un XOR
    de todos los bytes en data_bytes.
    """
    lrc = 0
    for byte in data_bytes:
        lrc ^= byte
    return bytes([lrc])

def wrap_message(data_dict):
    """
    Toma un diccionario de Python, lo convierte a JSON (bytes)
    y lo envuelve en una trama <STX><DATA><ETX><LRC>.
    """
    try:
        data_bytes = json.dumps(data_dict).encode('utf-8')
        lrc_byte = calculate_lrc(data_bytes)
        
        # Concatenamos la trama completa
        return STX + data_bytes + ETX + lrc_byte
    
    except Exception as e:
        print(f"[PROTO] Error al envolver mensaje: {e}")
        return None