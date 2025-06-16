import cv2

img = cv2.imread("images/garfield.jpg")

cv2.imshow("Garfield the Cat",img)

def scale_image(img, scale = 0.5):
    h = int(img.shape[0] * scale)
    w = int(img.shape[1] * scale)
    dimensions = (w,h)
    return cv2.resize(img,dimensions,scale,interpolation = cv2.INTER_AREA)

cv2.imshow("Scale Image",scale_image(img))

cv2.waitKey(0)

cv2.destroyWindow("Garfield the Cat")
cv2.destroyWindow("Scale Image")