import os
import logging
import threading
import time
import requests

from typing import List


class Stage:
    def __init__(self, timeout: int, points: int, name: str, descr: str = ""):
        self.timeout = timeout  # stage timeout in sec
        self.points = points
        self.descr = descr
        self.stage_name = name

    def start(self, stop) -> (bool, int):
        current_time = time.time()
        while time.time() < current_time + self.timeout:
            if stop():
                return False, 0
            if self.compute():
                return True, self.points
        return False, 0

    def compute(self):
        raise NotImplementedError

    def name(self) -> str:
        return self.stage_name
    
    def to_dict(self) -> dict:
        return {
            "descr" : self.descr,
            "stage_name" : self.stage_name
        }


class Sensor(Stage):
    def __init__(self, timeout: int, points: int, name: str, descr: str = ""):
        super().__init__(timeout, points, name, descr)

    def compute(self):
        logging.info("Sensor stage")
        time.sleep(5)
        return True


class SensorReading(Stage):
    def __init__(
        self,
        timeout: int,
        points: int,
        name: str,
        descr: str = "",
        duration: int = 3,
        threshold: int = 50,
        reading: str = "noise_level"
    ):
        super().__init__(timeout, points, name, descr)
        self.threshold = threshold
        self.duration = duration
        self.reading = reading

    def compute(self):
        time.sleep(5)
        logging.info("Sensor Noise Level stage")
        now = int(time.time())
        payload = {
            "token": os.environ["VKDA_TOKEN"],
            "user": os.environ["VKDA_USER"],
            "start": now - 10,
            "end": now,
            "aggregateInterval": "1s",
        }
        sensor_id = "e4e9157f-d08c-49e2-a7b0-162d6a15285b"
        r = requests.get(
            f"https://hackathon.verkada.com/sensors/{sensor_id}/sensor_data",
            params=payload,
        )
        data = r.json()
        if len(data) > self.duration:
            last_points = data[-self.duration :]
            print([point[self.reading] for point in last_points])
            if all([point[self.reading] > self.threshold for point in last_points]):
                return True
        time.sleep(2.1)
        return False


class Camera(Stage):
    def __init__(self, timeout: int, points: int, name: str, descr: str = ""):
        super().__init__(timeout, points, name, descr)

    def compute(self):
        logging.info("Camera stage")
        time.sleep(5)
        return True


class EscapeRoom:
    def __init__(self):
        self.current_stage_name = "Start"
        self.current_stage = 0
        self.points = 0
        self.current_game = None
        self.stop_game = False
        self.stages: List[Stage] = [
            SensorReading(5, 10, "Stage 1", "Yell super loud for 3 seconds!!", 3, 20), Sensor(5, 20, "Stage 2", "Smoke a vape under the sensor by the heater."),
            Camera(5, 20, "Stage 3", "Dance in front of the camera."), Camera(5, 30, "Stage 4", "Take your hat off."), Camera(5, 40, "Stage 5", "Make a sad face in front of the camera."),
        ]

    def start(self):
        # Stop current games and start a new one
        if self.current_game:
            self.stop()
        self.current_game = threading.Thread(target=self.run, args=(lambda: self.stop_game, ))
        self.current_game.start()

    def stop(self):
        self.stop_game = True
        if self.current_game:
            self.current_game.join()
        self.stop_game = False

    def run(self, stop):
        self.current_stage = 0
        self.points = 0
        for i, stage in enumerate(self.stages):
            result, points = stage.start(stop)
            logging.info(f"{i+1} -> Stage: {stage.name()} Result: {result} Points: {points}")
            self.points += points
            if not result:
                logging.info(f"YOU LOSE!")
                return
            logging.info(f"NEXT STAGE!")
            self.current_stage_name = stage.name()
            self.current_stage += 1

        self.current_stage_name = "Stop"
        self.current_stage += 1
        logging.info(f"Game completed -> Points: {self.points}")
