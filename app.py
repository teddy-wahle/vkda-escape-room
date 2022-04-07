# A welcome message to test our server
import logging

from flask import Flask, jsonify

from escape_room import EscapeRoom

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
app = Flask(__name__)
game = EscapeRoom()


@app.route("/ping")
def index():
    return {"hello": "there"}


@app.route("/start")
def start():
    global game
    game = EscapeRoom()
    game.start()
    return jsonify({}), 200


@app.route("/current")
def current():
    return jsonify({"current": game.current}), 200


@app.route("/points")
def points():
    return jsonify({"points": game.points}), 200


@app.route("/stop")
def stop():
    game.stop()
    return jsonify({}), 200


if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    app.run(threaded=True, port=5000)
