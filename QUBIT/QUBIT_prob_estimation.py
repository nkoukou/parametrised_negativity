import numpy as np
import numpy.random as nr
import matplotlib.pyplot as plt

from QUBIT_circuit_components import(makeState, makeGate)
from QUBIT_opt_neg import(optimize_neg)
from QUBIT_phase_space import(x2Gamma, W_state_1q, neg_state_1q, W_gate_1q,
                        neg_gate_1q, W_gate_2q, neg_gate_2q, W_meas_1q,
                        neg_meas_1q, n_Gammas)

def sample(circuit, x=0, niters=10000):
    ''' Samples given circuit with given parameter list x.
        x      - Gamma parameter list
               - if 0, Wigner distribution.
        niters - number of sampling iterations.
    '''
    p_sample = 0
    for n in range(niters):
        p_sample += sample_iter(circuit, x)
    return p_sample/niters


def compare_Wigner_para(circuit, niters=10000, save=0):
    '''Show the difference between sampling with Wigner distribution
       and sampling with the optimised parameter list 'opt_Gammas'.
       It prints the final p_estimate in each case
       and produces a plot showing the convergence of p_estimate
       in each case as a function of niters.
    '''
    opt_Gammas, Gamma_dist = optimize_neg(circuit)

    p_sample_Wigner = 0
    p_sample_opt = 0

    plot_Wigner = []
    plot_opt = []

    for n in range(niters):
        p_sample_Wigner += sample_iter(circuit, 0)
        p_sample_opt += sample_iter(circuit, opt_Gammas)

        plot_Wigner.append(p_sample_Wigner/(n+1))
        plot_opt.append(p_sample_opt/(n+1))

    # Print the final results
    print('----------------------------------------------------------------')
    print('Using Wigner: ', p_sample_Wigner/niters)
    print('Using optimised QP: ', p_sample_opt/niters)

    # Plot the results, both the Wigner and the optimised ones.
    x_axis = np.arange(niters)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(x_axis, plot_Wigner, linestyle='solid', color='tab:blue',
             label='Wigner')
    ax.plot(x_axis, plot_opt, linestyle='solid', color='tab:orange',
             label='Optimised')
    ax.set_xlabel("number of iterations")
    ax.set_ylabel("p_estimate")
    ax.legend(loc='upper right')
    plt.show()

    if save==1:
        path = 'P_estimate.txt'
        with open(path, 'a') as f:
            for n in range(niters):
                f.write(str(n)+" "+str(plot_opt[n]))
                f.write("\n")
        f.close()


def sample_iter(circuit, x):
    ''' Performs Monte Carlo sampling as outlined in Pashayan et al. (2015)
        for given circuit and Gamma parameter list x.
    '''
    state_string, gate_sequence, meas_string = circuit

    if isinstance(x, int): # If x==0, set every Gamma [1,1/2,1/2] (Wigner).
        x = [1,1/2,1/2]*n_Gammas(circuit)

    current_PS_point = []
    Gamma_index = 0
    Gammas = []
    p_estimate = 1.
    agg_Gates=[np.eye(2)]*len(state_string)

    # Input states
    for s in state_string:
        state = makeState(s)
        Gamma = x2Gamma(x[3*Gamma_index:3*(Gamma_index+1)])
        WF = W_state_1q(state, Gamma).flatten()
        neg = neg_state_1q(state, Gamma)

        prob = np.abs(WF)/neg

        PS_point = nr.choice(np.arange(len(prob)), p=prob)

        current_PS_point.append(PS_point)
        Gammas.append(Gamma)
        Gamma_index += 1
        p_estimate *= neg*np.sign(WF[PS_point])

    # Gates
    for g in gate_sequence:
        idx, gate = g[0], makeGate(g[1])
        if len(idx)==1:
            if g[1]=='H':
                Gamma_in = Gammas[idx[0]]
                Gamma_out = np.dot(np.dot(gate, Gamma_in),np.conjugate(gate.T))
            else:    
                Gamma_in = Gammas[idx[0]]
                Gamma_out = x2Gamma(x[3*Gamma_index:3*(Gamma_index+1)])
                Gamma_index += 1

            p_in = current_PS_point[idx[0]]//2
            q_in = current_PS_point[idx[0]]%2
            WF = W_gate_1q(gate, Gamma_in, Gamma_out)[p_in,q_in].flatten()
            neg = neg_gate_1q(gate, Gamma_in, Gamma_out)[p_in,q_in]

            prob = np.abs(WF)/neg

            Gammas[idx[0]] = Gamma_out    
            PS_point = nr.choice(np.arange(len(prob)), p=prob)
            current_PS_point[idx[0]] = PS_point            
            p_estimate *= neg*np.sign(WF[PS_point])

        elif len(idx)==2:
            Gamma_in1 = Gammas[idx[0]]
            Gamma_in2 = Gammas[idx[1]]
            Gamma_out1 = x2Gamma(x[3*Gamma_index:3*(Gamma_index+1)])
            Gamma_out2 = x2Gamma(x[3*(Gamma_index+1):3*(Gamma_index+2)])
            p_in1 = current_PS_point[idx[0]]//2
            q_in1 = current_PS_point[idx[0]]%2
            p_in2 = current_PS_point[idx[1]]//2
            q_in2 = current_PS_point[idx[1]]%2
            WF = W_gate_2q(gate,Gamma_in1,Gamma_in2,Gamma_out1,Gamma_out2
                           )[p_in1,q_in1,p_in2,q_in2].flatten()
            neg = neg_gate_2q(gate,Gamma_in1,Gamma_in2,Gamma_out1,Gamma_out2
                              )[p_in1,q_in1,p_in2,q_in2]

            prob = np.abs(WF)/neg

            PS_point = nr.choice(np.arange(len(prob)), p=prob)
            current_PS_point[idx[0]] = PS_point//4
            current_PS_point[idx[1]] = PS_point%4
            Gammas[idx[0]] = Gamma_out1
            Gammas[idx[1]] = Gamma_out2
            Gamma_index += 2
            p_estimate *= neg*np.sign(WF[PS_point])

        else:
            raise Exception('Too many gate indices')

    # Measurement
    for m in range(len(meas_string)):
        if meas_string[m]!='/':
            E = makeState(meas_string[m])
            Gamma = Gammas[m]
            WF = W_meas_1q(E, Gamma).flatten()

            p_estimate *= WF[current_PS_point[m]]

    return p_estimate