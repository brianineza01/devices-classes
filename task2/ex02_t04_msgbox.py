from tkinter import *
from tkinter import messagebox

window = Tk()
window.title("MessageBox example")

def mbox_show():
    messagebox.showinfo("ShowInfo MessageBox title","This is showinfo message box")
    messagebox.showwarning("ShowWarning MessageBox title","This is showwarning message box")
    messagebox.showerror("ShowError MessageBox title","This is showerror message box")

    response = messagebox.askyesno("Ask Yes/No message box title","Press Yes and observe the console")
    print(f"The reponse after pressing Yes is {response}")
    response = messagebox.askyesno("Ask Yes/No message box title","Press No and observe the console")
    print(f"The reponse after pressing No is {response}")

    response = messagebox.askokcancel("Ask Ok/Cancel message box title","Press Ok and observe the console")
    print(f"The reponse after pressing Ok is {response}")
    response = messagebox.askokcancel("Ask Ok/Cancel message box title","Press Cancel and observe the console")
    print(f"The reponse after pressing Cancel is {response}")

    response = messagebox.askquestion("Ask question message box title","Press Yes and observe the console")
    print(f"The reponse after pressing Yes is {response}")
    response = messagebox.askquestion("Ask question message box title","Press No and observe the console")
    print(f"The reponse after pressing No is {response}")

Button(window, text="Basic MessageBox test", command=mbox_show).pack()

mainloop()