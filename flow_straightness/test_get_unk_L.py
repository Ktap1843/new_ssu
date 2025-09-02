import numpy as np
import matplotlib.pyplot as plt

def L(beta):
    return 133.46 * beta**2 - 16.95 * beta + 67.81

def plot_L(beta_min=0.22, beta_max=0.81, points=200):
    betas = np.linspace(beta_min, beta_max, points)
    values = L(betas)
    plt.figure(figsize=(8, 5))
    plt.plot(betas, values, linewidth=2)
    plt.xlabel('β')
    plt.ylabel('L(β)')
    plt.title(f'График L(β) для β ∈ [{beta_min}, {beta_max}]')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    plot_L()
