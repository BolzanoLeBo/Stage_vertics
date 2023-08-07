from sched_32f import model_32f2 as mf2
from sched_32f import model_32f3 as mf3
from sched_32f import model_32f as mf
from sched_32g import model_32g as mg

from sched_32g import gen_taskset as gg
from sched_32f import gen_taskset as gf
import numpy as np
import copy
import os 

def main() : 
    dicog = gg.gen_dictionnary("./sched_32g/bench")
    dicof = gf.gen_dictionnary("./sched_32f/bench")
    proc_test = 'f'
    Ntests = 1
    nb_tasks = [16]
    res_dico = {}
    pattern_init = 0
    res_pattern = []

    for ni in nb_tasks :
        n = str(ni) 

        for i in range(Ntests):
            if proc_test == 'g' : 
                res = mg.solver(gg.gen_taskset(ni,1, dicog, 256000, 40000, 8000))
            else : 
                taskset = gf.gen_taskset(ni,1, dicof, 256000, 40000, 8000)
                
                res = mf.solver(taskset)
                res2 = mf2.solver(taskset)
                res3 = mf3.solver(taskset)
                print("res1 :", res)
                print("res2 :", res2)
                print("res3 :", res3)
            '''if not pattern_init : 
                #init of the res_pattern
                for j in range(len(res)) : 
                    
                    if type(res[j]) is float :
                        res_pattern.append(0.0)
                    elif type(res[j]) is int :
                        res_pattern.append(0)
                    elif type(res[j]) is dict : 
                        res_pattern.append({})
                pattern_init = 1
                print(res_pattern)
            if n not in res_dico : 
                res_dico[n] = res_pattern.copy()
            for j in range(len(res)) : 
                if type(res_dico[n][j]) is int or type(res_dico[n][j]) is float: 
                    res_dico[n][j] += res[j]
                elif type(res_dico[n][j]) is dict : 
                    if i == 0 : 
                        #get the dictionary pattern
                        res_dico[n][j] = copy.deepcopy(res[j])
                    else : 
                        #add the value for each dictionary "case"
                        for key in res[j].keys() : 
                            res_dico[n][j][key] += res[j][key]
            if i*100/Ntests%10 == 0 : 
                #os.system('cls')
                print(n, " tasks :", int(i*100/Ntests),"%")
    #average the results 
    for ni in nb_tasks :
        n = str(ni) 
        print("\n task ", n)
        count_var = 0
        count_dico = 0
        for j in range (len(res_dico[n])):
            if type(res_dico[n][j]) is int or type(res_dico[n][j]) is float: 
                res_dico[n][j] = round(res_dico[n][j]/Ntests,2)
                print("var", count_var, ":", res_dico[n][j])
                count_var += 1
            elif type(res_dico[n][j]) is dict :
                print("dico", count_dico) 
                count_dico+=1
                for key in res[j].keys() : 
                    res_dico[n][j][key] = round(res_dico[n][j][key]/Ntests, 2)
                    if res_dico[n][j][key] > 0 : 
                        print(key, ":", res_dico[n][j][key])'''

main()