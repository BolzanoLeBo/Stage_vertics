
import gurobipy as gp
from gurobipy import GRB
from csv import writer
import os
from multiprocessing import Pool
from copy import deepcopy
import time
def solver(taskset) : 
    start_time = time.perf_counter()
    n = len(taskset)
    
    model = gp.Model("ilp_ram_allocator")
    model.setParam('OutputFlag', 0)
    model.setParam('TimeLimit', 3600)
    model.setParam('Threads', 1)

    x_f = model.addVars(n,3, vtype = GRB.BINARY)
    x_p = model.addVars(n,2, vtype = GRB.BINARY)
    x_d = model.addVars(n,2, vtype = GRB.BINARY)
    x_ro = model.addVars(n,4, vtype = GRB.BINARY)

    mulfc = []
    for i in range(3) : 
        mulfc.append(model.addVars(n,2,vtype = GRB.BINARY))

    
    muldro = []
    for i in range(2) : 
        muldro.append(model.addVars(n,4,vtype = GRB.BINARY))
    mulfinal = []
    for f in range(3) :
        mulfinal.append([])
        for p in range(2) : 
            mulfinal[f].append([])
            for d in range(2) :
                mulfinal[f][p].append(model.addVars(n,4,vtype = GRB.BINARY)) 

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
    
    #we cannot multiply more than 3 elements so we do pre_operations
    model.addConstrs(mulfc[f][i,p] <= x_f[i,f]
                     for i in range(n)
                     for f in range(3)
                     for p in range(2))
    model.addConstrs(mulfc[f][i,p] <= x_p[i,p]
                     for i in range(n)
                     for f in range(3)
                     for p in range(2))
    model.addConstrs(mulfc[f][i,p] >= x_f[i,f] + x_p[i,p] -1
                     for i in range(n)
                     for f in range(3)
                     for p in range(2))
    
    
    model.addConstrs(muldro[d][i,ro] <= x_d[i,d]
                  for i in range (n) 
                  for d in range (2)
                  for ro in range (4))
    model.addConstrs(muldro[d][i,ro] <= x_ro[i,ro]
                  for i in range (n) 
                  for d in range (2)
                  for ro in range (4))
    model.addConstrs(muldro[d][i,ro] >= x_d[i,d] + x_ro[i,ro] -1
                  for i in range (n) 
                  for d in range (2)
                  for ro in range (4))
    

    model.addConstrs(mulfinal[f][p][d][i,ro] <= muldro[d][i, ro]
                    for f in range(3) 
                    for p in range(2) 
                    for d in range(2) 
                    for ro in range(4) 
                    for i in range (n))
    
    model.addConstrs(mulfinal[f][p][d][i,ro] <= mulfc[f][i, p]
                    for f in range(3) 
                    for p in range(2) 
                    for d in range(2) 
                    for ro in range(4) 
                    for i in range (n))
    
    model.addConstrs(mulfinal[f][p][d][i,ro] >= muldro[d][i,ro] + mulfc[f][i,p] - 1
                    for f in range(3) 
                    for p in range(2) 
                    for d in range(2) 
                    for ro in range(4) 
                    for i in range (n))
    
    #utilization less than 1 
    model.addConstr(gp.quicksum((taskset[i].perf[f][p][d][ro][0]/taskset[i].period)
                                 *mulfinal[f][p][d][i,ro]
                for f in range(3) 
                for p in range(2) 
                for d in range(2) 
                for ro in range(4) 
                for i in range (n)
                ) <= 1 )

    #minimize the energy
    model.setObjective(
    gp.quicksum(((taskset[i].perf[f][p][d][ro][1]/taskset[i].period)*mulfinal[f][p][d][i,ro])  
                for f in range(3) 
                for p in range(2) 
                for d in range(2) 
                for ro in range(4) 
                for i in range (n))
    ,
    GRB.MINIMIZE)
    end_time = time.perf_counter()
    create_time = end_time - start_time 

    start_time = time.perf_counter()
    model.optimize()
    end_time = time.perf_counter()
    run_time = end_time - start_time

    print("times : ", create_time, run_time)
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

    f_ccm = {}
    f_flash = {}

    U_tot = 0
    E_tot = 0
    E_ref = 0

    ccm_used = 0
    flash_used = 0
    ram_used = 0
    nb_instr_ccm = 0
    nb_instr_flash = 0
    for i in range (n) : 
        x_index = [0,0,0,0]
        for j in range (4) : 
            if j < 3 : 
                if x_f_sol[i,j] > 1-1e-6 : 
                    x_index[0] = j
                    if x_p_sol[i,1]> 1-1e-6 : 
                        if f_str[j] in f_ccm : 
                            f_ccm[f_str[j]] += 1
                        else : 
                            f_ccm[f_str[j]] = 1
                    elif x_p_sol[i,0] >1-1e-6  : 
                        if f_str[j] in f_flash : 
                            f_flash[f_str[j]] += 1
                        else : 
                            f_flash[f_str[j]] = 1

                
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
        #print(taskset[i].name, x_index) 
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

    U_gain = float((taskset.u_tot - U_tot)/taskset.u_tot)
    E_gain = (E_ref-E_tot)/E_ref


    for key in f_str : 
        if key in f_ccm :
            f_ccm[key] = f_ccm[key]/n
        else : 
            f_ccm[key] = 0
        if key in f_flash :
            f_flash[key] = f_flash[key]/n
        else : 
            f_flash[key] = 0
    res = [U_gain, E_gain, flash_ratio, ram_ratio, ccm_ratio]+list(f_ccm.values())+list(f_flash.values())
    round_res = [round(r,2) for r in res]
    f_exists = os.path.exists('results/res{}f.csv'.format(n))
    with open('results/res{}f.csv'.format(n), 'a') as file:
        w = writer(file,delimiter="\t" )
        if not f_exists : 
            w.writerow(["U_gain", "E_gain", "flash_ratio", "ram_ratio", "ccm_ratio"]+list(f_ccm.keys())+list(f_flash.keys()))
        w.writerow(res)
    f_exists = os.path.exists('results/round_res{}f.csv'.format(n))
    with open('results/round_res{}f.csv'.format(n), 'a') as file:
        w = writer(file,delimiter="\t" )
        if not f_exists : 
            w.writerow(["U_gain", "E_gain", "f_rat", "r_rat", "c_rat"]+list(f_ccm.keys())+list(f_flash.keys()))
        w.writerow(round_res)
    return(U_gain, E_gain, flash_ratio, ram_ratio, ccm_ratio, f_ccm, f_flash)
