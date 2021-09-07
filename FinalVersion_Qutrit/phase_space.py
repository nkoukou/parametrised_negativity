import autograd.numpy as np
import itertools as it

from state_functions import(DIM, tau, power)
from circuit_components import(makeGate, makeState, psi2rho)

def W_state(rho, x):
    return W_state_1q(rho, x2Gamma(x))

def W_gate(gate, x_list_in, x_list_out):
    n = len(x_list_in)

    if n==1:
        return W_gate_1q(gate, x2Gamma(x_list_in[0]), x2Gamma(x_list_out[0]))
    elif n==2:
        Gamma_in = [x2Gamma(x) for x in x_list_in]
        Gamma_out = [x2Gamma(x) for x in x_list_out]
        return W_gate_2q(gate, Gamma_in[0], Gamma_in[1], Gamma_out[0],
                         Gamma_out[1])
    elif n==3:
        Gamma_in = [x2Gamma(x) for x in x_list_in]
        Gamma_out = [x2Gamma(x) for x in x_list_out]
        return W_gate_3q(gate, Gamma_in[0], Gamma_in[1], Gamma_in[2],
                         Gamma_out[0], Gamma_out[1], Gamma_out[2])
    else:
        raise Exception('Not implemented for n > 3.')

def W_meas(E, x):
    return W_meas_1q(E, x2Gamma(x))

def x2Gamma(x):
    ''' Returns covariance matrix Gamma given array x of independent parameters
        with len(x) = 8 (Gamma is Hermitian with unit trace).
        x takes values in [-1,1].
        Wigner distribution corresponds to x = [1,0,0,0,0,0,1,0].
        Output - (3x3) complex ndarray
    '''
    return np.array([[ x[0],             x[1] + 1.j*x[2],  x[3] + 1.j*x[4] ],
                     [ x[1] - 1.j*x[2],  x[5],             x[6] + 1.j*x[7] ],
                     [ x[3] - 1.j*x[4],  x[6] - 1.j*x[7],  1 - x[0] - x[5] ]
                    ], dtype="complex_")

def get_trace_D(Gamma):
    ''' Returns traces tr[D_{p,q} Gamma] at all phase points x.
        Output - (DIM,DIM) complex ndarray
    '''
    return np.einsum('ijkl,lk->ij', D1q_list, Gamma)

def get_F1q0(Gamma):
    ''' Returns new displacement operator at the origin,
        F_0 = 1/DIM \sum_{p,q} 1/tr[D_{p,q} Gamma] D_{p,q}.
        Output - (DIM,DIM) complex ndarray
    '''
    traces = 1./get_trace_D(Gamma)
    return 1./DIM * np.einsum('ij,ijkl->kl', traces, D1q_list)

def test_F1q0(Gamma):
    D_Gamma_list = get_trace_D(Gamma)
    F1q0 = np.zeros((DIM,DIM), dtype="complex_")
    for w in it.product(range(DIM),repeat=2):
        p,q = w[0],w[1]
        F1q0 += D1q_list[p,q]/D_Gamma_list[p,q]
        # F1q0 += D1q_list[-p,-q]/D_Gamma_list[p,q]
    return np.array(F1q0/DIM, dtype="complex_")

def get_F1q_list(Gamma):
    ''' Returns new displacement operators at all phase space points x,
        F_{p,q} = D_{p,q} F_0 D_{-p,-q}.
        Output - (DIM,DIM,DIM,DIM) complex ndarray
    '''
    F1q0 = get_F1q0(Gamma)
    return np.einsum('ijkl,lm,ijnm->ijkn', D1q_list, F1q0, D1q_list.conj())

def get_G1q_list(Gamma):
    ''' Returns displaced Gamma matrix,
        G_{p,q} = D_{p,q} Gamma D_{-p,-q}.
        Output - (DIM,DIM,DIM,DIM) complex ndarray
    '''
    return np.einsum('ijkl,lm,ijnm->ijkn', D1q_list, Gamma, D1q_list.conj())

def W_state_1q(rho, Gamma):
    ''' Returns Gamma-distribution of state rho,
        W_rho(p,q) = 1/DIM tr[F_{p,q} rho].
        Output - (DIM, DIM) complex ndarray
    '''
    F1q = get_F1q_list(Gamma)
    return 1/DIM * np.real(np.einsum('ijkl,lk->ij', F1q, rho))

