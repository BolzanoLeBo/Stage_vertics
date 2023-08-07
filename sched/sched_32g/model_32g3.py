
import gurobipy as gp
from gurobipy import GRB

from multiprocessing import Pool
from csv import writer
import os
import time
def solver(taskset) : 
    n = len(taskset)
    start_time = time.perf_counter()

    model = gp.Model("ilp_ram_allocator")
    model.setParam('OutputFlag', 0)
    model.setParam('TimeLimit', 3600)
    model.setParam('Threads', 1)

    x_f = model.addVars(n,12, vtype = GRB.BINARY)
    x_p = model.addVars(n,2, vtype = GRB.BINARY)
    x_ro = model.addVars(n,4, vtype = GRB.BINARY)

    x_prec = model.addVars(n,4, vtype = GRB.BINARY)
    mulfp = []
    for i in range(12) : 
        mulfp.append(model.addVars(n,2,vtype = GRB.BINARY))

    
    mulcro = []
    for i in range(4) : 
        mulcro.append(model.addVars(n,4,vtype = GRB.BINARY))

    mulfinal = []
    for f in range(12) :
        mulfinal.append([])
        for p in range(2) : 
            mulfinal[f].append([])
            for prec in range(4) :
                mulfinal[f][p].append(model.addVars(n,4,vtype = GRB.BINARY)) 

    '''
        x_f : 
        100 000 000 000 16 range 2 
        010 000 000 000 26 range 2 
        001 000 000 000 16
        ...
        001 000 000 001 170 boost

        x_p : 
        10 cf 
        01 cc

        x_pre : 
        10 pre_on
        01 pre_off

        x_c : 
        10 cache_on
        01 cache_off


        x_prec
        c   pre     10 and 10   10 and 01    01 and 10   01 and 01
        0   0           1           0            0           0
        0   1           0           1            0           0
        1   0           0           0            1           0
        1   1           0           0            0           1

        x_ro : 
        1000 no_ro 
        0100 ro_f
        0010 ro_r
        0001  ro_c

        '''
    
    #var dimension 
    #no multiple allocation
    model.addConstrs(gp.quicksum(x_f[i,j] for j in range(12) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_p[i,j] for j in range(2) )== 1 for i in range(n))
    '''model.addConstrs(gp.quicksum(x_pre[i,j] for j in range(2) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_c[i,j] for j in range(2) )== 1 for i in range(n))'''
    model.addConstrs(gp.quicksum(x_prec[i,j] for j in range(4) )== 1 for i in range(n))
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
    model.addConstrs(mulfp[f][i,p] <= x_f[i,f]
                     for i in range(n)
                     for f in range(12)
                     for p in range(2))
    model.addConstrs(mulfp[f][i,p] <= x_p[i,p]
                     for i in range(n)
                     for f in range(12)
                     for p in range(2))
    model.addConstrs(mulfp[f][i,p] >= x_f[i,f] + x_p[i,p] -1
                     for i in range(n)
                     for f in range(12)
                     for p in range(2))
    
    
    model.addConstrs(mulcro[prec][i,ro] <= x_prec[i,prec]
                  for i in range (n) 
                  for prec in range (4)
                  for ro in range (4))
    model.addConstrs(mulcro[prec][i,ro] <= x_ro[i,ro]
                  for i in range (n) 
                  for prec in range (4)
                  for ro in range (4))
    model.addConstrs(mulcro[prec][i,ro] >= x_prec[i,prec] + x_ro[i,ro] -1
                  for i in range (n) 
                  for prec in range (4)
                  for ro in range (4))
    

    model.addConstrs(mulfinal[f][p][prec][i,ro] <= mulcro[prec][i, ro]
                    for f in range(12) 
                    for p in range(2) 
                    for prec in range(4) 
                    for ro in range(4) 
                    for i in range (n))
    
    model.addConstrs(mulfinal[f][p][prec][i,ro] <= mulfp[f][i, p]
                    for f in range(12) 
                    for p in range(2) 
                    for prec in range(4) 
                    for ro in range(4) 
                    for i in range (n))
    
    model.addConstrs(mulfinal[f][p][prec][i,ro] >= mulcro[prec][i,ro] + mulfp[f][i,p] - 1
                    for f in range(12) 
                    for p in range(2) 
                    for prec in range(4) 
                    for ro in range(4) 
                    for i in range (n))
    
    #utilization less than 1 
    model.addConstr(gp.quicksum((taskset[i].perf[f][p][prec][ro][0]/taskset[i].period)
                                 *mulfinal[f][p][prec][i,ro]
                for f in range(12) 
                for p in range(2) 
                for prec in range(4) 
                for ro in range(4) 
                for i in range (n)
                ) <= 1 )

    #minimize the energy
    model.setObjective(
    gp.quicksum((taskset[i].perf[f][p][prec][ro][1]/taskset[i].period)*mulfinal[f][p][prec][i,ro]
                for f in range(12) 
                for p in range(2) 
                for prec in range(4) 
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
    x_prec_sol = model.getAttr("x", x_prec)
    x_ro_sol = model.getAttr("x", x_ro)

    #read results
    error = 0
    f_str = ["16_RANGE2", "26_RANGE2", "16", "26", "30", "60", "90", "120", "150", "170", "150_BOOST", "170_BOOST"]
    c_str = ["code Flash", "code CCM"]
    prec_str = ["cache on prefetch on", "cache on prefetch off", "cache off prefetch on", "cache off prefetch off"]
    ro_str = ["no ro", "ro FLASH", "ro RAM", "ro CCM"]
    U_tot = 0
    E_tot = 0
    E_ref = 0

    ccm_used = 0
    flash_used = 0
    ram_used = 0
    f_ccm = {}
    f_flash = {}
    nb_instr_ccm = 0
    nb_instr_flash = 0
    nb_prefetch = 0
    nb_cache = 0

    for i in range (n) : 
        #check the decision on each variable
        x_index = [0,0,0,0]
        for j in range (12) : 
            if x_f_sol[i,j] > 1-1e-6 : 
                x_index[0] = j
                if x_p_sol[i,1]> 1-1e-6 : 
                    if f_str[j]+"c" in f_ccm : 
                        f_ccm[f_str[j]+"c"] += 1
                    else : 
                        f_ccm[f_str[j]+"c"] = 1
                elif x_p_sol[i,0] >1-1e-6  : 
                    if f_str[j]+"f" in f_flash : 
                        f_flash[f_str[j]+"f"] += 1
                    else : 
                        f_flash[f_str[j]+"f"] = 1

                
            if j < 2 : 
                if x_p_sol[i,j] > 1-1e-6 : 
                    x_index[1] = j
                    if j == 1 : 
                        ccm_used += taskset[i].size_i
                        nb_instr_ccm += 1 
                    else : 
                        flash_used += taskset[i].size_i
                        nb_instr_flash += 1
            if j < 4 : 
                if x_ro_sol[i,j] > 1-1e-6 :
                    x_index[3] = j      
                    if j == 1 : 
                        flash_used += taskset[i].size_ro
                    elif j == 2 : 
                        ram_used += taskset[i].size_ro
                    elif j == 3 :
                        ccm_used += taskset[i].size_ro 
                if x_prec_sol[i,j] > 1-1e-6 : 
                    x_index[2] = j
                    if j%2 == 0 : 
                        nb_prefetch += 1
                    elif j < 1 == 0 : 
                        nb_cache += 1  


        f, c, prec, ro = x_index   
        #calculate task utilization
        util = taskset[i].perf[f][c][prec][ro][0]/taskset[i].period
        U_tot += util
        #calculate task energy
        energy = taskset[i].perf[f][c][prec][ro][1]
        
        E_tot += energy/taskset[i].period
        E_ref += taskset[i].ref_energy/taskset[i].period

        
    #    print(taskset[i].name, f_str[f], c_str[c], prec_str[prec], ro_str[ro])
    #print(nb_cache, nb_prefetch, nb_instr_flash, nb_instr_ccm) 
    #print (U_tot, E_ref, E_tot)
    #calculate the utilization gain and energy gain
    U_gain = float((taskset.u_tot - U_tot)/taskset.u_tot)
    E_gain = (E_ref-E_tot)/E_ref
    for key in f_str : 
        keyc = key+"c"
        keyf = key+"f"
        if keyc in f_ccm :
            f_ccm[keyc] = f_ccm[keyc]/n
        else : 
            f_ccm[keyc] = 0
        if keyf in f_flash :
            f_flash[keyf] = f_flash[keyf]/n
        else : 
            f_flash[keyf] = 0
    #print(f_ccm)
    #print(f_flash)

    res = [U_gain, E_gain]+list(f_ccm.values())+list(f_flash.values())
    round_res = [round(r,2) for r in res]
    f_exists = os.path.exists('results/res{}g.csv'.format(n))
    with open('results/res{}g.csv'.format(n), 'a') as file:
        w = writer(file,delimiter="\t" )
        if not f_exists : 
            w.writerow(["U_gain", "E_gain"]+list(f_ccm.keys())+list(f_flash.keys()))
        w.writerow(res)
    f_exists = os.path.exists('results/round_res{}g.csv'.format(n))
    with open('results/round_res{}g.csv'.format(n), 'a') as file:
        w = writer(file,delimiter="\t" )
        if not f_exists : 
            w.writerow(["U_gain", "E_gain"]+list(f_ccm.keys())+list(f_flash.keys()))
        w.writerow(round_res)
    return(U_gain, E_gain, f_ccm, f_flash)

