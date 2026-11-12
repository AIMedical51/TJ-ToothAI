from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/square', methods=['POST'])
def calculate_square():
    data = request.get_json()
    if not data or 'number' not in data:
        return jsonify({"error": "Please provide a number in the request body"}), 400
    
    try:
        number = float(data['number'])
        result = number ** 2
        return jsonify({"square": result}), 200
    except ValueError:
        return jsonify({"error": "Invalid number format"}), 400

if __name__ == '__main__':
    app.run(host='10.0.16.12', port=80)
