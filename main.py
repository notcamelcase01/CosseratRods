"""
ONLY LINEAR ELEMENTS
main.py works using quaternions for rotation interpolations,
refer to nyu and test for other methods to interpolate rotations
"""
import numpy as np
import solver1d as sol
import matplotlib.pyplot as plt
import slerp as slerpsol
from AnimationController import ControlledAnimation
import scienceplots

plt.style.use(['science', 'high-vis'])
np.set_printoptions(linewidth=250)

"""
Set Finite Element Parameters
"""
DIMENSIONS = 1
DOF = 6

MAX_ITER = 100  # Max newton raphson iteration
element_type = 2
L = 1
numberOfElements = 20

icon, node_data = sol.get_connectivity_matrix(numberOfElements, L, element_type)
numberOfNodes = len(node_data)
ngpt = 1
wgp, gp = sol.init_gauss_points(ngpt)
u = np.zeros((numberOfNodes * DOF, 1))
du = np.zeros((numberOfNodes * DOF, 1))
nodesPerElement = element_type ** DIMENSIONS

"""
SET MATERIAL PROPERTIES
-----------------------------------------------------------------------------------------------------------------------
"""
E0 = 10 ** 8
G0 = E0 / 2.0
d = 1 / 1000 * 25.0
A = np.pi * d ** 2 * 0.25
i0 = np.pi * d ** 4 / 64
J = i0 * 2
EI = 3.5 * 10 ** 7
GA = 1.6 * 10 ** 8
ElasticityExtension = np.array([[G0 * A, 0, 0],
                                [0, G0 * A, 0],
                                [0, 0, E0 * A]])
ElasticityBending = np.array([[E0 * i0, 0, 0],
                              [0, E0 * i0, 0],
                              [0, 0, G0 * J]])

# ElasticityExtension = np.array([[GA, 0, 0],
#                                 [0, GA, 0],
#                                 [0, 0, 2 * GA]])
# ElasticityBending = np.array([[EI, 0, 0],
#                               [0, EI, 0],
#                               [0, 0, 0.5 * EI]])

"""
Starting point
"""
Elasticity = np.zeros((6, 6))
Elasticity[0: 3, 0: 3] = ElasticityExtension
Elasticity[3: 6, 3: 6] = ElasticityBending
# Elasticity = np.eye(6)
# Elasticity[2, 2] = 10
# Elasticity[5, 5] = 10

"""
Markers
"""
vi = np.array([i for i in range(numberOfNodes)])
vii = np.array([i for i in range(numberOfNodes) if i & 1 == 0])

"""
Starting point
"""
residue_norm = 0
increments_norm = 0
u *= 0
u[6 * vi + 2, 0] = node_data
u[6 * vi + 4, 0] = 0
# Thetas are zero

r1 = np.zeros(numberOfNodes)
r2 = np.zeros(numberOfNodes)
r3 = np.zeros(numberOfNodes)
for i in range(numberOfNodes):
    r1[i] = u[DOF * i][0]
    r2[i] = u[DOF * i + 1][0]
    r3[i] = u[DOF * i + 2][0]

"""
Initialize Graph
"""
fig, (ax, ay) = plt.subplots(1, 2, figsize=(16, 5), width_ratios=[1, 2])
ax.set_xlim(0, L)
ax.plot(r3, r2, label="un-deformed", marker="o")

"""
Set load and load steps
"""
# max_load = 2 * np.pi * E0 * i0 / L
max_load = 30 * E0 * i0
LOAD_INCREMENTS = 101  # Follower load usually needs larger steps compared to dead or pure bending
fapp__ = -np.linspace(0, max_load, LOAD_INCREMENTS)

"""
Main loop
"""