def neg_state_1q(rho, Gamma):
    ''' Calculates \sum_{p,q} |W_rho(p,q)|.
        Output - float
    '''
    return np.abs(W_state_1q(rho, Gamma)).sum()

def W_gate_1q(U1q, Gamma_in, Gamma_out):
    ''' Returns Gamma-distribution of 1-qudit gate U,
        W_U(p_out,q_out|p_in,q_in) = 1/DIM tr[U G_{p_in,q_in} U^\dagger
                                              F_{p_out,q_out}].
        Output - (DIM, DIM, DIM, DIM) complex ndarray
    '''
    G1q_in = get_G1q_list(Gamma_in)
    F1q_out = get_F1q_list(Gamma_out)
    rho_ev = np.einsum('lk,ijkn,mn->ijlm', U1q, G1q_in, U1q.conj())
    return 1/DIM * np.real(np.einsum('ijkl,mnlk->ijmn', rho_ev, F1q_out))

def neg_gate_1q(U1q, Gamma_in, Gamma_out):
    ''' Calculates \abs{\sum{p_out,q_out}|W_U(p_out,q_out|p_in,q_in)|}.
        Output - float
    '''
    return np.abs(W_gate_1q(U1q, Gamma_in, Gamma_out)).sum(axis=(2,3))

def neg_gate_1q_max(U1q, Gamma_in, Gamma_out):
    ''' Calculates \max_{p_in,q_in}
                   \sum{p_out,q_out}|W_U(p_out,q_out|p_in,q_in)|.
        Output - float
    '''
    return np.abs(W_gate_1q(U1q, Gamma_in, Gamma_out)).sum(axis=(2,3)).max()

def W_gate_2q(U2q, Gamma_in1, Gamma_in2, Gamma_out1, Gamma_out2):
    ''' Returns Gamma-distribution of 2-qubit gate U2q,
        W_U(p1_out,q1_out,p2_out,q2_out|p1_in,q1_in,p2_in,q2_in) =
        1/DIM^2 tr[U (G_{p1_in,q1_in} \otimes G_{p2_in,q2_in}) U^\dagger
                   (F_{p1_out,q1_out} \otimes F_{p2_out,q2_out})].
        Output - (DIM, DIM, DIM, DIM, DIM, DIM, DIM, DIM) complex ndarray
    '''
    G_in = np.einsum('ijkl,mnrs->ijmnkrls',
            get_G1q_list(Gamma_in1), get_G1q_list(Gamma_in2)
           ).reshape((DIM,DIM,DIM,DIM,DIM*DIM,DIM*DIM))
    F_out = np.einsum('ijkl,mnrs->ijmnkrls',
                       get_F1q_list(Gamma_out1), get_F1q_list(Gamma_out2)
                      ).reshape((DIM,DIM,DIM,DIM,DIM*DIM,DIM*DIM))
    U_ev = np.einsum('lk,ijsrkn,mn->ijsrlm', U2q, G_in, U2q.conj())
    return 1/DIM/DIM * np.real(np.einsum('ijsrkl,mnablk->ijsrmnab',
                                         U_ev, F_out))

def neg_gate_2q(U2q, Gamma_in1, Gamma_in2, Gamma_out1, Gamma_out2):
    ''' Calculates \sum{p1_out,q1_out, p2_out,q2_out}
                   |W_U(p1_out,q1_out,p2_out,q2_out|p1_in,q1_in,p2_in,q2_in)|.
        Output - float
    '''
    wigner_dist = W_gate_2q(U2q, Gamma_in1, Gamma_in2, Gamma_out1, Gamma_out2)
    return np.abs(wigner_dist).sum(axis=(4,5,6,7))

def neg_gate_2q_max(U2q, Gamma_in1, Gamma_in2, Gamma_out1, Gamma_out2):
    ''' Calculates \max_{p1_in,q1_in,p2_in,q2_in}
                   \sum{p1_out,q1_out, p2_out,q2_out}
                   |W_U(p1_out,q1_out,p2_out,q2_out|p1_in,q1_in,p2_in,q2_in)|.
        Output - float
    '''
    wigner_dist = W_gate_2q(U2q, Gamma_in1, Gamma_in2, Gamma_out1, Gamma_out2)
    return np.abs(wigner_dist).sum(axis=(4,5,6,7)).max()


