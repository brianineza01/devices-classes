from pathlib import Path
import json

files_folder = Path('files')
file_json = 'read_json.json'

try:
    with (open(files_folder.joinpath(file_json),"r") as file):
        content: dict = json.load(file)
        print(content)
        print(content["name"])
except FileNotFoundError:
    print("The requested file does not exit")
except PermissionError:
    print("You are not important enough to read this file")