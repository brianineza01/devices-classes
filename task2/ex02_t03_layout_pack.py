import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import *

wnd = tk.Tk()
wnd.title("Pack layout")
# windows in the middle of a screen
wnd_x_size = 800
wnd_y_size = 400
screen_x_size = wnd.winfo_screenwidth()
screen_y_size = wnd.winfo_screenheight()
center_x = int((screen_x_size - wnd_x_size)/2)
center_y = int((screen_y_size - wnd_y_size)/2)
wnd.geometry(f'{wnd_x_size}x{wnd_y_size}+{center_x}+{center_y}')
wnd.resizable(False,False)

def download_clicked():
    showinfo(title="Important info",
             message="Download has been clicked")

# window size 300x200; position x=100 y=50 from tof left corner
def open_new_window():
    wnd_new = tk.Toplevel(wnd)
    wnd_new.geometry('300x200+100+50')
    wnd_new.attributes('-alpha', 0.5)
    wnd_new.attributes('-topmost', 1)

def port_select():
    wnd_com = tk.Toplevel(wnd)
    wnd_com.geometry('400x300+100+50')
    wnd_com.title("Select proper COM port")
    fields = {}
    fields['selected_port_label'] = ttk.Label(wnd_com,
                                              text = "Selected COM port:")
    port_name = tk.StringVar()
    fields['selected_port'] = ttk.Entry(wnd_com,
                                        textvariable = port_name)
    fields['available_ports_label'] = ttk.Label(wnd_com,
                                                text = "Available COM ports")
    fields['available_ports'] = ttk.Combobox(wnd_com)
    fields['btn_copy'] = ttk.Button(wnd_com,
                                    text = "Copy port name")
    for field in fields.values():
        field.pack(anchor=tk.W, padx=10, pady=10, fill=tk.X)

btn_exit = ttk.Button(wnd, text="System down", command = lambda: wnd.destroy())
download_ico = tk.PhotoImage(file="ico_download.png")
btn_download = ttk.Button(wnd, image=download_ico, command = download_clicked)
btn_left = ttk.Button(wnd,text = "Open", command = open_new_window)
btn_right = ttk.Button(wnd,text = "Select COM port", command = port_select)

#https://www.pythontutorial.net/tkinter/tkinter-pack/
btn_left.pack(side = tk.TOP, expand = True, fill = tk.NONE, anchor = tk.W)
btn_download.pack(side = tk.TOP, expand = True, fill = tk.Y)
btn_right.pack(side = tk.TOP, expand = True, fill = tk.X)
btn_exit.pack(side = tk.TOP, expand = True, fill = tk.BOTH)

wnd.mainloop()
