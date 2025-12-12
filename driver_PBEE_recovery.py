def run_analysis(model_name, seed=None):

    '''This script facilitates the performance based functional recovery and
    reoccupancy assessment of a single building for a single intensity level
    
    Input data consists of building model info and simulated component-level
    damage and conesequence data for a suite of realizations, likely assessed
    as part of a FEMA P-58 analysis. Inputs are read from json files, as well 
    as loaded from csvs in the static_tables directory.
    
    Output data is saved to a specified outputs directory and is saved into a
    single json output file.
    
        Main file for running the code
    
    Parameters
    ----------
    model_name: string
        Name of the model. Inputs are expected to be in a directory with this 
        name. Outputs will save to a directory with this name
    
    
    """'''
    
    import time
    start_time = time.time() # For runtime calculation
    
    ''' ######################  Caution ########################'''
    # Ignoring runtime warnings
    import warnings
    warnings.filterwarnings('ignore')
    ''' ########################################################'''
        
    ## 1. Import Python modules to be used
    import os
    import json
    import numpy as np
    import math
    import pandas as pd
    from scipy.stats import truncnorm
    
    ## 2. Define User Inputs
    model_dir = 'inputs/example_inputs/'+model_name # Directory where the simulated inputs are located
    outputs_dir = 'outputs/'+model_name # Directory where the assessment outputs are saved
    
    ## 3. Load FEMA P-58 performance model data and simulated damage and loss
    f = open(os.path.join(os.path.dirname(__file__),model_dir, 'simulated_inputs.json'))
    simulated_inputs = json.load(f)
    
    building_model = simulated_inputs['building_model']
    damage = simulated_inputs['damage']
    damage_consequences = simulated_inputs['damage_consequences']
    functionality = simulated_inputs['functionality']
    functionality_options = simulated_inputs['functionality_options']
    impedance_options = simulated_inputs['impedance_options']
    repair_time_options = simulated_inputs['repair_time_options']
    tenant_units = simulated_inputs['tenant_units']
    
    # Change story indices in damage['tenant_units'], damage['story'] building_model['comps']['story'] to int from string
    damage_ten_units = []
    if ('tenant_units' in damage.keys()) == True:
        for tu in range(len(damage['tenant_units'])):
            damage_ten_units.append(damage['tenant_units'][str(tu)])
            
        damage['tenant_units'] = damage_ten_units  
    
    damage_story = []    
    for s in range(len(damage['story'])):
        damage_story.append(damage['story'][str(s)])
    
    damage['story'] = damage_story 
    
    bldg_comps_story = []
    for s in range(len(building_model['comps']['story'])):
        bldg_comps_story.append(building_model['comps']['story'][str(s)])
        
    building_model['comps']['story'] = bldg_comps_story
    
    ## 4. Load required static data
    systems = pd.read_csv(os.path.join(os.path.dirname(__file__), 'static_tables', 'systems.csv'))
    subsystems = pd.read_csv(os.path.join(os.path.dirname(__file__), 'static_tables', 'subsystems.csv'))
    impeding_factor_medians = pd.read_csv(os.path.join(os.path.dirname(__file__), 'static_tables', 'impeding_factors.csv'))
    tmp_repair_class = pd.read_csv(os.path.join(os.path.dirname(__file__), 'static_tables', 'temp_repair_class.csv'))
    
    ## 5. Run Recovery Method
    from main_PBEE_recovery import main_PBEE_recovery

    # set a seed
    # this seed propagates through the entire subfunctions
    # so if subfunction requires a distinct random variate, a seed instance will have to be used instead
    if seed is not None:
        np.random.seed(seed)
    
    functionality, damage_consequences = main_PBEE_recovery(damage, 
                                                            damage_consequences, 
                                                            building_model, 
                                                            tenant_units, 
                                                            systems, 
                                                            subsystems, 
                                                            tmp_repair_class,
                                                            impedance_options, 
                                                            impeding_factor_medians, 
                                                            repair_time_options,
                                                            functionality, 
                                                            functionality_options)
           
    # 6. Save Outputs
    # # Define Output path
    if os.path.exists(os.path.join(os.path.dirname(__file__),'outputs')) == False:
        os.mkdir(os.path.join(os.path.dirname(__file__),'outputs'))
    if os.path.exists(os.path.join(os.path.dirname(__file__),'outputs', model_name)) == False:
        os.mkdir(os.path.join(os.path.dirname(__file__),'outputs', model_name))
    
    # Covert arrays to list for writing to json file   
    fnc_keys_1 = list(functionality.keys())
    for k_1 in fnc_keys_1:
        if type(functionality[k_1]) == np.ndarray: 
            functionality[k_1] = functionality[k_1].tolist() 
        if type(functionality[k_1]) == dict:
            fnc_keys_2 = list(functionality[k_1].keys())    
       
            for k_2 in fnc_keys_2:
                if type(functionality[k_1][k_2]) == np.ndarray: 
                    functionality[k_1][k_2] = functionality[k_1][k_2].tolist()
                if type(functionality[k_1][k_2]) == dict:
                    fnc_keys_3 = list(functionality[k_1][k_2].keys())    
       
                    for k_3 in fnc_keys_3:
                        if type(functionality[k_1][k_2][k_3]) == np.ndarray: 
                            functionality[k_1][k_2][k_3] = functionality[k_1][k_2][k_3].tolist()
                        if type(functionality[k_1][k_2][k_3]) == dict:
                            fnc_keys_4 = list(functionality[k_1][k_2][k_3].keys())
     
                            for k_4 in fnc_keys_4:
                                if type(functionality[k_1][k_2][k_3][k_4]) == np.ndarray: 
                                    functionality[k_1][k_2][k_3][k_4] = functionality[k_1][k_2][k_3][k_4].tolist()
                                if type(functionality[k_1][k_2][k_3][k_4]) == dict:
                                    fnc_keys_5 = list(functionality[k_1][k_2][k_3][k_4].keys())
        
                                    for k_5 in fnc_keys_5:
                                        if type(functionality[k_1][k_2][k_3][k_4][k_5]) == np.ndarray: 
                                            functionality[k_1][k_2][k_3][k_4][k_5] = functionality[k_1][k_2][k_3][k_4][k_5].tolist()
                                        if type(functionality[k_1][k_2][k_3][k_4][k_5]) == dict:
                                            fnc_keys_6 = list(functionality[k_1][k_2][k_3][k_4][k_5].keys())
    
    output_json_object = json.dumps(functionality)
    
    with open(os.path.join(os.path.dirname(__file__),outputs_dir, "recovery_outputs.json"), "w") as outfile:
        outfile.write(output_json_object)
    
    end_time = time.time()
    
    print('Recovery assessment of model ' + model_name + ' complete')
    print('time to run '+str(round(end_time - start_time,2))+'s')
        
    
if __name__ == '__main__':

    model_name = 'ICSB'

    run_analysis(model_name)

