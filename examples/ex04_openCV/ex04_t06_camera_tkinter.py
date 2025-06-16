from tkinter import *
import cv2
from PIL import Image, ImageTk
from PIL.ImageTk import PhotoImage

img = cv2.VideoCapture(0)
img.set(cv2.CAP_PROP_FRAME_WIDTH,800)
img.set(cv2.CAP_PROP_FRAME_HEIGHT,600)

wnd = Tk()
wnd.title("Camera")
wnd_x_size = 1200
wnd_y_size = 800
screen_x_size = wnd.winfo_screenwidth()
screen_y_size = wnd.winfo_screenheight()
center_x = int((screen_x_size - wnd_x_size)/2)
center_y = int((screen_y_size - wnd_y_size)/2)
wnd.geometry(f'{wnd_x_size}x{wnd_y_size}+{center_x}+{center_y}')
wnd.resizable(False,False)

wnd.bind('<Escape>',lambda q: wnd.destroy())

label_cam = Label(wnd)
label_cam.pack()

def open_cam():
    _, frame = img.read()
    cv2_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGBA)
    cap_image = Image.fromarray(cv2_frame)
    photo_image = ImageTk.PhotoImage(image=cap_image)
    label_cam.photo_image = photo_image
    label_cam.configure(image=photo_image)
    label_cam.after(1, open_cam)
    button_cam.config(state='disabled')

button_cam = Button(wnd,text="Camera",command=open_cam)
button_cam.pack()
wnd.mainloop()
