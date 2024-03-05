from scipy.optimize import fsolve
import numpy as np
import matplotlib.pyplot as plt


def calculate_x_y(distances):
    # Coordinates of the fixed points
    x1, y1 = 0, 0
    x2, y2 = 0, 40
    x3, y3 = 40, 0
    x4, y4 = 40, 40

    # Distances to the new point Pi
    d1 = distances[0]
    d2 = distances[1]
    d3 = distances[2]
    d4 = distances[3]

    # Initial guess for the solution
    initial_guess = [0, 0]

    # Function representing the system of equations
    def equations(vars):        
        x, y = vars
        eq1 = (x - x1)**2 + (y - y1)**2 - d1**2
        eq2 = (x - x2)**2 + (y - y2)**2 - d2**2
        eq3 = (x - x3)**2 + (y - y3)**2 - d3**2
        eq4 = (x - x4)**2 + (y - y4)**2 - d4**2
        return [eq1, eq2]

    # Solve the system of equations
    solution = fsolve(equations, initial_guess)

    # The solution represents the coordinates (x, y) for Pi
    x_pi, y_pi = solution
    
    return (int(x_pi), int(y_pi))

def plot_solution(UEs, connections, E2N_info):
    # Vertices of the square
    x_values = [0, 0, 40, 40]  # Repeat the first point to close the square
    y_values = [0, 40, 0, 40]  # Repeat the first point to close the square
    
    c0, c1, c2, c3 = "black", "black", "black", "black"
    if 0 in E2N_info:
        c0 = "blue"
    if 1 in E2N_info:
        c1 = "red"
    if 2 in E2N_info:
        c2 = "orange"
    if 3 in E2N_info:
        c3 = "green"

    # Plotting the points
    plt.plot(x_values[0], y_values[0], marker='^', c=c0, markersize=30)
    plt.plot(x_values[1], y_values[1], marker='^', c=c1, markersize=30)
    plt.plot(x_values[2], y_values[2], marker='^', c=c2, markersize=30)
    plt.plot(x_values[3], y_values[3], marker='^', c=c3, markersize=30)

    # Adding labels to each dot
    for i, (x, y) in enumerate(zip(x_values, y_values)):
        bw, pw = 0, 0
        if i in E2N_info:
            bw = E2N_info[i]["bandwidth"]
            pw = E2N_info[i]["power"]

        plt.text(x, y, f'E2N {i}\nBW {bw}\nPW: {pw}', ha='center', va='bottom')

    for ue in UEs:
        # Calculate the position of the black dot
        new_point = calculate_x_y(distances=[i * -1 for i in ue.channel_gain])
        x_black = new_point[0]
        y_black = new_point[1]

        # Plotting the black dot
        plt.plot(x_black, y_black, marker='o', color="gray", markersize=10)  # 'ko' stands for black circle

        # plt.text(x_black, y_black, f'UE {ue.ID}', ha='center', va='bottom')

        if connections[ue.ID] == 0:
            x_E2N, y_E2N = 0, 0
            color = "blue"
        elif connections[ue.ID] == 1:
            x_E2N, y_E2N = 0, 40
            color = "red"
        elif connections[ue.ID] == 2:
            x_E2N, y_E2N = 40, 0
            color = "orange"
        elif connections[ue.ID] == 3:
            x_E2N, y_E2N = 40, 40
            color = "green"
        plt.plot([x_black, x_E2N], [y_black, y_E2N], color=color, linestyle="--")

    # Display the plot
    plt.xlabel('X-axis')
    plt.ylabel('Y-axis')
    plt.axis('equal')  # Equal scaling ensures that the square looks like a square
    plt.savefig("solution_{}_UEs.png".format(len(UEs)))