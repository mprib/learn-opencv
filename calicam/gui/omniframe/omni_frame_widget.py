
import calicam.logger
logger = calicam.logger.get(__name__)

import sys
from pathlib import Path
from threading import Thread, Event
import time

import cv2
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QImage, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QSizePolicy,
    QWidget,
    QSpinBox,
    QScrollArea,
    QComboBox,
    QCheckBox,
    QDialog,
    QGroupBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

# Append main repo to top of path to allow import of backend
from calicam.session import Session
from calicam.gui.omniframe.omni_frame_builder import OmniFrameBuilder
from calicam.cameras.synchronizer import Synchronizer
from calicam import __root__


class OmniFrameWidget(QWidget):
    
    def __init__(self,session:Session):

        super(OmniFrameWidget, self).__init__()
        self.session = session
        self.synchronizer:Synchronizer = self.session.get_synchronizer()

        self.frame_builder = OmniFrameBuilder(self.synchronizer)
        self.frame_emitter = OmniFrameEmitter(self.frame_builder)
        self.frame_emitter.start()

        self.layout_widgets()
        self.connect_widgets()        

    def layout_widgets(self):
        self.setLayout(QVBoxLayout())
       
        self.calibrate_collect_btn = QPushButton("Collect Calibration Data")
        self.layout().addWidget(self.calibrate_collect_btn)

        self.scroll_area = QScrollArea()
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # self.scroll_area.setLayout(QVBoxLayout())
        self.layout().addWidget(self.scroll_area)

        self.omni_frame_display = QLabel()
        self.scroll_area.setWidget(self.omni_frame_display)
        

    def connect_widgets(self):
        self.calibrate_collect_btn.clicked.connect(self.on_calibrate_connect_click)
        self.frame_emitter.ImageBroadcast.connect(self.ImageUpdateSlot)
        
    def on_calibrate_connect_click(self):
        if self.calibrate_collect_btn.text() == "Collect Calibration Data":
            logger.info("Begin collecting calibration data")
            # by default, data saved to session folder
            self.frame_builder.store_points.set()
            self.session.start_recording()
            self.calibrate_collect_btn.setText("Early Terminate Collection")
        elif self.calibrate_collect_btn.text() == "Early Terminate Collection":
            logger.info("Prematurely end data collection")
            self.frame_builder.store_points.clear()
            self.session.stop_recording()
            self.calibrate_collect_btn.setText("Collect Calibration Data")
        elif self.calibrate_collect_btn.text() == "Calibrate": 
            self.initiate_calibration()

    def ImageUpdateSlot(self, q_image):
        self.omni_frame_display.resize(self.omni_frame_display.sizeHint())

        qpixmap = QPixmap.fromImage(q_image)
        self.omni_frame_display.setPixmap(qpixmap)
        if self.omni_frame_display.height()==1:
            self.calibrate_collect_btn.setText("Calibrate")
            self.frame_emitter.stop()


    def initiate_calibration(self):
        def calibrate_worker():
            self.session.calibrate()

        self.calibrate_thead = Thread(target=calibrate_worker,args=(), daemon=True )
        self.calibrate_thead.start()
class OmniFrameEmitter(QThread):
    ImageBroadcast = pyqtSignal(QImage)
    
    def __init__(self, omniframe_builder:OmniFrameBuilder):
        
        super(OmniFrameEmitter,self).__init__()
        self.omniframe_builder = omniframe_builder
        logger.info("Initiated frame emitter")        
        self.keep_collecting = Event() 
        self.keep_collecting.set()
        
    def run(self):
        while self.keep_collecting.is_set():
            omni_frame = self.omniframe_builder.get_omni_frame()

            if omni_frame is not None:
                image = cv2_to_qlabel(omni_frame)
                self.ImageBroadcast.emit(image)
   
    def stop(self):
        self.keep_collecting.clear() 
    
def cv2_to_qlabel(frame):
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    qt_frame = QImage(
        image.data,
        image.shape[1],
        image.shape[0],
        QImage.Format.Format_RGB888,
    )
    return qt_frame

    
if __name__ == "__main__":
   
   
   
        App = QApplication(sys.argv)

        config_path = Path(__root__, "tests", "please work")

        session = Session(config_path)
        session.load_cameras()
        session.load_streams()
        # session.adjust_resolutions()


        omni_dialog = OmniFrameWidget(session)
        omni_dialog.show()

        sys.exit(App.exec())
