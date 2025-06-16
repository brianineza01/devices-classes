import cv2
import numpy as np

img = cv2.imread("images/garfield.jpg")
cv2.imshow("Garfield the Cat",img)
img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
cv2.imshow("Gray image",img_gray)
img_edges = cv2.Canny(img,125,275)
cv2.imshow("Canny edge detection",img_edges)

contours,hierarchies = cv2.findContours(img_edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
print(f'{len(contours)} contours found')

img_blank = np.zeros(img.shape,dtype='uint8')
cv2.drawContours(img_blank, contours, -1, (0,255,0),2)
cv2.imshow('Contours',img_blank)

cv2.waitKey(0)
cv2.destroyAllWindows()