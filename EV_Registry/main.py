#!/usr/bin/env python3
"""
EV_Registry: API REST para el registro de Puntos de Carga.
Expone endpoints para dar de alta CPs y obtener credenciales.
"""
import sys
from flask import Flask, request, jsonify
from EV_Registry import db

app = Flask(__name__)

# Inicializamos la DB al arrancar
db.init_db()

@app.route('/register', methods=['POST'])
def register():
    """
    Endpoint para registrar un CP.
    Espera un JSON: { "id": "CP_01", "location": "Madrid" }
    Retorna: { "status": "ok", "token": "uuid-secreto..." }
    """
    data = request.get_json()
    
    if not data or 'id' not in data or 'location' not in data:
        return jsonify({'status': 'error', 'message': 'Datos incompletos (id, location)'}), 400
    
    cp_id = data['id']
    location = data['location']
    
    print(f"[REGISTRY] Petición de registro recibida para: {cp_id} en {location}")
    
    # Registramos en BBDD y obtenemos el token
    token = db.register_cp(cp_id, location)
    
    print(f"[REGISTRY] CP {cp_id} registrado con éxito. Token generado.")
    
    return jsonify({
        'status': 'ok',
        'token': token,
        'message': 'CP registrado correctamente. Usa este token para autenticarte en la Central.'
    }), 200

if __name__ == '__main__':
    # El Registry correrá en el puerto 6000 para no chocar con otros
    # En producción usaríamos ssl_context='adhoc' para HTTPS, 
    # pero para desarrollo empezamos con HTTP simple.
    print("[REGISTRY] Servidor de Registro escuchando en puerto 6000...")
    app.run(host='0.0.0.0', port=6000, debug=True)