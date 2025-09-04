# 🧾 Extractor de Facturas PDF

Aplicación web en **Python + Flask** que permite subir archivos PDF de facturas, extraer texto (con soporte OCR para PDFs escaneados) y obtener los datos en distintos formatos (Excel, CSV, JSON).

## 🚀 Características

- Subida de archivos PDF vía interfaz web.
- Extracción de texto:
  - Si el PDF contiene texto digital → se usa [pdfplumber](https://github.com/jsvine/pdfplumber).
  - Si el PDF es una imagen escaneada → se usa OCR con [pytesseract](https://github.com/madmaze/pytesseract) + [pdf2image](https://github.com/Belval/pdf2image).
- Normalización del texto para mejorar resultados de OCR.
- Búsqueda de patrones de facturas (configurable):
  - `FAC-001`
  - `FACTURA N° 123`
  - `FACT. 456`
  - `N° COMPROB. 789`
  - `INVOICE 654`
- Extracción de importes en pesos (`$39000`, `$ 12.500,50`, etc.).
- Vista previa en tabla HTML.
- Exportación de resultados en:
  - 📊 Excel (`.xlsx`)
  - 📄 CSV
  - 🌐 JSON
- Interfaz con Bootstrap 5 + spinner de carga.

---

## 📂 Estructura del proyecto

project/
│── app.py # Backend Flask
│── templates/
│ └── index.html # Interfaz principal
│── static/
│ └── styles.css # Estilos CSS
│── uploads/ # PDFs y resultados generados


---

## ⚙️ Instalación y uso

### 1. Clonar repositorio
```bash
git clone https://github.com/Daniel-Collado/pdf-extractor.git
cd extractor-facturas
