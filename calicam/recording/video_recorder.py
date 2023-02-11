import calicam.logger

logger = calicam.logger.get(__name__)

from pathlib import Path
from queue import Queue
from threading import Thread, Event
import cv2
import sys
import pandas as pd

from calicam.cameras.synchronizer import Synchronizer


class VideoRecorder:
    def __init__(self, synchronizer):
        self.syncronizer = synchronizer

        # build dict that will be stored to csv
        self.recording = False
        self.trigger_stop = Event()

    def build_video_writers(self):

        # create a dictionary of videowriters
        self.video_writers = {}
        for port, stream in self.syncronizer.streams.items():

            path = str(Path(self.destination_folder, f"port_{port}.mp4"))
            logger.info(f"Building video writer for port {port}; recording to {path}")
            fourcc = cv2.VideoWriter_fourcc(*"MP4V")
            fps = self.syncronizer.fps_target
            frame_size = stream.camera.resolution

            writer = cv2.VideoWriter(path, fourcc, fps, frame_size)
            self.video_writers[port] = writer

    def save_frame_worker(self):
        # connect video recorder to synchronizer via an "in" queue
        self.build_video_writers()

        self.frame_history = {
            "sync_index": [],
            "port": [],
            "frame_index": [],
            "frame_time": [],
        }
        sync_index = 0

        self.sync_packet_in_q = Queue(-1)
        self.syncronizer.subscribe_to_sync_packets(self.sync_packet_in_q)

        while not self.trigger_stop.is_set():
            synched_frames = self.sync_packet_in_q.get()
            logger.debug("Pulling synched frames from record queue")

            for port, synched_frame_data in synched_frames.items():
                if synched_frame_data is not None:
                    # read in the data for this frame for this port
                    frame = synched_frame_data["frame"]
                    frame_index = synched_frame_data["frame_index"]
                    frame_time = synched_frame_data["frame_time"]

                    # store the frame
                    self.video_writers[port].write(frame)

                    # store to assocated data in the dictionary
                    self.frame_history["sync_index"].append(sync_index)
                    self.frame_history["port"].append(port)
                    self.frame_history["frame_index"].append(frame_index)
                    self.frame_history["frame_time"].append(frame_time)

                    # these two lines of code are just for ease of debugging
                    # cv2.imshow(f"port: {port}", frame)
                    # key = cv2.waitKey(1)

            sync_index += 1
        self.trigger_stop.clear()  # reset stop recording trigger
        self.syncronizer.release_sync_packet_q(self.sync_packet_in_q)

        # a proper release is strictly necessary to ensure file is readable
        for port, synched_frame_data in synched_frames.items():
            self.video_writers[port].release()

        self.store_frame_history()

    def store_frame_history(self):
        df = pd.DataFrame(self.frame_history)
        # TODO: #25 if file exists then change the name
        frame_hist_path = str(Path(self.destination_folder, "frame_time_history.csv"))
        logger.info(f"Storing frame history to {frame_hist_path}")
        df.to_csv(frame_hist_path, index=False, header=True)

    def start_recording(self, destination_folder):

        logger.info(f"All video data to be saved to {destination_folder}")

        self.destination_folder = destination_folder
        # create the folder if it doesn't already exist
        self.destination_folder.mkdir(exist_ok=True, parents=True)

        self.recording = True
        self.recording_thread = Thread(
            target=self.save_frame_worker, args=[], daemon=True
        )
        self.recording_thread.start()

    def stop_recording(self):
        self.trigger_stop.set()


if __name__ == "__main__":

    import time

    from calicam.cameras.camera import Camera
    from calicam.cameras.live_stream import LiveStream
    from calicam.session import Session
    from calicam.calibration.charuco import Charuco

    from calicam.recording.recorded_stream import RecordedStream, RecordedStreamPool
    
    # from calicam import __app_dir__

    repo = Path(str(Path(__file__)).split("calicam")[0], "calicam")

    # ports = [0, 1, 2, 3, 4]
    ports = [0,1]

    test_live = True
    # test_live = False

    if test_live:

        session_directory = Path(repo, "sessions", "5_cameras")
        session = Session(session_directory)
        session.load_cameras()
        session.load_streams()

        for port, stream in session.streams.items():
            stream._show_fps = True
            stream._show_charuco = True

        logger.info("Creating Synchronizer")
        syncr = Synchronizer(session.streams, fps_target=15)
        video_path = Path(session_directory, "recording2")
    else:
        recording_directory = Path(repo, "sessions", "5_cameras", "recording")
        charuco = Charuco(
            4, 5, 11, 8.5, aruco_scale=0.75, square_size_overide_cm=5.25, inverted=True
        )
        stream_pool = RecordedStreamPool(ports, recording_directory, charuco=charuco)
        logger.info("Creating Synchronizer")
        syncr = Synchronizer(stream_pool.streams, fps_target=3)
        stream_pool.play_videos()
        new_recording_directory = Path(repo, "sessions", "5_cameras", "recording2")
        video_path = Path(new_recording_directory)

    video_recorder = VideoRecorder(syncr)

    video_recorder.start_recording(video_path)
    time.sleep(10)
    # while not syncr.stop_event.is_set():
    #     time.sleep(1)

    video_recorder.stop_recording()
