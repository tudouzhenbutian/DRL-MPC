from casadi import *
import numpy as np
import time


line_width = 1.5
fontsize_labels = 12
import socket
# create socket object
import pickle

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind IP and port
server_socket.bind(('127.0.0.1', 8000))

#  accept client connections
server_socket.listen()

# accept client connections
client_socket, address = server_socket.accept()
print(f"Connection from {address} has been established.")

# updates the state and control sequence based on a given system dynamics
def shift(T, t0, x0, u, f, out, st_prev):
    st = x0
    print("================================", st)
    out_put = out(st)
    print("!!!!!!!!!!", out_put)
    con = u[:, 0].reshape(-1, 1)
    print("cccccccccccccccccccccooooooooooooooooooonnnnnnnnnnnnnnn", con)
    f_value = f(st, con)
    f_value[0] = out_put[0]
    f_value[1] = out_put[1]
    st_ground = st_prev + T * f_value
    print("=+++____________________________", f_value)
    x0 = np.array(st_ground.full())
    t0 = t0 + T
    # u0 = np.concatenate((u[1:,:], u[-1,:].reshape(1,-1)), axis=0).reshape(10,2)
    u0 = np.concatenate((u[1:, :], np.tile(u[-1, :], (1, 1))), axis=0)
    return t0, x0, u0



# parameters
T = 1;  # [s] sampling interval
N = 10;  # prediction horizon
a = 10;  # a is the parameter in ellipse area
w_lane = 5.25;  # the width of the lane
l_vehicle = 2;  # length of vehicle
w_vehicle = 2;  # width of vehicle

# states
Vx = SX.sym('Vx');
Vy = SX.sym('Vy');
x = SX.sym('x');
y = SX.sym('y');
theta = SX.sym('theta')
vtheta = SX.sym('vtheta')
states = vertcat(x, y, Vx, Vy, theta, vtheta)
n_states = states.numel()

# control
ax = SX.sym('ax');
delta = SX.sym('delta');
controls = vertcat(ax, delta)
n_controls = controls.numel()
print(n_controls)
# system
# rhs = vertcat(Vx, Vy, ax, ay)
caf = 1;
car = 1;
m = 26;
lf = 2;
lr = 2;
Iz = 10000;
g = 1;
h = 1;
vxtemp = 1

a1 = -(2 * caf + 2 * car) / (m * vxtemp)
a2 = -vxtemp - (2 * caf * lf - 2 * car * lr) / (m * vxtemp)
a3 = -(2 * caf * lf + 2 * car * lr) / (Iz * vxtemp)
a4 = -(2 * caf * lf * lf + 2 * car * lr * lr) / (Iz * vxtemp)
print("VX!!!!!!!!!!!", a1, a2, a3, a4)
b1 = 2 * caf / m
b2 = 2 * lf * caf / Iz

AA = np.array([[0, 0, 1, 0, 0, 0],
               [0, 0, 0, 1, 0, 0],
               [0, 0, 0, 0, 0, 0],
               [0, 0, 0, a1, 0, a2],
               [0, 0, 0, 0, 0, 1],
               [0, 0, 0, a3, 0, a4]])

BB = np.array([[0, 0],
               [0, 0],
               [1, 0],
               [0, b1],
               [0, 0],
               [0, b2]])

cos_val = casadi.cos(states[4])
sin_val = casadi.sin(states[4])

CC = casadi.vertcat(casadi.horzcat(cos_val, sin_val),
                    casadi.horzcat(-sin_val, cos_val))
CC_np = casadi.DM(CC).full()
# CC= np.array([[1,2],[22,3]])
print(states[4])


rhs = AA @ states + BB @ controls
output = CC @ casadi.vertcat(states[2], states[3])
print("%%%%%", output)

f = Function('f', [states, controls], [rhs])
out = Function('out', [states], [output])

U = SX.sym('U', n_controls, N)  # Decision variable (control input)
P = SX.sym('P', n_states + N * (n_states + n_controls))  # parameters (including initial state and reference state along predicted trajectory and reference control input)
X = SX.sym('X', n_states, N + 1)  # state variables (trajectories)

##cost function
# Q weight matrix
Q = np.zeros((6, 6))
Q[0, 0] = 1  # x-direction position weight
Q[1, 1] = 5  # y-direction position weight
Q[2, 2] = 100  # x-direction velocity weight
Q[3, 3] = 1  # Velocity weight in y direction
Q[4, 4] = 1 # ego vehicle corner weight
Q[5, 5] = 1 # ego vehicle angular velocity weight
# R weight matrix
R = np.zeros((2, 2))
R[0, 0] = 1  # Acceleration in the x direction weight
R[1, 1] = 0.1  # front wheel weight

