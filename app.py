import os, uuid, json, base64, re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, abort
import anthropic

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

DATA_FILE = 'naszyjniki.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def clean_text(text):
    # Remove any "Tekst 1", "Tekst 2", "[opis]", "[zachęta]" prefixes
    text = re.sub(r'^(tekst\s*\d+\s*[-—:]?\s*|\[opis\]\s*|\[zachęta\]\s*)', '', text, flags=re.IGNORECASE)
    return text.strip()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generuj', methods=['POST'])
def generuj():
    try:
        client_name = request.form.get('client_name', '').strip()
        gems = request.form.get('gems', '').strip()
        notes = request.form.get('notes', '').strip()
        photo_file = request.files.get('photo')

        if not gems:
            return jsonify({'error': 'Brak kamieni'}), 400

        photo_b64 = None
        photo_media_type = 'image/jpeg'
        if photo_file and photo_file.filename:
            photo_bytes = photo_file.read()
            photo_b64 = base64.standard_b64encode(photo_bytes).decode('utf-8')
            photo_media_type = photo_file.content_type or 'image/jpeg'

        api_key = os.environ.get('ANTHROPIC_API_KEY')
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Jesteś poetyckim twórcą opisów biżuterii z naturalnych kamieni dla marki Virelia Jewelry.

Napisz dwa teksty oddzielone wyłącznie znakiem |||
Zacznij BEZPOŚREDNIO od pierwszego słowa opisu. Absolutnie zero tytułów, zero numeracji, zero słów "Tekst", "opis", "zachęta".

Pierwszy tekst (80-110 słów) — poetycki opis naszyjnika:
Kamienie: {gems}
{f"Właściciel/ka: {client_name}" if client_name else ""}
{f"Informacje: {notes}" if notes else ""}
Pisz w 2. osobie do właścicielki lub właściciela.
Opisz energetyczne i duchowe właściwości kamieni.
Ton: mistyczny, poetycki, ciepły. Tylko po polsku.

Drugi tekst (max 10 słów) — krótka zachęta nad kodem QR. Tylko po polsku.

Odpowiedz dokładnie tak: [opis]|||[zachęta]"""

        if photo_b64:
            message_content = [
                {"type": "image", "source": {"type": "base64", "media_type": photo_media_type, "data": photo_b64}},
                {"type": "text", "text": prompt + "\n\nNa zdjęciu widzisz naszyjnik — uwzględnij jego wygląd w opisie."}
            ]
        else:
            message_content = prompt

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=700,
            messages=[{"role": "user", "content": message_content}]
        )

        raw = response.content[0].text.strip()
        parts = raw.split('|||')
        description = clean_text(parts[0]) if parts else raw
        tagline = clean_text(parts[1]) if len(parts) > 1 else "Odkryj magię ukrytą w kamieniach"

        numer = 'VJ-' + str(uuid.uuid4())[:6].upper()
        date_str = datetime.now().strftime('%d.%m.%Y')

        photo_data_url = None
        if photo_b64:
            photo_data_url = f"data:{photo_media_type};base64,{photo_b64}"

        entry = {
            'numer': numer,
            'client_name': client_name,
            'gems': gems,
            'notes': notes,
            'description': description,
            'tagline': tagline,
            'date': date_str,
            'photo': photo_data_url
        }

        data = load_data()
        data[numer] = entry
        save_data(data)

        return jsonify({'success': True, 'numer': numer, 'description': description, 'tagline': tagline, 'date': date_str})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/naszyjnik/<numer>')
def naszyjnik(numer):
    data = load_data()
    entry = data.get(numer)
    if not entry:
        abort(404)
    return render_template('naszyjnik.html', **entry)

if __name__ == '__main__':
    app.run(debug=True)
