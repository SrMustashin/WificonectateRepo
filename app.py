import os
import pandas as pd
import requests
from flask import Flask, request, render_template, redirect, url_for, flash
from dotenv import load_dotenv

# ─── CARGAR VARIABLES DE ENTORNO ───────────────────────────────────────────────
load_dotenv()
API_URL = os.getenv("IWISP_API_URL")      # Asegúrate de que termine en '/'
API_KEY = os.getenv("IWISP_API_KEY")   

print("🌐 Usando URL:", API_URL)
print("🔑 API KEY:", API_KEY[:5] + "..." if API_KEY else "No API key cargada")
   # Tu clave de API

# ─── CONFIGURACIÓN DE FLASK ───────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'clave_secreta'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ─── RUTAS ─────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html', preview=None, resultados=None)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No se envió ningún archivo')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('Nombre de archivo vacío')
        return redirect(url_for('index'))

    try:
        # ─ Leer y renombrar columnas ────────────────────────────────────────────
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        df = pd.read_excel(
            filepath,
            usecols=["Descripción", "Importe de crédito", "Fecha del apunte", "Referencia de cliente"],
            engine="openpyxl"
        )
        df.rename(columns={
            "Descripción": "descripcion",
            "Importe de crédito": "monto",
            "Fecha del apunte": "fecha_pago",
            "Referencia de cliente": "transaccion"
        }, inplace=True)

        # ─ Validar y separar cliente/teléfono ──────────────────────────────────
        split_cols = df['descripcion'].astype(str).str.strip().str.split(' ', n=1, expand=True)
        if split_cols.shape[1] != 2:
            raise ValueError("Cada 'Descripción' debe tener dos valores: ID y teléfono.")
        df['idcliente'] = split_cols[0]
        df['telefono'] = split_cols[1]

        # ─ Formatear y limpiar fechas ──────────────────────────────────────────
        df['fecha_pago'] = pd.to_datetime(df['fecha_pago'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['fecha_pago'])  # eliminar fechas inválidas

        # ─ Preparar vista previa ───────────────────────────────────────────────
        preview_df = df[['idcliente', 'telefono', 'transaccion', 'monto', 'fecha_pago']].copy()

        # ─ Enviar a iWisp ─────────────────────────────────────────────────────
        resultados = []
        for _, row in preview_df.iterrows():
            try:
                # Convertir fecha a string si aún no lo es
                if not isinstance(row["fecha_pago"], str):
                    fecha_str = row["fecha_pago"].strftime('%Y-%m-%d')
                else:
                    fecha_str = row["fecha_pago"]
            except Exception as e:
                resultados.append({
                    "idcliente": row["idcliente"],
                    "status": "Error",
                    "mensaje": f"Fecha inválida: {e}"
                })
                continue

            payload = {
                "api_key": API_KEY,
                "idcliente": str(row["idcliente"]),
                "telefono": str(row["telefono"]),
                "transaccion": str(row["transaccion"]),
                "monto": float(row["monto"]),
                "fecha_pago": fecha_str
            }

            headers = {"Content-Type": "application/json"}

            print("Payload enviado a iWisp:")
            print(payload)

            try:
                r = requests.post(API_URL, json=payload, headers=headers)
                contenido = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else r.text
                print(f"Status {r.status_code} -- {contenido}")

                resultados.append({
                    "idcliente": row["idcliente"],
                    "status": r.status_code,
                    "mensaje": contenido
                })
            except Exception as ex:
                resultados.append({
                    "idcliente": row["idcliente"],
                    "status": "Error",
                    "mensaje": str(ex)
                })

        return render_template('index.html',
                               preview=preview_df.to_dict(orient='records'),
                               resultados=resultados)

    except Exception as e:
        flash(f"Error al procesar el archivo: {e}")
        return redirect(url_for('index'))

# ─── EJECUCIÓN ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True)
