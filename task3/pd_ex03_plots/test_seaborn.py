import seaborn as sns
import matplotlib.pyplot as plt

sns.set(style="darkgrid")
df = sns.load_dataset("iris")
sns

sns.histplot(data=df, x="sepal_length")
plt.show()