obj = 0  # cost fuction
g = []  # constraint vector
st = X[:, 0]  # initial state

g = vertcat(g, st - P[0:6])  # initial condition constraint

for k in range(N):
    st = X[:, k]

    con = U[:, k]
    P1 = P
    P2 = P[8 * (k + 1) - 2]
    obj = obj + (st - P[8 * (k + 1) - 2:8 * (k + 1) + 4]).T @ Q @ (st - P[8 * (k + 1) - 2:8 * (k + 1) + 4]) + (
                con - P[8 * (k + 1) + 5:8 * (k + 1) + 6]).T @ R @ (
                      con - P[8 * (k + 1) + 5:8 * (k + 1) + 6])  # cost function


    ini_next = X[:, k + 1]
    f_value = f(st, con)
    ini_next_euler = st + (T * f_value)
    g = vertcat(g, ini_next - ini_next_euler)  # constraints

tempg = g


# constrains
Vx_min = -1  # m/s
Vx_max = 1  # m/s
Vy_min = -2  # m/s
Vy_max = 2  # m/s
x_min = float('-inf')
x_max = float('inf')
y_min = -30
y_max = 300  ##ymax limity
theta_min = -3.14
theta_max = 3.14
vtheta_min = -1.57
vtheta_max = 1.57

ax_min = -9
ax_max = 6
delta_min = -1.54/4
delta_max = 1.57/4

args = {}
args['lbg'] = [0] * 6 * (N + 1)  # Equality constraints
args['ubg'] = [0] * 6 * (N + 1)  # Equality constraints

# with obstacle
args['lbg'][6 * (N + 1):6 * (N + 1) + (N + 1)] = np.full((N + 1,), -np.inf)  # inequality constraints
args['ubg'][6 * (N + 1):6 * (N + 1) + (N + 1)] = np.zeros((N + 1,))  # inequality constraints

###################################

args['lbx'] = np.zeros((86, 1))  # state lower bound
args['ubx'] = np.zeros((86, 1))  # state upper bound

args['lbx'][0:6 * (N + 1):6, 0] = np.tile(x_min, (N + 1,))
args['ubx'][0:6 * (N + 1):6, 0] = np.tile(x_max, (N + 1,))
args['lbx'][1:6 * (N + 1):6, 0] = np.tile(y_min, (N + 1,))
args['ubx'][1:6 * (N + 1):6, 0] = np.tile(y_max, (N + 1,))
args['lbx'][2:6 * (N + 1):6, 0] = np.tile(Vx_min, (N + 1,))
args['ubx'][2:6 * (N + 1):6, 0] = np.tile(Vx_max, (N + 1,))
args['lbx'][3:6 * (N + 1):6, 0] = np.tile(Vy_min, (N + 1,))
args['ubx'][3:6 * (N + 1):6, 0] = np.tile(Vy_max, (N + 1,))
args['lbx'][4:6 * (N + 1):6, 0] = np.tile(theta_min, (N + 1,))
args['ubx'][4:6 * (N + 1):6, 0] = np.tile(theta_max, (N + 1,))
args['lbx'][5:6 * (N + 1):6, 0] = np.tile(vtheta_min, (N + 1,))
args['ubx'][5:6 * (N + 1):6, 0] = np.tile(vtheta_max, (N + 1,))

args['lbx'][6 * (N + 1) + 0:6 * (N + 1) + 2 * N:2, 0] = ax_min
args['ubx'][6 * (N + 1) + 0:6 * (N + 1) + 2 * N:2, 0] = ax_max
args['lbx'][6 * (N + 1) + 1:6 * (N + 1) + 2 * N:2, 0] = delta_min
args['ubx'][6 * (N + 1) + 1:6 * (N + 1) + 2 * N:2, 0] = delta_max
args['p'] = np.zeros((86, 1))


# Start MPC#
# ------------ initial values -------------------------
t0 = 0
x0 = np.array([0, 0, Vx_min, 0, 0, 0]).reshape(-1, 1)  # initial condition

# x0 = [0, w_lane/2, 20, 0]  # initial condition
xs = np.array([np.inf, 0, 20, 0]).reshape(-1, 1)  # reference states
xx = np.zeros((6, 2000))

xx[:,0:1] = x0
t = np.zeros(10000)

