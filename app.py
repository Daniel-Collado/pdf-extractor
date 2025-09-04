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


def procesar_datos(texto):
    texto_normalizado = normalizar_texto(texto)

    # Buscar facturas con todos los patrones
    facturas = []
    for pattern in FACTURA_PATTERNS:
        encontrados = re.findall(
            pattern, texto_normalizado, flags=re.IGNORECASE)
        for f in encontrados:
            facturas.append(f.strip())

    # Buscar importes
    importes = re.findall(r"\$ ?([\d.,]+)", texto_normalizado)

    # Convertir importes a float
    importes_limpios = []
    for imp in importes:
        imp_clean = imp.replace(".", "").replace(",", ".")
        try:
            importes_limpios.append(float(imp_clean))
        except ValueError:
            importes_limpios.append(0.0)

    # Igualar longitudes
    max_len = max(len(facturas), len(importes_limpios))
    facturas += ["SIN FACTURA"] * (max_len - len(facturas))
    importes_limpios += [0.0] * (max_len - len(importes_limpios))

    # DataFrame final
    df = pd.DataFrame({"Factura": facturas, "Importe": importes_limpios})
    total = df["Importe"].sum()
    df.loc[len(df)] = ["TOTAL GENERAL", total]
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

    # Procesamiento (puede tardar si hay OCR)
    texto = extraer_texto(pdf_path)
    df = procesar_datos(texto)

    return jsonify({
        "html": df.to_html(classes="table table-striped table-bordered", index=False),
        "filename": filename
    })


@app.route("/download/<fmt>", methods=["GET", "POST"])
def download(fmt):
    # Acepta GET (desde links) o POST (si quisieras)
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

    # Reprocesar (o podrías guardar el df previamente en disco/DB)
    texto = extraer_texto(pdf_path)
    df = procesar_datos(texto)

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

    # download_name funciona en Flask >=2.0
    return send_file(output_path, as_attachment=True, download_name=output_filename)


if __name__ == "__main__":
    # 🔹 El puerto se toma de la variable de entorno (Render lo define automáticamente).
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
