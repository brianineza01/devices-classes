Todo for task3:
[ ] use BMP-280 to collect temperature and pressure data Not implemented. task3.py only loads tabular data from CSV and has no BMP-280 sensor code, no hardware library imports, and no live sensor reading logic.

[x] displaying data on a chart/charts Implemented. The app draws charts with Matplotlib/Seaborn and supports multiple chart types in update_chart().

[ ] all descriptions on the interface should be configurable in the JSON configuration file Not implemented. Only chart title and axis labels come from JSON; the rest of the UI text is hardcoded, such as window title, button text, and status labels.

[ ] ability to load axis descriptions, units, chart title, and data from a JSON file Not fully implemented. Axis descriptions and chart title: present. Units: missing. Data from JSON: missing. Overall this requirement should be marked missing because it asks for all of those capabilities together.

[ ] add grid on/off button Not implemented. There is no grid toggle control and no grid enable/disable logic.

[ ] add buttons to move a marker in the chart Not implemented as required. There are prev_marker() and next_marker() methods, but no actual GUI buttons wired to them, and they do not move a marker on the existing chart.

[ ] display marker coordinates Not implemented as a UI feature. Coordinates are only drawn as an annotation in a separate figure in update_marker(), not displayed in the interface as current marker coordinates.

[ ] display marker coordinates on a chart next to the marker Not properly implemented. scatter mode annotates all points, not a selected movable marker, and update_marker() shows a separate figure instead of updating the main chart.

[ ] button - save data to a CSV file Not implemented. There is no save/export button and no CSV write logic