u0 = np.zeros((N, 2))  # two control inputs for each robot
X0 = np.tile(x0, (N + 1, 1)).reshape(11, 6)  # initialization of the states decision variables
sim_tim = 500

mpciter = 0
xx1 = np.empty((N + 1, 6, 2000))
u_cl = np.zeros((1, 2))

loop_start = time.time()

Vx_ref = 20
##########################################################################################

# ayref=[0.17610621, -1.0259259, -1.0807766, 0.7279068, 0.9102347, -0.5576487, -0.06529927, 0.5074239, 0.38864934, 1.0016279, -0.0042643547, 0.50953245, -0.5803425, -0.37296295, -0.31276894, 0.81512964, -0.37250692, 0.42198947, 0.24178913]
# sim_tim = np.size(ayref)
Vx_ref = 20
obs_x = 50
obs_y = 50
diam_safe = 10  # safty distance
x_prev = np.array([0, 0, 0, 0, 0, 0]).reshape(-1, 1)

while mpciter < sim_tim / T:  # condition for ending the loop
    # PPO refrence controller
    # Add constraints for collision avoidance
    g = tempg
    obs_y = obs_y - 0.2
    print("############", obs_x)
    for k in range(N + 1):
        g = vertcat(g, -np.sqrt(((X[0, k] - obs_x) ** 2) / (7 ** 2) + ((X[1, k] - obs_y) ** 2) / (4 ** 2)) + 1.05)  # Consider ellipse area
    # parameter preparation
    # make the decision variables one column vector
    OPT_variables = vertcat(reshape(X, (6 * (N + 1), 1)), reshape(U, (2 * N, 1)))


    nlp_prob = {'f': obj, 'x': OPT_variables, 'g': g, 'p': P}

    opts = {}
    opts['ipopt.max_iter'] = 2000
    opts['ipopt.print_level'] = 0
    opts['print_time'] = 0
    opts['ipopt.acceptable_tol'] = 1e-8
    opts['ipopt.acceptable_obj_change_tol'] = 1e-6

    solver = nlpsol('solver', 'ipopt', nlp_prob, opts)
    # Entrance
    data_str = client_socket.recv(1024)

    # deserialized data
    data = pickle.loads(data_str)
    # operate on the data
    result = [num for num in data]
    print(f"Received data: {data}, Result: {result}")
    aref = result[0]
    deltaref = result[1]
    print("deltaref!!!!!!!!!!!!!!!", deltaref)



    print(mpciter, sim_tim / T)
    current_time = mpciter * T  # get the current time
    # print(mpciter,"!!!!!!!!!!")
    args['p'][0:6] = np.array(x0)[:, 0].reshape(-1, 1)  # initial condition of the vehicle np.tile(x_min, (N+1,))
    # tempay=0
    # Vy_ref = 0

    for k in range(1, N + 1):  # set the reference to track

        t_predict = current_time + (k - 1) * T  # predicted time instant
        # the reference is time varying

        if xx[0, mpciter] + xx[2, mpciter]*(k)*T < 50:  # Lane keeping  ####################xx[0, mpciter]==0
            x_ref = 20 * t_predict
            y_ref = 0 * w_lane
            Vx_ref = 2
            Vy_ref = 0
            ax_ref = 0
            delta_ref = 0
            theta_ref = 0
            vtheta_ref = 0

        elif xx[0, mpciter + 1] + xx[2, mpciter + 1] * (
        k) * T < 500:  # Lane keeping  ####################xx[0, mpciter]==0
            x_ref = 50
            y_ref = 4 * t_predict
            Vx_ref = 0
            Vy_ref = 0
            ax_ref = aref
            delta_ref = deltaref
            theta_ref = 0
            vtheta_ref = 0

        args['p'][8 * (k) - 2:8 * (k) + 4] = np.array([x_ref, y_ref, Vx_ref, Vy_ref, theta_ref, vtheta_ref]).reshape(6,
                                                                                                                     1)  # args['p']少了4维
        args['p'][8 * k + 4:8 * k + 6] = np.array([ax_ref, delta_ref]).reshape(2, 1)

        # intial value of the optimization variables
    args['x0'] = np.vstack((X0.T.reshape(6 * (N + 1), 1), u0.T.reshape(2 * N, 1)))
    sol = solver(x0=args['x0'], lbx=args['lbx'], ubx=args['ubx'], lbg=args['lbg'], ubg=args['ubg'], p=args['p'])

    u = np.reshape(sol['x'][6 * (N + 1):], (N, 2))

    xx1[:, :, mpciter + 1] = np.reshape(sol['x'][:6 * (N + 1)], (N + 1, 6))  # get solution TRAJECTORY
    u_cl = np.vstack((u_cl, u[0]))  # append the first control to the control list

    print("ucl:axchoose,deltachoose.."
          "###########################", u_cl)
    print("XXXXXXXXXXXXXXXXXX"
          "###########################", u_cl[:, 0].tolist())
    print("YYYYYYYYYYYYYYY"
          "###########################", u_cl[:, 1].tolist())
    t[mpciter + 1] = t0

    # Apply the control and shift the solution

    t0, x0, u0 = shift(T, t0, x0, u.T, f, out, x_prev)
    print("ground::::::::::::::::::", x0)

    # exit, send x0 to PPO
    data = x0  # Pack two numbers into a list
    data_str = pickle.dumps(data)  # Serialize data into byte stream
    client_socket.send(data_str)


    x_prev = x0
    vxtemp = x0[2]

    xx[:, mpciter + 1: mpciter + 2] = x0
    # print(np.array(xx).shape)
    X0 = np.reshape(sol['x'][0:6 * (N + 1)], (N + 1, 6))  # get solution TRAJECTORY
    # print("111" ,X0)
    X0 = np.vstack((X0[1:], X0[-1]))  # shift trajectory to initialize the next step
    # print("222",X0[-1])
    mpciter += 1

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle, Ellipse


