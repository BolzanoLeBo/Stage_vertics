import time
import gurobipy as gp
from gurobipy import GRB
import numpy as np
import os
from multiprocessing import Pool


from gen_taskset import *

def solver(taskset) : 
    n = len(taskset)
    
    model = gp.Model("ilp_ram_allocator")
    model.setParam('OutputFlag', 0)
    model.setParam('TimeLimit', 3600)
    model.setParam('Threads', 1)

    x_f = model.addVars(n,3, vtype = GRB.BINARY)
    x_p = model.addVars(n,2, vtype = GRB.BINARY)
    x_d = model.addVars(n,3, vtype = GRB.BINARY)
    x_ro = model.addVars(n,4, vtype = GRB.BINARY)

    mulfc = []
    for i in range(3) : 
        mulfc.append(model.addVars(n,2,vtype = GRB.BINARY))

    
    muldro = []
    for i in range(2) : 
        muldro.append(model.addVars(n,4,vtype = GRB.BINARY))

    '''
        x_f : 
        100 24
        010 48
        001 72

        x_p : 
        10 cf 
        01 cc

        x_d : 
        10 no_d 
        01 dr

        x_ro : 
        1000 no_ro 
        0100 ro_f
        0010 ro_r
        0001  ro_c

        '''
    
    #var dimension 
    #no multiple allocation
    model.addConstrs(gp.quicksum(x_f[i,j] for j in range(3) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_p[i,j] for j in range(2) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_d[i,j] for j in range(2) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_ro[i,j] for j in range(4) )== 1 for i in range(n))
    #FLASH size constraint
    #we can have instruction or ro data
    model.addConstr(gp.quicksum((taskset[i].size_i * x_p[i,0] + 
                                taskset[i].size_ro * x_ro[i,1]) 
                                for i in range(n)) <= taskset.flash_size)
    #CCM size constraint
    #we can have instruction or ro data
    model.addConstr(gp.quicksum((taskset[i].size_i * x_p[i,1] + 
                                taskset[i].size_ro * x_ro[i,3])
                                for i in range(n)) <= taskset.ccm_size)
    #SRAM size constraint 
    #we can have input data or ro data 
    model.addConstr(gp.quicksum(taskset[i].size_ro * x_ro[i,2]
                                #+ taskset[i].size_d * x_d[i,1]
                                for i in range(n)) <= taskset.ram_size)
    
    #we cannot multiply more than 3 elements so we do pre-mutliplication
    model.addConstrs(mulfc[f][i,p] == x_f[i,f]*x_p[i,p] 
                  for i in range (n) 
                  for f in range (3)
                  for p in range (2))
    
    model.addConstrs(muldro[d][i,ro] == x_d[i,d]*x_ro[i,ro] 
                  for i in range (n) 
                  for d in range (2)
                  for ro in range (4))
    
    #utilization less than 1 
    model.addConstr(gp.quicksum((taskset[i].perf[f][p][d][ro][0]/taskset[i].period)
                                 *mulfc[f][i,p]*muldro[d][i,ro]  
                for f in range(3) 
                for p in range(2) 
                for d in range(2) 
                for ro in range(4) 
                for i in range (n)
                ) <= 1 )

    #minimize the energy
    model.setObjective(
    gp.quicksum((taskset[i].perf[f][p][d][ro][1]*mulfc[f][i,p]*muldro[d][i,ro])  
                for f in range(3) 
                for p in range(2) 
                for d in range(2) 
                for ro in range(4) 
                for i in range (n))
    ,
    GRB.MINIMIZE)


    model.optimize()

    
    if model.Status == GRB.INF_OR_UNBD:
        raise Exception('Model is infeasible or unbounded')
    elif model.Status == GRB.INFEASIBLE:
        raise Exception('Model is infeasible')
    elif model.Status == GRB.UNBOUNDED:
        raise Exception('Model is unbounded')
    x_f_sol = model.getAttr("x", x_f)
    x_p_sol = model.getAttr("x", x_p)
    x_d_sol = model.getAttr("x", x_d)
    x_ro_sol = model.getAttr("x", x_ro)


    error = 0
    f_str = ["24", "48", "72"]
    c_str = ["code Flash", "code CCM"]
    d_str = ["no Idata", "data ram"]
    ro_str = ["no ro", "ro FLASH", "ro RAM", "ro CCM"]
    U_tot = 0
    E_tot = 0
    E_ref = 0

    ccm_used = 0
    flash_used = 0
    ram_used = 0
    f_ccm_high = 0
    f_flash_low = 0
    nb_instr_ccm = 0
    nb_instr_flash = 0
    for i in range (n) : 
        x_index = [0,0,0,0]
        for j in range (4) : 
            if j < 3 : 
                if x_f_sol[i,j] > 1-1e-6 : 
                    x_index[0] = j
                    if x_p_sol[i,1]> 1-1e-6 and j == 2 : 
                        f_ccm_high += 1 
                    elif x_p_sol[i,0] >1-1e-6 and j < 2 : 
                        f_flash_low += 1

                
            if j < 2 : 
                if x_p_sol[i,j] > 1-1e-6 : 
                    x_index[1] = j
                    if j == 1 : 
                        ccm_used += taskset[i].size_i
                        nb_instr_ccm += 1 
                    else : 
                        flash_used += taskset[i].size_i
                        nb_instr_flash += 1
                    
                if x_d_sol[i,j] > 1-1e-6 : 
                    x_index[2] = j
                    '''if j == 1 : 
                        ram_used += taskset[i].size_d'''
            if x_ro_sol[i,j] > 1-1e-6 : 
                x_index[3] = j      
                if j == 1 : 
                    flash_used += taskset[i].size_ro
                elif j == 2 : 
                    ram_used += taskset[i].size_ro
                elif j == 3 :
                    ccm_used += taskset[i].size_ro 
        f, c, d, ro = x_index      
        #print(taskset[i].name," : ", f_str[f]," | ",c_str[c]," | ", d_str[d]," | ",ro_str[ro])
        #in the case where an unexistant config is taken 
        if taskset[i].perf[f][c][d][ro][0] > 8000 :
           error = 1
        util = taskset[i].perf[f][c][d][ro][0]/taskset[i].period
        energy = taskset[i].perf[f][c][d][ro][1]

        U_tot += util
        E_tot += energy/taskset[i].period
        E_ref += taskset[i].ref_energy/taskset[i].period
    
    flash_ratio = flash_used/taskset.flash_size
    ram_ratio =  ram_used/taskset.ram_size
    ccm_ratio = ccm_used/taskset.ccm_size
    '''print("total utilization :", U_tot)
    print("ref utilization: ", taskset.u_tot )
    print("total energy : ", E_tot)
    print("ref energy : ", E_ref)
    print("FLASH : {}%, SRAM : {}%, CCM : {}%".format(
       flash_ratio ,ram_ratio,ccm_ratio 
    ))'''
    U_gain = (taskset.u_tot - U_tot)/taskset.u_tot
    E_gain = (E_ref-E_tot)/E_ref
    if nb_instr_flash == 0 : 
        f_ratio_flash = 9999
    else : 
        f_ratio_flash = f_flash_low/nb_instr_flash
    return(U_gain, E_gain, flash_ratio, ram_ratio, ccm_ratio, f_ratio_flash, f_ccm_high/nb_instr_ccm, error)
