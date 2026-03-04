
import numpy as np
import json
import pandas as pd
import os
import re
import sys

def clean_types(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization,
    preserving NaN as float('nan') for Numpy compatibility in the engine.
    """
    if isinstance(obj, dict):
        return {k: clean_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_types(i) for i in obj]
    elif isinstance(obj, np.ndarray):
        return clean_types(obj.tolist())
    elif isinstance(obj, (np.int64, np.int32, int)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32, float)):
         # Preserving NaN for numpy compatibility in downstream engine
         return float(obj)
    elif pd.isna(obj): 
        # Handle standalone pandas/numpy NaNs/NaTs
        return float('nan') 
    return obj

def recursive_update(d, u):
    """
    Recursively update dictionary d with values from u.
    """
    for k, v in u.items():
        if isinstance(v, dict) and k in d and isinstance(d[k], dict):
            recursive_update(d[k], v)
        else:
            d[k] = v
    return d

def load_custom_static_tables(model_dir, static_dir, filename):
    path = os.path.join(model_dir, filename)
    if os.path.exists(path):
        print(f"found custom {filename} in inputs. Overriding static tables...")
    else:
        path = os.path.join(static_dir, filename)
    return pd.read_csv(path)


def build_simulated_inputs(model_dir):
    """
    Generates simulated_inputs dictionary from raw input files in the model directory.
    Based on the original build_inputs.py script.
    
    Parameters
    ----------
    model_dir: string
        Path to the directory containing raw input files.
        
    Returns
    -------
    simulated_inputs: dict
        The complete dictionary of inputs.
    """
        
    ''' PULL STATIC DATA
    If static data tables exist in the input directory, use those. Else, use
    the defaults in src/atc138/data/
    '''
    
    static_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    component_attributes = load_custom_static_tables(
        model_dir, static_data_dir, 'component_attributes.csv')

    damage_state_attribute_mapping = load_custom_static_tables(
        model_dir, static_data_dir, 'damage_state_attribute_mapping.csv')

    subsystems = load_custom_static_tables(
        model_dir, static_data_dir, 'subsystems.csv')

    tenant_function_requirements = load_custom_static_tables(
        model_dir, static_data_dir, 'tenant_function_requirements.csv')
    
    
    ''' LOAD BUILDING DATA
    This data is specific to the building model and will need to be created
    for each assessment. Data is formated as json structures or csv tables'''
    
    # 1. Building Model: Basic data about the building being assessed
    with open(os.path.join(model_dir, 'building_model.json'), 'r') as f:
        building_model = json.load(f)
    
    # If number of stories is 1, change individual values to lists in order to work with later code
    if building_model['num_stories'] == 1:
        for key in ['area_per_story_sf', 'ht_per_story_ft', 'occupants_per_story', 'stairs_per_story', 'struct_bay_area_per_story']:
            if not isinstance(building_model[key], list):
                building_model[key] = [building_model[key]]
    if building_model['num_stories'] == 1:
        for key in ['edge_lengths']:
            if not isinstance(building_model[key][0], list):
                building_model[key] = [[building_model[key][0]], [building_model[key][1]]]
    
    # 2. List of tenant units within the building and their basic attributes
    tenant_unit_list = pd.read_csv(os.path.join(model_dir, 'tenant_unit_list.csv'))
    
    
    # 3. List of component and damage states ids associated with the damage
    comp_ds_list = pd.read_csv(os.path.join(model_dir, 'comp_ds_list.csv'))
    
    # 4. List of component and damage states in the performance model
    comp_population = pd.read_csv(os.path.join(model_dir, 'comp_population.csv'))
    comp_header = list(comp_population.columns)
    comp_list = np.array(comp_header[2:len(comp_header)])
    comp_list= np.char.replace(np.array(comp_list),'_','.')
    comp_list = comp_list.tolist()
    # Remove suffixes from repated entries
    for i in range(len(comp_list)):
        if len(comp_list[i]) > 10:
            comp_list[i]=comp_list[i][0:10]
    building_model['comps'] = {'comp_list' : comp_list} #FZ# Component list has been added to building model dictionary.
    
    # Go through each story and assign component populations
    drs = np.unique(np.array(comp_population['dir']))
    
    building_model['comps']['story'] = {}
    for s in range (building_model['num_stories']):
        building_model['comps']['story'][s] = {}
        for d in range(len(drs)):
            # [FIX] Robust key generation and missing data handling
            current_dir = drs[d]
            filt = np.logical_and(np.array(comp_population['story']) == s+1, np.array(comp_population['dir']) == current_dir)
            
            # Format key identifier using integer representation of direction to ensure consistency (e.g. qty_dir_1 not qty_dir_1.0)
            try:
                dir_key_suffix = str(int(current_dir))
            except:
                dir_key_suffix = str(current_dir)
            
            qty_data = comp_population.to_numpy()[filt,2:len(comp_header)]
            
            if qty_data.shape[0] > 0:
                building_model['comps']['story'][s]['qty_dir_' + dir_key_suffix] = qty_data.tolist()[0]
            else:
                # Missing data for this story/direction, fill with zeros to avoid crashes
                num_comps = len(comp_header) - 2
                building_model['comps']['story'][s]['qty_dir_' + dir_key_suffix] = [0] * num_comps
    
    
    # Set comp info table
    comp_info = {'comp_id': [], 'comp_idx': [], 'structural_system': [], 'structural_system_alt': [], 'structural_series_id': []}
    for c in range(len(comp_list)):
        # Find the component attributes of this component
        comp_attr_filt = component_attributes['fragility_id'] == comp_list[c]
        if np.logical_not(sum(comp_attr_filt) == 1):
            sys.exit('error!.Could not find component attrubutes')
        else:
            comp_attr = component_attributes.to_numpy()[comp_attr_filt,:]
        comp_info['comp_id'].append(comp_list[c])
        comp_info['comp_idx'].append(c) 
        
        # [FIX] Scalar extraction: Use scalar indexing [0, col] instead of slicing [0, [col]] to avoid array-to-scalar conversion errors
        comp_info['structural_system'].append(float(comp_attr[0, component_attributes.columns.get_loc('structural_system')]))
        comp_info['structural_system_alt'].append(float(comp_attr[0, component_attributes.columns.get_loc('structural_system_alt')]))
        comp_info['structural_series_id'].append(float(comp_attr[0, component_attributes.columns.get_loc('structural_series_id')]))
    
    building_model['comps']['comp_table'] = comp_info
    
    
    ''' LOAD SIMULATED DATA
    This data is specific to the building performance at the assessed hazard intensity 
    and will need to be created for each assessment. 
    Data is formated as json structures.'''
    
    # 1. Simulated damage consequences - various building and story level consequences of simulated data, for each realization of the monte carlo simulation.
    with open(os.path.join(model_dir, 'damage_consequences.json'), 'r') as f:
        damage_consequences = json.load(f)
    
    # 2. Simulated utility downtimes for electrical, water, and gas networks for each realization of the monte carlo simulation.
    # If file exists load it 
    utility_path = os.path.join(model_dir, 'utility_downtime.json')
    if os.path.exists(utility_path):
        with open(utility_path, 'r') as f:
            functionality = json.load(f)
    # else If no data exist, assume there is no consequence of network downtime
    else:
        num_reals = len(damage_consequences["repair_cost_ratio_total"])
        functionality = {'utilities' : {'electrical':[], 'water':[], 'gas':[]} } 
    
        for real in range(num_reals):
            functionality['utilities']['electrical'].append(0)
            functionality['utilities']['water'].append(0)
            functionality['utilities']['gas'].append(0)
    
    
    # 3. Simulated component damage per tenant unit for each realization of the monte carlo simulation
    # 3. Simulated component damage per tenant unit for each realization of the monte carlo simulation
    with open(os.path.join(model_dir, 'simulated_damage.json'), 'r') as f:
        sim_damage = json.load(f)
    
    # Write in individual dictionaries part of larger 'damage' dictionary 
    damage = {'story' : {}, 'tenant_units' : {}}
    
    if 'story' in list(sim_damage.keys()):
        for tu in range(len(sim_damage['tenant_units'])):
            damage['tenant_units'][tu] = sim_damage['tenant_units'][tu]
    
    
    if 'tenant_units' in list(sim_damage.keys()):
        for s in range(len(sim_damage['story'])):
            damage['story'][s] = sim_damage['story'][s]
        
    ''' OPTIONAL INPUTS
    Various assessment otpions. Set to default options in the
    optional_inputs.json file. This file is expected to be in this input
    directory. This file can be customized for each assessment if desired.'''
    
    # Load defaults first, then merge user overrides
    pkg_dir = os.path.dirname(__file__)
    defaults_path = os.path.join(pkg_dir, 'data', 'default_inputs.json')
    with open(defaults_path, 'r') as f:
        options = json.load(f)

    user_options_path = os.path.join(model_dir, 'optional_inputs.json')
    if os.path.exists(user_options_path):
        with open(user_options_path, 'r') as f:
            user_options = json.load(f)
        options = recursive_update(options, user_options)
        
    functionality_options = options['functionality_options']
    impedance_options = options['impedance_options']
    repair_time_options = options['repair_time_options']

 
    
    # Preallocate tenant unit table
    tenant_units = tenant_unit_list.copy() # copy to avoid SettingWithCopy if passed dataframe
    tenant_units['exterior'] = np.zeros(len(tenant_units))
    tenant_units['interior'] = np.zeros(len(tenant_units))
    tenant_units['occ_per_elev'] = np.zeros(len(tenant_units))
    tenant_units['is_elevator_required'] = np.zeros(len(tenant_units))
    tenant_units['is_electrical_required'] = np.zeros(len(tenant_units))
    tenant_units['is_water_potable_required'] = np.zeros(len(tenant_units))
    tenant_units['is_water_sanitary_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_ventilation_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_heating_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_cooling_required'] = np.zeros(len(tenant_units))
    tenant_units['is_hvac_exhaust_required'] = np.zeros(len(tenant_units))
    tenant_units['is_data_required'] = np.zeros(len(tenant_units))  
    '''Pull default tenant unit attributes for each tenant unit listed in the
    tenant_unit_list'''
    for tu in range(len(tenant_unit_list)):
        occ_id = tenant_units.loc[tu, 'occupancy_id'] # Use .loc for pandas safety
        fnc_requirements_filt = tenant_function_requirements['occupancy_id'] == occ_id
        if sum(fnc_requirements_filt) != 1:
            raise ValueError(f'error! Tenant Unit Requirements for Occupancy ID {occ_id} Not Found')
        
        # Accessing filtered rows. Original input builder used filtered Series assignment.
        req_row = tenant_function_requirements[fnc_requirements_filt].iloc[0]
        
        tenant_units.loc[tu, 'exterior'] = req_row['exterior']
        tenant_units.loc[tu, 'interior'] = req_row['interior']
        tenant_units.loc[tu, 'occ_per_elev'] = req_row['occ_per_elev']
        
        story = tenant_units.loc[tu, 'story']
        if req_row['is_elevator_required'] == 1 and req_row['max_walkable_story'] < story:
            tenant_units.loc[tu, 'is_elevator_required'] = 1
        else:
            tenant_units.loc[tu, 'is_elevator_required'] = 0
    
        tenant_units.loc[tu, 'is_electrical_required'] = req_row['is_electrical_required']
        tenant_units.loc[tu, 'is_water_potable_required'] = req_row['is_water_potable_required']
        tenant_units.loc[tu, 'is_water_sanitary_required'] = req_row['is_water_sanitary_required']
        tenant_units.loc[tu, 'is_hvac_ventilation_required'] = req_row['is_hvac_ventilation_required']
        tenant_units.loc[tu, 'is_hvac_heating_required'] = req_row['is_hvac_heating_required']
        tenant_units.loc[tu, 'is_hvac_cooling_required'] = req_row['is_hvac_cooling_required']
        tenant_units.loc[tu, 'is_hvac_exhaust_required'] = req_row['is_hvac_exhaust_required']
        tenant_units.loc[tu, 'is_data_required'] = req_row['is_data_required']    
    '''Pull default component and damage state attributes for each component 
    in the comp_ds_list'''
    
    ## Populate data for each damage state
    comp_ds_info = {'comp_id' : [], 
                    'comp_type_id' : [], 
                    'comp_idx' : [], 
                    'ds_seq_id' : [], 
                    'ds_sub_id' : [],
                    'system' : [],
                    'subsystem_id' : [],
                    'structural_system' : [],
                    'structural_system_alt' : [],
                    'structural_series_id' : [],
                    'unit' : [],
                    'unit_qty' : [],
                    'service_location' : [],
                    'is_sim_ds' : [],
                    'safety_class' : [],
                    'affects_envelope_safety' : [],
                    'ext_falling_hazard' : [],
                    'int_falling_hazard' : [],
                    'global_hazardous_material' : [],
                    'local_hazardous_material' : [],
                    'weakens_fire_break' : [],
                    'affects_access' : [],
                    'damages_envelope_seal' : [],
                    'affects_roof_function' : [],
                    'obstructs_interior_space' : [],
                    'impairs_system_operation' : [],
                    'causes_flooding' : [],
                    'interior_area_factor' : [],
                    'interior_area_conversion_type' : [],
                    'exterior_surface_area_factor' : [],
                    'exterior_falling_length_factor' : [],
                    'crew_size' : [],
                    'permit_type' : [],
                    'redesign' : [],
                    'long_lead_time' : [],
                    'requires_shoring' : [],
                    'resolved_by_scaffolding' : [],
                    'tmp_repair_class' : [],
                    'tmp_repair_time_lower' : [],
                    'tmp_repair_time_upper' : [],
                    'tmp_repair_time_lower_qnty' : [],
                    'tmp_repair_time_upper_qnty' : [],
                    'tmp_crew_size' : [],
                    'n1_redundancy' : [],
                    'parallel_operation' :[],
                    'redundancy_threshold' : []
                    }
    
    for c in range(len(comp_ds_list)):
        
        # Find the component attributes of this component
        comp_attr_filt = component_attributes['fragility_id'] == comp_ds_list['comp_id'][c]
        if sum(comp_attr_filt) != 1:
            raise ValueError('error! Could not find component attrubutes')
        else:
            comp_attr = component_attributes[comp_attr_filt].iloc[0] # Changed to Series access for robust scalar extraction
                  
        ds_comp_filt = []
        for frag_reg in range(len(damage_state_attribute_mapping["fragility_id_regex"])):
            regex_str = damage_state_attribute_mapping["fragility_id_regex"][frag_reg]
            cid = comp_ds_list["comp_id"][c]
            match = re.search(regex_str, cid)
            

            # Mapping components with attributes - Cjecks are based on mapping, comp_id, seq_id and sub_id

            # Matching element ID using information contained in damage_state_attribute_mapping ["fragility_id_regex"]
            if match and match.string == cid:
                ds_comp_filt.append(True)
            else:
                ds_comp_filt.append(False)    
        
        ds_comp_filt = np.array(ds_comp_filt) # Convert to array for boolean indexing

        ds_seq_filt = damage_state_attribute_mapping['ds_index'] == comp_ds_list['ds_seq_id'][c]
        if comp_ds_list['ds_sub_id'][c] == 1:
            ds_sub_filt = np.logical_or(damage_state_attribute_mapping['sub_ds_index'] ==1, damage_state_attribute_mapping['sub_ds_index'].isnull())
        else:
            ds_sub_filt = damage_state_attribute_mapping['sub_ds_index'] == comp_ds_list['ds_sub_id'][c]
        
        ds_filt = ds_comp_filt & ds_seq_filt & ds_sub_filt
        
        if sum(ds_filt) != 1:
             raise ValueError('error!, Could not find damage state attrubutes')
        else:
            ds_attr = damage_state_attribute_mapping[ds_filt].iloc[0] # Series access
        
        ## Populate data for each damage state
        # Basic Component and DS identifiers
        comp_ds_info['comp_id'].append(comp_ds_list['comp_id'][c])
        comp_ds_info['comp_type_id'].append(comp_ds_list['comp_id'][c][0:5]) # first 5 characters indicate the type
        comp_ds_info['comp_idx'].append(c)
        comp_ds_info['ds_seq_id'].append(ds_attr['ds_index'])
        
        sub_id = ds_attr['sub_ds_index']
        if pd.isna(sub_id): sub_id = 1.0
        comp_ds_info['ds_sub_id'].append(sub_id)
            
        # Set Component Attributes
        comp_ds_info['system'].append(comp_attr['system_id'])
        comp_ds_info['subsystem_id'].append(comp_attr['subsystem_id'])
        comp_ds_info['structural_system'].append(comp_attr['structural_system'])
        comp_ds_info['structural_system_alt'].append(comp_attr['structural_system_alt']) # component_attributes.csv does not have structural_system_alt field
        comp_ds_info['structural_series_id'].append(comp_attr['structural_series_id'])
        comp_ds_info['unit'].append(comp_attr['unit']) #FZ# Check w.r.t. matlab output
        comp_ds_info['unit_qty'].append(comp_attr['unit_qty'])
        comp_ds_info['service_location'].append(comp_attr['service_location']) #FZ# Check w.r.t. matlab output
                   
        # Set Damage State Attributes
        # Map fields (legacy mapping logic preserved where simple)
        comp_ds_info['is_sim_ds'].append(ds_attr['is_sim_ds'])
        comp_ds_info['safety_class'].append(ds_attr['safety_class'])
        comp_ds_info['affects_envelope_safety'].append(ds_attr['affects_envelope_safety'])
        comp_ds_info['ext_falling_hazard'].append(ds_attr['exterior_falling_hazard'])
        comp_ds_info['int_falling_hazard'].append(ds_attr['interior_falling_hazard'])
        comp_ds_info['global_hazardous_material'].append(ds_attr['global_hazardous_material'])
        comp_ds_info['local_hazardous_material'].append(ds_attr['local_hazardous_material'])
        comp_ds_info['weakens_fire_break'].append(ds_attr['weakens_fire_break'])
        comp_ds_info['affects_access'].append(ds_attr['affects_access'])
        comp_ds_info['damages_envelope_seal'].append(ds_attr['damages_envelope_seal'])
        comp_ds_info['affects_roof_function'].append(ds_attr['affects_roof_function'])
        comp_ds_info['obstructs_interior_space'].append(ds_attr['obstructs_interior_space'])
        comp_ds_info['impairs_system_operation'].append(ds_attr['impairs_system_operation'])
        comp_ds_info['causes_flooding'].append(ds_attr['causes_flooding'])
        comp_ds_info['interior_area_factor'].append(ds_attr['interior_area_factor'])
        comp_ds_info['interior_area_conversion_type'].append(ds_attr['interior_area_conversion_type'])    
        comp_ds_info['exterior_surface_area_factor'].append(ds_attr['exterior_surface_area_factor'])
        comp_ds_info['exterior_falling_length_factor'].append(ds_attr['exterior_falling_length_factor'])                
        comp_ds_info['crew_size'].append(ds_attr['crew_size'])
        comp_ds_info['permit_type'].append(ds_attr['permit_type'])
        comp_ds_info['redesign'].append(ds_attr['redesign'])
        comp_ds_info['long_lead_time'].append(impedance_options['default_lead_time'] * ds_attr['long_lead'])
        comp_ds_info['requires_shoring'].append(ds_attr['requires_shoring'])
        comp_ds_info['resolved_by_scaffolding'].append(ds_attr['resolved_by_scaffolding'])
        comp_ds_info['tmp_repair_class'].append(ds_attr['tmp_repair_class'])
        comp_ds_info['tmp_repair_time_lower'].append(ds_attr['tmp_repair_time_lower'])
        comp_ds_info['tmp_repair_time_upper'].append(ds_attr['tmp_repair_time_upper'])
        
        tmp_class = ds_attr['tmp_repair_class']
        if tmp_class > 0:
            comp_ds_info['tmp_repair_time_lower_qnty'].append(ds_attr['time_lower_quantity'])
            comp_ds_info['tmp_repair_time_upper_qnty'].append(ds_attr['time_upper_quantity'])
        else:
            comp_ds_info['tmp_repair_time_lower_qnty'].append(np.nan)
            comp_ds_info['tmp_repair_time_upper_qnty'].append(np.nan)
    
        comp_ds_info['tmp_crew_size'].append(ds_attr['tmp_crew_size'])
    
        # Subsystem attributes
        sub_id = comp_attr['subsystem_id']
        subsystem_filt = subsystems['id'] == sub_id
        if sub_id == 0:
            # No subsytem
            comp_ds_info['n1_redundancy'].append(0)
            comp_ds_info['parallel_operation'].append(0)
            comp_ds_info['redundancy_threshold'].append(0)
        elif sum(subsystem_filt) != 1:
            sys.exit('error! Could not find damage state attrubutes')
        else:
            sub_row = subsystems[subsystem_filt].iloc[0]
            comp_ds_info['n1_redundancy'].append(sub_row['n1_redundancy'])
            comp_ds_info['parallel_operation'].append(sub_row['parallel_operation'])
            comp_ds_info['redundancy_threshold'].append(sub_row['redundancy_threshold'])
    
    damage['comp_ds_table'] = comp_ds_info
    
    ## Check missing data
    # Engineering Repair Cost Ratio - Assume is the sum of all component repair
    # costs that require redesign
    ## Check missing data
    # Engineering Repair Cost Ratio - Assume is the sum of all component repair
    # costs that require redesign
    if 'repair_cost_ratio_engineering' not in damage_consequences:
        eng_filt = np.array(damage['comp_ds_table']['redesign']).astype(bool)
        # Re-calc using numpy arrays
        costs = np.zeros(len(damage_consequences['repair_cost_ratio_total']))
        if 'story' in sim_damage:
             for s in range(len(sim_damage['story'])):
                 story_costs = np.array(sim_damage['story'][s]['repair_cost'])
                 costs += np.sum(story_costs[:, eng_filt], axis=1)
        damage_consequences['repair_cost_ratio_engineering'] = costs.tolist()
    

    # Convert tenant_units dataframe to dictionary
    tenant_units_dict = tenant_units.to_dict(orient='list')
         
    # Export output as simulated_inputs.json file 
    
    simulated_inputs = {'building_model' : building_model, 'damage' : damage, 'damage_consequences' : damage_consequences, 'functionality' : functionality, 'functionality_options' : functionality_options, 'impedance_options' : impedance_options, 'repair_time_options' : repair_time_options, 'tenant_units' : tenant_units_dict}
    
    # [FIX] Type cleaning using recursive helper (enables JSON serialization while preserving NaNs)
    simulated_inputs = clean_types(simulated_inputs)
    
    return simulated_inputs
