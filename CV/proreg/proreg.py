#!/usr/bin/env python

import os
import sys
import numpy as np
import time
import cv2
import json
import copy
import math
import matplotlib.pyplot as plt
import glob2
import pickle as pkl

import time

import ctypes as c
from numpy.ctypeslib import ndpointer

from collections import deque
import subprocess
import logging


LIB_PATH = os.path.dirname(__file__)
LIB_NAME = 'libSubsense'
IMG_PTR = ndpointer(c.c_uint8, flags="C_CONTIGUOUS")
CTX_PTR = c.c_void_p


def draw_protected_regions(image, polygons, colors):
    """Draws outline of protected regions on given image

    image: np.array(h, w, c)
    polygons: Dict(str, List(List))
    colors: Dict(str, color)

    returns:
    np.array(h, w, c)

    """
    for k, pts in polygons.items():
        pts = np.array(pts).reshape((-1, 1, 2))
        image = cv2.polylines(image, [pts], True, colors[k], 2)
    return image


def load_json(path):
    with open(path, "rb") as f:
        rois = json.load(f)
    return rois

class LBSP(object):
    def __init__(self,
                 lbsp_thresh=0.333,
                 desc_dist_thresh_offset=3,
                 min_color_dist_thresh=15,
                 num_bg_samples=100,
                 num_req_bg_samples=2,
                 num_samples_for_moving_avg=100,
                 feedback_t_lower=128.0):
        self._ctx = None
        self._params = (lbsp_thresh,
                        desc_dist_thresh_offset,
                        min_color_dist_thresh,
                        num_bg_samples,
                        num_req_bg_samples,
                        num_samples_for_moving_avg,
                        feedback_t_lower)
        self.lib_subsense = np.ctypeslib.load_library(LIB_NAME, LIB_PATH)

        # API: ss_create
        self.lib_subsense.ss_create.restype = CTX_PTR
        self.lib_subsense.ss_create.argtypes = [IMG_PTR,
                                                c.c_int,
                                                c.c_int,
                                                c.c_int,
                                                c.c_float,
                                                c.c_size_t,
                                                c.c_size_t,
                                                c.c_size_t,
                                                c.c_size_t,
                                                c.c_size_t,
                                                c.c_float]

        # API: ss_destroy
        self.lib_subsense.ss_destroy.restype = c.c_int
        self.lib_subsense.ss_destroy.argtypes = [CTX_PTR]

        # API: ss_apply
        self.lib_subsense.ss_apply.restype = c.c_int
        self.lib_subsense.ss_apply.argtypes = [CTX_PTR, IMG_PTR, IMG_PTR]

        # API: ss_initialize
        self.lib_subsense.ss_initialize.restype = c.c_int
        self.lib_subsense.ss_initialize.argtypes = [CTX_PTR, IMG_PTR, IMG_PTR]

        # API: ss_refresh
        self.lib_subsense.ss_refresh.restype = c.c_int
        self.lib_subsense.ss_refresh.argtypes = [
            CTX_PTR, c.c_float, IMG_PTR, c.c_bool]

    def _create(self, img):
        (h, w) = img.shape[:2]
        self.fg_mask = np.zeros((h, w), np.uint8)
        self._ctx = self.lib_subsense.ss_create(
            img, self._method(), w, h, *self._params)

    def apply(self, img):
        if self._ctx is None:
            self._create(img)
        self.lib_subsense.ss_apply(self._ctx, img, self.fg_mask)
        return self.fg_mask

    def initialize(self, img, mask):
        if self._ctx is None:
            self._create(img)
        self.lib_subsense.ss_initialize(self._ctx, img, mask)

    def refresh(self, frac, mask, fgforce):
        self.lib_subsense.ss_refresh(self._ctx, frac, mask, fgforce)

    def release(self):
        self.lib_subsense.ss_destroy(self._ctx)
        self._ctx = None


class Subsense(LBSP):
    def _method(self):
        return 0


class Lobster(LBSP):
    def _method(self):
        return 1


class MaskTemporalSmoother:
    def __init__(self, img_size, max_queue_len, dilate=False):
        self.queue = deque()
        self.sum = np.zeros(img_size)
        self.max_queue_len = float(max_queue_len)
        self.dilate = dilate
        self.dilate_kernel = np.ones((11, 11), np.uint8)

    def update(self, new_mask):
        if self.dilate:
            new_mask = cv2.dilate(new_mask, self.dilate_kernel, iterations=1)
        self.sum += new_mask
        self.queue.append(new_mask)
        if len(self.queue) > self.max_queue_len:
            sub = self.queue.popleft()
            self.sum -= sub
        return self.sum / len(self.queue)


