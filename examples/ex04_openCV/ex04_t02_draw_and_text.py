import cv2
import numpy as np

img = cv2.imread("images/garfield.jpg")
cv2.putText(img,'This is Garfield the cat',(25,50), cv2.FONT_HERSHEY_DUPLEX,1.5,(0,255,255),3)
cv2.imshow("Garfield",img)

img_blank = np.zeros((300,300,3),dtype='uint8')
cv2.imshow("Empty image",img_blank)
img_blank[:] = 0,255,0
cv2.imshow("Green image",img_blank)

#1. Image as a list
img_blank[200:,:20] = 255,0,0
cv2.imshow("Blue and green image",img_blank)

#2. Use openCV
cv2.rectangle(img_blank,(0,0),(50,50),(0,0,255),thickness=cv2.FILLED)
cv2.line(img_blank,(100,100),(200,200),(255,255,255), thickness=4)
cv2.imshow("RGB image",img_blank)

cv2.waitKey(0)
cv2.destroyAllWindows()
