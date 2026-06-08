# 1. INSTAL·LACIÓ
!pip install -q -U google-genai flask-cors pyngrok beautifulsoup4 requests
!pip install requests==2.32.4

import json, requests, time, re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from pyngrok import ngrok
from google.colab import userdata
from google import genai

# --- CONFIGURACIÓ DE SEGURETAT ---
try:
    client = genai.Client(api_key=userdata.get('GOOGLE_API_KEY'))
    ngrok.set_auth_token(userdata.get('token_ngrok'))
    print("✅ API i ngrok connectats.")
except Exception as e:
    print(f"❌ ERROR SECRETS: {e}")

app = Flask(__name__)
CORS(app)

# --- EXTRACTOR INTEL·LIGENT FORÇAT ---
URL_BASE = "https://gmartin.inscastellbisbal.net/"
dades_gerard = []

def executar_extractor_total():
    global dades_gerard
    dades_gerard = []
    urls_per_visitar = [URL_BASE]
    urls_visitades = set()
    domini = urlparse(URL_BASE).netloc

    print(f"🚀 Iniciant extracció forçada de {URL_BASE}...")

    # Forcem capçaleres de navegador real per evitar que WordPress bloquegi el bot
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }

    # Entrem a l'API de WordPress per agafar els enllaços reals de tots els teus posts de cop
    try:
        api_url = f"{URL_BASE}wp-json/wp/v2/posts?per_page=100"
        res_api = requests.get(api_url, headers=headers, timeout=10)
        if res_api.status_code == 200:
            posts = res_api.json()
            for post in posts:
                link = post.get('link')
                if link and link not in urls_per_visitar:
                    urls_per_visitar.append(link)
            print(f"📂 Èxit! Trobats {len(posts)} posts interns a través de l'API de WordPress.")
    except Exception:
        print("⚠️ No s'ha pogut llistar via API, buscant per enllaços tradicionals...")

    while urls_per_visitar and len(urls_visitades) < 200:
        url = urls_per_visitar.pop(0)

        if url in urls_visitades or any(x in url.lower() for x in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', 'wp-admin', 'replytocom']):
            continue

        try:
            time.sleep(1) 
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: continue

            soup = BeautifulSoup(res.text, 'html.parser')
            urls_visitades.add(url)

            titol = soup.title.string.strip() if soup.title else "Pàgina sense títol"

            blocs_text = []
            for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
                text = element.get_text(strip=True)
                if len(text) > 4 and not any(x in text.lower() for x in ['propietari', 'powered by', 'utilitza wordpress']):
                    blocs_text.append(text)

            contingut_net = " ".join(blocs_text)

            if len(contingut_net) > 15:
                dades_gerard.append({"url": url, "titol": titol, "contingut": contingut_net})
                print(f"✅ [{len(urls_visitades)}] Guardat a la BBDD: {titol[:50]}")

            for a in soup.find_all('a', href=True):
                enllac = urljoin(URL_BASE, a['href']).split('#')[0]
                if urlparse(enllac).netloc == domini and enllac not in urls_visitades and enllac not in urls_per_visitar:
                    urls_per_visitar.append(enllac)

        except Exception:
            continue

    with open('dades_gerard_total.json', 'w', encoding='utf-8') as f:
        json.dump(dades_gerard, f, ensure_ascii=False, indent=4)
    print(f"\n📁 BBDD FINALITZADA: {len(dades_gerard)} pàgines i entrades guardades amb èxit!")

# --- CERCADOR INTEL·LIGENT MILLORAT ---
def trobar_pagines_rellevants(pregunta, maxim=3):
    paraules = [p.lower() for p in re.findall(r'\w+', pregunta) if len(p) > 3]
    resultats = []

    for pagina in dades_gerard:
        text_pagina = (pagina['titol'] + " " + pagina['contingut']).lower()
        puntuacio = sum(2 for p in paraules if p in text_pagina)
        if any(p in pagina['titol'].lower() for p in paraules):
            puntuacio += 5
        resultats.append((puntuacio, pagina))

    resultats.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in resultats[:maxim]]

# --- LÒGICA IA MILLORADA ---
def demanar_a_ia(pregunta):
    pagines_filtrades = trobar_pagines_rellevants(pregunta, maxim=5)

    context = (
        "Ets l'assistent del portafolis d'en Gerard Martin. "
        "Respon de forma amable, propera i professional en català. "
        "Analitza i utilitza TOTA la informació real del seu web que tens aquí sota per respondre a l'usuari. "
        "No inventis res. Si l'usuari et pregunta per un Reto o Repte, "
        "busca bé en els textos que et passo a continuació:\n\n"
    )

    for d in pagines_filtrades:
        context += f"--- INICI ARTÍCLE: {d['titol']} ---\n"
        context += f"Contingut complet: {d['contingut']}\n"
        context += f"URL: {d['url']}\n"
        context += "--------------------------------------\n\n"

    prompt_final = f"{context}\nPregunta de l'usuari: {pregunta}\nResposta del chatbot en català:"

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt_final
        )
        return response.text
    except Exception as e:
        return f"Error processant la resposta de la IA: {str(e)}"

# --- RUTES I SERVIDOR ---
@app.route('/ask', methods=['POST'])
def ask():
    try:
        msg = request.json.get("message")
        print(f"📩 Usuari pregunta: {msg}")
        resposta = demanar_a_ia(msg)
        return jsonify({"reply": resposta})
    except Exception as e:
        print(f"❌ Error BackEnd: {e}")
        return jsonify({"reply": f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    executar_extractor_total()
    !pkill ngrok
    time.sleep(2)
    public_url = ngrok.connect(5000).public_url
    print(f"\n🌍 URL PER AL TEU JAVASCRIPT:\n{public_url}/ask\n")
    app.run(port=5000)