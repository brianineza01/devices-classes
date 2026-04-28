from pathlib import Path

files_folder = Path('files')
file_txt = 'read_txt.txt'

with open(files_folder.joinpath(file_txt),"rt") as file:
    content: str = file.read()
    print(content)

try:
    with open(files_folder.joinpath("missing_file.txt"),"r") as file:
        content: str = file.read()
        print(content)
except FileNotFoundError:
    print("The requested file does not exit")
except PermissionError:
    print("You are not important enough to read this file")