def detect_persistent_change(region_path, data_downloader,
                                    persistence=10, resolution=0.5, fps=4, debug=False):
    # data_downloader = VideoDownloader(stage_start, interval, timeout)
    video_path = data_downloader.next_segment()
    print(video_path)
    cap = cv2.VideoCapture(video_path)
    subtractor = Subsense(min_color_dist_thresh=15, feedback_t_lower=128)

    # parameters
    fg_queue_size = persistence * fps
    frame_change_threshold = 0.05
    time_change_threshold = 95
    process_rate = 1 if fps is None else cap.get(cv2.CAP_PROP_FPS) // fps

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) * resolution)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) * resolution)
    dim = (width, height)
    print(dim)
    # load protected regions
    protected_regions = load_json(region_path)
    roisp = height / protected_regions["dims"]["height"]
    protected_regions = {k: np.array([[x * roisp, y * roisp] for x, y in pr], np.int32)
                         for k, pr in protected_regions["rois"].items()}
    protected_region_masks = {k: cv2.fillConvexPoly(
        np.zeros([height, width], np.uint8), pr, 1) for k, pr in protected_regions.items()}
    fg_mask_all = np.zeros((height, width), np.uint8)
    num_pixels = {k: v.sum() for k, v in protected_region_masks.items()}

    # initializations
    fg_mask_smoother = MaskTemporalSmoother((height, width), fg_queue_size)
    frame_num = 1
    video_num = 0
    _, frame = cap.read()
    roimask = np.sum(
        list(protected_region_masks.values()), axis=0).astype(np.uint8) * 255

    subtractor.initialize(cv2.resize(
        frame, dim, interpolation=cv2.INTER_AREA), roimask)

    if debug:
        out_vid_path = "proreg_out.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        vwriter = cv2.VideoWriter(out_vid_path, fourcc, 20, (width*3, height))
        roi_colors = [(255, 0, 0), (0, 255, 0), (255, 255, 0), (255, 0, 255)]
        roi_colors = {k: roi_colors[i]
                      for i, k in enumerate(protected_regions.keys())}
        currcolor = {k: v for k, v in roi_colors.items()}

    while True:
        ret, frame = cap.read()
        logging.info(f"Proreg Processing Frame Num {frame_num}")
        if frame is None:
            video_num += 1
            video_path = data_downloader.next_segment()
            if not video_path:
                break
            cap = cv2.VideoCapture(video_path)
            frame_num = 0
            continue

        frame_num += 1
        if frame_num % process_rate != 0:
            continue

        # resize image
        resized = cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)
        start_time = time.time()
        fg_mask = subtractor.apply(resized)
        run_time = time.time() - start_time

        fg_mask_all = fg_mask_smoother.update(copy.deepcopy(fg_mask))
        fg_mask_all = ((fg_mask_all / 255.0 * 100))
        fg_mask_all = (fg_mask_all > time_change_threshold).astype(
            np.uint8) * 255

        # filter change for each protected region
        changed_keys = []
        for k, v in protected_region_masks.items():
            percent_change = (
                (v * (fg_mask_all != 0)).sum() / num_pixels[k]) * 100
            if percent_change > frame_change_threshold:
                changed_keys.append(k)
                return True
            if debug:
                currcolor[k] = (
                    0, 0, 255) if percent_change > frame_change_threshold else roi_colors[k]

        # refresh bg model if any change is seen
        for k in changed_keys:
            num_changes = np.sum(fg_mask_all) / 255.0
            change_score = 100.0 * num_changes / (width * height)
            subtractor.refresh(
                0.1, protected_region_masks[k] * 255, True)
            print('frame %d change score %.2f run time %f seconds' %
                  (frame_num, change_score, run_time))

        # draw protected regions and resize
        if debug:
            resized = draw_protected_regions(
                resized, protected_regions, currcolor)
            gb = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2RGB)
            gb = draw_protected_regions(gb, protected_regions, currcolor)
            gb_all = cv2.cvtColor(fg_mask_all, cv2.COLOR_GRAY2RGB)
            gb_all = draw_protected_regions(
                gb_all, protected_regions, currcolor)
            im_h = cv2.hconcat([resized, gb, gb_all])
            vwriter.write(im_h)
            # cv2.imshow('Foreground Mask', im_h)
            keycode = cv2.waitKey(1)
            quit = ((keycode & 0xFF) == ord('q'))
            if quit:
                break
    if debug:
        vwriter and vwriter.release()
    subtractor.release()
    return False
