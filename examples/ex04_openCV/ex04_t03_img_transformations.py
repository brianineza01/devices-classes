import cv2
import numpy as np

img = cv2.imread("images/garfield.jpg")

img_gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
cv2.imshow('Gray image',img_gray)

img_blur = cv2.GaussianBlur(img,(7,7),cv2.BORDER_DEFAULT)
cv2.imshow('Blurred image',img_blur)

canny = cv2.Canny(img_blur,125,175)
cv2.imshow('Canny edges',canny)

#Transaltion
def translate(img, x, y):
    transMatrix = np.float32([[1,0,x],[0,1,y]])
    return cv2.warpAffine(img, transMatrix, (img.shape[1],img.shape[0]))

translated_img = translate(img,100,50)
cv2.imshow("Vector (100,50)",translated_img)
translated_img = translate(img,-100,50)
cv2.imshow("Vector (-100,50)",translated_img)

def rotate(img, angle, rot_point = None):
    (h,w) = img.shape[:2]
    if rot_point is None:
        rot_point = (w//2, h//2)
    rotMatrix = cv2.getRotationMatrix2D(rot_point, angle, 0.5)
    return cv2.warpAffine(img,rotMatrix,(w,h))

rotated_img = rotate(img,45)
cv2.imshow("45deg rotation",rotated_img)

#Flip
flip_v = cv2.flip(img,0)
cv2.imshow("Flipped vertically",flip_v)
flip_h = cv2.flip(img,1)
cv2.imshow("Flipped horizotally",flip_h)
flip_vh = cv2.flip(img,-1)
cv2.imshow("Flipped V&H",flip_vh)

#Crop
cropped_img = img[100:200,200:300]
cv2.imshow("Cropped image",cropped_img)

cv2.waitKey(0)
cv2.destroyAllWindows()
