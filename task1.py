import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from tkinter import filedialog, ttk
import tkinter as tk

# Global variables at the top of the file
CHART_TYPES = ["line", "bar", "scatter", "step", "stem"]
DEFAULT_CHART_TYPE = "line"

class CSVChartApp:
    def __init__(self):
        # Create main window first
        self.root = tk.Tk()
        self.root.title("CSV Chart Viewer")
        
        # Initialize variables (after creating root window)
        self.data = None
        self.marker_index = 0
        self.chart_type_var = tk.StringVar(self.root)
        self.chart_type_var.set(DEFAULT_CHART_TYPE)
        self.chart_type = DEFAULT_CHART_TYPE
        self.csv_path = None
        self.config_path = None
        
        # Create file selection frame
        file_frame = tk.Frame(self.root)
        file_frame.pack(pady=5, padx=10, fill='x')
        
        # CSV selection
        csv_frame = tk.Frame(file_frame)
        csv_frame.pack(fill='x', pady=2)
        tk.Button(csv_frame, text="Load CSV", command=self.browse_csv).pack(side='left')
        self.csv_label = tk.Label(csv_frame, text="No CSV file selected", width=50)
        self.csv_label.pack(side='left', padx=5)
        
        # Config selection
        config_frame = tk.Frame(file_frame)
        config_frame.pack(fill='x', pady=2)
        tk.Button(config_frame, text="Load Config", command=self.browse_config).pack(side='left')
        self.config_label = tk.Label(config_frame, text="No config file selected", width=50)
        self.config_label.pack(side='left', padx=5)
        
        # Add render button
        render_frame = tk.Frame(self.root)
        render_frame.pack(pady=5, padx=10, fill='x')
        tk.Button(render_frame, text="Render Chart", command=self.update_chart).pack()
        
        # Create chart window
        self.chart_window = None
        self.chart_figure = None
        
    def browse_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            self.csv_path = file_path
            self.csv_label.config(text=f"Selected: {file_path.split('/')[-1]}")
            self.load_csv(file_path)
            
    def browse_config(self):
        config_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if config_file:
            self.config_path = config_file
            self.config_label.config(text=f"Selected: {config_file.split('/')[-1]}")
            self.load_config(config_file)
            
    def load_config(self, config_file):
        with open(config_file) as f:
            self.config = json.load(f)
        
    def load_csv(self, file_path):
        # Load and process CSV data
        self.data = pd.read_csv(file_path)
        
    def on_chart_type_change(self, event):
        self.chart_type = self.chart_type_var.get()
        self.update_chart()  # Automatically update chart when type changes
        
    def create_chart_window(self):
        # Close any existing chart window
        plt.close('all')
        
        # Create new figure
        self.chart_window = plt.figure(figsize=(8, 6))
        ax = self.chart_window.add_subplot(111)
        
        # Add chart type dropdown only once when creating the window
        chart_menu = tk.OptionMenu(
            self.chart_window.canvas.toolbar,
            self.chart_type_var,
            *CHART_TYPES,
            command=self.on_chart_type_change
        )
        chart_menu.pack(side='right', padx=5)
        return ax

    def update_chart(self):
        ax = self.create_chart_window()
        
        if self.data is not None:
            x = self.data.iloc[:, 0]
            y = self.data.iloc[:, 1]
            
            # Use self.chart_type_var.get() instead of self.chart_type
            current_chart_type = self.chart_type_var.get()
            
            if current_chart_type == "line":
                sns.lineplot(x=x, y=y, ax=ax)
                ax.scatter(x, y, color='red', s=50, zorder=5)
            elif current_chart_type == "bar":
                ax = sns.barplot(x=x, y=y, ax=ax)
                for i, bar in enumerate(ax.patches):
                    ax.text(
                        bar.get_x() + bar.get_width()/2,
                        bar.get_height(),
                        f'{y.iloc[i]:.2f}',
                        ha='center',
                        va='bottom'
                    )
            elif current_chart_type == "scatter":
                sns.scatterplot(x=x, y=y, ax=ax)
                for i, (xi, yi) in enumerate(zip(x, y)):
                    ax.annotate(
                        f'({xi}, {yi:.2f})',
                        (xi, yi),
                        xytext=(5, 5),
                        textcoords='offset points'
                    )
            elif current_chart_type == "step":
                ax.step(x, y)
                ax.scatter(x, y, color='red', s=50, zorder=5)
            elif current_chart_type == "stem":
                ax.stem(x, y)
            
            if hasattr(self, 'config'):
                ax.set_title(self.config["titles"]["chart"])
                ax.set_xlabel(self.config["labels"]["x_axis"])
                ax.set_ylabel(self.config["labels"]["y_axis"])
            
            plt.show()
        
    def prev_marker(self):
        if self.data is not None and len(self.data) > 0:
            self.marker_index = max(0, self.marker_index - 1)
            self.update_marker()
        
    def next_marker(self):
        if self.data is not None and len(self.data) > 0:
            self.marker_index = min(len(self.data) - 1, self.marker_index + 1)
            self.update_marker()
        
    def update_marker(self):
        if self.data is not None:
            plt.figure(figsize=(8, 6))
            x = self.data.iloc[self.marker_index, 0]
            y = self.data.iloc[self.marker_index, 1]
            plt.annotate(f"({x}, {y})", (x, y))
            plt.show()
            
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = CSVChartApp()
    app.run()
