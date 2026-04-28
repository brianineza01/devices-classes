from pathlib import Path

files_folder = Path('files')
file_name = 'txt_file.txt'

file = open(files_folder.joinpath(file_name),'w')
file.write("This is the first string in this file")
file.close()

with open(files_folder.joinpath(file_name),'a') as file:
    file.write("This is the 2nd string inside the txt file")

try:
    with open(files_folder.joinpath(file_name),'x') as file:
        file.write("Open file with x attribute")
except Exception as e:
    print(f'Error {e}')