import tkinter
import numpy as np
from matplotlib.figure import Figure
# https://matplotlib.org/stable/users/explain/figure/backends.html
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

wnd = tkinter.Tk()
wnd.title("Sine wave")

x = np.linspace(0, 10, 100)
y = np.sin(x)
fig = Figure(figsize=(6, 4), dpi=100)
fig.add_subplot().plot(x,y)

canvas = FigureCanvasTkAgg(fig, master=wnd)
canvas.draw()

button_quit = tkinter.Button(master=wnd, text="Quit", command=wnd.destroy)

button_quit.pack(side=tkinter.BOTTOM)
canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=True)

wnd.mainloop()