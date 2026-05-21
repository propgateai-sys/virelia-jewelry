
import os, uuid, json, base64, re
from datetime import datetime
from flask import Flask, request, jsonify, render_template, abort
import anthropic
import redis

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

def get_redis():
    url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    return redis.from_url(url, decode_responses=True)

def load_entry(numer):
    try:
        r = get_redis()
        data = r.get(f'naszyjnik:{numer}')
        return json.loads(data) if data else None
    except Exception:
        return None

def save_entry(numer, entry):
    try:
        r = get_redis()
        r.set(f'naszyjnik:{numer}', json.dumps(entry, ensure_ascii=False))
    except Exception as e:
        raise Exception(f'Błąd zapisu do bazy: {e}')

def clean_text(text):
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

        prompt = f"""Jesteś ekspertem od mineralogii i tradycji kryształoterapii oraz poetyckim twórcą opisów biżuterii dla marki Virelia Jewelry.

Napisz dwa teksty oddzielone znakiem |||
Zacznij BEZPOŚREDNIO od pierwszego słowa opisu. Zero tytułów, zero numeracji, zero słów "Tekst", "opis", "zachęta".

Pierwszy tekst (80-110 słów) — poetycki opis naszyjnika oparty na PRAWDZIWYCH właściwościach kamieni:
Kamienie: {gems}
{f"Właściciel/ka: {client_name}" if client_name else ""}
{f"Informacje: {notes}" if notes else ""}
- Opisz PRAWDZIWE energetyczne i duchowe właściwości każdego kamienia zgodne z tradycją kryształoterapii
- Pisz w 2. osobie bezpośrednio do właścicielki lub właściciela
- Ton: mistyczny, poetycki, ciepły, spersonalizowany
- Tylko po polsku

Drugi tekst (max 10 słów) — krótka zachęta nad kodem QR. Tylko po polsku.

Format odpowiedzi: [opis]|||[zachęta]"""

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

        save_entry(numer, entry)

        return jsonify({'success': True, 'numer': numer, 'description': description, 'tagline': tagline, 'date': date_str})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/naszyjnik/<numer>')
def naszyjnik(numer):
    entry = load_entry(numer)
    if not entry:
        abort(404)
    return render_template('naszyjnik.html', **entry)

if __name__ == '__main__':
    app.run(debug=True)
