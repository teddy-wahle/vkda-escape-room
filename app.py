# A welcome message to test our server
import logging

from flask import Flask, jsonify
from flask_cors import CORS

from escape_room import EscapeRoom

logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
app = Flask(__name__)
CORS(app)
game: EscapeRoom = None


@app.route("/ping")
def index():
    return {"hello": "there"}


@app.route("/restart")
def start():
    global game

    game = EscapeRoom()
    game.start()
    return jsonify({}), 200


@app.route("/current")
def current():
    if not game:
        return jsonify({"stage": -1}), 200
    
    print("all stages = ", game.stages)
    print("return data about curre stage, which is: " + str(game.current_stage))
    return jsonify({"stage": game.current_stage, "name": game.current_stage_name, "descr": game.stages[game.current_stage].descr}), 200


@app.route("/points")
def points():
    if not game:
        return jsonify({"message": "game not started"}), 400
    return jsonify({"points": game.points}), 200


@app.route("/developer/increment_stage")
def increment():
    game.current_stage += 1
    return jsonify({}), 200


@app.route("/stop")
def stop():
    global game
    if not game:
        return jsonify({"message": "game not started"}), 400
    game.stop()
    game = None
    return jsonify({}), 200

@app.route('/stages')
def stages():
    return jsonify({"stages": [stage.to_dict() for stage in game.stages]}), 200


if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    app.run(threaded=True, port=5000)