class DynamicPlot:
    def __init__(self):
        self.fig, self.ax = plt.subplots()
        self.x_r_1 = []
        self.y_r_1 = []
        self.line, = self.ax.plot([], [], '-r', linewidth=1.2)
        self.obstacle = Ellipse(xy=(50, 0), width=9, height=3.5, edgecolor='r', fc='red')
        self.obstacle1 = Ellipse(xy=(80, 0), width=9, height=4, edgecolor='r', fc='purple')
        self.vehicle = Rectangle((0, 0), 0, 0, linewidth=1.05, edgecolor='b', facecolor='blue')
        self.ax.add_patch(self.obstacle)
        self.ax.add_patch(self.vehicle)
        self.ax.set_xlim(-1, 200)
        self.ax.set_ylim(-10, 10)

    def __call__(self, k):
        self.ax.clear()
        self.ax.plot([0, 100], [0, 0], '--g', linewidth=1.2)
        self.ax.plot([0, 100], [10, 10], '-b', linewidth=1.2)
        self.ax.plot([0, 100], [-10, -10], '-b', linewidth=1.2)
        self.ax.plot([50, 50], [-50, 50], '--g', linewidth=1.2)
        self.ax.plot([40, 40], [-50, 50], '-b', linewidth=1.2)
        self.ax.plot([60, 60], [-50, 50], '-b', linewidth=1.2)

        x1 = xx[0, k]
        y1 = xx[1, k]
        self.x_r_1.append(x1)
        self.y_r_1.append(y1)
        self.line.set_data(self.x_r_1, self.y_r_1)

        if k < xx.shape[1] - 1:
            self.ax.plot(xx1[0:N, 0, k], xx1[0:N, 1, k], 'r--*')

            # Store the x and y coordinates of the last star marker
            last_star_x = xx1[0:N, 0, k][-1]
            last_star_y = xx1[0:N, 1, k][-1]

            # Plot the trajectory of the last star marker
            self.ax.plot(self.x_r_1, self.y_r_1, '-k', linewidth=1.0)

        self.ax.set_title(f'$N={N},a={a}$', fontsize=fontsize_labels)
        self.ax.set_ylabel('$y$(m)', fontsize=fontsize_labels)
        self.ax.set_xlabel('$x$(m)', fontsize=fontsize_labels)

        self.obstacle.set_center((50, 50 - 0.2*k))  # Update the center position of the ellipse

        self.ax.add_patch(self.obstacle)
        self.ax.add_patch(self.obstacle1)
        self.ax.add_patch(self.vehicle)
        self.vehicle.set_xy((x1 - l_vehicle / 2, y1 - w_vehicle / 2))
        self.vehicle.set_width(l_vehicle)
        self.vehicle.set_height(w_vehicle)

        return self.line, self.obstacle, self.vehicle

    def start_animation(self):
        ani = FuncAnimation(self.fig, self, frames=range(xx.shape[1]), interval=200)
        plt.show()


# Create an instance object of the DynamicPlot class
dp = DynamicPlot()

# Start the animation of the dynamic graph
dp.start_animation()
