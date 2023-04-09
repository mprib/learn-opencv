import pyxy3d.logger

logger = pyxy3d.logger.get(__name__)

import sys
import shutil
import time
from pathlib import Path
from threading import Thread
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QWidget,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QDockWidget,
    QFileDialog,
    QStackedWidget,
)

from pyxy3d.session import Session, Stage
from pyxy3d.gui.wizard_charuco import WizardCharuco
from pyxy3d.gui.camera_config.camera_tabs import CameraWizard
from pyxy3d.gui.wizard_directory import WizardDirectory
from pyxy3d import __root__, __app_dir__
from pyxy3d.session import Stage
from pyxy3d.gui.qt_logger import QtLogger
from pyxy3d.gui.stereoframe.stereo_frame_widget import (
    StereoFrameWidget,
    MIN_THRESHOLD_FOR_EARLY_CALIBRATE,
)
from pyxy3d.gui.vizualize.calibration.capture_volume_widget import CaptureVolumeWidget


class CalibrationWizard(QStackedWidget):
    cameras_connected = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.CAMS_IN_PROCESS = False

        self.setWindowTitle("Camera Calibration Wizard")
        self.setWindowIcon(QIcon(str(Path(__root__, "pyxy3d/gui/icons/pyxy_logo.svg"))))
        self.wizard_directory = WizardDirectory()
        self.addWidget(self.wizard_directory)  # index:1
        self.setCurrentIndex(0)
        self.connect_widgets()

    def connect_widgets(self):
        self.wizard_directory.launch_wizard_btn.clicked.connect(self.begin_wizard)
        self.cameras_connected.connect(self.on_cameras_connect)

    # create first page of wizard (charuco builder)
    def begin_wizard(self):
        if hasattr(self, "wizard_charuco"):
            self.setCurrentIndex(1)
        else:
            logger.info("Launching session")
            self.launch_session()
            logger.info("Creating charuco wizard session")
            self.wizard_charuco = WizardCharuco(self.session)
            self.wizard_charuco.navigation_bar.next_wizard_step_btn.clicked.connect(
                self.next_to_camera_config
            )
            logger.info("Adding charuco wizard")
            self.addWidget(self.wizard_charuco)
            logger.info("Setting index to 2 to activate widget")
            self.setCurrentIndex(1)

    # Start Session
    def launch_session(self):
        if self.wizard_directory.create_new_radio.isChecked():
            # only need to create a new session in the given directory:
            self.session_directory = self.wizard_directory.new_path.textbox.text()
            self.session = Session(self.session_directory)
        else:
            # need to copy over config from old directory to new directory before launching
            self.session_directory = self.wizard_directory.modified_path.textbox.text()
            old_config_path = self.wizard_directory.original_path.textbox.text()

            ## but check if it's the same directory
            if self.session_directory == old_config_path:
                # in which case don't do anything
                pass
            else:
                shutil.copyfile(
                    str(Path(old_config_path, "config.toml")),
                    str(Path(self.session_directory, "config.toml")),
                )

            self.session = Session(self.session_directory)

    ######################## STEP 1: Charuco Builder ###########################

    def next_to_camera_config(self):
        if hasattr(self, "camera_config"):
            logger.info("Camera config already exists; changing stack current index")
            self.setCurrentWidget(self.camera_config)
            active_port = self.camera_config.camera_tabs.currentIndex()
            self.camera_config.camera_tabs.toggle_tracking(active_port)
            logger.info("updating charuco in case necessary")
            for port, stream in self.session.streams.items():
                stream.update_charuco(self.session.charuco)
        else:
            logger.info("Initiating Camera Connection")
            self.initiate_camera_connection()
            self.qt_logger = QtLogger("Connecting to Cameras...")
            self.qt_logger.show()

    def initiate_camera_connection(self):

        if len(self.session.cameras) > 0:
            logger.info("Cameras already connected")
        else:

            def connect_to_cams_worker():
                self.CAMS_IN_PROCESS = True
                logger.info("Initiating camera connect worker")

                # find out if you are loading cameras or finding cameras
                if self.session.get_configured_camera_count() > 0:
                    self.session.load_cameras()
                    logger.info("Camera connect worker about to load stream tools")
                    self.session.load_streams()
                else:
                    # I believe find_cameras will establish the streams as well...
                    self.session.find_cameras()
                logger.info("Camera connect worker about to adjust resolutions")
                self.session.adjust_resolutions()
                logger.info("Camera connect worker about to load monocalibrators")
                self.session.load_monocalibrators()
                self.CAMS_IN_PROCESS = False

                logger.info("emitting cameras_connected signal")
                self.cameras_connected.emit()
                if hasattr(self, "qt_logger"):
                    del self.qt_logger
                # self.qt_logger.hide()

        if self.CAMS_IN_PROCESS:
            logger.info("Already attempting to connect to cameras...")
        else:
            self.connect_cams = Thread(
                target=connect_to_cams_worker, args=[], daemon=True
            )
            self.connect_cams.start()

    def on_cameras_connect(self):
        # load cameras config once the cameras are actually connected
        self.camera_config = CameraWizard(self.session)
        self.addWidget(self.camera_config)
        self.setCurrentWidget(self.camera_config)
        self.camera_config.navigation_bar.back_btn.clicked.connect(
            self.back_to_charuco_wizard
        )
        self.camera_config.navigation_bar.next_btn.clicked.connect(
            self.next_to_stereoframe
        )

    ####################### STEP 2: Single Camera Calibration #################
    def back_to_charuco_wizard(self):
        self.setCurrentIndex(1)
        self.session.pause_all_monocalibrators()

    def next_to_stereoframe(self):

        self.session.pause_all_monocalibrators()

        if hasattr(self.session, "synchronizer"):
            self.session.unpause_synchronizer()
        # else:
        # if hasattr(self, "stereoframe"):
        # self.removeWidget(self.stereoframe)
        # del self.stereoframe

        self.launch_new_stereoframe()

    def launch_new_stereoframe(self):
        self.stereoframe = StereoFrameWidget(self.session)
        self.addWidget(self.stereoframe)
        self.setCurrentWidget(self.stereoframe)

        self.stereoframe.navigation_bar.back_btn.clicked.connect(
            self.back_to_camera_config_wizard
        )
        # self.stereoframe.navigation_bar.calibrate_collect_btn.clicked.connect(
        #     self.on_stereo_calibrate_collect_btn
        # )

        self.stereoframe.calibration_complete.connect(self.next_to_capture_volume)
        self.stereoframe.calibration_initiated.connect(self.show_calibration_qt_logger)
        self.stereoframe.terminate.connect(self.refresh_stereoframe)

    ###################### Stereocalibration  ######################################
    def refresh_stereoframe(self):
        logger.info("Set current widget to config temporarily")
        self.setCurrentWidget(self.camera_config)

        logger.info("Remove stereoframe")
        self.removeWidget(self.stereoframe)
        self.stereoframe.frame_builder.unsubscribe_from_synchronizer()
        del self.stereoframe

        logger.info("Create new stereoframe")
        self.launch_new_stereoframe()
         
    def show_calibration_qt_logger(self):
        """
        Calibration is initiated back on the stereoframe widget,here only
        the logger launch is managed because it is main that must delete the logger
        """
        # if self.stereoframe.frame_builder.possible_to_initialize_array(MIN_THRESHOLD_FOR_EARLY_CALIBRATE):
        # weird if statement here...trying to avoid launching the logger when beginning
        # to collect data...
        logger.info("Launching calibration qt logger")
        self.qt_logger = QtLogger("Calibrating camera array...")
        self.qt_logger.show()

    def back_to_camera_config_wizard(self):
        logger.info("Moving back to camera config from stereoframe")
        # from stereoframe to camera config
        self.setCurrentWidget(self.camera_config)
        self.session.pause_synchronizer()

        self.stereoframe.frame_builder.unsubscribe_from_synchronizer()
        self.removeWidget(self.stereoframe)
        del self.stereoframe

        active_port = self.camera_config.camera_tabs.currentIndex()
        self.camera_config.camera_tabs.toggle_tracking(active_port)

    def next_to_capture_volume(self):
        # if hasattr(self, "capture_volume"):
        #     self.setCurrentWidget(self.capture_volume)

        # else:
        logger.info("Creating Capture Volume widget")
        self.capture_volume = CaptureVolumeWidget(self.session)
        logger.info("Adding capture volume widget to main Wizard")
        self.addWidget(self.capture_volume)
        logger.info("Set current index to capture volume widget")
        self.setCurrentWidget(self.capture_volume)
        self.capture_volume.navigation_bar.back_btn.clicked.connect(
            self.back_to_stereo_frame
        )

        del self.qt_logger

    ################## Capture Volume ########################
    def back_to_stereo_frame(self):

        logger.info("Set current widget to config temporarily")
        self.setCurrentWidget(self.camera_config)

        logger.info("Remove stereoframe")
        self.removeWidget(self.stereoframe)
        logger.info("Remove capture volume")
        self.removeWidget(self.capture_volume)
        del self.capture_volume
        self.stereoframe.frame_builder.unsubscribe_from_synchronizer()
        del self.stereoframe

        logger.info("Create new stereoframe")
        self.launch_new_stereoframe()
        self.session.unpause_synchronizer()

    # def on_stereo_calibrate_collect_btn(self):
    #     """
    #     Check if data is being collected, but not enough to initialize array
    #     If so, just wipe everything out and start out.
    #     """
    #     if (
    #         self.stereoframe.collection_in_process
    #         and not self.stereoframe.frame_builder.possible_to_initialize_array(
    #             MIN_THRESHOLD_FOR_EARLY_CALIBRATE
    #         )
    #     ):
    #         self.session.stop_recording()
    #         self.back_to_stereo_frame()


def launch_pyxy3d():

    app = QApplication(sys.argv)
    window = CalibrationWizard()
    window.show()

    app.exec()


if __name__ == "__main__":

    launch_pyxy3d()
