import tkinter as tk
from tkinter.ttk import *
from tkinter.messagebox import *

def convert():
    temp_K = temp_C.get() + 273.15
    print(temp_K)
    print(type(temp_K))
    showinfo(title="Temperature in K",message=str(temp_K))

#window
wnd = tk.Tk()
wnd.title("Temperature converter")
wnd.geometry('400x200')

#app window - label
#www.pythontutorial.net/tkinter/tkinter-label/
lab_title = Label(wnd,
                  text="Celsius to Kelvin converter",
                  font=('Helvetica',14))
lab_title.pack()

#app window - input field
frame_input = Frame(wnd)
temp_C = tk.DoubleVar()
entry = Entry(frame_input, textvariable=temp_C)
btn_convert = Button(frame_input,
                     text='Convert',
                     command=convert)
entry.pack(side='left',padx=15)
btn_convert.pack(side='left')
frame_input.pack(pady=15)

#run window
wnd.mainloop()
