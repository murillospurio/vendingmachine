from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Token do Mercado Pago
ACCESS_TOKEN = 'APP_USR-3217936625303024-041117-719141a8c5cfa8897a2e3dc22d59f79d-1433246274'

# Mapeamento de máquinas de cartão (serial) para IPs dos respectivos ESP32
MACHINE_MAP = {
    '8701372447323147': 'http://192.168.5.12/api',       # Máquina 1
    '23020562023041807721': 'http://192.168.5.11/api'    # Máquina 2
}

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == 'GET':
        topic = request.args.get('topic')
        payment_id = request.args.get('id')
        print(f"GET recebido - topic: {topic}, id: {payment_id}")
        return jsonify({'status': 'GET recebido'}), 200

    elif request.method == 'POST':
        data = request.get_json()
        print(f"POST recebido do Mercado Pago: {data}")

        try:
            payment_id = data['resource']
            topic = data['topic']
        except (KeyError, TypeError):
            return jsonify({'error': 'ID do pagamento ou tópico não encontrado no corpo da requisição.'}), 400

        print(f"Recebido POST - topic: {topic}, id: {payment_id}")

        payment_info = buscar_detalhes_pagamento(payment_id)

        if not payment_info:
            return jsonify({'error': 'Não foi possível obter detalhes do pagamento.'}), 400

        status = payment_info.get('status')
        valor_pago = payment_info.get('transaction_amount', 0)

        # Captura o serial da máquina a partir do campo external_reference
        machine_serial = payment_info.get('external_reference')

        if not machine_serial:
            return jsonify({'error': 'Número de série da máquina não informado (external_reference ausente).'}), 400

        esp32_url = MACHINE_MAP.get(machine_serial)

        if not esp32_url:
            return jsonify({'error': f'Máquina com serial {machine_serial} não está cadastrada.'}), 400

        signal = 'credito_disponivel' if status == 'approved' else 'credito_indisponivel'

        try:
            response = requests.post(esp32_url, json={
                'signal': signal,
                'valor_pago': valor_pago
            }, headers={'Content-Type': 'application/json'})

            if response.status_code == 200:
                print(f"✅ Enviado ao ESP32 ({esp32_url}): {signal} - Valor: {valor_pago}")
            else:
                print(f"❌ Erro ao enviar para o ESP32 ({esp32_url}): {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro ao comunicar com o ESP32 ({esp32_url}): {e}")

        return jsonify({'status': 'Pagamento processado com sucesso'}), 200

def buscar_detalhes_pagamento(payment_id):
    url = f'https://api.mercadopago.com/v1/payments/{payment_id}'
    headers = {
        'Authorization': f'Bearer {ACCESS_TOKEN}'
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("🧾 Detalhes do pagamento obtidos com sucesso.")
            return response.json()
        else:
            print(f"Erro ao buscar pagamento: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        print(f"Erro ao conectar com a API do Mercado Pago: {e}")
        return None

if __name__ == '__main__':
    app.run(debug=True)
