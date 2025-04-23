from tkinter import *
from PIL import Image, ImageTk

wnd = Tk()
wnd.title('Images')

t_img = ImageTk.PhotoImage(Image.open("wsg_logo.jpg"))
label_img = Label(image=t_img)
label_img.pack()

button_exit = Button(wnd,text="Quit",command=wnd.destroy)
button_exit.pack()

wnd.mainloop()