def fea(load_iter_, is_halt=False):
    """
        :param load_iter_: Load index
        :param is_halt: signals animator if user requested a pause
        :return: use input , True if user want to stop animation
        """
    global u
    global du
    global residue_norm
    global increments_norm
    print("--------------------------------------------------------------------------------------------------------------------------------------------------",
          fapp__[load_iter_], load_iter_)
    for iter_ in range(MAX_ITER):
        KG, FG = sol.init_stiffness_force(numberOfNodes, DOF)
        # Follower load
        s = sol.get_rotation_from_theta_tensor(u[-3:, 0]) @ np.array([0, fapp__[load_iter_], 0])[:, None]
        FG[-6:-3] = s
        # Pure Bending
        # FG[-3, 0] = -fapp__[load_iter_]
        for elm in range(numberOfElements):
            n = icon[elm][1:]
            xloc = node_data[n][:, None]
            rloc = np.array([u[6 * n, 0], u[6 * n + 1, 0], u[6 * n + 2, 0]])
            tloc = np.array([u[6 * n + 3, 0], u[6 * n + 4, 0], u[6 * n + 5, 0]])
            kloc, floc = sol.init_stiffness_force(nodesPerElement, DOF)
            q1 = slerpsol.rotation_vector_to_quaterion(tloc[:, 0].reshape(3, ))
            q2 = slerpsol.rotation_vector_to_quaterion(tloc[:, 1].reshape(3, ))

            gloc = np.zeros((6, 1))
            for xgp in range(len(wgp)):
                N_, Bmat = sol.get_lagrange_fn(gp[xgp], element_type)
                Jac = (xloc.T @ Bmat)[0][0]
                Nx_ = 1 / Jac * Bmat
                rds = rloc @ Nx_
                qh = slerpsol.slerp(q1, q2, N_)
                dqh = slerpsol.diff_slerp(q1, q2, Nx_, N_)

                Rot = slerpsol.get_rot_from_q(qh)
                # This is used to get kappa, and method is taken from Darboux, G. [1972]). Also available in literature of multi-body dynamics
                k = 2 * np.array([[-qh[1], qh[0], qh[3], qh[2]],
                                  [-qh[2], qh[3], qh[0], -qh[1]],
                                  [-qh[3], -qh[2], qh[1], qh[0]]]) @ dqh[:, None]
                v = Rot.T @ rds

                gloc[0: 3] = Rot @ ElasticityExtension @ (v - np.array([0, 0, 1])[:, None])
                gloc[3: 6] = Rot @ ElasticityBending @ k
                pi = sol.get_pi(Rot)

                n_tensor = sol.skew(gloc[0: 3])
                m_tensor = sol.skew(gloc[3: 6])
                tangent, res = sol.get_tangent_stiffness_residue(n_tensor, m_tensor, N_, Nx_, DOF, pi, Elasticity,
                                                                 sol.skew(rds), gloc, None)
                floc += res * wgp[xgp] * Jac
                kloc += tangent * wgp[xgp] * Jac

            iv = np.array(sol.get_assembly_vector(DOF, n))

            FG[iv[:, None], 0] += floc
            KG[iv[:, None], iv] += kloc

        # TODO: Make a generalized function for application of point as well as body loads
        f = np.zeros((6, 6))
        f[0: 3, 3: 6] = -sol.skew(s)
        KG[-6:, -6:] += f
        for ibc in range(6):
            sol.impose_boundary_condition(KG, FG, ibc, 0)
        du = -sol.get_displacement_vector(KG, FG)
        residue_norm = np.linalg.norm(FG)

        increments_norm = np.linalg.norm(du)
        if increments_norm > 1:
            du = du / increments_norm
        if increments_norm < 1e-6 and residue_norm < 1e-4:
            break
        """
        Configuration update (not working as of now) for angles greater than 360 deg, Make this work for multi-axis rotations
        """
        # TODO: Change this, this is working fine but numerically it is not the best way, it works perfectly if two rotations are about one axis
        u += du

    print(residue_norm, increments_norm)
    return is_halt


u = np.zeros((numberOfNodes * DOF, 1))
u[6 * vi + 2, 0] = node_data

marker_ = np.linspace(0, max_load, LOAD_INCREMENTS)
# marker_ = np.insert(marker_, 0, [2000, 6000, 12000], axis=0)
"""
------------------------------------------------------------------------------------------------------------------------------------
Post Processing
------------------------------------------------------------------------------------------------------------------------------------
"""

"""
Graph limits defaults
"""
xmax = 1e-7
ymax = 1e-7
xmin = 0
ymin = 0

video_request = False


def act(i):
    global u
    global xmax
    global ymax
    global xmin
    global ymin
    global video_request
    halt = fea(i)
    if halt:
        controlled_animation.stop()
        return
    y0 = u[DOF * vi + 1, 0]
    x0 = u[DOF * vi + 2, 0]
    if np.isclose(abs(fapp__[i]), marker_).any():
        xmax, ymax = max(xmax, np.max(x0)), max(np.max(y0), ymax)
        xmin, ymin = min(xmin, np.min(x0)), min(np.min(y0), ymin)
        ax.axis('equal')
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)

        line1.set_ydata(y0)
        line1.set_xdata(x0)
        ax.set_title("Centerline displacement, Applied Load : " + str(round(fapp__[i], 5)))
        if not video_request:
            ax.plot(x0, y0)
    if i == 0:
        ay.legend()
    ay.scatter(abs(fapp__[i]), -u[-4, 0] + L, marker=".", label="horizontal tip displacement")
    ay.scatter(abs(fapp__[i]), u[-5, 0], marker="+", label="vertical tip displacement")
    if i == LOAD_INCREMENTS - 1:
        controlled_animation.disconnect()


ay.axhline(y=0)
ay.set_xlabel(r"LOAD", fontsize=16)
ay.set_ylabel(r"Tip Displacement", fontsize=16)
ax.set_xlabel(r"$r_3$", fontsize=30)
ax.set_ylabel(r"$r_2$", fontsize=30)
ax.set_ylim(-85, 41)
y = u[DOF * vi + 1, 0]
x = u[DOF * vi + 2, 0]
line1, = ax.plot(x, y)
ax.set_title("Centerline displacement")
ay.set_title("Tip Displacement vs load")
controlled_animation = ControlledAnimation(fig, act, frames=len(fapp__), video_request=video_request, repeat=False)
controlled_animation.start()
print(max_load * L / GA / 2, u[-6:])