import logging
import threading
import time

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
            self.compute()
        return True, self.points

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
        time.sleep(10)


class Camera(Stage):
    def __init__(self, timeout: int, points: int, name: str, descr: str = ""):
        super().__init__(timeout, points, name, descr)

    def compute(self):
        logging.info("Camera stage")
        time.sleep(10)


class EscapeRoom:
    def __init__(self):
        self.current_stage_name = "Start"
        self.current_stage = 0
        self.points = 0
        self.current_game = None
        self.stop_game = False
        self.stages: List[Stage] = [
            Sensor(5, 10, "Stage 1", "desc 1"), Sensor(5, 10, "Stage 2", "desc 2"), Sensor(5, 20, "Stage 3", "desc 3"),
            Camera(5, 20, "Stage 4", "desc 4"), Camera(5, 30, "Stage 5", "desc 5"), Camera(5, 40, "Stage 6", "desc 6"),
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
                return
            self.current_stage_name = stage.name()
            self.current_stage += 1

        self.current_stage_name = "Stop"
        self.current_stage += 1
        logging.info(f"Game completed -> Points: {self.points}")
