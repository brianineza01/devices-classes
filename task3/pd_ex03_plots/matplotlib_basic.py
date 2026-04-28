import matplotlib.pyplot as plt

x = list(range(25))
y = [2 * i**2 + 1 for i in x]
plt.plot(y)
plt.show()

z = [-2 * i**2 + 10 for i in x]
plt.plot(x,y)
plt.scatter(x,z)
plt.show()


