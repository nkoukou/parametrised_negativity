from numba import(jitclass, types)
import numpy as np
import numpy.random as nr
# import time

@jitclass([
('sample_size', types.int32),
('meas_list', types.float32[:,:,:]),
('N', types.int8),
('index_list', types.int8[:,:]),
('state_qd', types.float32[:,:]),
('gate_qd', types.float32[:,:]),
('meas_qd', types.float32[:,:]),
('state_pd', types.float32[:,:]),
('gate_pd', types.float32[:,:]),
('meas_pd', types.float32[:,:]),
('state_sign', types.float32[:,:]),
('gate_sign', types.float32[:,:]),
('meas_sign', types.float32[:,:]),
('state_neg', types.float32[:]),
('gate_neg', types.float32[:,:]),
('meas_neg', types.float32[:]),
('p_estimate', types.float32)
])
class Sampler(object):
    '''
    Implements quasi-probability Monte Carlo sampling as outlined in
    Pashayan et al. (2015).
    '''
    def __init__(self, sample_size, meas_list, index_list, qd_list_states,
                 qd_list_gates, qd_list_meas, pd_list_states, pd_list_gates,
                 pd_list_meas, sign_list_states, sign_list_gates,
                 sign_list_meas, neg_list_states, neg_list_gates,
                 neg_list_meas):
        self.sample_size = sample_size
        self.meas_list = meas_list
        self.N = self.meas_list.shape[0]
        self.index_list = index_list

        self.state_qd = qd_list_states
        self.gate_qd = qd_list_gates
        self.meas_qd = qd_list_meas

        self.state_pd = pd_list_states
        self.gate_pd = pd_list_gates
        self.meas_pd = pd_list_meas

        self.state_sign = sign_list_states
        self.gate_sign = sign_list_gates
        self.meas_sign = sign_list_meas

        self.state_neg = neg_list_states
        self.gate_neg = neg_list_gates
        self.meas_neg = neg_list_meas

        self.p_estimate = 0.

    def sample_iter(self):
        current_ps_point = np.zeros(self.N, dtype=np.int32)
        p_estimate = 1.

        # Input states
        for s in range(self.N):
            ps_point = np.arange(len(self.state_pd[s]))[np.searchsorted(
              np.cumsum(self.state_pd[s]), np.random.random(), side="right")]
            current_ps_point[s] = ps_point
            p_estimate *= self.state_neg[s]*self.state_sign[s][ps_point]

        # Gates
        for g in range(self.index_list.shape[0]):
            idx = self.index_list[g]

            arr_dim = np.log2(len(self.gate_pd[g]))/2
            pq_in = 0
            for i in range(len(idx)):
                pq_in += current_ps_point[idx[i]]//2 * 2**(2*(arr_dim-i)-1)
                pq_in += current_ps_point[idx[i]]%2 * 2**(2*(arr_dim-i)-2)
            pq_in = int(pq_in)

            prob = self.gate_pd[g,pq_in:pq_in+int(2**arr_dim)]
            sign = self.gate_sign[g,pq_in:pq_in+int(2**arr_dim)]
            neg = self.gate_neg[g,int(pq_in//(2**arr_dim))]

            ps_point = np.arange(len(prob))[np.searchsorted(
              np.cumsum(prob), np.random.random(), side="right")]
            prob_dim = np.log2(len(prob))/2
            for i in range(len(idx)):
                current_ps_point[idx[i]] = int(ps_point/4**(prob_dim-1-i))%4
            p_estimate *= neg*sign[ps_point]


        # Measurement
        exp_qaoa = p_estimate
        temp = 0
        for m in range(self.N):
            p_estimate *= self.meas_qd[m,current_ps_point[m]]

            m_next = (m+1)%self.N
            temp += 0.5 * self.meas_qd[m_next,current_ps_point[m_next]]*\
                          self.meas_qd[m,current_ps_point[m]]
        exp_qaoa *= temp

        self.p_estimate = exp_qaoa # p_estimate #

    def sample(self):
        p_estimate = 0.
        for n in range(self.sample_size):
            if n%(self.sample_size//10)==0: print(n/self.sample_size*100, "%")
            self.sample_iter()
            p_estimate += 1./self.sample_size * self.p_estimate
        self.p_estimate = p_estimate

def get_qd_output(circuit, par_list, ps):
    '''
    Calculate the quasi-probability distribution of each circuit element
    and return them as a list of [state qds, gate qds, measurement qds].
    '''
    par_idx_states = np.arange(0, len(circuit["state_list"]))
    par_idx_gates = par_list[1]
    par_idx_meas = par_list[2]
    par_vals = par_list[0]

    qd_list_states = []   # qd lists
    qd_list_gates = []
    qd_list_meas = []

    neg_list_states = []  # qd negativity lists
    neg_list_gates = []
    neg_list_meas = []

    sign_list_states = [] # sign of qd lists
    sign_list_gates = []
    sign_list_meas = []

    pd_list_states = []   # normalised prob dist lists
    pd_list_gates = []
    pd_list_meas = []

    # States
    for s, state in enumerate(circuit['state_list']):
        x = par_vals[par_idx_states[s]]

        qd_state = ps.W_state(state, x)
        pd_state = np.abs(qd_state)
        neg_state = pd_state.sum()
        pd_state /= neg_state
        sign_state = np.sign(qd_state)

        qd_list_states.append(qd_state)
        pd_list_states.append(pd_state)
        neg_list_states.append(neg_state)
        sign_list_states.append(sign_state)

    # Gates
    for g, gate in enumerate(circuit['gate_list']):
        idx = circuit['index_list'][g]

        x_in, x_out = [], []
        for k in par_idx_gates[g][0]:
            x_in.append(par_vals[k])
        for k in par_idx_gates[g][1]:
            x_out.append(par_vals[k])

        qd_gate = ps.W_gate(gate, x_in, x_out)
        pd_gate = np.abs(qd_gate)
        neg_gate = pd_gate.sum(axis=tuple(range(2*len(idx),4*len(idx))))
        for i in range(2*len(idx)):
            pd_gate = pd_gate.swapaxes(i,2*len(idx)+i)
        pd_gate = pd_gate/neg_gate
        for i in range(2*len(idx)):
            pd_gate = pd_gate.swapaxes(i,2*len(idx)+i)
        sign_gate = np.sign(qd_gate)

        qd_list_gates.append(qd_gate)
        pd_list_gates.append(pd_gate)
        neg_list_gates.append(neg_gate)
        sign_list_gates.append(sign_gate)

    # Measurements
    for m, meas in enumerate(circuit['meas_list']):
        x = par_vals[par_idx_meas[m]]

        qd_meas = ps.W_meas(meas, x)
        pd_meas = np.abs(qd_meas)
        neg_meas = np.max(pd_meas)
        sign_meas = np.sign(qd_meas)

        qd_list_meas.append(qd_meas)
        pd_list_meas.append(pd_meas)
        neg_list_meas.append(neg_meas)
        sign_list_meas.append(sign_meas)

    output = {
    'qd_list_states': qd_list_states, 'qd_list_gates': qd_list_gates,
    'qd_list_meas': qd_list_meas, 'pd_list_states': pd_list_states,
    'pd_list_gates': pd_list_gates, 'pd_list_meas': pd_list_meas,
    'neg_list_states': neg_list_states, 'neg_list_gates': neg_list_gates,
    'neg_list_meas': neg_list_meas, 'sign_list_states': sign_list_states,
    'sign_list_gates': sign_list_gates, 'sign_list_meas': sign_list_meas
    }
    return output

def prepare_sampler(circuit, par_list, ps):
    meas_list = np.stack(circuit["meas_list"]).astype(np.float32)
    index_list = np.array(circuit["index_list"]).astype(np.int8)

    output = get_qd_output(circuit, par_list, ps)

    qd_list_states = np.stack([dist.flatten().astype(np.float32)
                               for dist in output["qd_list_states"]])
    qd_list_gates = np.stack([dist.flatten().astype(np.float32)
                              for dist in output["qd_list_gates"]])
    qd_list_meas = np.stack([dist.flatten().astype(np.float32)
                             for dist in output["qd_list_meas"]])

    neg_list_states = np.array(output["neg_list_states"]).astype(np.float32)
    neg_list_gates = np.stack([dist.flatten().astype(np.float32)
                               for dist in output["neg_list_gates"]])
    neg_list_meas = np.array(output["neg_list_meas"]).astype(np.float32)

    pd_list_states = np.stack([dist.flatten().astype(np.float32)
                               for dist in output["pd_list_states"]])
    pd_list_gates = np.stack([dist.flatten().astype(np.float32)
                              for dist in output["pd_list_gates"]])
    pd_list_meas = np.stack([dist.flatten().astype(np.float32)
                             for dist in output["pd_list_meas"]])

    sign_list_states = np.stack([dist.flatten().astype(np.float32)
                                 for dist in output["sign_list_states"]])
    sign_list_gates = np.stack([dist.flatten().astype(np.float32)
                                for dist in output["sign_list_gates"]])
    sign_list_meas = np.stack([dist.flatten().astype(np.float32)
                               for dist in output["sign_list_meas"]])

    return(meas_list, index_list, qd_list_states, qd_list_gates, qd_list_meas,
           pd_list_states, pd_list_gates, pd_list_meas, sign_list_states,
           sign_list_gates, sign_list_meas, neg_list_states, neg_list_gates,
           neg_list_meas)













# def sample_circuit(circuit, qd_output, sample_size=int(1e4)):
#     '''
#     The function performing the Monte Carlo sampling as outlined in
#     Pashayan et al. (2015) for the compressed version of the given circuit
#     and the parameter list. It prints the method we used, the sampling result
#     (p_estimate), and the computation time. It also returns the sampling
#     result and the full list of p_estimate of each iteration ('plot').
#     '''
#     def sample_iter():
#         current_ps_point = []
#         p_estimate = 1.

#         # Input states - PD NOT QD
#         for s, pd_state in enumerate(qd_output['pd_list_states']):
#             prob = pd_state.flatten()
#             neg = qd_output['neg_list_states'][s]
#             sign = qd_output['sign_list_states'][s].flatten()

#             ps_point = nr.choice(np.arange(len(prob)), p=prob)
#             current_ps_point.append(ps_point)
#             p_estimate *= neg*sign[ps_point]

#         # Gates
#         for g, pd_gate in enumerate(qd_output['pd_list_gates']):
#             idx = circuit['index_list'][g]

#             pq_in = [[current_ps_point[idx[i]]//2,current_ps_point[idx[i]]%2]
#                      for i in range(len(idx))]
#             pq_in = tuple([item for sublist in pq_in for item in sublist])

#             prob = pd_gate[pq_in].flatten()
#             neg = qd_output['neg_list_gates'][g][pq_in]
#             sign = qd_output['sign_list_gates'][g][pq_in].flatten()

#             ps_point = nr.choice(np.arange(len(prob)), p=prob)
#             str_repr = np.base_repr(ps_point, 4).zfill(len(idx))
#             for i in range(len(idx)):
#                 current_ps_point[idx[i]] = int(str_repr[i])
#             p_estimate *= neg*sign[ps_point]

#         # Measurement - QD NOT PD
#         exp_qaoa = p_estimate
#         temp = 0
#         for m, meas in enumerate(circuit['meas_list']):
#             wf = qd_output['qd_list_meas'][m].flatten()
#             p_estimate *= wf[current_ps_point[m]]

#             m_next = (m+1)%len(circuit['meas_list'])
#             wf_next = qd_output['qd_list_meas'][m_next].flatten()
#             temp += 0.5 * wf_next[current_ps_point[m_next]] * \
#                           wf[current_ps_point[m]]

#         exp_qaoa *= temp

#         return p_estimate # exp_qaoa

#     start_time = time.time()
#     p_estimate = np.zeros(sample_size)
#     print("\n"+"SAMPLING")
#     for n in range(sample_size):
#         if n%(sample_size//10)==0: print(n/sample_size*100, "%")
#         p_estimate[n] = sample_iter()
#     sampling_time = time.time() - start_time

#     print('====================== Sampling Results ======================')
#     print('p_estimate:    ', np.average(p_estimate))
#     print('Sample size:   ', sample_size)
#     print('Sampling time: ', sampling_time)
#     print('==============================================================')

#     return p_estimate



