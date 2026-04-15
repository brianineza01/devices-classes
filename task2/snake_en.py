import tkinter as tk
from tkinter import messagebox
import time
import random
import math
from PIL import Image, ImageTk
from gpiozero import Button

class SnakeGame:
    def __init__(self):
        # Game window setup
        self.window = tk.Tk()
        self.win_x, self.win_y = 800, 800
        self.window.geometry(f"{self.win_x}x{self.win_y}")
        self.window.resizable(0, 0)
        self.window.title("Snake")
        self.window.protocol("WM_DELETE_WINDOW", self.close_app)
        
        # Canvas setup
        self.canvas = tk.Canvas(self.window, width=self.win_x, height=self.win_y, bd=0, highlightthickness=0)
        self.canvas.pack()
        
        # Game dimensions
        self.info_height = 80
        self.playable_height = self.win_y - self.info_height
        self.grid_width = 40
        self.grid_height = 36
        self.snake_scale = min(self.win_x // self.grid_width, self.playable_height // self.grid_height)
        
        # Game state variables
        self.game_active = False
        self.menu_active = True
        self.lives = 3
        self.score = 0
        self.score_p1 = 0
        self.score_p2 = 0
        self.walls_enabled = True
        self.two_player_mode = False
        self.frames_per_second = 6
        self.closing = False
        self.gpio_pins = {
            "up": 17,
            "down": 27,
            "left": 22,
            "right": 23,
            "quit": 24,
        }
        self.gpio_buttons = {}
        
        # Initialize players
        self.initialize_players()
        
        # Wall coordinates
        self.wall_coords = []
        self.generate_walls()
        
        # Apple coordinates
        self.apple_coords = self.generate_apple_coords()
        
        # Set up key bindings
        self.setup_key_bindings()
        self.setup_gpio_buttons()
        
        # Show the start menu
        self.show_start_menu()
        
    def initialize_players(self):
        top_offset = self.info_height // self.snake_scale
        
        # Player 1 (primary snake)
        self.snake1 = {
            'coords': [self.grid_width // 2, top_offset + self.grid_height // 2],
            'tail': [],
            'move_dir': [1, 0],
            'moved_in_frame': False,
            'color': "#00ff00"  # Green
        }
        
        # Player 2 (secondary snake)
        self.snake2 = {
            'coords': [self.grid_width // 2 - 5, top_offset + self.grid_height // 2],
            'tail': [],
            'move_dir': [1, 0],
            'moved_in_frame': False,
            'color': "#0000ff"  # Blue
        }
    
    def generate_walls(self):
        self.wall_coords = []
        top_row = self.info_height // self.snake_scale
        
        # Top wall (with offset for info panel)
        for x in range(self.grid_width):
            self.wall_coords.append([x, top_row])
        
        # Bottom wall
        for x in range(self.grid_width):
            self.wall_coords.append([x, top_row + self.grid_height - 1])
        
        # Left and right walls
        for y in range(self.grid_height):
            self.wall_coords.append([0, top_row + y])  # Left wall
            self.wall_coords.append([self.grid_width - 1, top_row + y])  # Right wall
    
    def draw_walls(self):
        wall_color = "#888888"
        
        for wall in self.wall_coords:
            x, y = wall[0], wall[1]
            pixel_x = x * self.snake_scale
            pixel_y = y * self.snake_scale
            
            self.canvas.create_rectangle(
                pixel_x, pixel_y,
                pixel_x + self.snake_scale, pixel_y + self.snake_scale,
                fill=wall_color, outline=wall_color
            )
    
    def create_grid_item(self, coords, color):
        self.canvas.create_rectangle(
            coords[0] * self.snake_scale, 
            coords[1] * self.snake_scale, 
            (coords[0] + 1) * self.snake_scale,
            (coords[1] + 1) * self.snake_scale, 
            fill=color, 
            outline="#222222", 
            width=3
        )
    
    def generate_apple_coords(self):
        top_offset = self.info_height // self.snake_scale
        
        while True:
            # Generate apple within the playable area
            apple_coords = [
                random.randint(1, self.grid_width - 2), 
                random.randint(top_offset + 1, top_offset + self.grid_height - 2)
            ]
            
            # Check collisions with snake 1
            if apple_coords == self.snake1['coords'] or apple_coords in self.snake1['tail']:
                continue
            
            # Check collisions with snake 2
            if self.two_player_mode and (apple_coords == self.snake2['coords'] or apple_coords in self.snake2['tail']):
                continue
            
            # Check collisions with walls
            if apple_coords in self.wall_coords:
                continue
                
            return apple_coords
    
    def show_start_menu(self):
        # Clear canvas
        self.canvas.delete("all")
        
        # Set background
        self.canvas.create_rectangle(0, 0, self.win_x, self.win_y, fill="#222222", outline="#222222")
        
        # Title
        self.canvas.create_text(self.win_x // 2, 150, text="SNAKE GAME", fill="green", 
                               font=("Arial", 36, "bold"))
        
        # Menu buttons
        button_width = 200
        button_height = 50
        button_x = self.win_x // 2 - button_width // 2
        
        # 1 Player Mode button
        self.canvas.create_rectangle(button_x, 250, button_x + button_width, 250 + button_height, 
                                    fill="#444444", outline="#888888", width=2)
        self.canvas.create_text(self.win_x // 2, 250 + button_height // 2, text="1 Player Mode", 
                               fill="white", font=("Arial", 16))
        
        # 2 Player Mode button
        self.canvas.create_rectangle(button_x, 320, button_x + button_width, 320 + button_height, 
                                    fill="#444444", outline="#888888", width=2)
        self.canvas.create_text(self.win_x // 2, 320 + button_height // 2, text="2 Player Mode", 
                               fill="white", font=("Arial", 16))
        
        # Help button
        self.canvas.create_rectangle(button_x, 390, button_x + button_width, 390 + button_height, 
                                    fill="#444444", outline="#888888", width=2)
        self.canvas.create_text(self.win_x // 2, 390 + button_height // 2, text="Help", 
                               fill="white", font=("Arial", 16))
        
        # Exit button
        self.canvas.create_rectangle(button_x, 460, button_x + button_width, 460 + button_height, 
                                    fill="#444444", outline="#888888", width=2)
        self.canvas.create_text(self.win_x // 2, 460 + button_height // 2, text="Exit", 
                               fill="white", font=("Arial", 16))
    
    def show_help_screen(self):
        # Clear canvas
        self.canvas.delete("all")
        
        # Set background
        self.canvas.create_rectangle(0, 0, self.win_x, self.win_y, fill="#222222", outline="#222222")
        
        # Title
        self.canvas.create_text(self.win_x // 2, 100, text="HOW TO PLAY", fill="yellow", 
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
        RPi: GPIO buttons move Player 1, quit button closes the game
        """
        
        self.canvas.create_text(self.win_x // 2, 300, text=help_text, fill="white", 
                               font=("Arial", 16), justify="center")
        
        # Back button
        button_width = 200
        button_height = 50
        button_x = self.win_x // 2 - button_width // 2
        
        self.canvas.create_rectangle(button_x, 500, button_x + button_width, 500 + button_height, 
                                    fill="#444444", outline="#888888", width=2)
        self.canvas.create_text(self.win_x // 2, 500 + button_height // 2, text="Back to Menu", 
                               fill="white", font=("Arial", 16))
    
    def handle_menu_click(self, event):
        x, y = event.x, event.y
        
        if not self.menu_active:
            # Check if we're in the help screen
            button_width = 200
            button_height = 50
            button_x = self.win_x // 2 - button_width // 2
            
            # Back button
            if button_x <= x <= button_x + button_width and 500 <= y <= 500 + button_height:
                self.show_start_menu()
                self.menu_active = True
            return
        
        # Menu buttons logic
        button_width = 200
        button_height = 50
        button_x = self.win_x // 2 - button_width // 2
        
        # 1 Player Mode button
        if button_x <= x <= button_x + button_width and 250 <= y <= 250 + button_height:
            self.menu_active = False
            self.game_active = True
            self.two_player_mode = False
            self.reset_game()
            
        # 2 Player Mode button
        elif button_x <= x <= button_x + button_width and 320 <= y <= 320 + button_height:
            self.menu_active = False
            self.game_active = True
            self.two_player_mode = True
            self.reset_game()
            
        # Help button
        elif button_x <= x <= button_x + button_width and 390 <= y <= 390 + button_height:
            self.menu_active = False
            self.show_help_screen()
            
        # Exit button
        elif button_x <= x <= button_x + button_width and 460 <= y <= 460 + button_height:
            self.close_app()
    
    def reset_game(self):
        self.lives = 3
        self.score = 0
        self.score_p1 = 0
        self.score_p2 = 0
        
        top_offset = self.info_height // self.snake_scale
        
        # Reset player 1
        self.snake1['coords'] = [self.grid_width // 2, top_offset + self.grid_height // 2]
        self.snake1['tail'] = []
        self.snake1['move_dir'] = [1, 0]
        
        # Reset player 2 if two-player mode
        if self.two_player_mode:
            self.snake2['coords'] = [self.grid_width // 2 - 5, top_offset + self.grid_height // 2]
            self.snake2['tail'] = []
            self.snake2['move_dir'] = [1, 0]
        
        # Generate new apple
        self.apple_coords = self.generate_apple_coords()
    
    def return_to_menu(self, event):
        if event.keysym == "Escape" and self.game_active:
            self.game_active = False
            self.menu_active = True
            self.show_start_menu()
    
    def show_game_over(self):
        game_over_window = tk.Toplevel(self.window)
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
        
        if self.two_player_mode:
            tk.Label(game_over_window, text=f"Player 1 Score: {self.score_p1}", font=("Arial", 16)).pack(pady=2)
            tk.Label(game_over_window, text=f"Player 2 Score: {self.score_p2}", font=("Arial", 16)).pack(pady=2)
            winner_text = "Player 1 wins!" if self.score_p1 > self.score_p2 else "Player 2 wins!" if self.score_p2 > self.score_p1 else "It's a tie!"
            tk.Label(game_over_window, text=winner_text, font=("Arial", 16, "bold")).pack(pady=5)
        else:
            tk.Label(game_over_window, text=f"Final Score: {self.score}", font=("Arial", 16)).pack(pady=5)
        
        def restart_game():
            # Reset game state
            self.reset_game()
            self.game_active = True
            game_over_window.destroy()
        
        def return_to_menu():
            # Return to menu
            self.game_active = False
            self.menu_active = True
            game_over_window.destroy()
            self.show_start_menu()
        
        restart_button = tk.Button(game_over_window, text="Play Again", command=restart_game, font=("Arial", 14))
        restart_button.pack(pady=5)
        
        menu_button = tk.Button(game_over_window, text="Return to Menu", command=return_to_menu, font=("Arial", 14))
        menu_button.pack(pady=5)
        
        quit_button = tk.Button(game_over_window, text="Quit Game", command=self.close_app, font=("Arial", 14))
        quit_button.pack(pady=5)

    def cleanup_gpio_buttons(self):
        for button in self.gpio_buttons.values():
            button.close()
        self.gpio_buttons.clear()

    def close_app(self):
        if self.closing:
            return

        self.closing = True
        self.cleanup_gpio_buttons()
        self.game_active = False
        self.window.destroy()

    def set_snake1_direction(self, direction):
        if not self.game_active or self.menu_active or self.snake1['moved_in_frame']:
            return

        current_x, current_y = self.snake1['move_dir']
        next_x, next_y = direction
        if current_x == -next_x or current_y == -next_y:
            return

        self.snake1['moved_in_frame'] = True
        self.snake1['move_dir'] = [next_x, next_y]

    def move_snake1_left(self):
        self.set_snake1_direction((-1, 0))

    def move_snake1_right(self):
        self.set_snake1_direction((1, 0))

    def move_snake1_up(self):
        self.set_snake1_direction((0, -1))

    def move_snake1_down(self):
        self.set_snake1_direction((0, 1))

    def run_on_main_thread(self, callback):
        try:
            self.window.after(0, callback)
        except tk.TclError:
            pass

    def setup_gpio_buttons(self):
        self.gpio_buttons = {
            "up": Button(self.gpio_pins["up"], pull_up=True, bounce_time=0.05),
            "down": Button(self.gpio_pins["down"], pull_up=True, bounce_time=0.05),
            "left": Button(self.gpio_pins["left"], pull_up=True, bounce_time=0.05),
            "right": Button(self.gpio_pins["right"], pull_up=True, bounce_time=0.05),
            "quit": Button(self.gpio_pins["quit"], pull_up=True, bounce_time=0.05),
        }

        self.gpio_buttons["up"].when_pressed = lambda: self.run_on_main_thread(self.move_snake1_up)
        self.gpio_buttons["down"].when_pressed = lambda: self.run_on_main_thread(self.move_snake1_down)
        self.gpio_buttons["left"].when_pressed = lambda: self.run_on_main_thread(self.move_snake1_left)
        self.gpio_buttons["right"].when_pressed = lambda: self.run_on_main_thread(self.move_snake1_right)
        self.gpio_buttons["quit"].when_pressed = lambda: self.run_on_main_thread(self.close_app)
    
    def reset_snake(self, player_num):
        self.lives -= 1
        
        if self.lives <= 0:
            self.game_active = False
            self.show_game_over()
            return
        
        top_offset = self.info_height // self.snake_scale
        
        if player_num == 1:
            self.snake1['coords'] = [self.grid_width // 2, top_offset + self.grid_height // 2]
            self.snake1['tail'] = []
            self.snake1['move_dir'] = [1, 0]
        else:
            self.snake2['coords'] = [self.grid_width // 2 - 5, top_offset + self.grid_height // 2]
            self.snake2['tail'] = []
            self.snake2['move_dir'] = [1, 0]
    
    def toggle_two_player(self, event=None):
        self.two_player_mode = not self.two_player_mode
        
        if self.two_player_mode:
            top_offset = self.info_height // self.snake_scale
            self.snake2['coords'] = [self.grid_width // 2 - 5, top_offset + self.grid_height // 2]
            self.snake2['tail'] = []
            self.snake2['move_dir'] = [1, 0]
    
    def handle_snake1_keys(self, event):
        if event.keysym == "Left":
            self.move_snake1_left()
        elif event.keysym == "Right":
            self.move_snake1_right()
        elif event.keysym == "Up":
            self.move_snake1_up()
        elif event.keysym == "Down":
            self.move_snake1_down()
    
    def handle_snake2_keys(self, event):
        if not self.two_player_mode:
            return
            
        if not self.snake2['moved_in_frame']:
            self.snake2['moved_in_frame'] = True
            
            # WASD keys for player 2
            if event.keysym == "a" and self.snake2['move_dir'][0] != 1:
                self.snake2['move_dir'] = [-1, 0]
            elif event.keysym == "d" and self.snake2['move_dir'][0] != -1:
                self.snake2['move_dir'] = [1, 0]
            elif event.keysym == "w" and self.snake2['move_dir'][1] != 1:
                self.snake2['move_dir'] = [0, -1]
            elif event.keysym == "s" and self.snake2['move_dir'][1] != -1:
                self.snake2['move_dir'] = [0, 1]
            else:
                self.snake2['moved_in_frame'] = False
    
    def handle_special_keys(self, event):
        if event.keysym in ("t", "T"):
            self.toggle_two_player()
    
    def draw_info_panel(self):
        # Create info panel at the top
        info_panel_height = self.info_height
        self.canvas.create_rectangle(0, 0, self.win_x, info_panel_height, fill="#333333", outline="#444444")
        
        # Display score and lives in the info panel
        if self.two_player_mode:
            self.canvas.create_text(70, 25, text=f"P1 Score: {self.score_p1}", fill="#00ff00", font=("Arial", 14))
            self.canvas.create_text(200, 25, text=f"P2 Score: {self.score_p2}", fill="#0000ff", font=("Arial", 14))
            self.canvas.create_text(70, 55, text=f"Lives: {self.lives}", fill="white", font=("Arial", 14))
        else:
            self.canvas.create_text(70, 25, text=f"Score: {self.score}", fill="white", font=("Arial", 14))
            self.canvas.create_text(70, 55, text=f"Lives: {self.lives}", fill="white", font=("Arial", 14))
        
        # Display game mode and controls in the info panel
        mode_text = "Two Player Mode" if self.two_player_mode else "One Player Mode"
        mode_color = "yellow" if self.two_player_mode else "green"
        self.canvas.create_text(self.win_x // 2, 25, text=mode_text, fill=mode_color, font=("Arial", 14))
        
        # Display ESC hint
        self.canvas.create_text(self.win_x - 100, 25, text="ESC for Menu", fill="white", font=("Arial", 12))
        
        # Display controls reminder
        controls_text = "P1: Arrows/GPIO | P2: WASD" if self.two_player_mode else "Controls: Arrows/GPIO"
        self.canvas.create_text(self.win_x - 100, 55, text=controls_text, fill="white", font=("Arial", 12))
    
    def handle_snake_movement(self, snake, is_player1):
        # Add the current head position to the tail
        snake['tail'].append([snake['coords'][0], snake['coords'][1]])
        
        # Move the snake
        snake['coords'][0] += snake['move_dir'][0]
        snake['coords'][1] += snake['move_dir'][1]
        
        # Check for wall collision
        for wall in self.wall_coords:
            if snake['coords'][0] == wall[0] and snake['coords'][1] == wall[1]:
                self.reset_snake(1 if is_player1 else 2)
                return True
        
        # Check for wrapping (if not hitting walls)
        top_offset = self.info_height // self.snake_scale
        if snake['coords'][0] == self.grid_width:
            snake['coords'][0] = 0
        elif snake['coords'][0] == -1:
            snake['coords'][0] = self.grid_width - 1
        elif snake['coords'][1] == top_offset + self.grid_height:
            snake['coords'][1] = top_offset
        elif snake['coords'][1] == top_offset - 1:
            snake['coords'][1] = top_offset + self.grid_height - 1
        
        # Reset moved in frame flag
        snake['moved_in_frame'] = False
        
        # Check for head-tail collision
        for segment in snake['tail']:
            if segment[0] == snake['coords'][0] and segment[1] == snake['coords'][1]:
                self.reset_snake(1 if is_player1 else 2)
                return True
            self.create_grid_item(segment, snake['color'])
        
        return False
    
    def check_snake_collisions(self):
        # Check for collision between snake 1 and snake 2
        if self.two_player_mode:
            # Head-to-head collision
            if self.snake1['coords'] == self.snake2['coords']:
                self.reset_snake(1)
                self.reset_snake(2)
                return True
            
            # Snake 1 hitting snake 2's body
            for segment in self.snake2['tail']:
                if self.snake1['coords'][0] == segment[0] and self.snake1['coords'][1] == segment[1]:
                    self.reset_snake(1)
                    return True
            
            # Snake 2 hitting snake 1's body
            for segment in self.snake1['tail']:
                if self.snake2['coords'][0] == segment[0] and self.snake2['coords'][1] == segment[1]:
                    self.reset_snake(2)
                    return True
        
        return False
    
    def check_apple_collisions(self):
        # Check if an apple was eaten by player 1
        if self.apple_coords == self.snake1['coords']:
            self.apple_coords = self.generate_apple_coords()
            if self.two_player_mode:
                self.score_p1 += 1
            else:
                self.score += 1
                
            # Don't remove tail segment for player 1 (snake grows)
            if self.two_player_mode:
                # Still remove tail segment for player 2 (no growth)
                if self.snake2['tail']:
                    self.snake2['tail'].pop(0)
            return True
            
        # Check if an apple was eaten by player 2
        elif self.two_player_mode and self.apple_coords == self.snake2['coords']:
            self.apple_coords = self.generate_apple_coords()
            self.score_p2 += 1
            
            # Don't remove tail segment for player 2 (snake grows)
            # Still remove tail segment for player 1 (no growth)
            if self.snake1['tail']:
                self.snake1['tail'].pop(0)
            return True
            
        else:
            # Remove tail segment if no apple was eaten
            if self.snake1['tail']:
                self.snake1['tail'].pop(0)
            if self.two_player_mode and self.snake2['tail']:
                self.snake2['tail'].pop(0)
            return False
    
    def game_loop(self):
        # Schedule next frame
        self.window.after(1000 // self.frames_per_second, self.game_loop)
        
        # Skip if in menu or game not active
        if self.menu_active or not self.game_active:
            return

        # Clear canvas and set background
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, self.win_x, self.win_y, fill="#222222", outline="#222222")
        
        # Draw info panel
        self.draw_info_panel()
        
        # Draw walls
        self.draw_walls()
        
        # Handle snake 1 movement
        self.handle_snake_movement(self.snake1, True)
        
        # Handle snake 2 movement if in two-player mode
        if self.two_player_mode:
            self.handle_snake_movement(self.snake2, False)
        
        # Check for collisions between snakes
        self.check_snake_collisions()
        
        # Display apple
        self.create_grid_item(self.apple_coords, "#ff0000")
        
        # Check for apple collisions
        self.check_apple_collisions()
    
    def setup_key_bindings(self):
        self.window.bind("<KeyPress>", self.handle_snake1_keys)
        self.window.bind("<KeyPress>", self.handle_snake2_keys, add="+")
        self.window.bind("<KeyPress>", self.return_to_menu, add="+")
        self.window.bind("<KeyPress>", self.handle_special_keys, add="+")
        self.window.bind("<Button-1>", self.handle_menu_click)
    
    def start(self):
        try:
            self.game_loop()
            self.window.mainloop()
        finally:
            self.cleanup_gpio_buttons()

# Create and start the game
if __name__ == "__main__":
    game = SnakeGame()
    game.start()