import csv
import glob
import os
import sys
import pandas as pd
import numpy as np
import openpyxl
import xlsxwriter
def main() : 
    col = ['24MHz', '48MHz', '72MHz']
    #name = sys.argv[1]
    with open("param_tabl.txt", 'r') as f : 
        lines = f.readlines()
    reference = lines[0].removesuffix("\n")
    data_to_cmp = lines[1].removesuffix("\n")
    unity = lines[2]
    list_dir = os.popen("ls -d */").read().split()

    for i in range (len(list_dir)) : 
        list_dir[i] = list_dir[i].removesuffix("/")

    for dir in list_dir : 
        print("write the line of ", dir)
        with open(dir+'/'+ reference+'.csv', 'r') as ref : 
            reader = csv.reader(ref, delimiter = '\t')
            for line in reader: 
                if line[0] == unity : 
                    ref_val = line[1:len(line)]

        with open(dir+'/'+ data_to_cmp+'.csv', 'r') as ref : 
            reader = csv.reader(ref, delimiter = '\t')
            for line in reader: 
                if line[0] == unity : 
                    cmp_val = line[1:len(line)]
        
        final = [round((float(ref_val[i])-float(cmp_val[i]))/float(ref_val[i]),3) for i in range (len(ref_val))]
        print(final)
        

main()