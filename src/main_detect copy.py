#!/usr/bin/env python3
# -- coding: utf-8 --

import rospy
import numpy as np

import cv2
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image
from ultralytics import YOLO
import torch
import pyzed.sl as sl

from detector_2d.msg import DicBoxes, CoordBoxes
import processing as pr

class Detector:

    def __init__(self):
        image_topic = '~/zed2/zed_node/left_raw/image_raw_color'
        self.zed = sl.Camera
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # create detector
        self._bridge = CvBridge()

        # image and point cloud subscribers
        # and variables that will hold their values
        self._image_sub = rospy.Subscriber(image_topic, Image, self.image_callback)

        self._current_image = None
        self._current_pc = None

        # publisher for frames with detected objects
        self._imagepub = rospy.Publisher('~objects_label', Image, queue_size=10)
        self._boxespub = rospy.Publisher('~boxes_coordinates', DicBoxes, queue_size=10)
        
    
        rospy.loginfo('Ready to detect!')

    def image_callback(self, image):
        """Image callback"""
        # Store value on a private attribute
        self._current_image = image

    def run(self):
        # run while ROS runs
        while not rospy.is_shutdown():
            # only run if there's an image present
            if self._current_image is not None:
                try:
                    #Search image
                    small_frame = self._bridge.imgmsg_to_cv2(self._current_image, desired_encoding='bgr8')

                    #Load model
                    yolo = YOLO("yolov8n.pt")
                    results = yolo.predict(source=small_frame, conf=0.8, device=0)
                        
                    #classes
                    objects_in = []
                    class_boxes = DicBoxes()
                    for r in results:
                        boxes = r.boxes
                        for i, c in enumerate(r.boxes.cls):
                            arr = boxes[i].xywh[0]
                            tmp = sl.CustomBoxObjectData()
                            # Fill the detections into the correct SDK format
                            tmp.unique_object_id = str(c)
                            tmp.probability = 60
                            tmp.label = int(c)
                            tmp.bounding_box_2d = np.array(arr).cpu().detach()
                            tmp.is_grounded = True # objects are moving on the floor plane and tracked in 2D only
                            objects_in.append(tmp)
                        zed.ingest_custom_box_objects(objects_in)


                    #Plot bbox 
                    small_frame = pr.plot_bboxes(small_frame, results[0].boxes.boxes, conf=0.5)
                    
                    #Publisher
                    self._imagepub.publish(self._bridge.cv2_to_imgmsg(small_frame, 'rgb8'))
                    self._boxespub.publish(class_boxes)

                except CvBridgeError as e:
                    print(e)        

if __name__ == '__main__':
    rospy.init_node('detector_2d', log_level=rospy.INFO)
    try:
        Detector().run()
    except KeyboardInterrupt:
        rospy.loginfo('Shutting down')