def W_gate_3q(U3q, Gamma_in1, Gamma_in2, Gamma_in3,
                   Gamma_out1, Gamma_out2, Gamma_out3):
    ''' Returns Gamma-distribution of 3-qubit gate U3q'''
    G_in = np.einsum('ijkl,mnrs,xyzw->ijmnxykrzlsw', get_G1q_list(Gamma_in1),
                     get_G1q_list(Gamma_in2), get_G1q_list(Gamma_in3)
           ).reshape((DIM,DIM,DIM,DIM,DIM,DIM,DIM*DIM*DIM,DIM*DIM*DIM))
    F_out = np.einsum('ijkl,mnrs,xyzw->ijmnxykrzlsw', get_F1q_list(Gamma_out1),
                      get_F1q_list(Gamma_out2), get_F1q_list(Gamma_out3)
           ).reshape((DIM,DIM,DIM,DIM,DIM,DIM,DIM*DIM*DIM,DIM*DIM*DIM))
    U_ev = np.einsum('lk,ijsrxykn,mn->ijsrxylm', U3q, G_in, U3q.conj())
    return 1/DIM/DIM/DIM * np.real(np.einsum('ijsrxykl,mnabzwlk->ijsrxymnabzw',
                                         U_ev, F_out))

def neg_gate_3q(U3q, Gamma_in1, Gamma_in2, Gamma_in3,
                     Gamma_out1, Gamma_out2, Gamma_out3):
    ''' Calculates \sum{p1_out,q1_out, p2_out,q2_out}
                   |W_U(p1_out,q1_out,p2_out,q2_out|p1_in,q1_in,p2_in,q2_in)|.
        Output - float
    '''
    wigner_dist = W_gate_3q(U3q, Gamma_in1, Gamma_in2, Gamma_in3,
                                 Gamma_out1, Gamma_out2, Gamma_out3)
    return np.abs(wigner_dist).sum(axis=(6,7,8,9,10,11))

def neg_gate_3q_max(U3q, Gamma_in1, Gamma_in2, Gamma_in3,
                         Gamma_out1, Gamma_out2, Gamma_out3):
    return neg_gate_3q(U3q, Gamma_in1, Gamma_in2, Gamma_in3,
                       Gamma_out1, Gamma_out2, Gamma_out3).max()


def W_meas_1q(E, Gamma):
    ''' Returns Gamma-distribution of measurement effect E,
        W_E(p,q) = 1/DIM tr[G_{p,q} E].
        Output - (DIM, DIM) complex ndarray
    '''
    G1q = get_G1q_list(Gamma)
    return np.real(np.einsum('ijkl,lk->ij', G1q, E))

def neg_meas_1q(E, Gamma):
    ''' Calculates \max_{p,q} |W_E(p,q)|.
        Output - float
    '''
    return np.max(np.abs(W_meas_1q(E, Gamma)))

########################### DISPLACEMENT OPERATORS ############################
X = makeGate('X')
Z = makeGate('Z')
def D1q(w):
    ''' Returns 1-qudit displacement operator at phase space location w.
        w - tuple
    '''
    p = w[0]%DIM
    q = w[1]%DIM
    return tau**(p*q) * np.dot(power(X, p), power(Z, q))

def allD1qs():
    ''' Returns displacement operators D_x at all DIM*DIM phase space points x.
        Output - (DIM,DIM,DIM,DIM) complex ndarray
    '''
    D1q_list = []
    for w in it.product(range(DIM), repeat=2):
        w = np.array(w, dtype=int)
        D1q_list.append(D1q(w))
    D1q_list = np.array(np.reshape(D1q_list,(DIM,DIM,DIM,DIM)),
                        dtype="complex_")
    # print('Done calculating D1qs.')
    return D1q_list
D1q_list = allD1qs()


# print(get_F1q0(x2Gamma([1,1/2,1/2])))
# print(get_F1q_list(x2Gamma([1,1/2,1/2])))
# print(W_state_1q(psi2rho(np.array([1,-1.j])/np.sqrt(2)),
#                    x2Gamma([1,1/2,1/2])).flatten())
# x0w = [1,1/2,1/2]
# #x = [1,2,4]
# Gamma_in = x2Gamma(x0w)
# H_Gate = makeGate('H')
# Gamma_out = np.dot(np.dot(H_Gate, Gamma_in),np.conjugate(H_Gate.T))
# print(W_gate_1q(makeGate('H'), Gamma_in , Gamma_in))
# print(neg_gate_1q(makeGate('H'), Gamma_in , Gamma_in))
#
#print(makeGate('H'))
#print(makeGate('Z'))
#print(np.dot(makeGate('Z'),makeGate('X')))
#print(D1q_list[1,1])