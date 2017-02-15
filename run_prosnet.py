#!/usr/bin/python
# -*- coding: utf-8 -*-

### Author: Edward Huang

import file_operations
import os
import subprocess
import string
import sys
import time

### This script prepares the input files for Prosnet. Nodes need to be in a
### separate file.

# Records the set of nodes already written to file. Also unique number of edges.
global_node_set, global_edge_set, num_edge_types = set([]), set([]), 0

def get_protein_herb_edge_set():
    '''
    Get the set of (protein, herb) edges.
    '''
    protein_herb_edge_set = set([])
    f = open('./data/herb_protein_relations.txt', 'r')
    for line in f:
        line = line.strip().split('\t')
        if len(line) < 3:
            continue
        herb, protein_list = line[1], line[2:]
        if '茖葱' in herb: # Special case of alternate naming in the file.
            herb = '茖葱'
        for protein in protein_list:
            protein_herb_edge_set.add((protein, herb))
    f.close()
    return protein_herb_edge_set

def get_ppi_edge_set():
    '''
    Get the protein-protein edge set from a PPI network.
    '''
    entrez_to_hgnc_dct = file_operations.get_entrez_to_hgnc_dct()

    ppi_edge_set = set([])
    # Gene ID's in this PPI network are Entrez ID's.
    f = open('./data/HumanNet.v1.benchmark.txt', 'r')
    for line in f:
        line = line.split()
        assert len(line) == 2
        node_a, node_b = line
        # Skip if no HGNC analogues.
        if node_a not in entrez_to_hgnc_dct or node_b not in entrez_to_hgnc_dct:
            continue
        # Translate the Entrez ID to HGNC protein.
        ppi_edge_set.add((entrez_to_hgnc_dct[node_a],
            entrez_to_hgnc_dct[node_b]))
    f.close()
    return ppi_edge_set

def get_coocc_edge_set(fname_a, fname_b):
    '''
    Get the symptom-herb relations from the co-occurrence counts of the patient
    records.
    '''
    coocc_edge_set = set([])
    # Read the respective patient dictionaries.
    patient_dct_a = file_operations.read_spreadsheet(fname_a)[0]
    patient_dct_b = file_operations.read_spreadsheet(fname_b)[0]
    # Get the intersecting set of patients in both dictionaries.
    patient_set = set(patient_dct_a.keys()).intersection(patient_dct_b.keys())
    for inhospital_id in patient_set:
        for (node_a, node_a_freq) in patient_dct_a[inhospital_id]:
            for (node_b, node_b_freq) in patient_dct_b[inhospital_id]:
                # We skip self edges, but keep other same-type edges. TODO.
                if node_a != node_b:
                    coocc_edge_set.add((node_a, node_b))
    return coocc_edge_set

def write_files(node_out, edge_out, edge_set, node_type_a, node_type_b):
    '''
    Write the edges out to file. edge_label is just a letter to differentiate
    amongst the different types of edges. We write nodes out as integers, so
    map_out contains a word on each line corresponding to these integers.
    '''
    global global_node_set, global_edge_set, num_edge_types
    # The order of node type a, b must match the edge order in edge_set.
    node_type_tup = (node_type_a, node_type_b)

    # TODO: Set edge weight.
    # if 'p' in node_type_tup:
    #     edge_weight = 1.0
    # else:
    #     edge_weight = 0.25
    edge_weight = 1.0

    for edge in edge_set:
        # Check if edge has already been written.
        if edge in global_edge_set or edge[::-1] in global_edge_set:
            continue
        global_edge_set.add(edge)

        # TODO: making dict symptom-herb edges weight = 1.0
        # if edge in dict_symptom_herb_set:
        #     edge_weight = 1.0

        # Write out the edge.
        for i, node in enumerate(edge):
            # Write out the node if it hasn't appeared yet.
            if node not in global_node_set:
                global_node_set.add(node)
                node_out.write('%s\t%s\n' % (node, node_type_tup[i]))
            # Write out the edge.
            edge_out.write('%s\t' % node)
        # Edge weights are all = 1. Map the edge type to a letter.
        edge_label = string.ascii_lowercase[num_edge_types]
        edge_out.write('%g\t%s\n' % (edge_weight, edge_label))
    num_edge_types += 1

def run_prosnet():
    results_folder = './data/prosnet_data'
    command = ('../simons_mouse/Sheng/prosnet/model/embed -node "%s/prosnet_'
        'node_list.txt" -link "%s/prosnet_edge_list.txt" -output "%s/prosnet_'
        'node_vectors_%s_dims.vec" -binary 0 -size %s -negative 5 -samples 1 '
        '-iters 1000 -threads 24 -model 2 -depth 10 -restart 0.8 '
        '-edge_type_num %d -rwr_ppi 1 -rwr_seq 1 -train_mode 1' % (input_folder,
            input_folder, results_folder, num_dim, num_dim, num_edge_types))
    print command
    subprocess.call(command, shell=True)

def main():
    if len(sys.argv) != 2:
        print 'Usage:python %s num_dim' % sys.argv[0]
        exit()
    global num_dim, input_folder
    num_dim = sys.argv[1]
    assert num_dim.isdigit()

    # m: symptoms, n: syndromes, h: herbs, d: drugs, t: tests.
    # Symptom file must always come before herb file here.
    f_tuples = [('m', 'cancer_other_info_mr_symp'), ('h',
        'cancer_other_info_herbmed'), ('n', 'cancer_syndrome_syndromes'
        ), ('d', 'cancer_drug_2017_sheet2'), ('t', 'incase_check')]

    input_folder = './data/prosnet_data'
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
    node_out = open('%s/prosnet_node_list.txt' % input_folder, 'w')
    edge_out = open('%s/prosnet_edge_list.txt' % input_folder, 'w')

    # # Start off by writing out the protein-herb list and PPI list.
    # TODO: Decide whether or not to use prior information.
    protein_herb_edge_set = get_protein_herb_edge_set()
    write_files(node_out, edge_out, protein_herb_edge_set, 'p', 'h')
    ppi_edge_set = get_ppi_edge_set()
    write_files(node_out, edge_out, ppi_edge_set, 'p', 'p')

    # global dict_symptom_herb_set
    # Loop through every pair of node types.
    for i in range(len(f_tuples)):
        node_type_a, fname_a = f_tuples[i]
        # TODO: currently adding in same-type edges (i.e., herb-herb edges)
        # for j in range(i + 1, len(f_tuples)):
        for j in range(i, len(f_tuples)):
            node_type_b, fname_b = f_tuples[j]
            # Get the co-occurrence edge set.
            edge_set = get_coocc_edge_set('./data/%s.txt' % fname_a,
                './data/%s.txt' % fname_b)

            # # symptom-herb edges should add the medical textbook's edges.
            # TODO. Adding in the herb-symptom dictionary.
            if 'symp' in fname_a and 'herb' in fname_b:
                edge_set = edge_set.union(
                    file_operations.get_dictionary_symptom_herb_set())

            # Write the edges out to file.
            write_files(node_out, edge_out, edge_set, node_type_a, node_type_b)
            
    edge_out.close()
    node_out.close()

    # Run prosnet. Outputs the low-dimensional vectors into files.
    run_prosnet()

if __name__ == '__main__':
    start_time = time.time()
    main()
    print("--- %s seconds ---" % (time.time() - start_time))