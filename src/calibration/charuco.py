
#%%

from collections import defaultdict
from itertools import combinations
import cv2
from numpy import char
import json

INCHES_PER_MM = .0393701

class Charuco():
    """
    create a charuco board that can be printed out and used for camera 
    calibration, and used for drawing a grid during calibration    
    """

    def __init__(
        self, 
        columns, 
        rows, 
        board_height, 
        board_width, 
        dictionary="DICT_4X4_50",
        units="inch", 
        aruco_scale=0.75, 
        square_size_overide=None,
        inverted=False): # after printing, measure actual and return to overide
        
        """
        Create board based on shape and dimensions
        square_size_overide: correct for the actual printed size of the board
        """
        self.columns = columns
        self.rows = rows
        self.inverted = inverted

        if units == "inch":
            # convert to millimeters
            board_height = board_height/INCHES_PER_MM
            board_width = board_width/INCHES_PER_MM

        self.board_height = board_height
        self.board_width = board_width
        self.dictionary = dictionary
        self.aruco_scale = aruco_scale
        # if square length not provided, calculate based on board dimensions
        # to maximize size of squares
        self.square_size_overide = square_size_overide


    @property
    def dictionary_object(self):
        # grab the dictionary from the reference info at the foot of the module
        dictionary_integer = ARUCO_DICTIONARIES[self.dictionary]
        return cv2.aruco.Dictionary_get(dictionary_integer)

    @property
    def board(self):
        if self.square_size_overide:
            square_length = self.square_size_overide # note: in meters
        else:
            square_length = min([self.board_height/self.rows, 
                                self.board_width/self.columns]) 

        aruco_length = square_length * self.aruco_scale 
        # create the board
        return cv2.aruco.CharucoBoard_create(
                            self.columns,
                            self.rows,
                            square_length,
                            aruco_length,
                            # property based on dictionary text 
                            self.dictionary_object) 

    @property
    def board_img(self):
        """A cv2 image (numpy array) of the board"""
        width_inch = self.board_width * INCHES_PER_MM
        height_inch = self.board_height * INCHES_PER_MM

        img  = self.board.draw((int(width_inch*300), int(height_inch*300)))
        if self.inverted:
            img = ~img
        
        return img


    def save_image(self, path):
        cv2.imwrite(path, self.board_img)

    def save_mirror_image(self, path):
        mirror = cv2.flip(self.board_img,1)
        cv2.imwrite(path, mirror)

    def get_connected_corners(self):
        """
        For a given board, returns a set of corner id pairs that will connect to form
        a grid pattern. This will provide the "object points" used by the calibration
        functions. It is the ground truth of how the points relate in the world.

        The return value is a *set* not a list
        """
        # create sets of the vertical and horizontal line positions
        corners = self.board.chessboardCorners
        corners_x = corners[:,0]
        corners_y = corners[:,1]
        x_set = set(corners_x)
        y_set = set(corners_y)

        lines = defaultdict(list)

        # put each point on the same vertical line in a list
        for x_line in x_set:
            for corner, x, y in zip(range(0, len(corners)), corners_x, corners_y):
                if x == x_line:
                    lines[f"x_{x_line}"].append(corner)

        # and the same for each point on the same horizontal line
        for y_line in y_set:
            for corner, x, y in zip(range(0, len(corners)), corners_x, corners_y):
                if y == y_line:
                    lines[f"y_{y_line}"].append(corner)

        # create a set of all sets of corner pairs that should be connected
        connected_corners = set()
        for lines, corner_ids in lines.items():
            for i in combinations(corner_ids, 2):
                connected_corners.add(i)

        return connected_corners



    def get_object_corners(self, corner_ids):
        """
        Given an array of corner IDs, provide an array of their relative 
        position in a board from of reference, originating from a corner position.
        """

        return self.board.chessboardCorners[corner_ids, :]

    def export_as_json(self, path):
        charuco_str = json.dumps(self.__dict__, indent=4)    
        with open(path, 'w') as f:
            f.write(charuco_str)



 


################################## REFERENCE ###################################
ARUCO_DICTIONARIES = {
	"DICT_4X4_50": cv2.aruco.DICT_4X4_50,
	"DICT_4X4_100": cv2.aruco.DICT_4X4_100,
	"DICT_4X4_250": cv2.aruco.DICT_4X4_250,
	"DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
	"DICT_5X5_50": cv2.aruco.DICT_5X5_50,
	"DICT_5X5_100": cv2.aruco.DICT_5X5_100,
	"DICT_5X5_250": cv2.aruco.DICT_5X5_250,
	"DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
	"DICT_6X6_50": cv2.aruco.DICT_6X6_50,
	"DICT_6X6_100": cv2.aruco.DICT_6X6_100,
	"DICT_6X6_250": cv2.aruco.DICT_6X6_250,
	"DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
	"DICT_7X7_50": cv2.aruco.DICT_7X7_50,
	"DICT_7X7_100": cv2.aruco.DICT_7X7_100,
	"DICT_7X7_250": cv2.aruco.DICT_7X7_250,
	"DICT_7X7_1000": cv2.aruco.DICT_7X7_1000,
	"DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
	"DICT_APRILTAG_16h5": cv2.aruco.DICT_APRILTAG_16h5,
	"DICT_APRILTAG_25h9": cv2.aruco.DICT_APRILTAG_25h9,
	"DICT_APRILTAG_36h10": cv2.aruco.DICT_APRILTAG_36h10,
	"DICT_APRILTAG_36h11": cv2.aruco.DICT_APRILTAG_36h11
}


########################## DEMO  ###########################################

if __name__ == "__main__":
    charuco = Charuco(4,5,4,8.5,aruco_scale = .75, units = "inch", square_size_overide=.0525)
    charuco.save_image("test_charuco.png")  
    width, height = charuco.board_img.shape
    print(f"Board width is {width}\nBoard height is {height}")
# 
    while True:
        cv2.imshow("Charuco Board", charuco.board_img)
        # 
        key = cv2.waitKey(0)
        if key == ord('q'):
            cv2.destroyAllWindows()
            break
            
    charuco.export_as_json("test_json")
