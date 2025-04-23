import tkinter as tk
import time
import random
import sys
import math
####################################################################################################################
# game parameters
# game window
snake_window = tk.Tk()
# game window size
win_x, win_y = 800, 800
game_window_dimensions = [win_x, win_y]
snake_window.geometry(str(win_x) + "x" + str(win_y))
# block game window size
snake_window.resizable(0, 0)
# window title
snake_window.title("Snake")
# close game window
snake_window.protocol("WM_DELETE_WINDOW", sys.exit)
# game window: bd - background; highlightthickness - frame
snake_canvas = tk.Canvas(snake_window, width=win_x, height=win_y, bd=0, highlightthickness=0)
snake_canvas.pack()
# snake segment size
snake_scale = 25
game_dimensions = [win_x // snake_scale, win_y // snake_scale]
# snake head - start postition, snake tail list
snake_coords = [game_dimensions[0] // 2, game_dimensions[1] // 2]
snake_tail = []
# snake movement direction[x,y]
snake_move_dir = [1, 0]
snake_moved_in_this_frame = False
# frames per second
wps = 10
####################################################################################################################
# GAME FUNCTIONS
####################################################################################################################
# fill game field grid
def createGridItem(coords, hexcolor):
    snake_canvas.create_rectangle((coords[0]) * snake_scale, (coords[1]) * snake_scale, (coords[0] + 1) * snake_scale,
                                 (coords[1] + 1) * snake_scale, fill=hexcolor, outline="#222222", width=3)

# apple coordinates
def generateAppleCoords():
    # use snake tail
    global snake_tail
    # apple coordinates
    apple_coords = [random.randint(0, (game_dimensions[0] - 1)), random.randint(0, (game_dimensions[1] - 1))]
    # apple may not be a part of snake tail
    for segment in snake_tail:
        if (segment[0] == apple_coords[0] and segment[1] == apple_coords[1]):
            return generateAppleCoords()
    # apple coordinates
    return apple_coords

# game
def gameloop():
    # global game variables
    global wps
    global snake_moved_in_this_frame
    global snake_canvas
    global game_dimensions
    global window_dimensions
    global snake_tail
    global snake_coords
    global snake_move_dir
    global apple_coords

    # game speed =  1s/wps (frames per second)
    snake_window.after(1000 // wps, gameloop)
    # clear game window
    snake_canvas.delete("all")
    # set background
    snake_canvas.create_rectangle(0, 0, win_x, win_y, fill="#222222", outline="#222222")

    # add the snake head
    snake_tail.append([snake_coords[0], snake_coords[1]])
    # move the snake
    snake_coords[0] += snake_move_dir[0]
    snake_coords[1] += snake_move_dir[1]
    if (snake_coords[0] == game_dimensions[0]):
        snake_coords[0] = 0
    elif (snake_coords[0] == -1):
        snake_coords[0] = game_dimensions[0] - 1
    elif (snake_coords[1] == game_dimensions[1]):
        snake_coords[1] = 0
    elif (snake_coords[1] == -1):
        snake_coords[1] = game_dimensions[1] - 1
    # snake moved in the frame
    snake_moved_in_this_frame = False

    # head-tail collision - game restart
    for segment in snake_tail:
        if (segment[0] == snake_coords[0] and segment[1] == snake_coords[1]):
            snake_coords = [game_dimensions[0] // 2, game_dimensions[1] // 2]
            snake_tail = []
            snake_move_dir = [1, 0]
            apple_coords = generateAppleCoords()
        # display a snake
        createGridItem(segment, "#00ff00")

    # display an apple
    createGridItem(apple_coords, "#ff0000")
    # if an apple was eaten add one segment to the snake tail
    if (apple_coords[0] == snake_coords[0] and apple_coords[1] == snake_coords[1]):
        apple_coords = generateAppleCoords()
    else:
        snake_tail.pop(0)

# keyboard
def key(e):
    # global variables used
    global snake_move_dir
    global snake_moved_in_this_frame

    # check if snake moved in this frame
    if (snake_moved_in_this_frame == False):
        snake_moved_in_this_frame = True

        # arrow keys
        if (e.keysym == "Left" and snake_move_dir[0] != 1):
            snake_move_dir  = [-1, 0]
        elif (e.keysym == "Right" and snake_move_dir[0] != -1):
            snake_move_dir  = [1, 0]
        elif (e.keysym == "Up" and snake_move_dir[1] != 1):
            snake_move_dir  = [0, -1]
        elif (e.keysym == "Down" and snake_move_dir[1] != -1):
            snake_move_dir  = [0, 1]
        else:
            snake_moved_in_this_frame = False
####################################################################################################################
# place an apple
apple_coords = generateAppleCoords()
# binding function
snake_window.bind("<KeyPress>", key)
# game
gameloop()
# display game window and check for keyboard event
snake_window.mainloop()