import numpy as np
import numpy.random as nr
import matplotlib.pyplot as plt
import time
import itertools as it

from QUBIT_circuit_components import(makeState, makeGate)
from QUBIT_opt_neg import(optimize_neg_compressed)
from QUBIT_random_circuit_generator import(compress_circuit)
from QUBIT_phase_space import(x2Gamma, W_state_1q, neg_state_1q, W_gate_1q,
                        neg_gate_1q, W_gate_2q, neg_gate_2q, W_meas_1q,
                        neg_meas_1q)
DIM = 2

def compare_Wigner_optimised(circuit, niters=1000):
    '''
    Run sampling twice with Wigner parameters and optimised parameters, respectively,
    save the results, and plot the results as a function of iterations.
    '''
    Wigner = sample(circuit, 0, niters)
    Optimised = sample(circuit, 1, niters)

    p_sample_Wigner, plot_Wigner = Wigner.MC_sampling()
    p_sample_opt, plot_opt = Optimised.MC_sampling()

    ### Save the results
    path1 = 'Wigner.txt'
    path2 = 'Optimised.txt'

    with open(path1, 'a') as f1:
        for n in range(len(plot_Wigner)):
            f1.write(str(n+1)+" "+str(plot_Wigner[n]))
            f1.write("\n")
    f1.close()
    with open(path2, 'a') as f2:
        for n in range(len(plot_opt)):
            f2.write(str(n+1)+" "+str(plot_opt[n]))
            f2.write("\n")
    f2.close()

    ### Plot the results
    x_axis = np.arange(niters)
    plt.plot(x_axis, plot_Wigner, linestyle='solid', color='tab:blue', label='Wigner')
    plt.plot(x_axis, plot_opt, linestyle='solid', color='tab:orange', label='Optimised')
    plt.xlabel("number of iterations")
    plt.ylabel("p_estimate")
    plt.legend()
    plt.show()