def main(): 
    dico = gen_dictionnary("./bench")
    #U_gains E_gains flash_ratios ram_ratios ccm_ratios
    Ntests = 50
    data = [[],[],[],[],[],[],[]]
    task_dico = {"8" : data.copy(), "16" :data.copy(), "32" : data.copy(), "64" : data.copy(),"128":data.copy()}
    avrg_dico = {"8": np.zeros(7), "16" : np.zeros(7), "32": np.zeros(7), "64":np.zeros(7), "128":np.zeros(7) }
    for n in [8,16] : 
        for i in range(Ntests): 

            #(U_gain, E_gain, flash_ratio, ram_ratio, ccm_ratio, f_flash, f_ccm, error) = solver(gen_taskset(n, 1, dico, 256000, 40000, 8000))
            res = solver(gen_taskset(n, 1, dico, 256000, 40000, 8000))
            if not res[-1] : 
                for j in range (len(res)-1):
                    if j != 5 : 
                        task_dico[str(n)][j].append(res[j])   
                    else :
                        if res[j] < 9999 : #res[j] = 9999 when there is nothing in flash  
                            task_dico[str(n)][j].append(res[j])   
                '''
                task_dico[str(n)][0].append(U_gain)    
                task_dico[str(n)][1].append(E_gain)
                task_dico[str(n)][2].append(flash_ratio)
                task_dico[str(n)][3].append(ram_ratio)
                task_dico[str(n)][4].append(ccm_ratio)
                task_dico[str(n)][5].append(f_flash)
                task_dico[str(n)][6].append(f_ccm)'''
            if i*100/Ntests%10 == 0 : 
                os.system('cls')
                print(n, " tasks :", int(i*100/Ntests),"%")
        for j in range(len(res)-1) : 
            avrg_dico[str(n)][j] =  round(np.mean(task_dico[str(n)][j]), 2)
    print(avrg_dico)
main()