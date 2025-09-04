import re
import pdfplumber
import pandas as pd
from flask import Flask, request, render_template, send_file, jsonify
from pdf2image import convert_from_path
import pytesseract
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)

# Ruta a tesseract (solo en Windows local; en Render lo instalás en Dockerfile)
pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # valor por defecto en Windows
)

# Patrones configurables
FACTURA_PATTERNS = [
    r"FAC-?\d+",
    r"FACTURA\s*N[º°]?\s*\d+",
    r"FACT\.?\s*\d+",
    r"N[º°]?\s*FACTURA\s*\d+",
    r"N[º°]?\s*COMPROB\.?\s*\d+",
    r"INVOICE\s*\d+"
]


def extraer_texto(pdf_path):
    texto_total = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            texto = page.extract_text()
            if not texto or texto.strip() == "":
                # OCR si no hay texto en la página
                imagen = convert_from_path(
                    pdf_path, first_page=i+1, last_page=i+1)[0]
                texto = pytesseract.image_to_string(imagen, lang="spa")
            texto_total += "\n" + (texto or "")
    return texto_total


def normalizar_texto(texto):
    # reducir múltiples espacios a uno
    return re.sub(r"\s+", " ", texto)


# 🔹 Función de formateo manual estilo AR
def formatear_numero(x):
    try:
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def procesar_datos(texto):
    texto_normalizado = normalizar_texto(texto)

    # 🔎 Nuevos patrones de factura
    FACTURA_PATTERNS_EXT = FACTURA_PATTERNS + [
        r"Factura\s*n[úu]mero[:\s]*\d+",
        r"Nro\s*Factura[:\s]*[\w-]+",
        r"Factura\s*ID[:\s]*\d+",
        r"Comprobante\s*N[º°]?\s*[\w-]+"
    ]

    # Buscar facturas
    facturas = []
    for pattern in FACTURA_PATTERNS_EXT:
        encontrados = re.findall(pattern, texto_normalizado, flags=re.IGNORECASE)
        facturas.extend([f.strip() for f in encontrados])

    # Buscar importes en ARS / USD
    importes_ars = re.findall(r"(?:\$|ARS)\s*([\d.,]+)", texto_normalizado, flags=re.IGNORECASE)
    importes_usd = re.findall(r"(?:USD)\s*([\d.,]+)", texto_normalizado, flags=re.IGNORECASE)

    def limpiar_importe(imp):
        imp = imp.replace(".", "").replace(",", ".")
        try:
            return float(imp)
        except:
            return 0.0

    importes_ars = [limpiar_importe(i) for i in importes_ars]
    importes_usd = [limpiar_importe(i) for i in importes_usd]

    # Igualar longitudes (separado para ARS y USD)
    max_len = max(len(facturas), len(importes_ars), len(importes_usd))
    facturas += ["SIN FACTURA"] * (max_len - len(facturas))
    importes_ars += [0.0] * (max_len - len(importes_ars))
    importes_usd += [0.0] * (max_len - len(importes_usd))

    # Armar DataFrame con números puros
    df = pd.DataFrame({
        "Factura": facturas,
        "Importe_ARS": importes_ars,
        "Importe_USD": importes_usd
    })

    # Totales
    total_ars = df["Importe_ARS"].sum()
    total_usd = df["Importe_USD"].sum()
    df.loc[len(df)] = ["TOTAL GENERAL", total_ars, total_usd]

    return df


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/preview", methods=["POST"])
def preview_file():
    if "file" not in request.files:
        return jsonify({"error": "No se subió archivo"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    filename = secure_filename(file.filename)
    os.makedirs("uploads", exist_ok=True)
    pdf_path = os.path.join("uploads", filename)
    file.save(pdf_path)

    # Procesamiento
    texto = extraer_texto(pdf_path)
    df = procesar_datos(texto)

    # 🔹 Formatear SOLO para vista previa
    df_preview = df.copy()
    df_preview["Importe_ARS"] = df_preview["Importe_ARS"].apply(formatear_numero)
    df_preview["Importe_USD"] = df_preview["Importe_USD"].apply(formatear_numero)

    return jsonify({
        "html": df_preview.to_html(classes="table table-striped table-bordered", index=False),
        "filename": filename
    })


@app.route("/download/<fmt>", methods=["GET", "POST"])
def download(fmt):
    if request.method == "GET":
        filename = request.args.get("filename")
    else:
        filename = request.form.get("filename")

    if not filename:
        return "No se recibió nombre de archivo", 400

    filename = secure_filename(filename)
    pdf_path = os.path.join("uploads", filename)
    if not os.path.exists(pdf_path):
        return "El archivo no existe en el servidor", 400

    texto = extraer_texto(pdf_path)
    df = procesar_datos(texto)  # números crudos

    output_filename = f"resultado.{fmt}"
    output_path = os.path.join("uploads", output_filename)

    if fmt == "xlsx":
        df.to_excel(output_path, index=False)
    elif fmt == "csv":
        df.to_csv(output_path, index=False)
    elif fmt == "json":
        df.to_json(output_path, orient="records", force_ascii=False)
    else:
        return "Formato no soportado", 400

    return send_file(output_path, as_attachment=True, download_name=output_filename)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
