import logging
import threading
import time

from typing import List


class Stage:
    def __init__(self, timeout: int, points: int):
        self.timeout = timeout  # stage timeout in sec
        self.points = points

    def start(self, stop) -> (bool, int):
        current_time = time.time()
        while time.time() < current_time + self.timeout:
            if stop():
                return False, 0
            self.compute()
        return True, self.points

    def compute(self):
        raise NotImplementedError


class Sensor(Stage):
    def __init__(self, timeout: int, points: int):
        super().__init__(timeout, points)

    def compute(self):
        logging.info("Sensor stage")
        time.sleep(10)


class Camera(Stage):
    def __init__(self, timeout: int, points: int):
        super().__init__(timeout, points)

    def compute(self):
        logging.info("Camera stage")
        time.sleep(10)


class EscapeRoom:
    def __init__(self):
        self.current = 0
        self.points = 0
        self.current_game = None
        self.stop_game = False
        self.stages: List[Stage] = [
            Sensor(5, 10), Sensor(5, 10), Sensor(5, 20),
            Camera(5, 20), Camera(5, 30), Camera(5, 40),
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
        self.current = 0
        self.points = 0
        for i, stage in enumerate(self.stages):
            result, points = stage.start(stop)
            logging.info(f"Stage: {i+1} Result: {result} Points: {points}")
            self.points += points
            if not result:
                return
            self.current += 1
