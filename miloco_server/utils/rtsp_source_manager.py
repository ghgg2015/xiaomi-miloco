# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""
RTSP source manager.
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from collections import deque
from typing import Callable, Coroutine, Dict, Optional

import cv2
from pydantic import ValidationError

from miloco_server.dao.kv_dao import DeviceInfoKeys, KVDao
from miloco_server.schema.miot_schema import CameraImgInfo, CameraImgSeq, CameraInfo
from miloco_server.schema.rtsp_schema import RTSPSource, RTSPSourceCreate, RTSPSourceUpdate

logger = logging.getLogger(__name__)


class _TTLImageQueue:
    def __init__(self, max_size: int, ttl: int):
        self._queue = deque(maxlen=max_size)
        self._ttl = ttl
        self._lock = threading.Lock()

    def put(self, item: CameraImgInfo) -> None:
        with self._lock:
            now = time.time()
            self._queue.append((item, now))
            self._filter(now)

    def get_recent(self, count: int) -> list[CameraImgInfo]:
        with self._lock:
            self._filter(time.time())
            return [item for item, _ in list(self._queue)[-count:]]

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def _filter(self, now: float) -> None:
        while self._queue and now - self._queue[0][1] > self._ttl:
            self._queue.popleft()


class RTSPSourceWorker:
    def __init__(self, source: RTSPSource, loop: asyncio.AbstractEventLoop, max_size: int, ttl: int):
        self.source = source
        self._loop = loop
        self._max_size = max_size
        self._ttl = ttl
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: Dict[str, Callable[[str, bytes, int, int, int], Coroutine]] = {}
        self._img_queue = _TTLImageQueue(max_size=max_size, ttl=ttl)
        self.online = False
        self._sequence = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name=f"rtsp-{self.source.source_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self.online = False
        self._img_queue.clear()

    def update_source(self, source: RTSPSource) -> None:
        self.source = source
        self.stop()
        if source.enabled:
            self.start()

    def register_callback(self, callback: Callable[[str, bytes, int, int, int], Coroutine]) -> str:
        callback_id = str(uuid.uuid4())
        with self._lock:
            self._callbacks[callback_id] = callback
        return callback_id

    def unregister_callback(self, callback_id: str) -> None:
        with self._lock:
            self._callbacks.pop(callback_id, None)

    def get_recent_camera_img(self, count: int) -> CameraImgSeq:
        return CameraImgSeq(
            camera_info=CameraInfo(
                did=self.source.source_id,
                name=self.source.name,
                online=self.online,
                model="rtsp.camera",
                icon=None,
                home_name=self.source.home_name,
                room_name=self.source.room_name,
                is_set_pincode=0,
                order_time=None,
                channel_count=1,
                camera_status="CONNECTED" if self.online else "DISCONNECTED",
                source_type="rtsp",
                stream_type="jpeg",
            ),
            channel=0,
            img_list=self._img_queue.get_recent(count),
        )

    def _run(self) -> None:
        url = self.source.rtsp_url
        if self.source.username and self.source.password and "@" not in url:
            prefix, rest = url.split("://", maxsplit=1)
            url = f"{prefix}://{self.source.username}:{self.source.password}@{rest}"

        while not self._stop_event.is_set():
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                self.online = False
                time.sleep(2)
                continue

            self.online = True
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    self.online = False
                    break

                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok:
                    continue

                frame_bytes = encoded.tobytes()
                ts = int(time.time() * 1000)
                self._sequence += 1
                self._img_queue.put(CameraImgInfo(data=frame_bytes, timestamp=ts))
                self._emit(frame_bytes, ts)

            cap.release()
            time.sleep(1)

    def _emit(self, frame_bytes: bytes, ts: int) -> None:
        with self._lock:
            callbacks = list(self._callbacks.values())
        for callback in callbacks:
            asyncio.run_coroutine_threadsafe(
                callback(self.source.source_id, frame_bytes, ts, self._sequence, 0),
                self._loop,
            )


