import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

class CSVChartApp:
    def __init__(self):
        # Load configuration
        self.load_config("config.json")
        
        # Initialize variables
        self.data = None
        self.marker_index = 0
        self.chart_type = "line"
        
    def load_config(self, config_file):
        with open(config_file) as f:
            self.config = json.load(f)
        
    def load_csv(self, file_path):
        # Load and process CSV data
        self.data = pd.read_csv(file_path)
        self.update_chart()
        
    def update_chart(self):
        plt.figure(figsize=(8, 6))
        
        if self.data is not None:
            x = self.data.iloc[:, 0]
            y = self.data.iloc[:, 1]
            
            if self.chart_type == "line":
                sns.lineplot(x=x, y=y)
            elif self.chart_type == "bar":
                sns.barplot(x=x, y=y)
            elif self.chart_type == "scatter":
                sns.scatterplot(x=x, y=y)
            elif self.chart_type == "step":
                plt.step(x, y)
            elif self.chart_type == "stem":
                plt.stem(x, y)
            
            plt.title(self.config["titles"]["chart"])
            plt.xlabel(self.config["labels"]["x_axis"])
            plt.ylabel(self.config["labels"]["y_axis"])
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

if __name__ == "__main__":
    app = CSVChartApp()
    app.load_csv("data.csv")  # Replace with your CSV file path
    app.chart_type = "line"   # Set the chart type
    app.update_chart()
