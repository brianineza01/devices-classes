from pathlib import Path
import csv

files_folder = Path('files')
file_csv = 'read_csv.csv'

try:
    with (open(files_folder.joinpath(file_csv),"r") as file):
        content = csv.reader(file)
        print(type(content))
        for line in content:
            print(line)
        print(type(line))
except FileNotFoundError:
    print("The requested file does not exit")
except PermissionError:
    print("You are not important enough to read this file")