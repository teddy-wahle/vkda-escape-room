import os
import logging
import threading
import time
import requests
import json
import subprocess

from typing import List
from CV.proreg.proreg import detect_persistent_change
from CV.emotion.emotion_detector import detect_emotion


class Stage:
    def __init__(self, timeout: int, points: int, name: str, descr: str = ""):
        self.timeout = timeout  # stage timeout in sec
        self.points = points
        self.descr = descr
        self.stage_name = name

    def start(self, stop) -> (bool, int):
        current_time = time.time()
        flag = False
        while time.time() < current_time + self.timeout:
            if stop():
                return False, 0
            flag = self.compute()
        return flag, self.points if flag else 0

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


class SensorNoiseLevel(Stage):
    def __init__(
        self,
        timeout: int,
        points: int,
        name: str,
        descr: str = "",
        duration: int = 3,
        threshold: int = 50,
    ):
        super().__init__(timeout, points, name, descr)
        self.threshold = threshold
        self.duration = duration

    def compute(self):
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
            print(last_points)
            if all([point["noise_level"] > self.threshold for point in last_points]):
                return True
        time.sleep(2.1)
        return False


class Camera(Stage):
    def __init__(self, timeout: int, points: int, name: str, descr: str = ""):
        super().__init__(timeout, points, name, descr)

    def compute(self):
        logging.info("Camera stage")
        time.sleep(3)
        return True


class CameraProreg(Stage):
    def __init__(
        self,
        timeout: int,
        points: int,
        name: str,
        descr: str = "",
        duration: int = 30,
        region_path: str = "data/regions.json",
        ):
        super().__init__(timeout, points, name, descr)
        self.duration = duration
        self.region_path = region_path
        self.camera_id = "717abf97-4d4d-4c8e-94b6-995d755e482d"

    def compute(self):
        logging.info("CameraProreg stage")
        stage_start = int(time.time()) #1649389582
        interval = 20
        success = detect_persistent_change(
            self.region_path,
            VideoDownloader(self.camera_id, stage_start, interval, self.timeout),
            self.duration,
            debug=True)
        return success


class CameraEmotion(Stage):
    def __init__(
        self,
        timeout: int,
        points: int,
        name: str,
        descr: str = "",
        duration: int = 10,
        emotion: str = "happy",
        ):
        super().__init__(timeout, points, name, descr)
        self.duration = duration
        self.emotion = emotion
        self.camera_id = "117c365c-17cd-498c-ae25-2ea7b4aa07b0"

    def compute(self):
        logging.info("CameraEmotion stage")
        stage_start = int(time.time())
        interval = 20
        emotion = "happy"
        success = detect_emotion(
            emotion,
            VideoDownloader(self.camera_id, stage_start, interval, self.timeout),
            self.duration,
            debug=True)
        return success


class VideoDownloader:
    def __init__(self, camera_id, stage_start, interval, timeout):
        self.stage_start = stage_start
        self.end = stage_start
        self.timeout = timeout
        self.user = os.environ["VKDA_USER"]
        self.token = os.environ["VKDA_TOKEN"]
        self.endpoint = f"https://hackathon.verkada.com/devices/{camera_id}/history/video.m3u8"
        self.interval = interval
        print("setup downloader!")

    def next_segment(self):
        if self.timeout < self.end - self.stage_start:
            return ""
        while int(time.time()) < self.end + 4:
            time.sleep(5)
        print(self.timeout, self.end, self.stage_start)
        video_path = f"data/{self.end}.mp4"
        start = self.end - self.interval
        url = f"{self.endpoint}?user={self.user}&token={self.token}&start={start}&end={self.end}&resolution=low"
        command = f"ffmpeg -i {url} -c copy -bsf:a aac_adtstoasc {video_path}"
        subprocess.run(command.split(" "))
        self.end += self.interval
        return video_path


class EscapeRoom:
    def __init__(self):
        self.current_stage_name = "Stage 1"
        self.current_stage = 0
        self.points = 0
        self.current_game = None
        self.stop_game = False
        self.stages: List[Stage] = [
            CameraEmotion(80, 40, "Stage 0", "Smile in front of the TV facing camera", duration=10, emotion="Happy"),
            # SensorReading(60, 10, "Stage 1", "Yell super loud for 3 seconds!!", 3, 60), Sensor(10, 20, "Stage 2", "Lie down on the couch for 3 seconds"),
            Sensor(5, 20, "Stage 3", "Smoke a vape under one of the sensors."),
            Camera(5, 20, "Stage 4", "Wear a red shirt in front of the camera."), Camera(5, 30, "Stage 5", "Turn on the heater!"),
            CameraEmotion(80, 40, "Stage 0", "Smile in front of the TV facing camera", duration=10, emotion="Happy"),
            CameraProreg(80, 40, "Stage 0", "Lie on the smaller sofa", 15)
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
