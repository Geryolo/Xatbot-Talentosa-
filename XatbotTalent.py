# =====================================================
# CHATBOT GERARD MARTIN - Google Colab
# Llibreria: google-genai (nova, substitueix google-generativeai)
# =====================================================

# 1. INSTAL·LACIÓ
!pip install -q google-genai flask-cors pyngrok beautifulsoup4
!pip install -q requests==2.32.4

import json, requests, time, re
from google import genai
from google.genai import types
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from pyngrok import ngrok
from google.colab import userdata

# =====================================================
# 2. CONFIGURACIÓ
# =====================================================
try:
    client = genai.Client(api_key=userdata.get('GOOGLE_API_KEY'))
    ngrok.set_auth_token(userdata.get('token_ngrok'))
    print("✅ API i ngrok connectats correctament.")
except Exception as e:
    print(f"❌ ERROR SECRETS: {e}")

app = Flask(__name__)
CORS(app)

# =====================================================
# 3. EXTRACTOR DEL WEB
# =====================================================
URL_BASE = "https://gmartin.inscastellbisbal.net/"
dades_gerard = []

def executar_extractor_total():
    global dades_gerard
    dades_gerard = []
    urls_per_visitar = [URL_BASE]
    urls_visitades = set()
    domini = urlparse(URL_BASE).netloc

    print(f"🚀 Iniciant extracció de {URL_BASE}...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        api_url = f"{URL_BASE}wp-json/wp/v2/posts?per_page=100"
        res_api = requests.get(api_url, headers=headers, timeout=10)
        if res_api.status_code == 200:
            posts = res_api.json()
            for post in posts:
                link = post.get('link')
                if link and link not in urls_per_visitar:
                    urls_per_visitar.append(link)
            print(f"📄 {len(posts)} posts trobats via API WordPress")
    except:
        pass

    while urls_per_visitar and len(urls_visitades) < 200:
        url = urls_per_visitar.pop(0)
        if url in urls_visitades or any(x in url.lower() for x in ['.jpg', '.png', '.gif', '.pdf', 'wp-admin', 'wp-login']):
            continue

        try:
            time.sleep(1)
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, 'html.parser')
            urls_visitades.add(url)
            titol = soup.title.string.strip() if soup.title else "Pàgina"

            blocs_text = [
                element.get_text(strip=True)
                for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])
                if len(element.get_text()) > 10
            ]
            contingut_net = " ".join(blocs_text)

            if len(contingut_net) > 20:
                dades_gerard.append({
                    "url": url,
                    "titol": titol,
                    "contingut": contingut_net
                })
                print(f"✅ Guardat: {titol[:50]}")

            for a in soup.find_all('a', href=True):
                enllac = urljoin(URL_BASE, a['href']).split('#')[0]
                if urlparse(enllac).netloc == domini and enllac not in urls_visitades:
                    urls_per_visitar.append(enllac)
        except:
            continue

    print(f"\n✅ Extracció finalitzada. {len(dades_gerard)} pàgines guardades.")

# =====================================================
# 4. CERCADOR
# =====================================================
def trobar_pagines_rellevants(pregunta, maxim=5):
    paraules = [p.lower() for p in re.findall(r'\w+', pregunta) if len(p) > 3]
    resultats = []
    for pagina in dades_gerard:
        text_complet = (pagina['titol'] + ' ' + pagina['contingut']).lower()
        puntuacio = sum(2 for p in paraules if p in text_complet)
        if puntuacio > 0:
            resultats.append((puntuacio, pagina))
    resultats.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in resultats[:maxim]]

# =====================================================
# 5. LÒGICA IA - Llibreria nova google-genai
# =====================================================
def demanar_a_ia(pregunta):
    pagines_filtrades = trobar_pagines_rellevants(pregunta, maxim=5)

    context = "Ets l'assistent personal d'en Gerard Martin. Respon sempre en català, de forma amable i clara, usant la informació del seu portfolio:\n\n"

    if pagines_filtrades:
        for d in pagines_filtrades:
            context += f"--- {d['titol']} ({d['url']}) ---\n{d['contingut'][:600]}\n\n"
    else:
        context += "(No s'ha trobat informació específica sobre aquest tema al portfolio)\n\n"

    prompt_final = f"{context}\nPregunta de l'usuari: {pregunta}\n\nResposta en català:"

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-lite',
            contents=prompt_final
        )
        return response.text
    except Exception as e:
        return f"Error en la IA: {str(e)}"

# =====================================================
# 6. RUTES FLASK
# =====================================================
@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({"reply": "Error: missatge buit"}), 400
        msg = data.get("message", "").strip()
        if not msg:
            return jsonify({"reply": "Error: missatge buit"}), 400
        resposta = demanar_a_ia(msg)
        return jsonify({"reply": resposta})
    except Exception as e:
        return jsonify({"reply": f"Error del servidor: {str(e)}"}), 500

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "✅ Servidor actiu", "pagines": len(dades_gerard)})

# =====================================================
# 7. ARRENCADA
# =====================================================
if __name__ == '__main__':
    executar_extractor_total()

    !pkill ngrok
    time.sleep(2)

    public_url = ngrok.connect(5000).public_url
    print(f"\n{'='*50}")
    print(f"🌍 URL PER AL TEU HTML:")
    print(f"   {public_url}/ask")
    print(f"{'='*50}\n")

    app.run(port=5000)
