# A welcome message to test our server
from flask import Flask, request, jsonify
app = Flask(__name__)

@app.route('/ping')
def index():
    return {"hello":"there"}

if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    app.run(threaded=True, port=5000)