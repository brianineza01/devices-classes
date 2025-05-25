import tkinter as tk
from tkinter import messagebox
import time
import random
import sys
import math
from PIL import Image, ImageTk

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

# Leave space at the top for information (80 pixels)
info_height = 80
playable_height = win_y - info_height

# Set game grid dimensions directly
grid_width = 40  # Number of cells across
grid_height = 36  # Number of cells vertically in playable area
game_dimensions = [grid_width, grid_height]

# Calculate snake segment size based on window dimensions and grid size
snake_scale = min(win_x // grid_width, playable_height // grid_height)


print("game_dimensions: ", game_dimensions)
print("snake_scale: ", snake_scale)
# Game state variables
game_active = False  # Changed to False so game doesn't start immediately
menu_active = True   # New variable to track if we're in the menu
lives = 3
score = 0
score_p1 = 0  # Separate score for player 1
score_p2 = 0  # Separate score for player 2
walls_enabled = True

# Player 1 snake
snake_coords = [game_dimensions[0] // 2, game_dimensions[1] // 2]
snake_tail = []
snake_move_dir = [1, 0]
snake_moved_in_this_frame = False

# Player 2 snake (for two-player mode)
snake2_coords = [game_dimensions[0] // 2 - 5, game_dimensions[1] // 2]
snake2_tail = []
snake2_move_dir = [1, 0]
snake2_moved_in_this_frame = False
two_player_mode = False

# frames per second
wps = 6

# Wall coordinates
wall_coords = []
def generate_crash_walls():
    global wall_coords
    wall_coords = []
    # Create border walls - note the offset for top wall to leave space for info
    top_row = info_height // snake_scale
    
    # Top wall (with offset)
    for x in range(game_dimensions[0]):
        wall_coords.append([x, top_row])
    
    # Bottom wall
    for x in range(game_dimensions[0]):
        wall_coords.append([x, top_row + game_dimensions[1] - 1])
    
    # Left and right walls
    for y in range(game_dimensions[1]):
        wall_coords.append([0, top_row + y])  # Left wall
        wall_coords.append([game_dimensions[0] - 1, top_row + y])  # Right wall

generate_crash_walls()
# Draw continuous walls with rounded corners

def draw_walls():
    global wall_coords
    wall_color = "#888888"
    
    for wall in wall_coords:
        x, y = wall[0], wall[1]
        
        # Calculate pixel coordinates
        pixel_x = (x * snake_scale)
        pixel_y = (y * snake_scale)
        
        # Draw a rectangle that fills the entire cell to create continuous walls
        snake_canvas.create_rectangle(
            pixel_x, pixel_y,
            pixel_x + snake_scale, pixel_y + snake_scale,
            fill=wall_color, outline=wall_color
        )


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
    global snake_tail, snake2_tail, wall_coords
    
    # Offset for the top info panel
    top_offset = info_height // snake_scale
    
    # apple coordinates
    while True:
        # Generate apple within the playable area
        apple_coords = [
            random.randint(1, game_dimensions[0] - 2), 
            random.randint(top_offset + 1, top_offset + game_dimensions[1] - 2)
        ]
        
        # Check if apple is on snake 1
        if [apple_coords[0], apple_coords[1]] == [snake_coords[0], snake_coords[1]]:
            continue
            
        collision = False
        for segment in snake_tail:
            if segment[0] == apple_coords[0] and segment[1] == apple_coords[1]:
                collision = True
                break
        
        # Check if apple is on snake 2
        if two_player_mode:
            if [apple_coords[0], apple_coords[1]] == [snake2_coords[0], snake2_coords[1]]:
                collision = True
            
            for segment in snake2_tail:
                if segment[0] == apple_coords[0] and segment[1] == apple_coords[1]:
                    collision = True
                    break
        
        # Check if apple is on a wall
        for wall in wall_coords:
            if wall[0] == apple_coords[0] and wall[1] == apple_coords[1]:
                collision = True
                break
                
        if not collision:
            return apple_coords

# Show start menu
def show_start_menu():
    global menu_active, game_active, two_player_mode
    
    # Clear canvas
    snake_canvas.delete("all")
    
    # Set background
    snake_canvas.create_rectangle(0, 0, win_x, win_y, fill="#222222", outline="#222222")
    
    # Title
    snake_canvas.create_text(win_x // 2, 150, text="SNAKE GAME", fill="green", 
                            font=("Arial", 36, "bold"))
    
    # Menu buttons
    button_width = 200
    button_height = 50
    button_x = win_x // 2 - button_width // 2
    
    # 1 Player Mode button
    snake_canvas.create_rectangle(button_x, 250, button_x + button_width, 250 + button_height, 
                                 fill="#444444", outline="#888888", width=2)
    snake_canvas.create_text(win_x // 2, 250 + button_height // 2, text="1 Player Mode", 
                            fill="white", font=("Arial", 16))
    
    # 2 Player Mode button
    snake_canvas.create_rectangle(button_x, 320, button_x + button_width, 320 + button_height, 
                                 fill="#444444", outline="#888888", width=2)
    snake_canvas.create_text(win_x // 2, 320 + button_height // 2, text="2 Player Mode", 
                            fill="white", font=("Arial", 16))
    
    # Help button
    snake_canvas.create_rectangle(button_x, 390, button_x + button_width, 390 + button_height, 
                                 fill="#444444", outline="#888888", width=2)
    snake_canvas.create_text(win_x // 2, 390 + button_height // 2, text="Help", 
                            fill="white", font=("Arial", 16))
    
    # Exit button
    snake_canvas.create_rectangle(button_x, 460, button_x + button_width, 460 + button_height, 
                                 fill="#444444", outline="#888888", width=2)
    snake_canvas.create_text(win_x // 2, 460 + button_height // 2, text="Exit", 
                            fill="white", font=("Arial", 16))

# Show help screen
def show_help_screen():
    # Clear canvas
    snake_canvas.delete("all")
    
    # Set background
    snake_canvas.create_rectangle(0, 0, win_x, win_y, fill="#222222", outline="#222222")
    
    # Title
    snake_canvas.create_text(win_x // 2, 100, text="HOW TO PLAY", fill="yellow", 
                            font=("Arial", 30, "bold"))
    
    # Help text
    help_text = """
    Controls:
    Player 1: Arrow Keys to move
    Player 2: WASD Keys to move
    
    Game Rules:
    - Eat apples to grow and score points
    - Avoid hitting walls and your own tail
    - You have 3 lives
    - In 2-player mode, avoid colliding with the other snake
    
    Press ESC during gameplay to return to menu
    """
    
    snake_canvas.create_text(win_x // 2, 300, text=help_text, fill="white", 
                            font=("Arial", 16), justify="center")
    
    # Back button
    button_width = 200
    button_height = 50
    button_x = win_x // 2 - button_width // 2
    
    snake_canvas.create_rectangle(button_x, 500, button_x + button_width, 500 + button_height, 
                                 fill="#444444", outline="#888888", width=2)
    snake_canvas.create_text(win_x // 2, 500 + button_height // 2, text="Back to Menu", 
                            fill="white", font=("Arial", 16))

# Handle menu clicks
def menu_click(event):
    global menu_active, game_active, two_player_mode
    
    # Get coordinates
    x, y = event.x, event.y
    
    # Check if we're in the menu
    if menu_active:
        button_width = 200
        button_height = 50
        button_x = win_x // 2 - button_width // 2
        
        # 1 Player Mode button
        if button_x <= x <= button_x + button_width and 250 <= y <= 250 + button_height:
            menu_active = False
            game_active = True
            two_player_mode = False
            reset_game()
            
        # 2 Player Mode button
        elif button_x <= x <= button_x + button_width and 320 <= y <= 320 + button_height:
            menu_active = False
            game_active = True
            two_player_mode = True
            reset_game()
            
        # Help button
        elif button_x <= x <= button_x + button_width and 390 <= y <= 390 + button_height:
            show_help_screen()
            
        # Exit button
        elif button_x <= x <= button_x + button_width and 460 <= y <= 460 + button_height:
            sys.exit()
    
    # Check if we're in the help screen
    else:
        button_width = 200
        button_height = 50
        button_x = win_x // 2 - button_width // 2
        
        # Back button
        if button_x <= x <= button_x + button_width and 500 <= y <= 500 + button_height:
            show_start_menu()

# Reset game state
def reset_game():
    global lives, score, score_p1, score_p2, snake_coords, snake_tail, snake_move_dir
    global snake2_coords, snake2_tail, snake2_move_dir, apple_coords
    
    # Reset game state
    lives = 3
    score = 0
    score_p1 = 0
    score_p2 = 0
    
    # Offset for the top info panel
    top_offset = info_height // snake_scale
    
    # Reset player 1
    snake_coords = [game_dimensions[0] // 2, top_offset + game_dimensions[1] // 2]
    snake_tail = []
    snake_move_dir = [1, 0]
    
    # Reset player 2
    if two_player_mode:
        snake2_coords = [game_dimensions[0] // 2 - 5, top_offset + game_dimensions[1] // 2]
        snake2_tail = []
        snake2_move_dir = [1, 0]
    
    # Generate new apple
    apple_coords = generateAppleCoords()

# Return to menu during gameplay
def escape_to_menu(e):
    global game_active, menu_active
    
    if e.keysym == "Escape" and game_active:
        game_active = False
        menu_active = True
        show_start_menu()

# Show game over window
def show_game_over():
    global game_active, lives, score, score_p1, score_p2, menu_active
    
    game_over_window = tk.Toplevel(snake_window)
    game_over_window.title("Game Over")
    game_over_window.geometry("400x300")
    game_over_window.resizable(False, False)
    
    # Try to load game over image
    try:
        img = Image.open("game_over.png")
        img = img.resize((200, 150), Image.LANCZOS)
        game_over_img = ImageTk.PhotoImage(img)
        img_label = tk.Label(game_over_window, image=game_over_img)
        img_label.image = game_over_img  # Keep a reference
        img_label.pack(pady=10)
    except:
        # If image loading fails, show text instead
        tk.Label(game_over_window, text="GAME OVER", font=("Arial", 24, "bold")).pack(pady=20)
    
    if two_player_mode:
        tk.Label(game_over_window, text=f"Player 1 Score: {score_p1}", font=("Arial", 16)).pack(pady=2)
        tk.Label(game_over_window, text=f"Player 2 Score: {score_p2}", font=("Arial", 16)).pack(pady=2)
        winner_text = "Player 1 wins!" if score_p1 > score_p2 else "Player 2 wins!" if score_p2 > score_p1 else "It's a tie!"
        tk.Label(game_over_window, text=winner_text, font=("Arial", 16, "bold")).pack(pady=5)
    else:
        tk.Label(game_over_window, text=f"Final Score: {score}", font=("Arial", 16)).pack(pady=5)
    
    def restart_game():
        global game_active
        
        # Reset game state
        reset_game()
        game_active = True
        
        # Close game over window
        game_over_window.destroy()
    
    def return_to_menu():
        global game_active, menu_active
        
        # Return to menu
        game_active = False
        menu_active = True
        
        # Close game over window
        game_over_window.destroy()
        
        # Show menu
        show_start_menu()
    
    restart_button = tk.Button(game_over_window, text="Play Again", command=restart_game, font=("Arial", 14))
    restart_button.pack(pady=5)
    
    menu_button = tk.Button(game_over_window, text="Return to Menu", command=return_to_menu, font=("Arial", 14))
    menu_button.pack(pady=5)
    
    quit_button = tk.Button(game_over_window, text="Quit Game", command=sys.exit, font=("Arial", 14))
    quit_button.pack(pady=5)

# Reset snake after collision
def reset_snake(player=1):
    global snake_coords, snake_tail, snake_move_dir, lives
    global snake2_coords, snake2_tail, snake2_move_dir
    global game_active
    
    lives -= 1
    
    if lives <= 0:
        game_active = False
        show_game_over()
        return
    
    # Offset for the top info panel
    top_offset = info_height // snake_scale
    
    if player == 1:
        snake_coords = [game_dimensions[0] // 2, top_offset + game_dimensions[1] // 2]
        snake_tail = []  # Clear the tail
        snake_move_dir = [1, 0]
    else:
        snake2_coords = [game_dimensions[0] // 2 - 5, top_offset + game_dimensions[1] // 2]
        snake2_tail = []  # Clear the tail
        snake2_move_dir = [1, 0]

# Toggle two-player mode
def toggle_two_player():
    global two_player_mode, snake2_coords, snake2_tail, snake2_move_dir
    
    two_player_mode = not two_player_mode
    
    if two_player_mode:
        snake2_coords = [game_dimensions[0] // 2 - 5, game_dimensions[1] // 2]
        snake2_tail = []
        snake2_move_dir = [1, 0]

# game
def gameloop():
    # global game variables
    global wps, snake_moved_in_this_frame, snake2_moved_in_this_frame
    global snake_canvas, game_dimensions
    global snake_tail, snake_coords, snake_move_dir
    global snake2_tail, snake2_coords, snake2_move_dir
    global apple_coords, lives, score, score_p1, score_p2, game_active, menu_active, two_player_mode

    # Schedule next frame
    snake_window.after(1000 // wps, gameloop)
    
    # Check if we're in the menu
    if menu_active:
        return
        
    # Check if game is active
    if not game_active:
        return

    # clear game window
    snake_canvas.delete("all")
    # set background
    snake_canvas.create_rectangle(0, 0, win_x, win_y, fill="#222222", outline="#222222")
    
    # Create info panel at the top
    info_panel_height = info_height
    snake_canvas.create_rectangle(0, 0, win_x, info_panel_height, fill="#333333", outline="#444444")
    
    # Draw continuous walls with rounded corners
    draw_walls()
    
    # Display score and lives in the info panel
    if two_player_mode:
        snake_canvas.create_text(70, 25, text=f"P1 Score: {score_p1}", fill="#00ff00", font=("Arial", 14))
        snake_canvas.create_text(200, 25, text=f"P2 Score: {score_p2}", fill="#0000ff", font=("Arial", 14))
        snake_canvas.create_text(70, 55, text=f"Lives: {lives}", fill="white", font=("Arial", 14))
    else:
        snake_canvas.create_text(70, 25, text=f"Score: {score}", fill="white", font=("Arial", 14))
        snake_canvas.create_text(70, 55, text=f"Lives: {lives}", fill="white", font=("Arial", 14))
    
    # Display game mode and controls in the info panel
    if two_player_mode:
        snake_canvas.create_text(win_x // 2, 25, text="Two Player Mode", fill="yellow", font=("Arial", 14))
    else:
        snake_canvas.create_text(win_x // 2, 25, text="One Player Mode", fill="green", font=("Arial", 14))
    
    # Display ESC hint
    snake_canvas.create_text(win_x - 100, 25, text="ESC for Menu", fill="white", font=("Arial", 12))
    
    # Display controls reminder
    if two_player_mode:
        controls_text = "P1: Arrows | P2: WASD"
    else:
        controls_text = "Controls: Arrow Keys"
    snake_canvas.create_text(win_x - 100, 55, text=controls_text, fill="white", font=("Arial", 12))
    
    # PLAYER 1 SNAKE LOGIC
    # add the snake head
    snake_tail.append([snake_coords[0], snake_coords[1]])
    # move the snake
    snake_coords[0] += snake_move_dir[0]
    snake_coords[1] += snake_move_dir[1]
    
    # Check for wall collision
    wall_collision = False
    for wall in wall_coords:
        if snake_coords[0] == wall[0] and snake_coords[1] == wall[1]:
            wall_collision = True
            break
    
    if wall_collision:
        reset_snake(1)
    else:
        # Check for wrapping (if not hitting walls)
        if (snake_coords[0] == game_dimensions[0]):
            snake_coords[0] = 0
        elif (snake_coords[0] == -1):
            snake_coords[0] = game_dimensions[0] - 1
        elif (snake_coords[1] == game_dimensions[1] + (info_height // snake_scale)):
            snake_coords[1] = info_height // snake_scale
        elif (snake_coords[1] == (info_height // snake_scale) - 1):
            snake_coords[1] = game_dimensions[1] + (info_height // snake_scale) - 1
    
    # snake moved in the frame
    snake_moved_in_this_frame = False

    # head-tail collision - lose a life
    for segment in snake_tail:
        if (segment[0] == snake_coords[0] and segment[1] == snake_coords[1]):
            reset_snake(1)
            break
        # display snake segments
        createGridItem(segment, "#00ff00")
    
    # PLAYER 2 SNAKE LOGIC (if two-player mode is enabled)
    if two_player_mode:
        # add the snake 2 head
        snake2_tail.append([snake2_coords[0], snake2_coords[1]])
        # move snake 2
        snake2_coords[0] += snake2_move_dir[0]
        snake2_coords[1] += snake2_move_dir[1]
        
        # Check for wall collision for snake 2
        wall_collision = False
        for wall in wall_coords:
            if snake2_coords[0] == wall[0] and snake2_coords[1] == wall[1]:
                wall_collision = True
                break
        
        if wall_collision:
            reset_snake(2)
        else:
            # Check for wrapping (if not hitting walls)
            if (snake2_coords[0] == game_dimensions[0]):
                snake2_coords[0] = 0
            elif (snake2_coords[0] == -1):
                snake2_coords[0] = game_dimensions[0] - 1
            elif (snake2_coords[1] == game_dimensions[1] + (info_height // snake_scale)):
                snake2_coords[1] = info_height // snake_scale
            elif (snake2_coords[1] == (info_height // snake_scale) - 1):
                snake2_coords[1] = game_dimensions[1] + (info_height // snake_scale) - 1
        
        # snake 2 moved in the frame
        snake2_moved_in_this_frame = False

        # Check for snake 2 head-tail collision
        for segment in snake2_tail:
            if (segment[0] == snake2_coords[0] and segment[1] == snake2_coords[1]):
                reset_snake(2)
                break
            # display snake 2 segments
            createGridItem(segment, "#0000ff")  # Blue for player 2
        
        # Check for collision between snake 1 and snake 2
        if (snake_coords[0] == snake2_coords[0] and snake_coords[1] == snake2_coords[1]):
            # Both snakes reset in a head-to-head collision
            reset_snake(1)
            reset_snake(2)
        
        # Check if snake 1 hits snake 2's body
        for segment in snake2_tail:
            if (snake_coords[0] == segment[0] and snake_coords[1] == segment[1]):
                reset_snake(1)  # Only snake 1 resets
                break
        
        # Check if snake 2 hits snake 1's body
        for segment in snake_tail:
            if (snake2_coords[0] == segment[0] and snake2_coords[1] == segment[1]):
                reset_snake(2)  # Only snake 2 resets
                break

    # display an apple
    createGridItem(apple_coords, "#ff0000")
    
    # if an apple was eaten by player 1
    if (apple_coords[0] == snake_coords[0] and apple_coords[1] == snake_coords[1]):
        apple_coords = generateAppleCoords()
        if two_player_mode:
            score_p1 += 1
        else:
            score += 1
        # Don't remove tail segment for player 1 (snake grows)
        if two_player_mode:
            # Still remove tail segment for player 2 (no growth)
            snake2_tail.pop(0)
    # if an apple was eaten by player 2
    elif two_player_mode and (apple_coords[0] == snake2_coords[0] and apple_coords[1] == snake2_coords[1]):
        apple_coords = generateAppleCoords()
        score_p2 += 1
        # Don't remove tail segment for player 2 (snake grows)
        # Still remove tail segment for player 1 (no growth)
        snake_tail.pop(0)
    else:
        # Remove tail segment if no apple was eaten
        if len(snake_tail) > 0:
            snake_tail.pop(0)
        if two_player_mode and len(snake2_tail) > 0:
            snake2_tail.pop(0)

# keyboard for player 1
def key(e):
    # global variables used
    global snake_move_dir, snake_moved_in_this_frame
    global two_player_mode

    # Toggle two-player mode with 'T' key
    if e.keysym == "t" or e.keysym == "T":
        toggle_two_player()
        return

    # check if snake moved in this frame
    if (snake_moved_in_this_frame == False):
        snake_moved_in_this_frame = True

        # arrow keys for player 1
        if (e.keysym == "Left" and snake_move_dir[0] != 1):
            snake_move_dir = [-1, 0]
        elif (e.keysym == "Right" and snake_move_dir[0] != -1):
            snake_move_dir = [1, 0]
        elif (e.keysym == "Up" and snake_move_dir[1] != 1):
            snake_move_dir = [0, -1]
        elif (e.keysym == "Down" and snake_move_dir[1] != -1):
            snake_move_dir = [0, 1]
        else:
            snake_moved_in_this_frame = False

# keyboard for player 2
def key2(e):
    # global variables used
    global snake2_move_dir, snake2_moved_in_this_frame, two_player_mode
    
    if not two_player_mode:
        return

    # check if snake 2 moved in this frame
    if (snake2_moved_in_this_frame == False):
        snake2_moved_in_this_frame = True

        # WASD keys for player 2
        if (e.keysym == "a" and snake2_move_dir[0] != 1):
            snake2_move_dir = [-1, 0]
        elif (e.keysym == "d" and snake2_move_dir[0] != -1):
            snake2_move_dir = [1, 0]
        elif (e.keysym == "w" and snake2_move_dir[1] != 1):
            snake2_move_dir = [0, -1]
        elif (e.keysym == "s" and snake2_move_dir[1] != -1):
            snake2_move_dir = [0, 1]
        else:
            snake2_moved_in_this_frame = False

####################################################################################################################
# place an apple
apple_coords = generateAppleCoords()
# binding function
snake_window.bind("<KeyPress>", key)
snake_window.bind("<KeyPress>", key2, add="+")  # Add second binding for player 2
snake_window.bind("<KeyPress>", escape_to_menu, add="+")  # Add binding for ESC key
snake_window.bind("<Button-1>", menu_click)  # Add binding for mouse clicks

# Show the start menu
show_start_menu()

# game
gameloop()
# display game window and check for keyboard event
snake_window.mainloop()