class sample(object):
    '''
    For a given circuit and a list of parameters for Gammas,
    define functions needed, compress the circuit, and run sampling.
    '''
    def __init__(self, circuit, x=0, niters=1000):
        '''
        [INPUT] 
        - circuit : the given circuit.
        - x : the list of parameters for Gammas.
              If x=0, use the Wigner parameters.
              If x=1, run optimisation and use the optimised parameters.
              If x is a parameter list, then use it as x_list.
        - niters: the number of iterations in sampling.
        [Self-parameters]
        - self.compressed_circuit : the compressed version of the given circuit.
        - self.niters : the number of iterations in sampling.
        - self.len_Gammas :  the number of different Gammas needed.
        - self.x_list : the list of parameters for Gammas. Set depending on the input 'x'.
        - self.method: which method we use to set 'x_list'; Wigner, Optimised, or Given.
        - self.PD_list : the pre-saved list of quasi-prob. distribution of each element in the compressed circuit.
        - self.neg_list: the pre-saved list of quasi-prob. negativity of each element in the compressed circuit.
        '''
        self.compressed_circuit = compress_circuit(circuit)
        self.niters = niters
        self.len_Gammas = self.n_Gammas()

        if isinstance(x, int): # If x is not a list, depending on the value, set 'x_list'.
            if x==0: # When x=0, 'x_list' is the Wigner parameters.
                self.x_list = [1,1/2,1/2]*self.len_Gammas
                self.method = 'Wigner'
            elif x==1: # When x=1, run optimisation and find the optimised x_list.
                self.x_list = optimize_neg_compressed(self.compressed_circuit)[0]
                self.method = 'Optimised'
        else: # When x_list is given.
            self.x_list = x
            self.method = 'Given'

        self.PD_list, self.neg_list = self.get_prob_list()

    def MC_sampling(self):
        '''
        The function actually performing the Monte Carlo sampling as outlined in Pashayan et al. (2015)
        for the compressed version of the given circuit and the parameter list.
        It prints the method we used, the sampling result (p_estimate), and the computation time.
        It also returns the sampling result and the full list of p_estimate of each iteration ('plot').
        '''
        p_sample = 0
        plot = []

        start_time = time.time()
        for n in range(self.niters):
            p_sample += self.sample_iter()
            plot.append(p_sample/(n+1))
        sampling_time = time.time() - start_time

        # Print the final results
        print('==================Sampling Results====================')
        print('Sampling method: ', self.method)
        print('Sampling results (p_estimate): ', p_sample/self.niters)
        print('Sampling time: ', sampling_time)
        print('======================================================')

        return p_sample/self.niters, plot

    def sample_iter(self):
        ''' 
        One iteration of the Monte Carlo sampling.
        '''
        state_string, gate_sequence, meas_string = self.compressed_circuit

        # The list of Gamma quasi-probability distributions and the negativity of circuit elements
        PD_list_states, PD_list_gates, PD_list_meas = self.PD_list
        neg_list_states, neg_list_gates = self.neg_list

        ### Sampling
        current_PS_point = []
        p_estimate = 1.
       
        # Input states
        for s in range(len(state_string)):
            WF = PD_list_states[s].flatten()
            prob = np.abs(WF)
            PS_point = nr.choice(np.arange(len(prob)), p=prob)

            current_PS_point.append(PS_point)
            p_estimate *= neg_list_states[s]*np.sign(WF[PS_point])

        # Gates
        for g in range(len(gate_sequence)):
            idx = gate_sequence[g][0]
            if len(idx)==1:
                p_in = current_PS_point[idx[0]]//2
                q_in = current_PS_point[idx[0]]%2
                WF = (PD_list_gates[g][p_in,q_in]).flatten()
                prob = np.abs(WF)

                PS_point = nr.choice(np.arange(len(prob)), p=prob)
                current_PS_point[idx[0]] = PS_point            
                p_estimate *= neg_list_gates[g][p_in,q_in]*np.sign(WF[PS_point])
            elif len(idx)==2:
                p_in1 = current_PS_point[idx[0]]//2
                q_in1 = current_PS_point[idx[0]]%2
                p_in2 = current_PS_point[idx[1]]//2
                q_in2 = current_PS_point[idx[1]]%2

                WF = (PD_list_gates[g][p_in1,q_in1,p_in2,q_in2]).flatten()
                prob = np.abs(WF)

                PS_point = nr.choice(np.arange(len(prob)), p=prob)
                current_PS_point[idx[0]] = PS_point//4
                current_PS_point[idx[1]] = PS_point%4
                p_estimate *= neg_list_gates[g][p_in1,q_in1,p_in2,q_in2]*np.sign(WF[PS_point])
            else:
                raise Exception('Too many gate indices')

        # Measurement
        for m in range(len(meas_string)):
            if meas_string[m]!='/':
                WF = PD_list_meas[m].flatten()
                p_estimate *= WF[current_PS_point[m]]

        return p_estimate

    def get_prob_list(self):
        '''
        Calculate the quasi-probability distribution of each circuit element
        and return them as a list of [state part, gate part, measurement part].
        '''
        state_string, gate_sequence, meas_string = self.compressed_circuit

        Gamma_index = 0
        Gammas = []

        PD_list_states = [] # The state part of the quasi-prob. distribution list
        PD_list_gates = [] # The gate part of the quasi-prob. distribution list
        PD_list_meas = [] # The measurement part of the quasi-prob. distribution list
        neg_list_states = [] # The state part of the quasi-prob. negativity list
        neg_list_gates = [] # The gate part of the quasi-prob. negativity list
        
        # Input states
        for s in state_string:
            state = makeState(s)
            Gamma = x2Gamma(self.x_list[3*Gamma_index:3*(Gamma_index+1)])
            WF = W_state_1q(state, Gamma)
            neg = np.abs(WF).sum()
            prob = WF/neg
            
            PD_list_states.append(prob)
            neg_list_states.append(neg)

            Gammas.append(Gamma)
            Gamma_index += 1

        # Gates
        for g in gate_sequence:
            idx, gate = g[0], g[1]
            if len(idx)==1:
                if g[1]=='H': # When the gate is Hadamard gate, we have a particular way to assign Gamma_out.
                    Gamma_in = Gammas[idx[0]]
                    Gamma_out = np.dot(np.dot(gate, Gamma_in),np.conjugate(gate.T))
                else:    
                    Gamma_in = Gammas[idx[0]]
                    Gamma_out = x2Gamma(self.x_list[3*Gamma_index:3*(Gamma_index+1)])
                    Gamma_index += 1
                WF = W_gate_1q(gate, Gamma_in, Gamma_out)
                neg = np.abs(WF).sum(axis=(2,3)) # [p_in, q_in] index
                prob = np.array([WF[p_in, q_in]/neg[p_in, q_in] for p_in, q_in 
                    in it.product(range(DIM), repeat=2)]).reshape((DIM, DIM, DIM, DIM))

                PD_list_gates.append(prob)
                neg_list_gates.append(neg)

                Gammas[idx[0]] = Gamma_out    
            elif len(idx)==2:
                Gamma_in1 = Gammas[idx[0]]
                Gamma_in2 = Gammas[idx[1]]
                Gamma_out1 = x2Gamma(self.x_list[3*Gamma_index:3*(Gamma_index+1)])
                Gamma_out2 = x2Gamma(self.x_list[3*(Gamma_index+1):3*(Gamma_index+2)])
                WF = W_gate_2q(gate,Gamma_in1,Gamma_in2,Gamma_out1,Gamma_out2)
                neg = np.abs(WF).sum(axis=(4,5,6,7)) # [p1_in,q1_in,p2_in,q2_in]
                prob = np.array([WF[p1_in,q1_in,p2_in,q2_in]/neg[p1_in,q1_in,p2_in,q2_in] for p1_in,q1_in,p2_in,q2_in 
                    in it.product(range(DIM), repeat=4)]).reshape((DIM,DIM,DIM,DIM,DIM,DIM,DIM,DIM))

                PD_list_gates.append(prob)
                neg_list_gates.append(neg)

                Gammas[idx[0]] = Gamma_out1
                Gammas[idx[1]] = Gamma_out2
                Gamma_index += 2
            else:
                raise Exception('Too many gate indices')

        # Measurement
        for m in range(len(meas_string)):
            if meas_string[m]!='/':
                E = makeState(meas_string[m])
                Gamma = Gammas[m]
                WF = W_meas_1q(E, Gamma)
                PD_list_meas.append(WF)
            else:
                PD_list_meas.append([])

        return [PD_list_states, PD_list_gates, PD_list_meas], [neg_list_states, neg_list_gates]

    def n_Gammas(self):
        '''
        Calculate the number of different Gammas in the compressed circuit
        '''
        state_string, gate_sequence, meas_string = self.compressed_circuit
        Gamma_index = 0
        for s in state_string:
            Gamma_index += 1
        for g in gate_sequence:
            idx = g[0]
            if len(idx)==1:
                if g[1]=='H':
                    continue
                Gamma_index += 1
            elif len(idx)==2:
                Gamma_index += 2
        return Gamma_index