class RTSPSourceManager:
    def __init__(self, kv_dao: KVDao, loop: asyncio.AbstractEventLoop, max_size: int = 6, ttl: int = 12):
        self._kv_dao = kv_dao
        self._loop = loop
        self._max_size = max_size
        self._ttl = ttl
        self._sources: Dict[str, RTSPSource] = {}
        self._workers: Dict[str, RTSPSourceWorker] = {}
        self._stream_regs: Dict[tuple[str, int], str] = {}
        self._load_sources()

    def _load_sources(self) -> None:
        raw = self._kv_dao.get(DeviceInfoKeys.RTSP_SOURCE_CONFIGS_KEY, "[]") or "[]"
        try:
            source_list = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid RTSP source config payload, reset to empty list")
            source_list = []
        for item in source_list:
            try:
                source = RTSPSource.model_validate(item)
            except ValidationError as err:
                logger.warning("Skip invalid RTSP source config: %s", err)
                continue
            self._sources[source.source_id] = source
            worker = RTSPSourceWorker(source, self._loop, self._max_size, self._ttl)
            self._workers[source.source_id] = worker
            if source.enabled:
                worker.start()

    def _save_sources(self) -> None:
        payload = [source.model_dump() for source in self._sources.values()]
        self._kv_dao.set(DeviceInfoKeys.RTSP_SOURCE_CONFIGS_KEY, json.dumps(payload))

    def list_sources(self) -> list[RTSPSource]:
        return list(self._sources.values())

    def create_source(self, payload: RTSPSourceCreate) -> RTSPSource:
        source_id = payload.source_id or f"rtsp:{uuid.uuid4().hex[:12]}"
        source = RTSPSource(source_id=source_id, **payload.model_dump(exclude={"source_id"}))
        self._sources[source.source_id] = source
        worker = RTSPSourceWorker(source, self._loop, self._max_size, self._ttl)
        self._workers[source.source_id] = worker
        if source.enabled:
            worker.start()
        self._save_sources()
        return source

    def update_source(self, source_id: str, payload: RTSPSourceUpdate) -> RTSPSource:
        if source_id not in self._sources:
            raise KeyError(source_id)
        current = self._sources[source_id]
        source = current.model_copy(update=payload.model_dump(exclude_unset=True))
        self._sources[source_id] = source
        self._workers[source_id].update_source(source)
        self._save_sources()
        return source

    def delete_source(self, source_id: str) -> bool:
        source = self._sources.pop(source_id, None)
        worker = self._workers.pop(source_id, None)
        if not source or not worker:
            return False
        worker.stop()
        self._save_sources()
        return True

    def get_camera_list(self) -> list[CameraInfo]:
        camera_list: list[CameraInfo] = []
        for source in self._sources.values():
            worker = self._workers[source.source_id]
            camera_list.append(CameraInfo(
                did=source.source_id,
                name=source.name,
                online=worker.online if source.enabled else False,
                model="rtsp.camera",
                icon=None,
                home_name=source.home_name,
                room_name=source.room_name,
                is_set_pincode=0,
                order_time=None,
                channel_count=1,
                camera_status="CONNECTED" if worker.online and source.enabled else "DISCONNECTED",
                source_type="rtsp",
                stream_type="jpeg",
            ))
        return camera_list

    def get_recent_camera_img(self, source_id: str, recent_count: int) -> Optional[CameraImgSeq]:
        worker = self._workers.get(source_id)
        if not worker:
            return None
        return worker.get_recent_camera_img(recent_count)

    async def start_video_stream(self, source_id: str, channel: int,
                                 callback: Callable[[str, bytes, int, int, int], Coroutine]) -> None:
        if channel != 0:
            raise ValueError(f"RTSP source only supports channel 0, got {channel}")
        worker = self._workers.get(source_id)
        if not worker:
            raise KeyError(source_id)
        if worker.source.enabled:
            worker.start()
        reg_id = worker.register_callback(callback)
        self._stream_regs[(source_id, channel)] = reg_id

    async def stop_video_stream(self, source_id: str, channel: int) -> None:
        worker = self._workers.get(source_id)
        if not worker:
            return
        reg_id = self._stream_regs.pop((source_id, channel), None)
        if reg_id:
            worker.unregister_callback(reg_id)
