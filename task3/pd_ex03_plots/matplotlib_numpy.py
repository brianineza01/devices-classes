import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.plot(x, y, label='Sine Wave')
plt.xlabel('X Axis')
plt.ylabel('Y Axis')
plt.title('Sine wave')
plt.legend()

plt.figure()
data = np.random.normal(10000,2500,2000)
plt.hist(data,50)

plt.show()